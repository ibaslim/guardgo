from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model


class FakeEngine:
    def __init__(self, tenant):
        self.tenant = tenant
        self.saved = []

    async def find_one(self, _model, *_args, **_kwargs):
        return self.tenant

    async def save(self, model):
        self.saved.append(model)


@pytest.mark.anyio
async def test_set_tenant_status_returns_idempotent_when_same_status():
    tenant = db_tenant_model(tenant_type=TenantType.GUARD, profile={}, status=TenantStatus.ACTIVE)
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)

    result = await manager.set_tenant_status(str(tenant.id), TenantStatus.ACTIVE, current_user=SimpleNamespace(username="admin"))

    assert result["message"] == "No change - tenant already in target status"
    assert result["status"] == TenantStatus.ACTIVE


@pytest.mark.anyio
async def test_set_tenant_status_activate_sets_verified_and_date():
    tenant = db_tenant_model(tenant_type=TenantType.GUARD, profile={}, status=TenantStatus.PENDING_ACTIVATION, verified=False)
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

    result = await manager.set_tenant_status(
        str(tenant.id),
        TenantStatus.ACTIVE,
        current_user=SimpleNamespace(username="admin", role=user_role.ADMIN),
    )

    assert result["status"] == TenantStatus.ACTIVE.value
    assert tenant.verified is True
    assert tenant.verified_date is not None


@pytest.mark.anyio
async def test_set_tenant_status_pending_activation_resets_approval_state():
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ACTIVE,
        approvals_required=1,
        approval_actors=["a", "b"],
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

    result = await manager.set_tenant_status(str(tenant.id), TenantStatus.PENDING_ACTIVATION)

    assert result["status"] == TenantStatus.PENDING_ACTIVATION.value
    assert tenant.approvals_required >= 2
    assert tenant.approval_actors == []


@pytest.mark.anyio
async def test_set_tenant_status_raises_404_when_tenant_missing():
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(None)

    with pytest.raises(HTTPException) as exc:
        await manager.set_tenant_status("507f1f77bcf86cd799439011", TenantStatus.ACTIVE)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Tenant not found"
