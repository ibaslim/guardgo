from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import GuardOwnershipType, TenantStatus, TenantType, db_tenant_model
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


@pytest.mark.anyio
async def test_service_provider_owned_guard_uses_single_approval_on_first_update(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ONBOARDING,
        approvals_required=2,
        approval_actors=["someone"],
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
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
            json=_tenant_payload(TenantType.GUARD, TenantStatus.PENDING_ACTIVATION),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TenantStatus.PENDING_ACTIVATION.value
    assert data["approvals_required"] == 1
    assert tenant.status == TenantStatus.PENDING_ACTIVATION
    assert tenant.approvals_required == 1
    assert tenant.approval_actors == []


@pytest.mark.anyio
async def test_service_provider_owned_guard_cannot_self_update_operational_coverage(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={
            "operational_region_code": "ON",
            "operational_city_code": "TORONTO",
            "max_travel_radius_km": 15,
        },
        status=TenantStatus.ACTIVE,
        approvals_required=1,
        approval_actors=[],
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
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

    payload = _tenant_payload(TenantType.GUARD, TenantStatus.ACTIVE)
    payload["profile"] = {
        "operational_region_code": "BC",
        "operational_city_code": "VANCOUVER",
        "max_travel_radius_km": 30,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/tenant", json=payload)

    assert response.status_code == 403
    assert "can only be updated by the owning service provider" in response.json()["detail"]
    assert tenant.profile["operational_region_code"] == "ON"
    assert tenant.profile["operational_city_code"] == "TORONTO"
    assert tenant.profile["max_travel_radius_km"] == 15


@pytest.mark.anyio
async def test_service_provider_owned_guard_cannot_self_update_weekly_availability(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={
            "operational_region_code": "ON",
            "operational_city_code": "TORONTO",
            "max_travel_radius_km": 15,
            "weekly_availability": {
                "Monday": [{"start": "09:00", "end": "17:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
        },
        status=TenantStatus.ACTIVE,
        approvals_required=1,
        approval_actors=[],
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
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

    payload = _tenant_payload(TenantType.GUARD, TenantStatus.ACTIVE)
    payload["profile"] = {
        "weekly_availability": {
            "Monday": [{"start": "12:00", "end": "20:00"}],
            "Tuesday": [],
            "Wednesday": [],
            "Thursday": [],
            "Friday": [],
            "Saturday": [],
            "Sunday": [],
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put("/api/tenant", json=payload)

    assert response.status_code == 403
    assert "weekly availability" in response.json()["detail"]
    assert tenant.profile["weekly_availability"]["Monday"][0]["start"] == "09:00"
