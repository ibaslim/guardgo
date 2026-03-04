import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pathlib import Path

from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.responses import Response

from orion.api.interactive.account_manager.models.node_callback_model import NodeCallbackModel
from orion.api.interactive.account_manager.models.user_meta_model import user_meta_model
from orion.api.interactive.account_manager.models.user_param_model import user_param_model
from orion.api.interactive.account_manager.models.user_model import user_model
from orion.api.interactive.account_manager.models.platform_admin_model import (
    PlatformAdminCreateRequest,
    PlatformAdminUpdateRequest,
    PlatformAdminStatusReasonRequest,
)
from orion.api.interactive.tenant_manager.models.tenant_param_model import tenant_param_model
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import (
    db_user_account,
    UserStatus,
    LicenseName,
    user_role,
    is_super_admin_role,
    is_platform_admin_role,
)
from orion.services.encryption_manager.key_manager import KeyManager
from orion.services.mail_manager.mail_manager import mail_manager
from orion.services.session_manager.session_manager import session_manager
from orion.constants.constant import CONSTANTS
from orion.constants import constant
from orion.services.mongo_manager.shared_model.db_keys import db_keys
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, db_tenant_model
from orion.helper_manager.env_handler import env_handler


class AccountManager:
    __instance = None

    def __init__(self):
        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.IMAGE_DIR = self.BASE_DIR / "static" / "resource" / "profile"
        self._engine = mongo_controller.get_instance().get_engine()

        self.BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
        self.TENANT_DIR = self.BASE_DIR / "static" / "resource" / "tenant"
        self.TENANT_DIR.mkdir(parents=True, exist_ok=True)
        if AccountManager.__instance is not None:
            raise Exception("This class is a singleton!")
        AccountManager.__instance = self

    @staticmethod
    def get_instance():
        if AccountManager.__instance is None:
            if AccountManager.__instance is None:
                AccountManager.__instance = AccountManager()
        return AccountManager.__instance

    async def _generate_platform_admin_username(self, email: str) -> str:
        local_part = email.split("@")[0].lower()
        normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", local_part)
        if not normalized or not normalized[0].isalpha():
            normalized = f"admin_{normalized}"

        base = normalized[:14]
        if len(base) < 8:
            base = (base + "_adminusr")[:8]

        for _ in range(12):
            suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(3))
            candidate = f"{base}_{suffix}"[:20]
            existing = await self._engine.find_one(db_user_account, db_user_account.username == candidate)
            if not existing:
                return candidate

        fallback = f"admin_{secrets.token_hex(4)}"[:20]
        return fallback

    async def _send_platform_admin_invite_mail(self, username: str, email: str, invite_token: str):
        app_url = env_handler.get_instance().env("APP_URL")
        invite_url = f"{app_url}/invite/{invite_token}"
        subject = "You are invited to GuardGo Admin"
        html_content = constant.mail_template.render(
            username=username,
            email=email,
            subject=subject,
            lurlHeading="Set your password link : ",
            url=invite_url,
        )
        await mail_manager.get_instance().send_verification_mail(
            to=email,
            subject=subject,
            body=html_content,
        )

    def _normalize_status_value(self, status_value) -> str:
        if status_value is None:
            return ""
        if hasattr(status_value, "value"):
            return str(status_value.value).strip().lower()
        return str(status_value).strip().lower()

    def _normalized_platform_status(self, status_value) -> str:
        normalized = self._normalize_status_value(status_value)
        if normalized == UserStatus.DISABLE.value:
            return UserStatus.BLOCKED.value
        return normalized

    async def _apply_platform_status_change(
        self,
        user,
        target_status: Optional[UserStatus],
        actor_username: str,
        reason: Optional[str] = None,
    ):
        if target_status is None:
            return

        normalized_target = self._normalized_platform_status(target_status)
        reason_text = (reason or "").strip() or None

        if normalized_target in [UserStatus.BLOCKED.value, UserStatus.DELETED.value] and not reason_text:
            raise HTTPException(status_code=400, detail="Reason is required when blocking or deleting a platform user")

        user.status = UserStatus(normalized_target)
        user.status_changed_by = actor_username
        user.status_changed_at = datetime.now(timezone.utc)
        user.status_reason = reason_text

        if normalized_target == UserStatus.DELETED.value:
            user.deleted_at = datetime.now(timezone.utc)
            user.deleted_by = actor_username
            user.invite_pending = False
            user.verification_token = None
            user.verification_expiry = None
        else:
            user.deleted_at = None
            user.deleted_by = None

    async def get_all_users(self, current_user) -> List[user_param_model]:
        if is_super_admin_role(current_user.role) or LicenseName.MAINTAINER in (current_user.licenses or []):
            tenant_uuid = current_user.tenant_uuid
            # Use raw collection to avoid odmantic parse errors on legacy records
            collection = self._engine.get_collection(db_user_account)
            docs = await collection.find({"tenant_uuid": tenant_uuid}).to_list(length=None)

            sanitized = []
            for d in docs:
                try:
                    sanitized.append(user_param_model(
                        username=d.get("username"),
                        email=d.get("email"),
                        role=d.get("role"),
                        status=d.get("status"),
                        subscription=d.get("subscription"),
                        licenses=d.get("licenses"),
                        preferences=d.get("preferences"),
                    ))
                except Exception:
                    # Skip legacy/invalid records instead of failing the whole list
                    continue
            return sanitized
        return []

    async def create_user(self, data: user_model, current_user):
        try:
            engine = mongo_controller.get_instance().get_engine()

            # Only admins of the same tenant can create users
            allowed_roles = [user_role.ADMIN, user_role.CLIENT_ADMIN, user_role.GUARD_ADMIN, user_role.SP_ADMIN]
            if current_user.role not in allowed_roles:
                raise HTTPException(status_code=403, detail="Not allowed")

            username = (data.username or "").strip()
            email = (data.email or "").strip().lower()
            password = (data.password or "").strip()

            username_pattern = r"^[A-Za-z0-9_-]{4,20}$"
            if not re.match(username_pattern, username):
                raise HTTPException(status_code=400, detail="Username already exist")

            email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
            if not re.match(email_pattern, email):
                raise HTTPException(status_code=400, detail="Invalid email format")

            existing_user = await engine.find_one(db_user_account, db_user_account.username == username)
            existing_mail = await engine.find_one(db_user_account, db_user_account.email == email)
            if existing_user or existing_mail:
                raise HTTPException(status_code=400, detail="Username or email already exists")

            if password.startswith("$2b$") and len(password) >= 60:
                hashed_password = password
            else:
                if len(password) > 256:
                    raise HTTPException(status_code=400, detail="Password too long")
                hashed_password = CONSTANTS.S_AUTH_PWD_CONTEXT.hash(password)

            user = db_user_account(
                username=username,
                email=email,
                password=hashed_password,
                tenant_uuid=current_user.tenant_uuid,
                role=data.role,
                status=data.status,
                subscription=data.subscription,
                licenses=data.licenses, )

            await engine.save(user)
            await KeyManager.get_instance().create_user_dek(user.id)

            return {"message": "User created successfully", "username": username, "email": email}

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e) or "Error creating user")

    async def list_platform_admin_users(self, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        collection = self._engine.get_collection(db_user_account)
        docs = await collection.find({
            "role": {"$in": [
                user_role.ADMIN.value,
                user_role.SUPER_ADMIN.value,
                user_role.OPS_ADMIN.value,
                user_role.SUPPORT_ADMIN.value,
                user_role.COMPLIANCE_ADMIN.value,
                user_role.READ_ONLY_ADMIN.value,
            ]}
        }).to_list(length=None)

        rows = []
        for d in docs:
            normalized_status = self._normalized_platform_status(d.get("status"))
            rows.append({
                "id": str(d.get("_id")),
                "username": d.get("username", ""),
                "full_name": d.get("full_name", "") or "",
                "email": d.get("email", ""),
                "role": str(d.get("role", "")),
                "status": normalized_status or None,
                "status_reason": d.get("status_reason"),
                "tenant_uuid": d.get("tenant_uuid") or None,
                "licenses": d.get("licenses", []) or [],
                "invite_pending": bool(d.get("invite_pending", False)),
                "invite_expires_at": d.get("verification_expiry"),
                "deleted_at": d.get("deleted_at"),
            })

        return rows

    async def create_platform_admin_user(self, data: PlatformAdminCreateRequest, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        email = str(data.email).strip().lower()
        existing = await self._engine.find_one(
            db_user_account,
            db_user_account.email == email
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        username = await self._generate_platform_admin_username(email)
        invite_token = session_manager.get_instance().generate_verification_token()
        invite_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        temp_password_plain = f"TmpA1!{secrets.token_urlsafe(12)}"
        temp_password_hashed = CONSTANTS.S_AUTH_PWD_CONTEXT.hash(temp_password_plain)

        user = db_user_account(
            username=username,
            full_name="",
            email=email,
            password=temp_password_hashed,
            role=data.role,
            status=UserStatus.INACTIVE,
            subscription=True,
            licenses=[LicenseName.MAINTAINER],
            tenant_uuid="",
            verification_token=invite_token,
            verification_expiry=invite_expiry,
            invite_pending=True,
            status_reason="Invite pending",
            status_changed_by=getattr(current_user, "username", "system"),
            status_changed_at=datetime.now(timezone.utc),
        )
        await self._engine.save(user)

        await self._send_platform_admin_invite_mail(username=username, email=email, invite_token=invite_token)

        return {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": self._normalized_platform_status(user.status),
            "status_reason": user.status_reason,
            "tenant_uuid": user.tenant_uuid or None,
            "licenses": [l.value if hasattr(l, "value") else str(l) for l in (user.licenses or [])],
            "invite_sent": True,
            "invite_expires_at": invite_expiry.isoformat(),
        }

    async def resend_platform_admin_invite(self, user_id: str, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        user = await self._engine.find_one(db_user_account, db_user_account.id == ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not is_platform_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Target user is not a platform admin")

        if not getattr(user, "invite_pending", False):
            raise HTTPException(status_code=400, detail="Invite is not pending for this user")

        invite_token = session_manager.get_instance().generate_verification_token()
        invite_expiry = datetime.now(timezone.utc) + timedelta(hours=24)

        user.verification_token = invite_token
        user.verification_expiry = invite_expiry
        user.status = UserStatus.INACTIVE
        user.status_reason = "Invite resent"
        user.status_changed_by = getattr(current_user, "username", "system")
        user.status_changed_at = datetime.now(timezone.utc)
        await self._engine.save(user)

        await self._send_platform_admin_invite_mail(
            username=user.username,
            email=user.email,
            invite_token=invite_token,
        )

        return {
            "message": "Invite resent successfully",
            "id": str(user.id),
            "invite_expires_at": invite_expiry.isoformat(),
        }

    async def update_platform_admin_user(self, user_id: str, data: PlatformAdminUpdateRequest, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        user = await self._engine.find_one(db_user_account, db_user_account.id == ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not is_platform_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Target user is not a platform admin")

        if is_super_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Super admin role cannot be modified by this endpoint")

        if data.role is not None:
            user.role = data.role
        await self._apply_platform_status_change(
            user=user,
            target_status=data.status,
            actor_username=getattr(current_user, "username", "system"),
            reason=data.status_reason,
        )
        if data.licenses is not None:
            user.licenses = data.licenses

        await self._engine.save(user)

        return {
            "id": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": self._normalized_platform_status(user.status),
            "status_reason": user.status_reason,
            "tenant_uuid": user.tenant_uuid or None,
            "licenses": [l.value if hasattr(l, "value") else str(l) for l in (user.licenses or [])],
            "deleted_at": user.deleted_at,
        }

    async def soft_delete_platform_admin_user(self, user_id: str, data: PlatformAdminStatusReasonRequest, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        user = await self._engine.find_one(db_user_account, db_user_account.id == ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not is_platform_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Target user is not a platform admin")

        if is_super_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Super admin user cannot be deleted by this endpoint")

        await self._apply_platform_status_change(
            user=user,
            target_status=UserStatus.DELETED,
            actor_username=getattr(current_user, "username", "system"),
            reason=data.reason,
        )
        await self._engine.save(user)

        return {"message": "Platform user deleted", "id": str(user.id), "status": UserStatus.DELETED.value}

    async def restore_platform_admin_user(self, user_id: str, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        user = await self._engine.find_one(db_user_account, db_user_account.id == ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not is_platform_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Target user is not a platform admin")

        if self._normalized_platform_status(user.status) != UserStatus.DELETED.value:
            raise HTTPException(status_code=400, detail="Only deleted platform users can be restored")

        await self._apply_platform_status_change(
            user=user,
            target_status=UserStatus.INACTIVE,
            actor_username=getattr(current_user, "username", "system"),
            reason="Restored by super admin",
        )
        await self._engine.save(user)

        return {
            "message": "Platform user restored",
            "id": str(user.id),
            "status": UserStatus.INACTIVE.value,
        }

    async def permanently_delete_platform_admin_user(self, user_id: str, current_user):
        if not is_super_admin_role(current_user.role):
            raise HTTPException(status_code=403, detail="Not allowed")

        user = await self._engine.find_one(db_user_account, db_user_account.id == ObjectId(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not is_platform_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Target user is not a platform admin")

        if is_super_admin_role(user.role):
            raise HTTPException(status_code=400, detail="Super admin user cannot be permanently deleted")

        if self._normalized_platform_status(user.status) != UserStatus.DELETED.value:
            raise HTTPException(status_code=400, detail="Only soft-deleted platform users can be permanently deleted")

        await self._engine.remove(db_keys, db_keys.auth_id == str(user.id))

        image_path = self.IMAGE_DIR / f"{user.id}.enc"
        if image_path.exists():
            image_path.unlink()

        await self._engine.delete(user)

        return {"message": "Platform user permanently deleted", "id": user_id}

    async def delete_user(self, user, current_user):
        user = await self._engine.find_one(db_user_account, db_user_account.username == user.username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if is_super_admin_role(user.role):
            raise HTTPException(status_code=401, detail="This user type cannot be deleted")

        if current_user.licenses.__contains__(LicenseName.MAINTAINER):
            if user.tenant_uuid != current_user.tenant_uuid:
                raise HTTPException(
                    status_code=401, detail="Maintainer can only delete non-maintainer users from the same tenant")
        else:
            raise HTTPException(status_code=401, detail="You are not allowed to delete users")

        await self._engine.remove(db_keys, db_keys.auth_id == str(user.id))

        image_path = self.IMAGE_DIR / f"{user.id}.enc"
        if image_path.exists():
            image_path.unlink()

        await self._engine.delete(user)

        return {"message": "User deleted successfully"}

    async def update_user(self, request: tenant_param_model, current_user):
        user = await self._engine.find_one(db_user_account, db_user_account.username == request.username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if current_user.licenses.__contains__(LicenseName.MAINTAINER) and str(user.tenant_uuid) == str(
                current_user.tenant_uuid):
            pass
        else:
            raise HTTPException(status_code=401, detail="You are not allowed to update this user")

        if is_super_admin_role(user.role):
            raise HTTPException(status_code=401, detail="This user type cannot be updated")

        if request.status == UserStatus.DISABLE:
            user.status = UserStatus.DISABLE
        elif user.status == UserStatus.DISABLE:
            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(user.tenant_uuid))
            active_count = await self._engine.count(
                db_user_account,
                (db_user_account.tenant_uuid == str(user.tenant_uuid)) & (
                            db_user_account.status == UserStatus.ACTIVE.value))

            if tenant is not None and not tenant.is_default and tenant.user_quota is not None and request.status == UserStatus.ACTIVE and user.status == UserStatus.DISABLE and active_count >= tenant.user_quota:
                raise HTTPException(status_code=400, detail="User quota exceeded1")
            if request.status == UserStatus.ACTIVE:
                user.status = UserStatus.ACTIVE


        user.licenses = request.licenses
        await self._engine.save(user)


        return {"message": "User updated successfully", "id": str(user.id)}

    async def update_current_user(self, request: user_meta_model, current_user):
        user = await self._engine.find_one(db_user_account, db_user_account.username == current_user.username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if request.username is not None:
            user.username = request.username
        if request.full_name is not None:
            user.full_name = request.full_name
        if request.email is not None:
            user.email = request.email
        if request.preferences is not None:
            user.preferences = request.preferences
        if request.twofa_enabled is not None:
            user.twofa_enabled = request.twofa_enabled

        await self._engine.save(user)

        return {"message": "User updated successfully"}

    async def getProfileImage(self, userId: str):
        file_path = Path(self.TENANT_DIR) / f"{userId}.png"
        default_path = Path(self.TENANT_DIR) / "default.png"

        is_default = not file_path.is_file()
        target_path = default_path if is_default else file_path

        with open(target_path, "rb") as f:
            data = f.read()

        return Response(
            content=data,
            media_type="image/png",
            headers={"X-Default-Image": "true" if is_default else "false", "Access-Control-Expose-Headers": "X-Default-Image"})

    def safe_decrypt(self, enc: Fernet, value: str | None) -> str:
        if not value:
            return ""
        try:
            return enc.decrypt(value.encode()).decode()
        except Exception:
            return ""

    async def get_node(self, current_user) -> NodeCallbackModel:
        user = current_user
        tenant = None
        tenant_uuid = str(getattr(user, "tenant_uuid", "") or "").strip()
        if tenant_uuid and ObjectId.is_valid(tenant_uuid):
            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_uuid))

        user_image_file = self.IMAGE_DIR / f"{str(user.id)}.png"
        user_image_path = "/api/s/static/user/" + (str(user.id) if user_image_file.is_file() else "default")

        if tenant is None:
            node = NodeCallbackModel.model_validate(
                {
                    "user": {
                        "email": user.email,
                        "twofa_enabled": user.twofa_enabled,
                        "username": user.username,
                        "full_name": getattr(user, "full_name", "") or "",
                        "full_name": getattr(user, "full_name", "") or "",
                        "role": user.role,
                        "status": user.status,
                        "subscription": user.subscription,
                        "verificationDate": user.account_verify_at.isoformat() if user.account_verify_at else None,
                        "license": [license.value for license in user.licenses],
                        "image": user_image_path,
                    },
                    "tenant": {
                        "has_onboarding": False,
                        "id": "",
                        "is_default": False,
                        "name": "",
                        "phone": "",
                        "country": "",
                        "city": "",
                        "postal_code": "",
                        "tax_id": "",
                        "user_id": "",
                        "licenses": [],
                        "assigned_quota": "0",
                        "quota_exceeded": False,
                        "image": "/api/s/static/tenant/default",
                        "tenant_type": None,
                        "status": None,
                    },
                }
            )
            return node

        dek = await KeyManager.get_instance().get_or_create_dek(str(tenant.id))
        enc = Fernet(dek)

        assigned_quota = tenant.user_quota
        total_user = await self._engine.count(db_user_account, (db_user_account.tenant_uuid == str(user.tenant_uuid)))

        tenant_image_file = self.TENANT_DIR / f"{str(tenant.id)}.png"
        tenant_image_path = "/api/s/static/tenant/" + (str(tenant.id) if tenant_image_file.is_file() else "default")

        profile = tenant.profile or {}
        tenant_name = profile.get("name", "")
        tenant_phone = profile.get("phone", "")
        tenant_country = profile.get("country", "")
        tenant_city = profile.get("city", "")
        tenant_postal_code = profile.get("postal_code", "")

        node = NodeCallbackModel.model_validate(
            {"user": {"email": user.email, "twofa_enabled": user.twofa_enabled, "username": user.username, "full_name": getattr(user, "full_name", "") or "", "role": user.role, "status": user.status, "subscription": user.subscription, "verificationDate": user.account_verify_at.isoformat() if user.account_verify_at else None, "license": [
                license.value for license in
                user.licenses], "image": user_image_path, }, "tenant": {"has_onboarding": tenant.status == TenantStatus.ONBOARDING, "id": str(
                tenant.id), "is_default": str(tenant.is_default), "name": tenant_name, "phone": tenant_phone, "country": tenant_country, "city": tenant_city, "postal_code": tenant_postal_code, "tax_id": str(tenant.id), "user_id": "", "licenses": [
                self.safe_decrypt(enc, l) for l in (tenant.licenses or [])], "assigned_quota": str(
                assigned_quota), "quota_exceeded": bool(
                not tenant.is_default and tenant.user_quota is not None and assigned_quota < total_user), "image": tenant_image_path, "tenant_type": tenant.tenant_type.value, "status": tenant.status.value, } })

        return node
