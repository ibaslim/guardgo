from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model
from routes.tenant_routes import tenant_routes


class FakeEngine:
    def __init__(self, tenant: db_tenant_model):
        self.tenant = tenant
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_tenant_model:
            return self.tenant
        return None

    async def save(self, model):
        self.saved.append(model)


def _build_app(current_user: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.include_router(tenant_routes)
    async def _current_user():
        return current_user

    async def _current_role():
        return current_user.role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


def _tenant_payload(tenant_type: TenantType, status: TenantStatus) -> dict:
    return {
        "tenant_type": tenant_type.value,
        "profile": None,
        "subscription": False,
        "verified": False,
        "user_quota": 2,
        "status": status.value,
        "approvals_required": 2,
        "approval_actors": [],
        "licenses": [],
        "iocs": [],
    }


@pytest.mark.anyio
async def test_guard_cannot_force_active_status_during_onboarding_update(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ONBOARDING,
        approvals_required=2,
        approval_actors=[],
    )
    fake_engine = FakeEngine(tenant)
    manager = object.__new__(TenantManager)
    manager._engine = fake_engine

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change
    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: manager))

    current_user = SimpleNamespace(
        tenant_uuid=str(tenant.id),
        role=user_role.GUARD_ADMIN,
        username="guardadmin1",
    )
    app = _build_app(current_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/tenant",
            json=_tenant_payload(TenantType.GUARD, TenantStatus.ACTIVE),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TenantStatus.PENDING_ACTIVATION.value
    assert tenant.status == TenantStatus.PENDING_ACTIVATION


@pytest.mark.anyio
async def test_client_becomes_active_without_approval_on_first_update(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.CLIENT,
        profile={},
        status=TenantStatus.ONBOARDING,
        approvals_required=2,
        approval_actors=["someone"],
    )
    fake_engine = FakeEngine(tenant)
    manager = object.__new__(TenantManager)
    manager._engine = fake_engine

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change
    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: manager))

    current_user = SimpleNamespace(
        tenant_uuid=str(tenant.id),
        role=user_role.CLIENT_ADMIN,
        username="clientadmin1",
    )
    app = _build_app(current_user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            "/api/tenant",
            json=_tenant_payload(TenantType.CLIENT, TenantStatus.PENDING_ACTIVATION),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TenantStatus.ACTIVE.value
    assert tenant.status == TenantStatus.ACTIVE
    assert tenant.verified is True
    assert tenant.approval_actors == []
