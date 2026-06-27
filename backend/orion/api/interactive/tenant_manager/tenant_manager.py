import re
import secrets
import threading
from copy import deepcopy
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from starlette import status
from cryptography.fernet import Fernet

from orion.api.interactive.account_manager.models.user_model import user_model
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_keys import db_keys
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    IocCategory,
    db_tenant_model,
    TenantRequest,
    TenantStatus,
    TenantType,
    TenantPayload,
    GuardOwnershipType,
    GuardStatusAction,
    GuardStatusRequestStatus,
    GuardStatusChangeRequest,
)
from orion.api.interactive.tenant_manager.models.tenant_profile_update import TenantProfileUpdate
from orion.api.interactive.tenant_manager.models.service_provider_guard_models import (
    ServiceProviderGuardInviteRequest,
    ServiceProviderGuardStatusRequestPayload,
    ServiceProviderGuardOperationalCoveragePayload,
    GuardStatusRequestDecisionPayload,
    GuardServiceProviderLinkPayload,
    GuardServiceProviderUnlinkPayload,
)
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, LicenseName, db_user_account, user_role, is_platform_admin_role, normalize_role_value
from orion.services.encryption_manager.key_manager import KeyManager
from orion.constants.constant import CONSTANTS
from orion.constants import constant
from orion.services.mail_manager.mail_manager import mail_manager
from orion.helper_manager.env_handler import env_handler
from orion.services.session_manager.session_manager import session_manager
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatusAudit
from orion.api.interactive.activity_manager.activity_manager import ActivityManager
from configs.metadata_constants import CANADIAN_PROVINCE_OPTIONS, CANADIAN_CITIES_BY_PROVINCE_OPTIONS


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
    def _normalized_status_value(status_value: Any) -> str:
        value = str(getattr(status_value, "value", status_value) or "").strip().lower()
        if value == TenantStatus.PENDING_VERIFICATION.value:
            return TenantStatus.PENDING_ACTIVATION.value
        return value

    @staticmethod
    def _is_service_provider_owned_guard(tenant: Optional[db_tenant_model]) -> bool:
        if not tenant:
            return False
        if getattr(tenant, "tenant_type", None) != TenantType.GUARD:
            return False
        ownership_type = str(getattr(getattr(tenant, "ownership_type", None), "value", getattr(tenant, "ownership_type", None)) or "").strip().lower()
        provider_tenant_id = str(getattr(tenant, "service_provider_tenant_id", "") or "").strip()
        return ownership_type == GuardOwnershipType.SERVICE_PROVIDER.value and bool(provider_tenant_id)

    @classmethod
    def _required_approval_count_for_tenant(cls, tenant: Optional[db_tenant_model]) -> int:
        return 1 if cls._is_service_provider_owned_guard(tenant) else 2

    @classmethod
    def _reset_pending_activation_approval_state(cls, tenant: db_tenant_model) -> None:
        tenant.approval_actors = []
        tenant.approvals_required = cls._required_approval_count_for_tenant(tenant)

    @classmethod
    def _can_service_provider_approve_guard(cls, tenant: db_tenant_model, current_user: Any) -> bool:
        if not cls._is_service_provider_owned_guard(tenant):
            return False
        role_value = normalize_role_value(getattr(current_user, "role", ""))
        if role_value != user_role.SP_ADMIN.value:
            return False
        actor_provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        owner_provider_tenant_id = str(getattr(tenant, "service_provider_tenant_id", "") or "").strip()
        return bool(actor_provider_tenant_id) and actor_provider_tenant_id == owner_provider_tenant_id

    @classmethod
    def _assert_service_provider_guard_management_allowed(cls, provider: Optional[db_tenant_model]) -> None:
        if not provider or getattr(provider, "tenant_type", None) != TenantType.SERVICE_PROVIDER:
            raise HTTPException(status_code=403, detail="Only service providers can manage guards")

        normalized_status = cls._normalized_status_value(getattr(provider, "status", None))
        if normalized_status == TenantStatus.ACTIVE.value:
            return
        if normalized_status == TenantStatus.PENDING_ACTIVATION.value:
            raise HTTPException(status_code=403, detail="Pending approval")
        raise HTTPException(status_code=403, detail="Only active service providers can manage guards")

    @staticmethod
    def _guard_operational_coverage_snapshot(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        data = profile or {}
        radius = data.get("max_travel_radius_km")
        try:
            normalized_radius = round(float(radius), 2) if radius not in [None, ""] else None
        except Exception:
            normalized_radius = None

        return {
            "operational_region_code": TenantManager._normalize_code(data.get("operational_region_code")),
            "operational_city_code": str(data.get("operational_city_code") or "").strip().upper(),
            "max_travel_radius_km": normalized_radius,
        }

    @staticmethod
    def _guard_weekly_availability_snapshot(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        data = profile or {}
        weekly_availability = data.get("weekly_availability")
        return deepcopy(weekly_availability) if isinstance(weekly_availability, dict) else {}

    @classmethod
    def _guard_weekly_availability_is_complete(cls, weekly_availability: Any) -> bool:
        if not isinstance(weekly_availability, dict):
            return False

        for day_ranges in weekly_availability.values():
            if not isinstance(day_ranges, list):
                continue
            for entry in day_ranges:
                if not isinstance(entry, dict):
                    continue
                start = str(entry.get("start") or "").strip()
                end = str(entry.get("end") or "").strip()
                if start and end:
                    return True
        return False

    @classmethod
    def _ensure_service_provider_guard_managed_profile_ready(cls, tenant: db_tenant_model) -> None:
        profile = dict(getattr(tenant, "profile", None) or {})
        coverage = cls._guard_operational_coverage_snapshot(profile)
        if (
            not coverage.get("operational_region_code")
            or not coverage.get("operational_city_code")
            or coverage.get("max_travel_radius_km") is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Service-provider-owned guards must have operational province, city, and radius "
                    "configured by the owning service provider before approval"
                ),
            )

        normalized_profile = cls._validate_and_normalize_profile_for_tenant_type(
            TenantType.GUARD,
            deepcopy(profile),
        )
        if not cls._guard_weekly_availability_is_complete(normalized_profile.get("weekly_availability")):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Service-provider-owned guards must have weekly availability configured by the owning "
                    "service provider before approval"
                ),
            )

    @classmethod
    def _self_managed_guard_can_mutate_operational_coverage(cls, tenant: db_tenant_model, current_user: Any) -> bool:
        if not cls._is_service_provider_owned_guard(tenant):
            return True
        return normalize_role_value(getattr(current_user, "role", "")) == user_role.SP_ADMIN.value

    @staticmethod
    def _approvals_summary(tenant: db_tenant_model) -> Dict[str, Any]:
        required = TenantManager._required_approval_count_for_tenant(tenant)
        actors = list(dict.fromkeys(getattr(tenant, "approval_actors", []) or []))
        done = len(actors)
        remaining = max(required - done, 0)
        return {
            "approvals_done": done,
            "approvals_required": required,
            "approvals_remaining": remaining,
            "approval_actors": actors,
        }

    @staticmethod
    def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in (update or {}).items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = TenantManager._deep_merge(base.get(k, {}), v)
            else:
                base[k] = v
        return base

    @staticmethod
    def _province_codes() -> set[str]:
        return {str(item.get("value") or "").strip().upper() for item in CANADIAN_PROVINCE_OPTIONS}

    @staticmethod
    def _province_label_map() -> Dict[str, str]:
        return {
            str(item.get("value") or "").strip().upper(): str(item.get("label") or "").strip()
            for item in CANADIAN_PROVINCE_OPTIONS
        }

    @staticmethod
    def _city_maps_by_province() -> Dict[str, Dict[str, Any]]:
        maps: Dict[str, Dict[str, Any]] = {}
        for province_code, cities in CANADIAN_CITIES_BY_PROVINCE_OPTIONS.items():
            code = str(province_code or "").strip().upper()
            by_code: Dict[str, str] = {}
            by_label: Dict[str, str] = {}
            for city in cities or []:
                city_code = str(city.get("value") or "").strip().upper()
                city_label = str(city.get("label") or "").strip()
                if not city_code or not city_label:
                    continue
                by_code[city_code] = city_label
                by_label[city_label.lower()] = city_code
            maps[code] = {"by_code": by_code, "by_label": by_label}
        return maps

    @staticmethod
    def _normalize_code(value: Any) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _coerce_coordinate(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            parsed = float(value)
        except Exception:
            return None
        return parsed

    @classmethod
    def _resolve_city_code(cls, region_code: str, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        maps = cls._city_maps_by_province().get(region_code, {})
        by_code = maps.get("by_code", {})
        by_label = maps.get("by_label", {})
        code_candidate = raw.upper()
        if code_candidate in by_code:
            return code_candidate
        return str(by_label.get(raw.lower()) or "")

    @classmethod
    def _validate_and_normalize_guard_operational_city(
        cls,
        profile: Dict[str, Any],
        *,
        allow_missing: bool = False,
    ) -> None:
        region_code = cls._normalize_code(profile.get("operational_region_code"))
        city_code = cls._resolve_city_code(region_code, profile.get("operational_city_code")) if region_code else ""

        if allow_missing and not region_code and not city_code:
            profile.pop("operational_region_code", None)
            profile.pop("operational_city_code", None)
            return

        if not region_code:
            raise HTTPException(status_code=400, detail="Guard operational province is required")
        if not city_code:
            raise HTTPException(status_code=400, detail="Guard operational city is required")

        province_codes = cls._province_codes()
        if region_code not in province_codes:
            raise HTTPException(status_code=400, detail=f"Invalid guard operational province: {region_code}")

        city_maps = cls._city_maps_by_province().get(region_code, {})
        by_code = city_maps.get("by_code", {})
        if city_code not in by_code:
            raise HTTPException(status_code=400, detail=f"Invalid guard operational city '{city_code}' for province '{region_code}'")

        profile["operational_region_code"] = region_code
        profile["operational_city_code"] = city_code

    @classmethod
    def _validate_and_normalize_guard_operational_radius(
        cls,
        profile: Dict[str, Any],
        *,
        allow_missing: bool = False,
    ) -> None:
        raw_radius = profile.get("max_travel_radius_km")
        if raw_radius in [None, ""]:
            if allow_missing:
                profile.pop("max_travel_radius_km", None)
                return
            raise HTTPException(status_code=400, detail="Guard operational radius is required")

        try:
            radius_km = round(float(raw_radius), 2)
        except Exception:
            raise HTTPException(status_code=400, detail="Guard operational radius must be a valid number")

        if radius_km < 1:
            raise HTTPException(status_code=400, detail="Guard operational radius must be at least 1 km")

        profile["max_travel_radius_km"] = radius_km

    @classmethod
    def _validate_and_normalize_provider_operating_regions(cls, profile: Dict[str, Any]) -> None:
        operating_regions = profile.get("operating_regions")
        if not isinstance(operating_regions, list) or not operating_regions:
            raise HTTPException(status_code=400, detail="At least one operating region is required")

        province_codes = cls._province_codes()
        province_labels = cls._province_label_map()
        city_maps_by_province = cls._city_maps_by_province()
        normalized_regions: List[Dict[str, Any]] = []

        for index, region in enumerate(operating_regions):
            if not isinstance(region, dict):
                raise HTTPException(status_code=400, detail=f"Operating region at index {index} is invalid")

            region_code = cls._normalize_code(region.get("region_code") or region.get("province"))
            if not region_code:
                raise HTTPException(status_code=400, detail=f"Operating region province is required at index {index}")
            if region_code not in province_codes:
                raise HTTPException(status_code=400, detail=f"Invalid operating region province '{region_code}' at index {index}")

            city_codes_raw = region.get("city_codes")
            city_entries_raw = region.get("city_entries")
            default_region_radius = None
            try:
                default_region_radius = float(region.get("coverage_radius_km")) if region.get("coverage_radius_km") is not None else None
            except Exception:
                default_region_radius = None

            if not isinstance(city_entries_raw, list):
                city_entries_raw = []

            if not isinstance(city_codes_raw, list):
                city_codes_raw = []
                legacy_city = region.get("city")
                if legacy_city:
                    city_codes_raw.append(legacy_city)

            if not city_entries_raw and city_codes_raw:
                city_entries_raw = [{"city_code": value, "coverage_radius_km": default_region_radius} for value in city_codes_raw]

            resolved_city_codes: List[str] = []
            normalized_city_entries: List[Dict[str, Any]] = []
            seen: set[str] = set()
            city_maps = city_maps_by_province.get(region_code, {})
            by_code = city_maps.get("by_code", {})

            for entry in city_entries_raw:
                if isinstance(entry, dict):
                    raw_city = entry.get("city_code") or entry.get("city")
                    raw_radius = entry.get("coverage_radius_km")
                else:
                    raw_city = entry
                    raw_radius = default_region_radius

                code = cls._resolve_city_code(region_code, raw_city)
                if not code or code in seen:
                    continue
                if code not in by_code:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid city '{raw_city}' for province '{region_code}' at index {index}"
                    )

                try:
                    radius_km = float(raw_radius) if raw_radius is not None else None
                except Exception:
                    radius_km = None

                latitude = cls._coerce_coordinate(entry.get("latitude") if isinstance(entry, dict) else None)
                longitude = cls._coerce_coordinate(entry.get("longitude") if isinstance(entry, dict) else None)

                if radius_km is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Coverage radius is required for city '{code}' in province '{region_code}' at index {index}"
                    )

                if radius_km < 1:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Coverage radius must be at least 1 km for city '{code}' in province '{region_code}' at index {index}"
                    )

                if latitude is None or longitude is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Latitude and longitude are required for city '{code}' in province '{region_code}' at index {index}"
                    )

                if latitude < -90 or latitude > 90:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Latitude must be between -90 and 90 for city '{code}' in province '{region_code}' at index {index}"
                    )

                if longitude < -180 or longitude > 180:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Longitude must be between -180 and 180 for city '{code}' in province '{region_code}' at index {index}"
                    )

                seen.add(code)
                resolved_city_codes.append(code)
                normalized_city_entries.append({
                    "city_code": code,
                    "city": by_code.get(code, code),
                    "coverage_radius_km": radius_km,
                    "latitude": latitude,
                    "longitude": longitude,
                })

            if not resolved_city_codes:
                raise HTTPException(status_code=400, detail=f"At least one valid city is required for province '{region_code}' at index {index}")

            city_labels = [by_code.get(code, code) for code in resolved_city_codes]
            first_city_code = resolved_city_codes[0]

            normalized_region = dict(region)
            normalized_region["country"] = "CA"
            normalized_region["province"] = region_code
            normalized_region["region_code"] = region_code
            normalized_region["region_label"] = province_labels.get(region_code, region_code)
            normalized_region["city_codes"] = resolved_city_codes
            normalized_region["city_labels"] = city_labels
            normalized_region["city_entries"] = normalized_city_entries
            normalized_region["city_code"] = first_city_code
            normalized_region["city"] = by_code.get(first_city_code, first_city_code)
            normalized_region["coverage_radius_km"] = normalized_city_entries[0]["coverage_radius_km"] if normalized_city_entries else default_region_radius
            normalized_region["latitude"] = normalized_city_entries[0]["latitude"] if normalized_city_entries else None
            normalized_region["longitude"] = normalized_city_entries[0]["longitude"] if normalized_city_entries else None
            normalized_regions.append(normalized_region)

        profile["operating_regions"] = normalized_regions

    @classmethod
    def _validate_and_normalize_profile_for_tenant_type(
        cls,
        tenant_type: TenantType,
        profile: Dict[str, Any],
        *,
        allow_missing_guard_operational_coverage: bool = False,
    ) -> Dict[str, Any]:
        if not isinstance(profile, dict):
            return profile

        if tenant_type == TenantType.GUARD:
            cls._validate_and_normalize_guard_operational_city(
                profile,
                allow_missing=allow_missing_guard_operational_coverage,
            )
            cls._validate_and_normalize_guard_operational_radius(
                profile,
                allow_missing=allow_missing_guard_operational_coverage,
            )
        elif tenant_type == TenantType.SERVICE_PROVIDER:
            cls._validate_and_normalize_provider_operating_regions(profile)

        return profile

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

            if data.tenant_type in [TenantType.GUARD, TenantType.SERVICE_PROVIDER]:
                from orion.api.interactive.billing_manager.billing_manager import BillingManager
                await BillingManager.get_instance().ensure_tenant_rate_snapshot(
                    str(data.id),
                    data.tenant_type,
                )
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

        if normalize_role_value(current_user.role) == user_role.ADMIN.value:
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
            tenant.status = TenantStatus.PENDING_ACTIVATION
            self._reset_pending_activation_approval_state(tenant)

        await self._engine.save(tenant)

        if not is_update and tenant.tenant_type in [TenantType.GUARD, TenantType.SERVICE_PROVIDER]:
            from orion.api.interactive.billing_manager.billing_manager import BillingManager
            await BillingManager.get_instance().ensure_tenant_rate_snapshot(
                str(tenant.id),
                tenant.tenant_type,
            )

        # If status changed from onboarding -> pending_activation, record audit and notify
        if previous_status == TenantStatus.ONBOARDING and tenant.status == TenantStatus.PENDING_ACTIVATION:
            try:
                await self._post_status_change(tenant, previous_status, actor=getattr(current_user, "username", None), actor_role=getattr(current_user, "role", None))
            except Exception:
                # Don't fail the update if notification/audit fails
                pass

        allowed_licenses = set(data.licenses or [])
        if "maintainer" in allowed_licenses and normalize_role_value(current_user.role) != user_role.ADMIN.value:
            raise HTTPException(status_code=401, detail="Only admin can assign maintainer license")

        if normalize_role_value(current_user.role) == user_role.ADMIN.value:
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
        if is_platform_admin_role(role):
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
        if (
            tenant.tenant_type == TenantType.GUARD
            and not self._self_managed_guard_can_mutate_operational_coverage(tenant, current_user)
        ):
            existing_coverage = self._guard_operational_coverage_snapshot(existing_profile)
            requested_coverage = self._guard_operational_coverage_snapshot(merged)
            existing_weekly_availability = self._guard_weekly_availability_snapshot(existing_profile)
            requested_weekly_availability = self._guard_weekly_availability_snapshot(merged)
            if requested_coverage != existing_coverage or requested_weekly_availability != existing_weekly_availability:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Operational region, radius, and weekly availability for service-provider guards "
                        "can only be updated by the owning service provider"
                    ),
                )
        merged = TenantManager._validate_and_normalize_profile_for_tenant_type(tenant.tenant_type, merged)

        tenant.profile = merged
        tenant.updated_at = tenant.updated_at  # keep field present; odmantic will persist
        await self._engine.save(tenant)

        return {"message": "Profile updated", "tenant_id": str(tenant.id), "tenant_type": tenant.tenant_type, "profile": tenant.profile or {}}

    async def upsert_tenant(self, data: TenantPayload, current_user, is_update: bool = True):
        """Unified endpoint for GET/POST/PUT complete tenant data (including profile)."""
        role = getattr(current_user, "role", None)
        is_platform_admin = is_platform_admin_role(role)
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
            allowed = is_platform_admin or (
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
            normalized_requested = self._normalized_status_value(data.status)
            tenant.status = TenantStatus(normalized_requested)
        if data.licenses:
            tenant.licenses = data.licenses
        if data.iocs:
            tenant.iocs = data.iocs

        # Merge profile (only for non-legacy types)
        if data.profile is not None:
            # Ensure profile type matches tenant_type
            existing = deepcopy(tenant.profile or {})
            merged = TenantManager._deep_merge(deepcopy(existing), data.profile)

            if (
                is_update
                and tenant.tenant_type == TenantType.GUARD
                and not self._self_managed_guard_can_mutate_operational_coverage(tenant, current_user)
            ):
                existing_coverage = self._guard_operational_coverage_snapshot(existing)
                requested_coverage = self._guard_operational_coverage_snapshot(merged)
                existing_weekly_availability = self._guard_weekly_availability_snapshot(existing)
                requested_weekly_availability = self._guard_weekly_availability_snapshot(merged)
                if requested_coverage != existing_coverage or requested_weekly_availability != existing_weekly_availability:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Operational region, radius, and weekly availability for service-provider guards "
                            "can only be updated by the owning service provider"
                        ),
                    )
                allow_missing_guard_operational_coverage = not any(existing_coverage.values())
            else:
                allow_missing_guard_operational_coverage = False

            merged = TenantManager._validate_and_normalize_profile_for_tenant_type(
                tenant.tenant_type,
                merged,
                allow_missing_guard_operational_coverage=allow_missing_guard_operational_coverage,
            )
            tenant.profile = merged

        if is_update and not is_platform_admin:
            # Tenant admins cannot directly mutate lifecycle states from update payloads.
            tenant.status = previous_status
            if previous_status == TenantStatus.ONBOARDING:
                if tenant.tenant_type == TenantType.CLIENT:
                    tenant.status = TenantStatus.ACTIVE
                    tenant.verified = True
                    if not tenant.verified_date:
                        tenant.verified_date = datetime.utcnow()
                    tenant.approval_actors = []
                else:
                    tenant.status = TenantStatus.PENDING_ACTIVATION
                    self._reset_pending_activation_approval_state(tenant)

        tenant.updated_at = datetime.utcnow()
        if data.verified and not tenant.verified_date:
            tenant.verified_date = datetime.utcnow()

        await self._engine.save(tenant)

        # Record status-change side effects on update when lifecycle changed.
        if is_update and self._normalized_status_value(previous_status) != self._normalized_status_value(tenant.status):
            try:
                await self._post_status_change(tenant, previous_status, actor=getattr(current_user, "username", None), actor_role=getattr(current_user, "role", None))
            except Exception:
                pass

        return {
            "message": "Tenant updated" if is_update else "Tenant created",
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "status": self._normalized_status_value(tenant.status),
            **self._approvals_summary(tenant),
            "profile": tenant.profile or {},
        }

    async def approve_tenant_activation(self, tenant_id: str, current_user=None):
        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        previous_status = tenant.status
        current_status = self._normalized_status_value(tenant.status)
        actor_username = getattr(current_user, "username", None)
        actor_role = getattr(current_user, "role", None)

        if current_status in [TenantStatus.INACTIVE.value, TenantStatus.BANNED.value]:
            return await self.set_tenant_status(tenant_id, TenantStatus.ACTIVE, current_user=current_user)

        if current_status not in [TenantStatus.PENDING_ACTIVATION.value, TenantStatus.PENDING_VERIFICATION.value]:
            raise HTTPException(status_code=400, detail="Tenant is not pending activation")

        tenant.status = TenantStatus.PENDING_ACTIVATION
        tenant.approvals_required = self._required_approval_count_for_tenant(tenant)
        existing_actors = list(dict.fromkeys(getattr(tenant, "approval_actors", []) or []))

        if self._is_service_provider_owned_guard(tenant):
            if not self._can_service_provider_approve_guard(tenant, current_user):
                raise HTTPException(status_code=403, detail="Only the owning service provider can approve this guard")
            self._ensure_service_provider_guard_managed_profile_ready(tenant)
        elif normalize_role_value(actor_role) not in {user_role.ADMIN.value, user_role.COMPLIANCE_ADMIN.value}:
            raise HTTPException(status_code=403, detail="Only platform admins can approve this tenant")

        if actor_username in existing_actors:
            summary = self._approvals_summary(tenant)
            return {
                "message": "Approval already recorded for this user",
                "id": str(tenant.id),
                "status": tenant.status,
                **summary,
            }

        existing_actors.append(actor_username)
        tenant.approval_actors = existing_actors
        summary = self._approvals_summary(tenant)

        if summary["approvals_done"] >= summary["approvals_required"]:
            tenant.status = TenantStatus.ACTIVE
            tenant.verified = True
            tenant.verified_date = datetime.utcnow()

        tenant.updated_at = datetime.utcnow()
        await self._engine.save(tenant)

        try:
            await self._post_status_change(
                tenant,
                previous_status,
                actor=actor_username,
                actor_role=actor_role,
                reason="approval",
                metadata={
                    "approvals_done": summary["approvals_done"],
                    "approvals_required": summary["approvals_required"],
                    "approvals_remaining": summary["approvals_remaining"],
                    "approval_actors": summary["approval_actors"],
                },
            )
        except Exception:
            pass

        return {
            "message": "Tenant approved" if tenant.status != TenantStatus.ACTIVE else "Tenant activated",
            "id": str(tenant.id),
            "status": tenant.status,
            "verified": tenant.verified,
            "verified_date": tenant.verified_date,
            **summary,
        }

    async def set_tenant_status(self, tenant_id: str, target_status: TenantStatus, current_user=None):
        tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        previous_status = tenant.status

        current_status = self._normalized_status_value(previous_status)
        target_status_value = self._normalized_status_value(target_status)
        if target_status_value == TenantStatus.PENDING_VERIFICATION.value:
            target_status_value = TenantStatus.PENDING_ACTIVATION.value
        target_status_enum = TenantStatus(target_status_value)

        # Idempotent: if no change, do nothing
        if current_status == target_status_value:
            return {
                "message": "No change - tenant already in target status",
                "id": str(tenant.id),
                "status": tenant.status,
            }

        tenant.status = target_status_enum
        tenant.updated_at = datetime.utcnow()

        if target_status_enum == TenantStatus.ACTIVE:
            tenant.verified = True
            tenant.verified_date = datetime.utcnow()

        if target_status_enum == TenantStatus.PENDING_ACTIVATION:
            self._reset_pending_activation_approval_state(tenant)

        await self._engine.save(tenant)

        # Record audit + send notifications
        try:
            await self._post_status_change(tenant, previous_status, actor=getattr(current_user, "username", None), actor_role=getattr(current_user, "role", None))
        except Exception:
            # Don't fail the request if notification/audit fails
            pass

        return {
            "message": "Tenant status updated",
            "id": str(tenant.id),
            "status": self._normalized_status_value(tenant.status),
            "verified": tenant.verified,
            "verified_date": tenant.verified_date,
            **self._approvals_summary(tenant),
        }

    async def _post_status_change(self, tenant: db_tenant_model, previous_status: TenantStatus, actor: Optional[str] = None, actor_role: Optional[str] = None, reason: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        normalized_previous = self._normalized_status_value(previous_status)
        normalized_current = self._normalized_status_value(tenant.status)

        # Persist audit record
        audit = TenantStatusAudit(
            tenant_id=str(tenant.id),
            previous_status=TenantStatus(normalized_previous),
            new_status=TenantStatus(normalized_current),
            actor=actor,
            actor_role=str(actor_role) if actor_role is not None else None,
            reason=reason,
            created_at=datetime.utcnow(),
        )
        try:
            await self._engine.save(audit)
        except Exception:
            pass

        # Persist reusable/generic activity log
        try:
            await ActivityManager.get_instance().log_event(
                module="tenant",
                entity_type="tenant",
                entity_id=str(tenant.id),
                action="status_changed",
                actor_id=str(getattr(actor, "id", "") or "") if hasattr(actor, "id") else None,
                actor_username=actor,
                actor_role=str(actor_role) if actor_role is not None else None,
                previous_status=normalized_previous,
                new_status=normalized_current,
                reason=reason,
                metadata=metadata or self._approvals_summary(tenant),
                severity="info",
            )
        except Exception:
            pass

        # Notify tenant admins / contacts
        try:
            users = await self._engine.find(db_user_account, db_user_account.tenant_uuid == str(tenant.id))
            emails = [u.email for u in users if getattr(u, "email", None)]
            if not emails:
                return

            # Choose subject + body based on new status
            if normalized_current == TenantStatus.PENDING_ACTIVATION.value:
                subject = "Your account is pending activation"
                lurlHeading = ""
                url = ""
                header_text = "Account Pending Activation"
                body_text = "Your account is pending activation. Two platform approvals are required before activation."
            elif normalized_current == TenantStatus.ACTIVE.value:
                subject = "Your account has been verified"
                lurlHeading = ""
                url = ""
                header_text = "Account Verified"
                body_text = "Your account has been verified and is now active. You can sign in and access services as normal."
            elif normalized_current == TenantStatus.INACTIVE.value:
                subject = "Your account has been deactivated"
                lurlHeading = ""
                url = ""
                header_text = "Account Deactivated"
                body_text = "Your account has been deactivated by an administrator. If you believe this is in error, please contact support."
            elif normalized_current == TenantStatus.BANNED.value:
                subject = "Your account has been banned"
                lurlHeading = ""
                url = ""
                header_text = "Account Banned"
                body_text = "Your account has been banned due to a policy violation. Contact support if you need more information."
            else:
                subject = f"Tenant status changed to {normalized_current}"
                lurlHeading = ""
                url = ""
                header_text = f"Tenant Status: {normalized_current}"
                body_text = f"Your tenant status has been updated to {normalized_current}."

            html_content = constant.mail_template.render(
                username=actor or "",
                email=emails[0] or "",
                subject=subject,
                lurlHeading=lurlHeading,
                url=url,
                header=header_text,
                body_text=body_text,
            )
            # Debug/log recipients and subject to help trace delivery issues
            try:
                print(f"[TenantManager] Sending status-change mail: subject='{subject}' to {len(emails)} recipients: {emails}")
                # Send individually using the same API used by signup to reduce differences
                for to in emails:
                    try:
                        await mail_manager.get_instance().send_verification_mail(to=to, subject=subject, body=html_content)
                        print(f"[TenantManager] Mail sent to {to} for tenant {tenant.id}")
                    except Exception as e_inner:
                        print(f"[TenantManager] ERROR sending status-change mail to {to} for tenant {tenant.id}: {str(e_inner)}")
            except Exception as e:
                # Log the error for diagnostics but don't fail the status change
                print(f"[TenantManager] ERROR sending status-change mail for tenant {tenant.id}: {str(e)}")
        except Exception:
            # swallow errors from mail sending
            pass

        try:
            from orion.api.interactive.notification_manager.notification_manager import NotificationManager

            if normalized_current == TenantStatus.PENDING_ACTIVATION.value:
                notification_title = "Account pending activation"
                notification_message = "Your account is pending activation. Two platform approvals are required before full access is enabled."
            elif normalized_current == TenantStatus.ACTIVE.value:
                notification_title = "Account activated"
                notification_message = "Your account is now active and ready to use."
            elif normalized_current == TenantStatus.INACTIVE.value:
                notification_title = "Account deactivated"
                notification_message = "Your account has been deactivated by an administrator. Contact support if this needs review."
            elif normalized_current == TenantStatus.BANNED.value:
                notification_title = "Account banned"
                notification_message = "Your account has been banned due to a policy or compliance issue. Contact support for details."
            else:
                notification_title = "Account status updated"
                notification_message = f"Your account status changed to {normalized_current}."

            await NotificationManager.get_instance().create_for_tenant_users(
                tenant_id=str(tenant.id),
                title=notification_title,
                message=notification_message,
                category="info",
                source_module="tenant",
                action_url="/dashboard/notifications",
                action_label="Review updates",
                metadata={
                    "tenant_id": str(tenant.id),
                    "previous_status": normalized_previous,
                    "new_status": normalized_current,
                    **(metadata or {}),
                },
            )
        except Exception:
            pass

    @staticmethod
    def _extract_tenant_name(profile: Optional[Dict[str, Any]]) -> str:
        if not isinstance(profile, dict):
            return ""
        for key in ["legal_company_name", "trading_name", "legal_entity_name", "full_name", "company_name", "name"]:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    async def _provider_summary(self, provider_tenant_id: Optional[str]) -> Optional[Dict[str, Any]]:
        provider_id = str(provider_tenant_id or "").strip()
        if not provider_id:
            return None
        try:
            provider = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(provider_id))
        except Exception:
            provider = None
        if not provider:
            return {"id": provider_id, "name": None}
        return {
            "id": str(provider.id),
            "name": self._extract_tenant_name(provider.profile or {}),
        }

    async def _get_guard_tenant(self, guard_tenant_id: str) -> db_tenant_model:
        try:
            guard = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(guard_tenant_id))
        except Exception:
            guard = None
        if not guard or guard.tenant_type != TenantType.GUARD:
            raise HTTPException(status_code=404, detail="Guard tenant not found")
        return guard

    async def _get_tenant(self, tenant_id: str) -> db_tenant_model | None:
        try:
            return await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            return None

    def _is_owned_by_service_provider(self, guard: db_tenant_model, service_provider_tenant_id: str) -> bool:
        return (
            guard.ownership_type == GuardOwnershipType.SERVICE_PROVIDER
            and str(getattr(guard, "service_provider_tenant_id", "") or "").strip() == str(service_provider_tenant_id or "").strip()
        )

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
            current_status = self._normalized_status_value(doc.get("status"))
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
            approval_actors = list(dict.fromkeys(doc.get("approval_actors") or []))
            approvals_required = int(doc.get("approvals_required") or 2)
            approvals_done = len(approval_actors)
            approvals_remaining = max(approvals_required - approvals_done, 0)
            provider_summary = await self._provider_summary(doc.get("service_provider_tenant_id"))
            data.append({
                "id": str(doc.get("_id")),
                "name": self._extract_tenant_name(profile),
                "tenant_type": doc.get("tenant_type"),
                "status": self._normalized_status_value(doc.get("status")),
                "ownership_type": doc.get("ownership_type"),
                "service_provider_tenant_id": doc.get("service_provider_tenant_id"),
                "service_provider": provider_summary,
                "verified": bool(doc.get("verified", False)),
                "subscription": bool(doc.get("subscription", False)),
                "user_quota": int(doc.get("user_quota", 0) or 0),
                "approvals_required": approvals_required,
                "approvals_done": approvals_done,
                "approvals_remaining": approvals_remaining,
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

        tenant_role_to_admin_role = {
            TenantType.GUARD: user_role.GUARD_ADMIN,
            TenantType.CLIENT: user_role.CLIENT_ADMIN,
            TenantType.SERVICE_PROVIDER: user_role.SP_ADMIN,
        }
        expected_admin_role = tenant_role_to_admin_role.get(tenant.tenant_type)

        tenant_admin_user = None
        if expected_admin_role is not None:
            candidate_users = await self._engine.find(
                db_user_account,
                (db_user_account.tenant_uuid == str(tenant.id)) & (db_user_account.role == expected_admin_role),
            )

            selected_user = None
            active_users = [u for u in candidate_users if str(getattr(u, "status", "")) == UserStatus.ACTIVE.value]
            if active_users:
                selected_user = active_users[0]
            elif candidate_users:
                selected_user = candidate_users[0]

            if selected_user is not None:
                tenant_admin_user = {
                    "id": str(selected_user.id),
                    "username": selected_user.username,
                    "full_name": (selected_user.full_name or "").strip() or None,
                    "email": (selected_user.email or "").strip() or None,
                    "invite_pending": bool(getattr(selected_user, "invite_pending", False)),
                    "invite_expires_at": getattr(selected_user, "verification_expiry", None),
                }

        provider_summary = await self._provider_summary(getattr(tenant, "service_provider_tenant_id", None))

        return {
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "profile": profile,
            "ownership_type": tenant.ownership_type,
            "service_provider_tenant_id": tenant.service_provider_tenant_id,
            "service_provider": provider_summary,
            "subscription": tenant.subscription,
            "verified": tenant.verified,
            "user_quota": tenant.user_quota,
            "status": self._normalized_status_value(tenant.status),
            "approvals_required": self._approvals_summary(tenant)["approvals_required"],
            "approvals_done": self._approvals_summary(tenant)["approvals_done"],
            "approvals_remaining": self._approvals_summary(tenant)["approvals_remaining"],
            "approval_actors": self._approvals_summary(tenant)["approval_actors"],
            "licenses": licenses,
            "iocs": iocs,
            "tenant_admin_user": tenant_admin_user,
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

            if data.role in ["demo"] and normalize_role_value(current_user.role) != user_role.ADMIN.value:

                raise HTTPException(status_code=401, detail="You are not allowed to manage this user")

            dek = await KeyManager.get_instance().get_profile_dek(str(tenant.id))
            enc = Fernet(dek)

            tenant_allowed = set(enc.decrypt(l.encode()).decode() for l in (tenant.licenses or []))

            requested = set(data.licenses or [])

            if requested and not requested.issubset(tenant_allowed) and normalize_role_value(current_user.role) != user_role.ADMIN.value:
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

    async def _generate_invited_guard_username(self, email: str) -> str:
        local_part = str(email or "").split("@")[0].lower()
        normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", local_part)
        if not normalized or not normalized[0].isalpha():
            normalized = f"guard_{normalized}"
        base = normalized[:14]
        if len(base) < 8:
            base = (base + "_guardusr")[:8]

        for _ in range(20):
            suffix = secrets.token_hex(2)
            candidate = f"{base}_{suffix}"[:20]
            existing = await self._engine.find_one(db_user_account, db_user_account.username == candidate)
            if not existing:
                return candidate
        return f"guard_{secrets.token_hex(4)}"[:20]

    async def _get_guard_admin_user(self, guard_tenant_id: str):
        users = await self._engine.find(
            db_user_account,
            (db_user_account.tenant_uuid == str(guard_tenant_id)) & (db_user_account.role == user_role.GUARD_ADMIN),
            limit=1,
        )
        return users[0] if users else None

    async def invite_guard_for_service_provider(
        self,
        data: ServiceProviderGuardInviteRequest,
        current_user,
    ) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        if not provider_tenant_id:
            raise HTTPException(status_code=400, detail="Invalid service provider association")

        provider = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(provider_tenant_id))
        self._assert_service_provider_guard_management_allowed(provider)

        email = str(data.email).strip().lower()
        existing_email_user = await self._engine.find_one(db_user_account, db_user_account.email == email)
        if existing_email_user:
            raise HTTPException(status_code=400, detail="Email already exists")

        guard_tenant = db_tenant_model(
            iocs=[],
            user_quota=2,
            licenses=["maintainer", "free"],
            status=TenantStatus.ONBOARDING,
            tenant_type=TenantType.GUARD,
            profile={"name": "N/A"},
            ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
            service_provider_tenant_id=provider_tenant_id,
            linked_at=datetime.now(timezone.utc),
            linked_by=getattr(current_user, "username", None),
            unlinked_at=None,
            unlinked_by=None,
        )
        await self.create_tenant(guard_tenant)

        invite_token = session_manager.get_instance().generate_verification_token()
        invite_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        placeholder_username = await self._generate_invited_guard_username(email)
        temporary_password = CONSTANTS.S_AUTH_PWD_CONTEXT.hash(f"TmpG1!{secrets.token_urlsafe(12)}")

        guard_user = db_user_account(
            username=placeholder_username,
            full_name="",
            email=email,
            password=temporary_password,
            role=user_role.GUARD_ADMIN,
            status=UserStatus.INACTIVE,
            subscription=False,
            licenses=[LicenseName.MAINTAINER],
            tenant_uuid=str(guard_tenant.id),
            verification_token=invite_token,
            verification_expiry=invite_expiry,
            invite_pending=True,
            status_reason="Invite pending",
            status_changed_by=getattr(current_user, "username", "system"),
            status_changed_at=datetime.now(timezone.utc),
        )
        await self._engine.save(guard_user)

        try:
            app_url = env_handler.get_instance().env("APP_URL")
            invite_url = f"{app_url}/invite/{invite_token}"
            subject = "You are invited as a Guard"
            html_content = constant.mail_template.render(
                username=guard_user.username,
                email=guard_user.email,
                subject=subject,
                lurlHeading="Set your password link : ",
                url=invite_url,
            )
            await mail_manager.get_instance().send_verification_mail(
                to=guard_user.email,
                subject=subject,
                body=html_content,
            )
        except Exception:
            # Roll back pre-linked guard records when invite email cannot be dispatched.
            try:
                await self._engine.delete(guard_user)
            except Exception:
                pass
            try:
                await self._engine.delete(guard_tenant)
            except Exception:
                pass
            raise HTTPException(status_code=503, detail="Failed to send invite email. Please try again.")

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=str(guard_tenant.id),
            action="invite_sent",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            metadata={
                "guard_tenant_id": str(guard_tenant.id),
                "service_provider_tenant_id": provider_tenant_id,
                "email": email,
                "invite_expires_at": invite_expiry.isoformat(),
            },
        )

        return {
            "message": "Guard invite sent",
            "guard_tenant_id": str(guard_tenant.id),
            "email": email,
            "invite_expires_at": invite_expiry.isoformat(),
            "ownership_type": GuardOwnershipType.SERVICE_PROVIDER.value,
            "service_provider_tenant_id": provider_tenant_id,
        }

    async def list_service_provider_guards(self, current_user, page: int = 1, rows: int = 20) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        if not provider_tenant_id:
            raise HTTPException(status_code=400, detail="Invalid service provider association")

        provider = await self._get_tenant(provider_tenant_id)
        self._assert_service_provider_guard_management_allowed(provider)

        guards = await self._engine.find(
            db_tenant_model,
            (db_tenant_model.tenant_type == TenantType.GUARD)
            & (db_tenant_model.ownership_type == GuardOwnershipType.SERVICE_PROVIDER)
            & (db_tenant_model.service_provider_tenant_id == provider_tenant_id),
        )

        items: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for guard in guards:
            admin_user = await self._get_guard_admin_user(str(guard.id))
            invite_pending = bool(getattr(admin_user, "invite_pending", False)) if admin_user else False
            invite_expiry = getattr(admin_user, "verification_expiry", None) if admin_user else None
            invite_status = None
            if invite_pending:
                expiry_utc = invite_expiry if (invite_expiry and invite_expiry.tzinfo) else (
                    invite_expiry.replace(tzinfo=timezone.utc) if invite_expiry else None
                )
                invite_status = "expired" if expiry_utc and now > expiry_utc else "pending"
            elif admin_user:
                invite_status = "accepted"

            items.append({
                "id": str(guard.id),
                "name": self._extract_tenant_name(guard.profile or {}),
                "status": self._normalized_status_value(guard.status),
                "ownership_type": guard.ownership_type,
                "service_provider_tenant_id": guard.service_provider_tenant_id,
                "invite_status": invite_status,
                "invite_expires_at": invite_expiry,
                "email": getattr(admin_user, "email", None),
                "verified": bool(guard.verified),
                "created_at": guard.created_at,
                "updated_at": guard.updated_at,
            })

        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(items)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows

        return {
            "items": items[start:end],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def get_service_provider_guard(self, guard_tenant_id: str, current_user) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        provider = await self._get_tenant(provider_tenant_id)
        self._assert_service_provider_guard_management_allowed(provider)
        guard = await self._get_guard_tenant(guard_tenant_id)
        if not self._is_owned_by_service_provider(guard, provider_tenant_id):
            raise HTTPException(status_code=403, detail="Guard does not belong to your service provider")
        return await self._serialize_tenant(guard)

    async def update_service_provider_guard_operational_coverage(
        self,
        guard_tenant_id: str,
        payload: ServiceProviderGuardOperationalCoveragePayload,
        current_user,
    ) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        provider = await self._get_tenant(provider_tenant_id)
        self._assert_service_provider_guard_management_allowed(provider)
        guard = await self._get_guard_tenant(guard_tenant_id)
        if not self._is_owned_by_service_provider(guard, provider_tenant_id):
            raise HTTPException(status_code=403, detail="Guard does not belong to your service provider")

        normalized_provider_profile = dict(provider.profile or {})
        self._validate_and_normalize_provider_operating_regions(normalized_provider_profile)
        operating_regions = normalized_provider_profile.get("operating_regions") or []

        target_region_code = self._normalize_code(payload.operational_region_code)
        target_city_code = self._resolve_city_code(target_region_code, payload.operational_city_code)
        if not target_region_code or not target_city_code:
            raise HTTPException(status_code=400, detail="Operational province and city are required")

        matched_city_entry = None
        for region in operating_regions:
            if self._normalize_code(region.get("region_code")) != target_region_code:
                continue
            for city_entry in region.get("city_entries") or []:
                if str(city_entry.get("city_code") or "").strip().upper() == target_city_code:
                    matched_city_entry = city_entry
                    break
            if matched_city_entry:
                break

        if not matched_city_entry:
            raise HTTPException(
                status_code=400,
                detail="The selected operational region must belong to the service provider coverage map",
            )

        provider_city_radius = matched_city_entry.get("coverage_radius_km")
        try:
            provider_city_radius_km = round(float(provider_city_radius), 2) if provider_city_radius is not None else None
        except Exception:
            provider_city_radius_km = None

        if provider_city_radius_km is not None and payload.max_travel_radius_km > provider_city_radius_km:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Guard operational radius cannot exceed the service provider coverage radius "
                    f"for {target_city_code} ({provider_city_radius_km} km)"
                ),
            )

        profile = dict(guard.profile or {})
        profile["operational_region_code"] = target_region_code
        profile["operational_city_code"] = target_city_code
        profile["max_travel_radius_km"] = payload.max_travel_radius_km
        if payload.weekly_availability is not None:
            profile["weekly_availability"] = deepcopy(payload.weekly_availability)
        profile = self._validate_and_normalize_profile_for_tenant_type(TenantType.GUARD, profile)

        guard.profile = profile
        guard.updated_at = datetime.utcnow()
        await self._engine.save(guard)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=guard_tenant_id,
            action="operational_coverage_updated_by_service_provider",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            metadata={
                "service_provider_tenant_id": provider_tenant_id,
                "operational_region_code": target_region_code,
                "operational_city_code": target_city_code,
                "max_travel_radius_km": payload.max_travel_radius_km,
                "weekly_availability_updated": payload.weekly_availability is not None,
            },
        )

        serialized = await self._serialize_tenant(guard)
        serialized["message"] = (
            "Guard operational coverage and weekly availability updated"
            if payload.weekly_availability is not None
            else "Guard operational coverage updated"
        )
        return serialized

    async def delete_expired_pending_guard_invite(self, guard_tenant_id: str, current_user) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        provider = await self._get_tenant(provider_tenant_id)
        self._assert_service_provider_guard_management_allowed(provider)
        guard = await self._get_guard_tenant(guard_tenant_id)
        if not self._is_owned_by_service_provider(guard, provider_tenant_id):
            raise HTTPException(status_code=403, detail="Guard does not belong to your service provider")

        admin_user = await self._get_guard_admin_user(guard_tenant_id)
        if not admin_user or not getattr(admin_user, "invite_pending", False):
            raise HTTPException(status_code=400, detail="No pending invite found for this guard")

        expiry = getattr(admin_user, "verification_expiry", None)
        if not expiry:
            raise HTTPException(status_code=400, detail="Invite expiry not found")
        expiry_utc = expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) <= expiry_utc:
            raise HTTPException(status_code=400, detail="Invite is not expired")

        await self._engine.delete(admin_user)
        await self._engine.delete(guard)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=guard_tenant_id,
            action="invite_deleted",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            reason="expired_invite_cleanup",
            metadata={"guard_tenant_id": guard_tenant_id, "service_provider_tenant_id": provider_tenant_id},
        )

        return {"message": "Expired invite deleted", "guard_tenant_id": guard_tenant_id}

    async def request_guard_status_change(
        self,
        guard_tenant_id: str,
        payload: ServiceProviderGuardStatusRequestPayload,
        current_user,
    ) -> Dict[str, Any]:
        provider_tenant_id = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        provider = await self._get_tenant(provider_tenant_id)
        self._assert_service_provider_guard_management_allowed(provider)
        guard = await self._get_guard_tenant(guard_tenant_id)
        if not self._is_owned_by_service_provider(guard, provider_tenant_id):
            raise HTTPException(status_code=403, detail="Guard does not belong to your service provider")

        action = payload.action
        reason = (payload.reason or "").strip() or None
        if action == GuardStatusAction.DEACTIVATE and not reason:
            raise HTTPException(status_code=400, detail="Reason is required for deactivation request")

        if action == GuardStatusAction.ACTIVATE:
            current_status = self._normalized_status_value(guard.status)
            if current_status == TenantStatus.PENDING_ACTIVATION.value:
                result = await self.approve_tenant_activation(guard_tenant_id, current_user=current_user)
            else:
                result = await self.set_tenant_status(guard_tenant_id, TenantStatus.ACTIVE, current_user=current_user)
        else:
            result = await self.set_tenant_status(guard_tenant_id, TenantStatus.INACTIVE, current_user=current_user)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=guard_tenant_id,
            action="status_changed_by_service_provider",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            reason=reason,
            metadata={
                "requested_action": action.value,
                "service_provider_tenant_id": provider_tenant_id,
            },
        )

        return {
            "message": result.get("message") or "Tenant status updated",
            "guard_tenant_id": guard_tenant_id,
            "requested_action": action.value,
            "status": result.get("status"),
            "reason": reason,
            "verified": result.get("verified"),
            "verified_date": result.get("verified_date"),
            "approvals_done": result.get("approvals_done"),
            "approvals_required": result.get("approvals_required"),
            "approvals_remaining": result.get("approvals_remaining"),
        }

    async def list_guard_status_requests(self, page: int = 1, rows: int = 20) -> Dict[str, Any]:
        docs = await self._engine.find(GuardStatusChangeRequest)
        items: List[Dict[str, Any]] = []
        for req in docs:
            provider_summary = await self._provider_summary(req.service_provider_tenant_id)
            items.append({
                "id": str(req.id),
                "guard_tenant_id": req.guard_tenant_id,
                "service_provider_tenant_id": req.service_provider_tenant_id,
                "service_provider": provider_summary,
                "requested_action": req.requested_action.value if hasattr(req.requested_action, "value") else str(req.requested_action),
                "status": req.status.value if hasattr(req.status, "value") else str(req.status),
                "reason": req.reason,
                "requested_by_user_id": req.requested_by_user_id,
                "requested_by_username": req.requested_by_username,
                "reviewed_by_user_id": req.reviewed_by_user_id,
                "reviewed_by_username": req.reviewed_by_username,
                "review_comment": req.review_comment,
                "reviewed_at": req.reviewed_at,
                "created_at": req.created_at,
                "updated_at": req.updated_at,
            })

        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(items)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        return {
            "items": items[start:end],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def approve_guard_status_request(
        self,
        request_id: str,
        payload: GuardStatusRequestDecisionPayload,
        current_user,
    ) -> Dict[str, Any]:
        request_doc = await self._engine.find_one(GuardStatusChangeRequest, GuardStatusChangeRequest.id == ObjectId(request_id))
        if not request_doc:
            raise HTTPException(status_code=404, detail="Status request not found")
        if request_doc.status != GuardStatusRequestStatus.PENDING:
            raise HTTPException(status_code=400, detail="Status request is no longer pending")

        target_status = TenantStatus.ACTIVE if request_doc.requested_action == GuardStatusAction.ACTIVATE else TenantStatus.INACTIVE
        status_result = await self.set_tenant_status(request_doc.guard_tenant_id, target_status, current_user=current_user)

        request_doc.status = GuardStatusRequestStatus.APPROVED
        request_doc.review_comment = (payload.comment or "").strip() or None
        request_doc.reviewed_by_user_id = str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None
        request_doc.reviewed_by_username = getattr(current_user, "username", None)
        request_doc.reviewed_at = datetime.now(timezone.utc)
        request_doc.updated_at = datetime.now(timezone.utc)
        await self._engine.save(request_doc)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=request_doc.guard_tenant_id,
            action="status_change_request_approved",
            actor_id=request_doc.reviewed_by_user_id,
            actor_username=request_doc.reviewed_by_username,
            actor_role=getattr(current_user, "role", None),
            reason=request_doc.reason,
            metadata={
                "request_id": str(request_doc.id),
                "requested_action": request_doc.requested_action.value,
                "review_comment": request_doc.review_comment,
            },
        )

        return {
            "message": "Status request approved",
            "request_id": str(request_doc.id),
            "status": request_doc.status.value,
            "guard_status": status_result.get("status"),
        }

    async def reject_guard_status_request(
        self,
        request_id: str,
        payload: GuardStatusRequestDecisionPayload,
        current_user,
    ) -> Dict[str, Any]:
        request_doc = await self._engine.find_one(GuardStatusChangeRequest, GuardStatusChangeRequest.id == ObjectId(request_id))
        if not request_doc:
            raise HTTPException(status_code=404, detail="Status request not found")
        if request_doc.status != GuardStatusRequestStatus.PENDING:
            raise HTTPException(status_code=400, detail="Status request is no longer pending")

        request_doc.status = GuardStatusRequestStatus.REJECTED
        request_doc.review_comment = (payload.comment or "").strip() or None
        request_doc.reviewed_by_user_id = str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None
        request_doc.reviewed_by_username = getattr(current_user, "username", None)
        request_doc.reviewed_at = datetime.now(timezone.utc)
        request_doc.updated_at = datetime.now(timezone.utc)
        await self._engine.save(request_doc)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=request_doc.guard_tenant_id,
            action="status_change_request_rejected",
            actor_id=request_doc.reviewed_by_user_id,
            actor_username=request_doc.reviewed_by_username,
            actor_role=getattr(current_user, "role", None),
            reason=request_doc.reason,
            metadata={
                "request_id": str(request_doc.id),
                "requested_action": request_doc.requested_action.value,
                "review_comment": request_doc.review_comment,
            },
        )

        return {
            "message": "Status request rejected",
            "request_id": str(request_doc.id),
            "status": request_doc.status.value,
        }

    async def link_guard_to_service_provider(
        self,
        guard_tenant_id: str,
        payload: GuardServiceProviderLinkPayload,
        current_user,
    ) -> Dict[str, Any]:
        guard = await self._get_guard_tenant(guard_tenant_id)

        try:
            provider = await self._engine.find_one(
                db_tenant_model, db_tenant_model.id == ObjectId(payload.service_provider_tenant_id)
            )
        except Exception:
            provider = None
        if not provider or provider.tenant_type != TenantType.SERVICE_PROVIDER:
            raise HTTPException(status_code=404, detail="Service provider tenant not found")

        previous_provider = str(getattr(guard, "service_provider_tenant_id", "") or "").strip() or None
        guard.ownership_type = GuardOwnershipType.SERVICE_PROVIDER
        guard.service_provider_tenant_id = str(provider.id)
        guard.linked_at = datetime.now(timezone.utc)
        guard.linked_by = getattr(current_user, "username", None)
        guard.unlinked_at = None
        guard.unlinked_by = None
        guard.updated_at = datetime.now(timezone.utc)
        await self._engine.save(guard)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=str(guard.id),
            action="service_provider_linked",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            reason=payload.reason,
            metadata={
                "previous_service_provider_tenant_id": previous_provider,
                "service_provider_tenant_id": str(provider.id),
            },
        )

        return {
            "message": "Guard linked to service provider",
            "guard_tenant_id": str(guard.id),
            "ownership_type": GuardOwnershipType.SERVICE_PROVIDER.value,
            "service_provider_tenant_id": str(provider.id),
        }

    async def unlink_guard_from_service_provider(
        self,
        guard_tenant_id: str,
        payload: GuardServiceProviderUnlinkPayload,
        current_user,
    ) -> Dict[str, Any]:
        guard = await self._get_guard_tenant(guard_tenant_id)
        previous_provider = str(getattr(guard, "service_provider_tenant_id", "") or "").strip() or None
        if not previous_provider:
            raise HTTPException(status_code=400, detail="Guard is not linked to a service provider")

        guard.ownership_type = GuardOwnershipType.PLATFORM
        guard.service_provider_tenant_id = None
        guard.unlinked_at = datetime.now(timezone.utc)
        guard.unlinked_by = getattr(current_user, "username", None)
        guard.updated_at = datetime.now(timezone.utc)
        await self._engine.save(guard)

        await ActivityManager.get_instance().log_event(
            module="tenant",
            entity_type="guard",
            entity_id=str(guard.id),
            action="service_provider_unlinked",
            actor_id=str(getattr(current_user, "id", "") or "") if hasattr(current_user, "id") else None,
            actor_username=getattr(current_user, "username", None),
            actor_role=getattr(current_user, "role", None),
            reason=payload.reason,
            metadata={
                "previous_service_provider_tenant_id": previous_provider,
            },
        )

        return {
            "message": "Guard unlinked from service provider",
            "guard_tenant_id": str(guard.id),
            "ownership_type": GuardOwnershipType.PLATFORM.value,
            "service_provider_tenant_id": None,
        }
