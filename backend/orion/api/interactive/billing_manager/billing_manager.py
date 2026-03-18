import threading
from datetime import datetime
from typing import List, Dict, Any

from bson import ObjectId
from fastapi import HTTPException
from starlette import status

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_billing_model import (
    BillingRate,
    BillingRateAudit,
)
from orion.services.mongo_manager.shared_model.db_auth_models import user_role
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
        actor = getattr(current_user, "username", None)
        actor_role = str(getattr(current_user, "role", None))

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

            # Write audit record
            await self._write_audit(
                scope="guard",
                region_code=code,
                prev_std=existing.standard_rate if existing else 0.0,
                prev_wkd=existing.weekend_rate if existing else 0.0,
                prev_hol=existing.holiday_rate if existing else 0.0,
                new_std=std,
                new_wkd=wkd,
                new_hol=hol,
                actor=actor,
                actor_role=actor_role,
            )

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

        return {"message": "Guard rates saved", "count": len(payload)}

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
        actor = getattr(current_user, "username", None)
        actor_role = str(getattr(current_user, "role", None))

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

            await self._write_audit(
                scope=provider_id,
                region_code=code,
                prev_std=existing.standard_rate if existing else 0.0,
                prev_wkd=existing.weekend_rate if existing else 0.0,
                prev_hol=existing.holiday_rate if existing else 0.0,
                new_std=std,
                new_wkd=wkd,
                new_hol=hol,
                actor=actor,
                actor_role=actor_role,
            )

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

        return {"message": "Provider rates saved", "count": len(payload)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _write_audit(
        self,
        scope: str,
        region_code: str,
        prev_std: float,
        prev_wkd: float,
        prev_hol: float,
        new_std: float,
        new_wkd: float,
        new_hol: float,
        actor: str | None,
        actor_role: str | None,
    ):
        try:
            audit = BillingRateAudit(
                scope=scope,
                region_code=region_code,
                previous_standard_rate=prev_std,
                previous_weekend_rate=prev_wkd,
                previous_holiday_rate=prev_hol,
                new_standard_rate=new_std,
                new_weekend_rate=new_wkd,
                new_holiday_rate=new_hol,
                actor=actor,
                actor_role=actor_role,
                created_at=datetime.utcnow(),
            )
            await self._engine.save(audit)
        except Exception:
            pass
