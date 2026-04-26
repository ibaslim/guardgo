from types import SimpleNamespace

import pytest

from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model


class FakeEngine:
    def __init__(self, tenant: db_tenant_model):
        self.tenant = tenant
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        return self.tenant if model is db_tenant_model else None

    async def save(self, model):
        self.saved.append(model)


@pytest.mark.anyio
async def test_approve_tenant_activation_requires_two_distinct_approvals():
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.PENDING_ACTIVATION,
        approvals_required=2,
        approval_actors=[],
    )
    engine = FakeEngine(tenant)
    manager = object.__new__(TenantManager)
    manager._engine = engine

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

    approver_1 = SimpleNamespace(username="compliance1", role=user_role.COMPLIANCE_ADMIN)
    approver_2 = SimpleNamespace(username="compliance2", role=user_role.COMPLIANCE_ADMIN)

    first = await manager.approve_tenant_activation(str(tenant.id), current_user=approver_1)
    assert first["status"] == TenantStatus.PENDING_ACTIVATION
    assert first["approvals_done"] == 1
    assert tenant.status == TenantStatus.PENDING_ACTIVATION

    second = await manager.approve_tenant_activation(str(tenant.id), current_user=approver_2)
    assert second["status"] == TenantStatus.ACTIVE
    assert second["approvals_done"] == 2
    assert tenant.status == TenantStatus.ACTIVE
    assert tenant.verified is True


@pytest.mark.anyio
async def test_duplicate_approver_does_not_increment_approval_count():
    tenant = db_tenant_model(
        tenant_type=TenantType.SERVICE_PROVIDER,
        profile={},
        status=TenantStatus.PENDING_ACTIVATION,
        approvals_required=2,
        approval_actors=["compliance1"],
    )
    engine = FakeEngine(tenant)
    manager = object.__new__(TenantManager)
    manager._engine = engine

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change
    approver = SimpleNamespace(username="compliance1", role=user_role.COMPLIANCE_ADMIN)

    result = await manager.approve_tenant_activation(str(tenant.id), current_user=approver)
    assert result["message"] == "Approval already recorded for this user"
    assert result["approvals_done"] == 1
    assert tenant.approval_actors == ["compliance1"]


@pytest.mark.anyio
async def test_approve_tenant_reactivates_inactive_tenant_via_set_status(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.INACTIVE,
        approvals_required=2,
        approval_actors=[],
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)

    async def _set_status(tenant_id, target_status, current_user=None):
        assert tenant_id == str(tenant.id)
        assert target_status == TenantStatus.ACTIVE
        return {"id": tenant_id, "status": "active"}

    monkeypatch.setattr(manager, "set_tenant_status", _set_status)
    result = await manager.approve_tenant_activation(str(tenant.id), current_user=SimpleNamespace(username="admin1", role=user_role.ADMIN))

    assert result["status"] == "active"


@pytest.mark.anyio
async def test_approve_tenant_reactivates_banned_tenant_via_set_status(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.SERVICE_PROVIDER,
        profile={},
        status=TenantStatus.BANNED,
        approvals_required=2,
        approval_actors=[],
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)

    async def _set_status(tenant_id, target_status, current_user=None):
        assert tenant_id == str(tenant.id)
        assert target_status == TenantStatus.ACTIVE
        return {"id": tenant_id, "status": "active"}

    monkeypatch.setattr(manager, "set_tenant_status", _set_status)
    result = await manager.approve_tenant_activation(str(tenant.id), current_user=SimpleNamespace(username="admin1", role=user_role.ADMIN))

    assert result["status"] == "active"
