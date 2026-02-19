import re
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException
from starlette import status
from cryptography.fernet import Fernet

from orion.api.interactive.account_manager.models.user_model import user_model
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_keys import db_keys
from orion.services.mongo_manager.shared_model.db_tenant_model import IocCategory, db_tenant_model, TenantRequest, TenantStatus, TenantType, TenantPayload
from orion.api.interactive.tenant_manager.models.tenant_profile_update import TenantProfileUpdate
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, db_user_account, user_role
from orion.services.encryption_manager.key_manager import KeyManager
from orion.constants.constant import CONSTANTS


class TenantManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance():
        if TenantManager.__instance is None:
            with TenantManager.__lock:
                if TenantManager.__instance is None:
                    TenantManager.__instance = TenantManager()
        return TenantManager.__instance

    def __init__(self):
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.IMAGE_DIR = self.BASE_DIR / "static" / "resource" / "profile"
        self._engine = mongo_controller.get_instance().get_engine()

        if TenantManager.__instance is not None:
            raise Exception("This class is a singleton!")
        TenantManager.__instance = self

    @staticmethod
    def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in (update or {}).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = TenantManager._deep_merge(base.get(k, {}), v)
            else:
                base[k] = v
        return base

    @staticmethod
    async def _dek(tenant_id: str) -> bytes:
        return await KeyManager.get_instance().get_or_create_dek(tenant_id)

    async def create_tenant(self, data: db_tenant_model):
        try:
            dek = await KeyManager.get_instance().create_dek(str(data.id))
            enc = Fernet(dek)

            # Encrypt licenses (used by both legacy and new code)
            data.licenses = [enc.encrypt(l.encode()).decode() for l in (data.licenses or [])]

            # Encrypt IOC values
            data.iocs = [IocCategory(
                ioc_id=enc.encrypt(ioc.ioc_id.encode()).decode(),
                name=enc.encrypt(ioc.name.encode()).decode(),
                values=[enc.encrypt(v.encode()).decode() for v in (ioc.values or [])]) for ioc in (data.iocs or [])]

            # Ensure status is set
            data.status = TenantStatus.ONBOARDING

            # Save the tenant
            await self._engine.save(data)
        except Exception as _:
            # Cleanup related documents (don't delete the tenant itself if it wasn't saved)
            await self._engine.remove(db_user_account, db_user_account.tenant_uuid == str(data.id))
            await self._engine.remove(db_keys, db_keys.id == str(data.id))
            raise

    async def get_tenant(self, current_user) -> TenantRequest:
        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(current_user.tenant_uuid))
        if not tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not found in get tenant")

        dek = await KeyManager.get_instance().get_profile_dek(str(tenant.id))
        enc = Fernet(dek)

        ioc_models = [IocCategory(
            ioc_id=enc.decrypt(ioc.ioc_id.encode()).decode(),
            name=enc.decrypt(ioc.name.encode()).decode(),
            values=[enc.decrypt(v.encode()).decode() for v in (ioc.values or [])]) for ioc in (tenant.iocs or [])]

        tenant_request = TenantRequest(
            id=str(current_user.tenant_uuid), name=enc.decrypt(tenant.name.encode()).decode(), iocs=ioc_models)

        return tenant_request

    async def update_tenant(self, data: TenantRequest, current_user):

        if current_user.role in ["admin"]:
            tenant_id = data.id
        elif current_user.licenses == ["maintainer"] and current_user.tenant_uuid == data.id:
            tenant_id = data.id
        else:
            tenant_id = current_user.tenant_uuid

        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        if not tenant:

            raise HTTPException(status_code=401, detail="Onboarding record not found for this user.")

        if tenant.is_default:
            raise HTTPException(status_code=401, detail="Default account cant be updated")

        previous_status = tenant.status

        dek = await KeyManager.get_instance().get_profile_dek(str(tenant.id))
        enc = Fernet(dek)

        tenant.name = enc.encrypt((data.name or "").encode()).decode()
        tenant.phone = enc.encrypt((data.phone or "").encode()).decode()
        tenant.country = enc.encrypt((data.country or "").encode()).decode()
        tenant.city = enc.encrypt((data.city or "").encode()).decode()
        tenant.postal_code = enc.encrypt((data.postal_code or "").encode()).decode()

        if data.verified is not None:
            tenant.verified = data.verified

        if data.user_quota is not None:
            if data.user_quota < 0:
                data.user_quota = 0
            tenant.user_quota = data.user_quota

        if data.status is not None:
            tenant.status = data.status

        if data.licenses is not None and len(data.licenses) > 0:
            tenant.licenses = [enc.encrypt(l.encode()).decode() for l in (data.licenses or [])]

        if data.iocs is not None and len(data.iocs) > 0:
            tenant.iocs = [IocCategory(
                ioc_id=enc.encrypt(ioc.ioc_id.encode()).decode(),
                name=enc.encrypt(ioc.name.encode()).decode(),
                values=[enc.encrypt(v.encode()).decode() for v in (ioc.values or [])]) for ioc in (data.iocs or [])]

        if previous_status == TenantStatus.ONBOARDING:
            tenant.status = TenantStatus.PENDING_VERIFICATION

        await self._engine.save(tenant)

        allowed_licenses = set(data.licenses or [])
        if "maintainer" in allowed_licenses and current_user.role not in ["admin"]:
            raise HTTPException(status_code=401, detail="Only admin can assign maintainer license")

        if current_user.role in ["admin"]:
            users = await self._engine.find(db_user_account, db_user_account.tenant_uuid == tenant_id)
            for u in users:
                if "maintainer" in (u.licenses or []):
                    u.status = UserStatus.ACTIVE
                    if set(allowed_licenses) == {"free"}:
                        u.licenses = ["maintainer"]
                    await self._engine.save(u)
                elif not set(u.licenses or []).issubset(allowed_licenses):
                    u.status = UserStatus.DISABLE
                    u.licenses = ["free"]
                    await self._engine.save(u)

        active_count = await self._engine.count(
            db_user_account,
            (db_user_account.tenant_uuid == tenant_id) & (db_user_account.status == UserStatus.ACTIVE.value))

        if tenant.user_quota and active_count > tenant.user_quota:
            excess = active_count - tenant.user_quota
            extra_users = await self._engine.find(
                db_user_account,
                (db_user_account.tenant_uuid == tenant_id) & (db_user_account.status == UserStatus.ACTIVE.value) & (
                        db_user_account.licenses != ["maintainer"]),
                limit=excess)
            for u in extra_users:
                u.status = UserStatus.DISABLE.value
                await self._engine.save(u)


        tenant_data = tenant.model_dump()
        tenant_data["id"] = str(tenant.id)

        tenant_data["name"] = enc.decrypt((tenant_data.get("name") or "").encode()).decode() if tenant_data.get(
            "name") else ""
        tenant_data["phone"] = enc.decrypt((tenant_data.get("phone") or "").encode()).decode() if tenant_data.get(
            "phone") else ""
        tenant_data["country"] = enc.decrypt((tenant_data.get("country") or "").encode()).decode() if tenant_data.get(
            "country") else ""
        tenant_data["city"] = enc.decrypt((tenant_data.get("city") or "").encode()).decode() if tenant_data.get(
            "city") else ""
        tenant_data["postal_code"] = enc.decrypt(
            (tenant_data.get("postal_code") or "").encode()).decode() if tenant_data.get("postal_code") else ""
        tenant_data["licenses"] = [enc.decrypt(x.encode()).decode() for x in (tenant_data.get("licenses") or [])]
        tenant_data["iocs"] = [{**ioc, "ioc_id": enc.decrypt((ioc.get("ioc_id") or "").encode()).decode() if ioc.get(
            "ioc_id") else "", "name": enc.decrypt((ioc.get("name") or "").encode()).decode() if ioc.get(
            "name") else "", "values": [enc.decrypt(v.encode()).decode() for v in (ioc.get("values") or [])], } for ioc
            in (tenant_data.get("iocs") or [])]


        return {"message": "Tenant updated", "user": current_user.username, "company": tenant_data[
            "name"], "tenant": tenant_data}

    async def update_profile(self, data: TenantProfileUpdate, current_user):
        tenant_id = getattr(current_user, "tenant_uuid", None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Invalid company association")

        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Role guard: Admin can update any; domain admins can update their domain type only
        role = getattr(current_user, "role", None)
        allowed = False
        if role == user_role.ADMIN:
            allowed = True
        else:
            if tenant.tenant_type == TenantType.GUARD and role == user_role.GUARD_ADMIN:
                allowed = True
            elif tenant.tenant_type == TenantType.CLIENT and role == user_role.CLIENT_ADMIN:
                allowed = True
            elif tenant.tenant_type == TenantType.SERVICE_PROVIDER and role == user_role.SP_ADMIN:
                allowed = True

        if not allowed:
            raise HTTPException(status_code=401, detail="You are not allowed to update this profile")

        # Ensure request matches tenant type
        selected_type = data.selected_type()
        if selected_type is None:
            raise HTTPException(status_code=400, detail="Profile payload is required")
        if selected_type != tenant.tenant_type:
            raise HTTPException(status_code=400, detail="Profile type does not match tenant type")

        update_payload = data.dump_selected() or {}
        existing_profile = tenant.profile or {}
        merged = TenantManager._deep_merge(existing_profile, update_payload)

        tenant.profile = merged
        tenant.updated_at = tenant.updated_at  # keep field present; odmantic will persist
        await self._engine.save(tenant)

        return {"message": "Profile updated", "tenant_id": str(tenant.id), "tenant_type": tenant.tenant_type, "profile": tenant.profile or {}}

    async def upsert_tenant(self, data: TenantPayload, current_user, is_update: bool = True):
        """Unified endpoint for GET/POST/PUT complete tenant data (including profile)."""
        if is_update:
            # Update existing tenant
            tenant_id = getattr(current_user, "tenant_uuid", None)
            if not tenant_id:
                raise HTTPException(status_code=400, detail="Invalid company association")

            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            previous_status = tenant.status

            # Role guard: only ADMIN or matching domain admin
            role = getattr(current_user, "role", None)
            allowed = role == user_role.ADMIN or (
                tenant.tenant_type == TenantType.GUARD and role == user_role.GUARD_ADMIN or
                tenant.tenant_type == TenantType.CLIENT and role == user_role.CLIENT_ADMIN or
                tenant.tenant_type == TenantType.SERVICE_PROVIDER and role == user_role.SP_ADMIN
            )
            if not allowed:
                raise HTTPException(status_code=401, detail="You are not allowed to update this tenant")
        else:
            # Create new tenant
            tenant = db_tenant_model(
                tenant_type=data.tenant_type,
                profile=data.profile,
                subscription=data.subscription,
                verified=data.verified,
                user_quota=data.user_quota,
                status=TenantStatus.ONBOARDING,
                licenses=data.licenses,
                iocs=data.iocs,
            )
            previous_status = tenant.status

        # Update base fields
        tenant.tenant_type = data.tenant_type
        tenant.subscription = data.subscription
        tenant.verified = data.verified
        tenant.user_quota = data.user_quota
        if data.status is not None:
            tenant.status = data.status
        if data.licenses:
            tenant.licenses = data.licenses
        if data.iocs:
            tenant.iocs = data.iocs

        # Merge profile (only for non-legacy types)
        if data.profile is not None:
            # Ensure profile type matches tenant_type
            existing = tenant.profile or {}
            merged = TenantManager._deep_merge(existing, data.profile)
            tenant.profile = merged

        if is_update and previous_status == TenantStatus.ONBOARDING:
            tenant.status = TenantStatus.PENDING_VERIFICATION

        tenant.updated_at = datetime.utcnow()
        if data.verified and not tenant.verified_date:
            tenant.verified_date = datetime.utcnow()

        await self._engine.save(tenant)

        return {
            "message": "Tenant updated" if is_update else "Tenant created",
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "status": tenant.status,
            "profile": tenant.profile or {},
        }

    async def set_tenant_status(self, tenant_id: str, target_status: TenantStatus):
        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.status = target_status
        tenant.updated_at = datetime.utcnow()

        if target_status == TenantStatus.ACTIVE:
            tenant.verified = True
            tenant.verified_date = datetime.utcnow()

        await self._engine.save(tenant)

        return {
            "message": "Tenant status updated",
            "id": str(tenant.id),
            "status": tenant.status,
            "verified": tenant.verified,
            "verified_date": tenant.verified_date,
        }

    @staticmethod
    def _extract_tenant_name(profile: Optional[Dict[str, Any]]) -> str:
        if not isinstance(profile, dict):
            return ""
        for key in ["legal_company_name", "trading_name", "legal_entity_name", "full_name", "company_name", "name"]:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def get_tenants_datatable(
            self,
            page: int = 1,
            rows: int = 10,
            tenant_type: Optional[str] = None,
            tenant_status: Optional[str] = None,
            keyword: Optional[str] = None,
            sort_by: str = "created_at",
            sort_order: str = "desc"):
        collection = self._engine.get_collection(db_tenant_model)
        docs = await collection.find({"is_default": False}).to_list(length=None)

        # Ensure no tenant id validation or ObjectId parsing occurs in datatable logic
        # This endpoint should not raise 'Invalid tenant id' unless explicitly passed and validated

        normalized_type = (tenant_type or "").strip().lower()
        normalized_status = (tenant_status or "").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()

        filtered_docs: List[Dict[str, Any]] = []
        for doc in docs:
            current_type = str(doc.get("tenant_type") or "").strip().lower()
            current_status = str(doc.get("status") or "").strip().lower()
            profile = doc.get("profile") or {}
            display_name = self._extract_tenant_name(profile)

            if normalized_type and current_type != normalized_type:
                continue

            if normalized_status and current_status != normalized_status:
                continue

            if normalized_keyword:
                searchable_blob = " ".join([
                    str(doc.get("_id") or ""),
                    current_type,
                    current_status,
                    display_name.lower(),
                    str(profile).lower(),
                ])
                if normalized_keyword not in searchable_blob:
                    continue

            filtered_docs.append(doc)

        reverse = (sort_order or "desc").lower() != "asc"
        allowed_sort_fields = {
            "tenant_type", "status", "created_at", "updated_at", "verified_date",
            "user_quota", "verified", "subscription", "name", "id"
        }
        selected_sort = sort_by if sort_by in allowed_sort_fields else "created_at"

        def sort_key(doc: Dict[str, Any]):
            if selected_sort == "name":
                return self._extract_tenant_name(doc.get("profile") or {}).lower()
            if selected_sort == "id":
                return str(doc.get("_id") or "")
            value = doc.get(selected_sort)
            return (value is None, value)

        filtered_docs.sort(key=sort_key, reverse=reverse)

        safe_rows = rows if rows and rows > 0 else 10
        safe_page = page if page and page > 0 else 1
        total_items = len(filtered_docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = filtered_docs[start:end]

        data = []
        for doc in page_docs:
            profile = doc.get("profile") or {}
            data.append({
                "id": str(doc.get("_id")),
                "name": self._extract_tenant_name(profile),
                "tenant_type": doc.get("tenant_type"),
                "status": doc.get("status"),
                "verified": bool(doc.get("verified", False)),
                "subscription": bool(doc.get("subscription", False)),
                "user_quota": int(doc.get("user_quota", 0) or 0),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "verified_date": doc.get("verified_date"),
            })

        return {
            "items": data,
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "tenant_type": tenant_type,
                "tenant_status": tenant_status,
                "keyword": keyword,
                "sort_by": selected_sort,
                "sort_order": "desc" if reverse else "asc",
            }
        }

    async def _serialize_tenant(self, tenant: db_tenant_model) -> Dict[str, Any]:
        profile = tenant.profile or {}

        try:
            dek = await KeyManager.get_instance().get_profile_dek(ObjectId(tenant.id))
            enc: Fernet | None = Fernet(dek) if dek else None
        except Exception:
            enc = None

        licenses = []
        for l in (tenant.licenses or []):
            if enc:
                try:
                    licenses.append(enc.decrypt(l.encode()).decode())
                    continue
                except Exception:
                    pass
            licenses.append(l)

        iocs = []
        for ioc in (tenant.iocs or []):
            if enc:
                try:
                    ioc_id = enc.decrypt(ioc.ioc_id.encode()).decode()
                except Exception:
                    ioc_id = ioc.ioc_id
                try:
                    name = enc.decrypt(ioc.name.encode()).decode()
                except Exception:
                    name = ioc.name
            else:
                ioc_id = ioc.ioc_id
                name = ioc.name
            values = []
            for v in (ioc.values or []):
                if enc:
                    try:
                        values.append(enc.decrypt(v.encode()).decode())
                        continue
                    except Exception:
                        pass
                values.append(v)
            iocs.append(IocCategory(ioc_id=ioc_id, name=name, values=values))

        return {
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "profile": profile,
            "subscription": tenant.subscription,
            "verified": tenant.verified,
            "user_quota": tenant.user_quota,
            "status": tenant.status,
            "licenses": licenses,
            "iocs": iocs,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at,
            "verified_date": tenant.verified_date,
        }

    async def get_tenant_by_id(self, tenant_id: str) -> Dict[str, Any]:
        try:
            object_id = ObjectId(tenant_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tenant id")

        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == object_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        return await self._serialize_tenant(tenant)

    async def get_all_tenant(self) -> List[db_tenant_model]:
        tenants = await self._engine.find(db_tenant_model, db_tenant_model.is_default == False)
        result = []
        for tenant in tenants:
            result.append(await self._serialize_tenant(tenant))

        return result

    async def create_tenant_user(self, data: user_model, current_user):
        try:
            engine = mongo_controller.get_instance().get_engine()

            username = (data.username or "").strip()
            email = (data.email or "").strip().lower()
            password = (data.password or "").strip()

            username_pattern = r"^[A-Za-z0-9_-]{4,20}$"
            if not re.match(username_pattern, username):
                raise HTTPException(status_code=400, detail="Username already exist")

            email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
            if not re.match(email_pattern, email) and not data.role in ["demo"]:
                raise HTTPException(status_code=400, detail="Invalid email format")

            existing_user = await engine.find_one(
                db_user_account, (db_user_account.username == username) | (db_user_account.email == email))
            existing_mail = await engine.find_one(db_user_account, (db_user_account.email == email))

            if (existing_user or existing_mail) and data.role != "demo":
                raise HTTPException(status_code=400, detail="Username or email already exists")

            if password.startswith("$2b$") and len(password) >= 60:
                hashed_password = password
            else:
                if len(password) > 256:
                    raise HTTPException(status_code=400, detail="Password too long")
                try:
                    hashed_password = CONSTANTS.S_AUTH_PWD_CONTEXT.hash(password)
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid password")

            tenant_uuid = getattr(current_user, "tenant_uuid", None)
            if not tenant_uuid:
                raise HTTPException(status_code=400, detail="Invalid company association")

            tenant = await engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_uuid))
            if not tenant:
                raise HTTPException(status_code=400, detail="Tenant not found")

            users_count = await engine.count(db_user_account, db_user_account.tenant_uuid == tenant_uuid)

            if tenant.is_default == False and tenant.user_quota is not None and (users_count + 1) > tenant.user_quota:
                raise HTTPException(status_code=400, detail="User allocated quota exceeded")

            if data.role in ["demo"] and current_user.role not in ["admin"]:

                raise HTTPException(status_code=401, detail="You are not allowed to manage this user")

            dek = await KeyManager.get_instance().get_profile_dek(str(tenant.id))
            enc = Fernet(dek)

            tenant_allowed = set(enc.decrypt(l.encode()).decode() for l in (tenant.licenses or []))

            requested = set(data.licenses or [])

            if requested and not requested.issubset(tenant_allowed) and not current_user.role in ["admin"]:
                raise HTTPException(status_code=400, detail="User assigned license not allowed for this tenant")

            users_count = await engine.count(db_user_account, db_user_account.tenant_uuid == tenant_uuid)
            if tenant.is_default == False and tenant.user_quota and users_count >= tenant.user_quota:
                raise HTTPException(status_code=400, detail="User quota exceeded")

            user = db_user_account(
                username=username,
                email=email,
                password=hashed_password,
                role=data.role,
                status=data.status,
                subscription=data.subscription,
                licenses=data.licenses,
                tenant_uuid=tenant_uuid, )

            await engine.save(user)


            return {"message": "User created successfully", "username": username, "email": email, "tenant_uuid": tenant_uuid, "allowed_licenses": list(
                tenant_allowed), }

        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e) or "Error creating user")
