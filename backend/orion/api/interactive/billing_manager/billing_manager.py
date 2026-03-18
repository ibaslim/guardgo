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
from configs.metadata_constants import CANADIAN_PROVINCE_OPTIONS


# Use all Canadian provinces and territories
CANADIAN_PROVINCES = CANADIAN_PROVINCE_OPTIONS


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

    # ------------------------------------------------------------------
    # Guard rates – scope="guard"
    # ------------------------------------------------------------------

    async def get_guard_rates(self) -> List[Dict[str, Any]]:
        """Return one record per Canadian province for the 'guard' scope."""
        existing = await self._engine.find(
            BillingRate, BillingRate.scope == "guard"
        )
        by_code = {r.region_code: r for r in existing}

        result = []
        for prov in CANADIAN_PROVINCES:
            code = prov["value"]
            rec = by_code.get(code)
            result.append({
                "region_code": code,
                "region_label": prov["label"],
                "standard_rate": rec.standard_rate if rec else 0.0,
                "weekend_rate": rec.weekend_rate if rec else 0.0,
                "holiday_rate": rec.holiday_rate if rec else 0.0,
                "currency": "CAD",
            })
        return result

    async def save_guard_rates(
        self, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert guard-scope rates for all provinces in the payload."""
        valid_codes = {p["value"] for p in CANADIAN_PROVINCES}
        now = datetime.utcnow()
        actor_id = str(getattr(current_user, "id", "") or "") or None
        actor = getattr(current_user, "username", None)
        actor_role = str(getattr(current_user, "role", None))
        updated_count = 0

        for row in payload:
            code = row.get("region_code", "")
            if code not in valid_codes:
                continue

            std = round(float(row.get("standard_rate", 0)), 2)
            wkd = round(float(row.get("weekend_rate", 0)), 2)
            hol = round(float(row.get("holiday_rate", 0)), 2)

            existing = await self._engine.find_one(
                BillingRate,
                (BillingRate.scope == "guard") & (BillingRate.region_code == code),
            )

            prev_std = existing.standard_rate if existing else 0.0
            prev_wkd = existing.weekend_rate if existing else 0.0
            prev_hol = existing.holiday_rate if existing else 0.0

            if not self._has_rate_change(prev_std, prev_wkd, prev_hol, std, wkd, hol):
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
                    scope="guard",
                    region_code=code,
                    standard_rate=std,
                    weekend_rate=wkd,
                    holiday_rate=hol,
                    currency="CAD",
                    updated_at=now,
                    updated_by=actor,
                ))

            await self._write_activity_log(
                entity_id="guard-default-rates",
                entity_name="Guard Default Rates",
                scope="guard",
                region_code=code,
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
            "message": "Guard rates saved",
            "count": len(payload),
            "updated_count": updated_count,
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
    # Provider rates – scope=<provider_id>
    # ------------------------------------------------------------------

    async def get_provider_rates(self, provider_id: str) -> List[Dict[str, Any]]:
        """Return province rates for a specific provider."""
        existing = await self._engine.find(
            BillingRate, BillingRate.scope == provider_id
        )
        by_code = {r.region_code: r for r in existing}

        result = []
        for prov in CANADIAN_PROVINCES:
            code = prov["value"]
            rec = by_code.get(code)
            result.append({
                "region_code": code,
                "region_label": prov["label"],
                "standard_rate": rec.standard_rate if rec else 0.0,
                "weekend_rate": rec.weekend_rate if rec else 0.0,
                "holiday_rate": rec.holiday_rate if rec else 0.0,
                "currency": "CAD",
            })
        return result

    async def save_provider_rates(
        self, provider_id: str, payload: List[Dict[str, Any]], current_user=None
    ) -> Dict[str, Any]:
        """Upsert rates for a specific provider across all provinces."""
        # Validate provider exists and is a service provider
        try:
            tenant = await self._engine.find_one(
                db_tenant_model, db_tenant_model.id == ObjectId(provider_id)
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid provider id")
        if not tenant or tenant.tenant_type != TenantType.SERVICE_PROVIDER:
            raise HTTPException(status_code=404, detail="Service provider not found")

        valid_codes = {p["value"] for p in CANADIAN_PROVINCES}
        now = datetime.utcnow()
        actor_id = str(getattr(current_user, "id", "") or "") or None
        actor = getattr(current_user, "username", None)
        actor_role = str(getattr(current_user, "role", None))
        provider_name = self._extract_tenant_name(getattr(tenant, "profile", None) or {}) or provider_id
        updated_count = 0

        for row in payload:
            code = row.get("region_code", "")
            if code not in valid_codes:
                continue

            std = round(float(row.get("standard_rate", 0)), 2)
            wkd = round(float(row.get("weekend_rate", 0)), 2)
            hol = round(float(row.get("holiday_rate", 0)), 2)

            existing = await self._engine.find_one(
                BillingRate,
                (BillingRate.scope == provider_id) & (BillingRate.region_code == code),
            )

            prev_std = existing.standard_rate if existing else 0.0
            prev_wkd = existing.weekend_rate if existing else 0.0
            prev_hol = existing.holiday_rate if existing else 0.0

            if not self._has_rate_change(prev_std, prev_wkd, prev_hol, std, wkd, hol):
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
                    scope=provider_id,
                    region_code=code,
                    standard_rate=std,
                    weekend_rate=wkd,
                    holiday_rate=hol,
                    currency="CAD",
                    updated_at=now,
                    updated_by=actor,
                ))

            await self._write_activity_log(
                entity_id=provider_id,
                entity_name=provider_name,
                scope=provider_id,
                region_code=code,
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
            "message": "Provider rates saved",
            "count": len(payload),
            "updated_count": updated_count,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _write_activity_log(
        self,
        entity_id: str,
        entity_name: str,
        scope: str,
        region_code: str,
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
