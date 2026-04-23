import threading
from datetime import datetime
from typing import List, Dict, Any

from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.activity_manager.activity_manager import ActivityManager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_billing_model import (
    BillingRate,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    db_tenant_model,
    TenantStatus,
    TenantType,
)
from configs.metadata_constants import (
    CANADIAN_PROVINCE_OPTIONS,
    CANADIAN_CITIES_BY_PROVINCE_OPTIONS,
    BILLING_REGION_CITY_OPTIONS,
)


# Use all Canadian provinces and territories
CANADIAN_PROVINCES = CANADIAN_PROVINCE_OPTIONS
BILLING_LOCATIONS = BILLING_REGION_CITY_OPTIONS


class BillingManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance() -> "BillingManager":
        if BillingManager.__instance is None:
            with BillingManager.__lock:
                if BillingManager.__instance is None:
                    BillingManager.__instance = BillingManager()
        return BillingManager.__instance

    def __init__(self):
        if BillingManager.__instance is not None:
            raise Exception("BillingManager is a singleton")
        self._engine = mongo_controller.get_instance().get_engine()

    SCOPE_GUARD_DEFAULT = "guard_default"
    SCOPE_GUARD_DEFAULT_LEGACY = "guard"
    SCOPE_PROVIDER_DEFAULT = "provider_default"
    SCOPE_GUARD_MARGIN_DEFAULT = "guard_margin_default"
    SCOPE_PROVIDER_COMMISSION_DEFAULT = "provider_commission_default"

    @staticmethod
    def _extract_tenant_name(profile: Any) -> str:
        if not isinstance(profile, dict):
            return ""
        for key in ["legal_company_name", "trading_name", "legal_entity_name", "full_name", "company_name", "name"]:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _region_label(region_code: str) -> str:
        for region in CANADIAN_PROVINCES:
            if region["value"] == region_code:
                return region["label"]
        return region_code

    @staticmethod
    def _normalize_city_code(city_code: Any) -> str:
        return str(city_code or "").strip().upper()

    @staticmethod
    def _rate_key(region_code: str, city_code: str) -> str:
        return f"{region_code}:{city_code}"

    @staticmethod
    def _city_label(region_code: str, city_code: str) -> str:
        normalized = city_code.strip().upper()
        if not normalized:
            return ""
        for city in CANADIAN_CITIES_BY_PROVINCE_OPTIONS.get(region_code, []):
            if city["value"] == normalized:
                return city["label"]
        return normalized

    def _location_label(self, region_code: str, city_code: str) -> str:
        region_label = self._region_label(region_code)
        city_label = self._city_label(region_code, city_code)
        if city_label:
            return f"{region_label} / {city_label}"
        return region_label

    @staticmethod
    def _provider_scope(provider_id: str) -> str:
        return f"provider:{provider_id}"

    @staticmethod
    def _guard_scope(guard_id: str) -> str:
        return f"guard:{guard_id}"

    @staticmethod
    def _has_rate_change(
        prev_std: float,
        prev_wkd: float,
        prev_hol: float,
        new_std: float,
        new_wkd: float,
        new_hol: float,
    ) -> bool:
        return (
            prev_std != new_std
            or prev_wkd != new_wkd
            or prev_hol != new_hol
        )

    async def _compose_rates_by_scope_priority(
        self,
        scopes: List[str],
    ) -> List[Dict[str, Any]]:
        by_scope: Dict[str, Dict[str, BillingRate]] = {}
        for scope in scopes:
            existing = await self._engine.find(BillingRate, BillingRate.scope == scope)
            by_scope[scope] = {
                self._rate_key(r.region_code, self._normalize_city_code(getattr(r, "city_code", ""))): r
                for r in existing
            }

        result = []
        for location in BILLING_LOCATIONS:
            code = location["region_code"]
            city_code = self._normalize_city_code(location.get("city_code"))
            province_label = location["region_label"]
            city_label = location.get("city_label", "")
            rec = None
            for scope in scopes:
                scoped_rates = by_scope.get(scope, {})
                rec = scoped_rates.get(self._rate_key(code, city_code))
                if not rec:
                    # Backward compatibility: province-level defaults without city_code.
                    rec = scoped_rates.get(self._rate_key(code, ""))
                if rec:
                    break

            result.append({
                "region_code": code,
                "region_label": province_label,
                "city_code": city_code,
                "city_label": city_label,
                "location_label": self._location_label(code, city_code),
                "standard_rate": rec.standard_rate if rec else 0.0,
                "weekend_rate": rec.weekend_rate if rec else 0.0,
                "holiday_rate": rec.holiday_rate if rec else 0.0,
                "currency": "CAD",
            })
        return result

    async def _save_scope_rates(
        self,
        scope: str,
        payload: List[Dict[str, Any]],
        current_user,
        entity_id: str,
        entity_name: str,
        write_activity: bool = True,
        force_create_missing: bool = False,
    ) -> Dict[str, Any]:
        valid_location_keys = {
            self._rate_key(loc["region_code"], self._normalize_city_code(loc.get("city_code")))
            for loc in BILLING_LOCATIONS
        }
        valid_codes = {p["value"] for p in CANADIAN_PROVINCES}
        now = datetime.utcnow()
        actor_id = str(getattr(current_user, "id", "") or "") or None
        actor = getattr(current_user, "username", None)
        actor_role = str(getattr(current_user, "role", None))
        updated_count = 0

        for row in payload:
            code = str(row.get("region_code", "")).strip().upper()
            if code not in valid_codes:
                continue

            input_city_code = self._normalize_city_code(row.get("city_code", ""))

            target_cities: List[str]
            if input_city_code:
                if self._rate_key(code, input_city_code) not in valid_location_keys:
                    continue
                target_cities = [input_city_code]
            else:
                target_cities = [
                    self._normalize_city_code(loc.get("city_code"))
                    for loc in BILLING_LOCATIONS
                    if loc["region_code"] == code
                ]
                if not target_cities:
                    continue

            std = round(float(row.get("standard_rate", 0)), 2)
            wkd = round(float(row.get("weekend_rate", 0)), 2)
            hol = round(float(row.get("holiday_rate", 0)), 2)

            for city_code in target_cities:
                existing = await self._engine.find_one(
                    BillingRate,
                    (BillingRate.scope == scope)
                    & (BillingRate.region_code == code)
                    & (BillingRate.city_code == city_code),
                )

                prev_std = existing.standard_rate if existing else 0.0
                prev_wkd = existing.weekend_rate if existing else 0.0
                prev_hol = existing.holiday_rate if existing else 0.0

                changed = self._has_rate_change(prev_std, prev_wkd, prev_hol, std, wkd, hol)
                if not changed and not (force_create_missing and not existing):
                    continue

                if existing:
                    existing.standard_rate = std
                    existing.weekend_rate = wkd
                    existing.holiday_rate = hol
                    existing.updated_at = now
                    existing.updated_by = actor
                    await self._engine.save(existing)
                else:
                    await self._engine.save(BillingRate(
                        scope=scope,
                        region_code=code,
                        city_code=city_code,
                        standard_rate=std,
                        weekend_rate=wkd,
                        holiday_rate=hol,
                        currency="CAD",
                        updated_at=now,
                        updated_by=actor,
                    ))

                if write_activity and changed:
                    await self._write_activity_log(
                        entity_id=entity_id,
                        entity_name=entity_name,
                        scope=scope,
                        region_code=code,
                        city_code=city_code,
                        prev_std=prev_std,
                        prev_wkd=prev_wkd,
                        prev_hol=prev_hol,
                        new_std=std,
                        new_wkd=wkd,
                        new_hol=hol,
                        actor_id=actor_id,
                        actor=actor,
                        actor_role=actor_role,
                    )

                updated_count += 1

        return {
            "count": len(payload),
            "updated_count": updated_count,
        }

    async def get_billing_location_metadata(self) -> Dict[str, Any]:
        return {
            "canadianProvinces": CANADIAN_PROVINCES,
            "canadianCitiesByProvince": CANADIAN_CITIES_BY_PROVINCE_OPTIONS,
            "billingLocationOptions": BILLING_LOCATIONS,
        }

    async def _get_tenant_or_404(self, tenant_id: str, tenant_type: TenantType, detail: str):
        try:
            tenant = await self._engine.find_one(
                db_tenant_model,
                db_tenant_model.id == ObjectId(tenant_id),
            )
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid {detail.lower()} id")

        if not tenant or tenant.tenant_type != tenant_type:
            raise HTTPException(status_code=404, detail=f"{detail} not found")
        return tenant

    # ------------------------------------------------------------------
    # Guard default rates
    # ------------------------------------------------------------------

    async def get_guard_rates(self) -> List[Dict[str, Any]]:
        """Return one record per Canadian province for guard defaults."""
        return await self._compose_rates_by_scope_priority([
            self.SCOPE_GUARD_DEFAULT,
            self.SCOPE_GUARD_DEFAULT_LEGACY,
        ])

    async def save_guard_rates(
        self, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert guard-default rates for all provinces in the payload."""
        save_result = await self._save_scope_rates(
            scope=self.SCOPE_GUARD_DEFAULT,
            payload=payload,
            current_user=current_user,
            entity_id="guard-default-rates",
            entity_name="Guard Default Rates",
        )

        return {
            "message": "Guard rates saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def get_guard_margin_rates(self) -> List[Dict[str, Any]]:
        """Return one record per Canadian province for guard margin defaults."""
        return await self._compose_rates_by_scope_priority([
            self.SCOPE_GUARD_MARGIN_DEFAULT,
        ])

    async def save_guard_margin_rates(
        self, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert guard margin defaults by province."""
        save_result = await self._save_scope_rates(
            scope=self.SCOPE_GUARD_MARGIN_DEFAULT,
            payload=payload,
            current_user=current_user,
            entity_id="guard-margin-default-rates",
            entity_name="Guard Margin Default Rates",
        )

        return {
            "message": "Guard margin defaults saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def list_active_guards(self) -> List[Dict[str, Any]]:
        """Return id + name for every active guard tenant."""
        guards = await self._engine.find(
            db_tenant_model,
            (db_tenant_model.tenant_type == TenantType.GUARD)
            & (db_tenant_model.status == TenantStatus.ACTIVE),
        )

        seen_ids = set()
        result = []
        for g in guards:
            guard_id = str(g.id)
            if guard_id in seen_ids:
                continue

            profile = getattr(g, "profile", None) or {}
            name = self._extract_tenant_name(profile)
            if not name:
                name = guard_id

            seen_ids.add(guard_id)
            result.append({"id": guard_id, "name": name})

        result.sort(key=lambda item: item["name"].lower())
        return result

    async def get_guard_override_rates(self, guard_id: str) -> List[Dict[str, Any]]:
        """Return province rates for a specific guard with default fallback."""
        guard = await self._get_tenant_or_404(guard_id, TenantType.GUARD, "Guard")
        await self.ensure_guard_rate_snapshot(guard_id, guard=guard)

        return await self._compose_rates_by_scope_priority([
            self._guard_scope(guard_id),
            self.SCOPE_GUARD_DEFAULT,
            self.SCOPE_GUARD_DEFAULT_LEGACY,
        ])

    async def save_guard_override_rates(
        self, guard_id: str, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert province override rates for a specific guard."""
        guard = await self._get_tenant_or_404(guard_id, TenantType.GUARD, "Guard")
        guard_name = self._extract_tenant_name(getattr(guard, "profile", None) or {}) or guard_id

        save_result = await self._save_scope_rates(
            scope=self._guard_scope(guard_id),
            payload=payload,
            current_user=current_user,
            entity_id=guard_id,
            entity_name=guard_name,
            force_create_missing=True,
        )

        return {
            "message": "Guard rates saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def sync_guard_override_with_defaults(
        self, guard_id: str, current_user=None
    ) -> Dict[str, Any]:
        """Sync a guard override matrix from current guard defaults."""
        guard = await self._get_tenant_or_404(guard_id, TenantType.GUARD, "Guard")
        guard_name = self._extract_tenant_name(getattr(guard, "profile", None) or {}) or guard_id
        defaults = await self.get_guard_rates()

        save_result = await self._save_scope_rates(
            scope=self._guard_scope(guard_id),
            payload=defaults,
            current_user=current_user,
            entity_id=guard_id,
            entity_name=guard_name,
            force_create_missing=True,
        )

        return {
            "message": "Guard rates synced from defaults",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    # ------------------------------------------------------------------
    # Provider default rates
    # ------------------------------------------------------------------

    async def get_provider_default_rates(self) -> List[Dict[str, Any]]:
        """Return one record per Canadian province for provider defaults."""
        return await self._compose_rates_by_scope_priority([
            self.SCOPE_PROVIDER_DEFAULT,
        ])

    async def save_provider_default_rates(
        self, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert provider-default rates for all provinces in the payload."""
        save_result = await self._save_scope_rates(
            scope=self.SCOPE_PROVIDER_DEFAULT,
            payload=payload,
            current_user=current_user,
            entity_id="provider-default-rates",
            entity_name="Service Provider Default Rates",
        )

        return {
            "message": "Provider default rates saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def get_provider_commission_rates(self) -> List[Dict[str, Any]]:
        """Return one record per Canadian province for provider commission defaults."""
        return await self._compose_rates_by_scope_priority([
            self.SCOPE_PROVIDER_COMMISSION_DEFAULT,
        ])

    async def save_provider_commission_rates(
        self, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert provider commission defaults by province."""
        save_result = await self._save_scope_rates(
            scope=self.SCOPE_PROVIDER_COMMISSION_DEFAULT,
            payload=payload,
            current_user=current_user,
            entity_id="provider-commission-default-rates",
            entity_name="Provider Commission Default Rates",
        )

        return {
            "message": "Provider commission defaults saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    # ------------------------------------------------------------------
    # Provider list
    # ------------------------------------------------------------------

    async def list_active_providers(self) -> List[Dict[str, Any]]:
        """Return id + name for every active service-provider tenant."""
        providers = await self._engine.find(
            db_tenant_model,
            (db_tenant_model.tenant_type == TenantType.SERVICE_PROVIDER)
            & (db_tenant_model.status == TenantStatus.ACTIVE),
        )
        seen_ids = set()
        result = []
        for p in providers:
            provider_id = str(p.id)
            if provider_id in seen_ids:
                continue

            profile = getattr(p, "profile", None) or {}
            name = self._extract_tenant_name(profile)
            if not name:
                continue

            seen_ids.add(provider_id)
            result.append({"id": provider_id, "name": name})

        result.sort(key=lambda item: item["name"].lower())
        return result

    # ------------------------------------------------------------------
    # Provider override rates
    # ------------------------------------------------------------------

    async def get_provider_rates(self, provider_id: str) -> List[Dict[str, Any]]:
        """Return province rates for a specific provider with default fallback."""
        provider = await self._get_tenant_or_404(provider_id, TenantType.SERVICE_PROVIDER, "Service provider")
        await self.ensure_provider_rate_snapshot(provider_id, provider=provider)

        return await self._compose_rates_by_scope_priority([
            self._provider_scope(provider_id),
            provider_id,
            self.SCOPE_PROVIDER_DEFAULT,
        ])

    async def save_provider_rates(
        self, provider_id: str, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert rates for a specific provider across all provinces."""
        tenant = await self._get_tenant_or_404(provider_id, TenantType.SERVICE_PROVIDER, "Service provider")
        provider_name = self._extract_tenant_name(getattr(tenant, "profile", None) or {}) or provider_id

        save_result = await self._save_scope_rates(
            scope=self._provider_scope(provider_id),
            payload=payload,
            current_user=current_user,
            entity_id=provider_id,
            entity_name=provider_name,
            force_create_missing=True,
        )

        return {
            "message": "Provider rates saved",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def sync_provider_override_with_defaults(
        self, provider_id: str, current_user=None
    ) -> Dict[str, Any]:
        """Sync a provider override matrix from current provider defaults."""
        tenant = await self._get_tenant_or_404(provider_id, TenantType.SERVICE_PROVIDER, "Service provider")
        provider_name = self._extract_tenant_name(getattr(tenant, "profile", None) or {}) or provider_id
        defaults = await self.get_provider_default_rates()

        save_result = await self._save_scope_rates(
            scope=self._provider_scope(provider_id),
            payload=defaults,
            current_user=current_user,
            entity_id=provider_id,
            entity_name=provider_name,
            force_create_missing=True,
        )

        return {
            "message": "Provider rates synced from defaults",
            "count": save_result["count"],
            "updated_count": save_result["updated_count"],
        }

    async def ensure_provider_rate_snapshot(self, provider_id: str, provider=None) -> Dict[str, Any]:
        """Copy provider default matrix to provider override scope if no provider snapshot exists."""
        if provider is None:
            provider = await self._get_tenant_or_404(provider_id, TenantType.SERVICE_PROVIDER, "Service provider")

        has_new_scope = await self._engine.find_one(BillingRate, BillingRate.scope == self._provider_scope(provider_id))
        has_legacy_scope = await self._engine.find_one(BillingRate, BillingRate.scope == provider_id)
        if has_new_scope or has_legacy_scope:
            return {"created": False, "count": 0}

        defaults = await self.get_provider_default_rates()
        save_result = await self._save_scope_rates(
            scope=self._provider_scope(provider_id),
            payload=defaults,
            current_user=None,
            entity_id=provider_id,
            entity_name=self._extract_tenant_name(getattr(provider, "profile", None) or {}) or provider_id,
            write_activity=False,
            force_create_missing=True,
        )
        return {"created": True, "count": save_result["updated_count"]}

    async def ensure_guard_rate_snapshot(self, guard_id: str, guard=None) -> Dict[str, Any]:
        """Copy guard default matrix to guard override scope if no guard snapshot exists."""
        if guard is None:
            guard = await self._get_tenant_or_404(guard_id, TenantType.GUARD, "Guard")

        has_scope = await self._engine.find_one(BillingRate, BillingRate.scope == self._guard_scope(guard_id))
        if has_scope:
            return {"created": False, "count": 0}

        defaults = await self.get_guard_rates()
        save_result = await self._save_scope_rates(
            scope=self._guard_scope(guard_id),
            payload=defaults,
            current_user=None,
            entity_id=guard_id,
            entity_name=self._extract_tenant_name(getattr(guard, "profile", None) or {}) or guard_id,
            write_activity=False,
            force_create_missing=True,
        )
        return {"created": True, "count": save_result["updated_count"]}

    async def ensure_tenant_rate_snapshot(self, tenant_id: str, tenant_type: TenantType):
        """Initialize per-entity override matrix from defaults at tenant creation time."""
        if tenant_type == TenantType.SERVICE_PROVIDER:
            await self.ensure_provider_rate_snapshot(tenant_id)
        elif tenant_type == TenantType.GUARD:
            await self.ensure_guard_rate_snapshot(tenant_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _write_activity_log(
        self,
        entity_id: str,
        entity_name: str,
        scope: str,
        region_code: str,
        city_code: str,
        prev_std: float,
        prev_wkd: float,
        prev_hol: float,
        new_std: float,
        new_wkd: float,
        new_hol: float,
        actor_id: str | None,
        actor: str | None,
        actor_role: str | None,
    ):
        try:
            await ActivityManager.get_instance().log_event(
                module="billing",
                entity_type="billing_rate",
                entity_id=entity_id,
                action="rate_changed",
                actor_id=actor_id,
                actor_username=actor,
                actor_role=actor_role,
                metadata={
                    "entity_name": entity_name,
                    "scope": scope,
                    "region_code": region_code,
                    "region_label": self._region_label(region_code),
                    "city_code": city_code,
                    "city_label": self._city_label(region_code, city_code),
                    "location_label": self._location_label(region_code, city_code),
                    "currency": "CAD",
                    "previous_rates": {
                        "standard_rate": prev_std,
                        "weekend_rate": prev_wkd,
                        "holiday_rate": prev_hol,
                    },
                    "new_rates": {
                        "standard_rate": new_std,
                        "weekend_rate": new_wkd,
                        "holiday_rate": new_hol,
                    },
                },
                severity="info",
            )
        except Exception:
            pass
