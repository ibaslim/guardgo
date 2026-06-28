from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantPayload, TenantStatus, TenantType, db_tenant_model


class FakeEngine:
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.saved = []

    async def find_one(self, _model, *_args, **_kwargs):
        return self.tenant

    async def save(self, model):
        self.saved.append(model)


def _payload(tenant_type=TenantType.GUARD):
    return TenantPayload(
        tenant_type=tenant_type,
        profile=None,
        subscription=False,
        verified=False,
        user_quota=2,
        status=TenantStatus.ONBOARDING,
        approvals_required=2,
        approval_actors=[],
        licenses=[],
        iocs=[],
    )


@pytest.mark.anyio
async def test_upsert_tenant_rejects_missing_tenant_association():
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine()

    with pytest.raises(HTTPException) as exc:
        await manager.upsert_tenant(_payload(), current_user=SimpleNamespace(role=user_role.GUARD_ADMIN), is_update=True)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid company association"


@pytest.mark.anyio
async def test_upsert_tenant_rejects_not_found_tenant():
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant=None)
    current_user = SimpleNamespace(tenant_uuid="507f1f77bcf86cd799439011", role=user_role.GUARD_ADMIN)

    with pytest.raises(HTTPException) as exc:
        await manager.upsert_tenant(_payload(), current_user=current_user, is_update=True)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Tenant not found"


@pytest.mark.anyio
async def test_upsert_tenant_rejects_role_mismatch():
    tenant = db_tenant_model(tenant_type=TenantType.GUARD, profile={}, status=TenantStatus.ONBOARDING)
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant=tenant)
    current_user = SimpleNamespace(tenant_uuid=str(tenant.id), role=user_role.CLIENT_ADMIN, username="clientadmin1")

    with pytest.raises(HTTPException) as exc:
        await manager.upsert_tenant(_payload(tenant_type=TenantType.GUARD), current_user=current_user, is_update=True)

    assert exc.value.status_code == 401
    assert exc.value.detail == "You are not allowed to update this tenant"


def test_validate_and_normalize_provider_operating_regions_requires_city_coordinates():
    profile = {
        "operating_regions": [
            {
                "country": "CA",
                "region_code": "ON",
                "city_entries": [
                    {
                        "city_code": "TORONTO",
                        "coverage_radius_km": 15,
                    }
                ],
            }
        ]
    }

    with pytest.raises(HTTPException) as exc:
        TenantManager._validate_and_normalize_provider_operating_regions(profile)

    assert exc.value.status_code == 400
    assert "Latitude and longitude are required" in str(exc.value.detail)


@pytest.mark.anyio
async def test_create_tenant_seeds_default_guard_leave_quota(monkeypatch):
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine()
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ONBOARDING,
        approvals_required=2,
        approval_actors=[],
        licenses=[],
        iocs=[],
    )

    class FakeKeyManager:
        async def create_dek(self, _tenant_id):
            return Fernet.generate_key()

    class FakeBillingManager:
        async def ensure_tenant_rate_snapshot(self, *_args, **_kwargs):
            return None

    seeded = {}

    class FakeLeaveManager:
        async def _ensure_guard_leave_policy(self, *, guard_tenant, **_kwargs):
            seeded["guard_id"] = str(guard_tenant.id)
            return SimpleNamespace(id="policy-1")

        async def _ensure_guard_leave_balance(self, *, guard_tenant, policy, **_kwargs):
            seeded["balance_guard_id"] = str(guard_tenant.id)
            seeded["policy_id"] = str(policy.id)
            return SimpleNamespace(id="balance-1")

    monkeypatch.setattr(
        "orion.api.interactive.tenant_manager.tenant_manager.KeyManager.get_instance",
        staticmethod(lambda: FakeKeyManager()),
    )
    monkeypatch.setattr(
        "orion.api.interactive.billing_manager.billing_manager.BillingManager.get_instance",
        staticmethod(lambda: FakeBillingManager()),
    )
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestShiftManager.get_instance",
        staticmethod(lambda: FakeLeaveManager()),
    )

    await manager.create_tenant(tenant)

    assert manager._engine.saved[0] is tenant
    assert seeded == {
        "guard_id": str(tenant.id),
        "balance_guard_id": str(tenant.id),
        "policy_id": "policy-1",
    }
