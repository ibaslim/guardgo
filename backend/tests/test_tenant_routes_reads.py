from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model
from routes.tenant_routes import tenant_routes


def _app(role, current_user=None):
    app = FastAPI()
    app.include_router(tenant_routes)
    resolved_user = current_user or SimpleNamespace(
        username="tester",
        role=role,
        tenant_uuid="507f1f77bcf86cd799439011",
    )

    async def _current_user():
        return resolved_user

    async def _current_role():
        return role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


class FakeEngine:
    def __init__(self, tenant):
        self.tenant = tenant

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_tenant_model:
            return self.tenant
        return None


@pytest.mark.anyio
async def test_get_tenant_returns_current_tenant(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={"business_name": "Acme Guard"},
        status=TenantStatus.PENDING_ACTIVATION,
        approvals_required=2,
        approval_actors=["admin1"],
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(tenant)
    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: manager))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN, SimpleNamespace(
        username="guardadmin1", role=user_role.GUARD_ADMIN, tenant_uuid=str(tenant.id)
    ))), base_url="http://test") as client:
        response = await client.get("/api/tenant")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(tenant.id)
    assert data["status"] == TenantStatus.PENDING_ACTIVATION.value
    assert data["approvals_done"] == 1


@pytest.mark.anyio
async def test_get_tenant_returns_404_when_missing(monkeypatch):
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(None)
    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: manager))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenant")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


@pytest.mark.anyio
async def test_get_tenants_datatable_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_tenants_datatable(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.COMPLIANCE_ADMIN)), base_url="http://test") as client:
        response = await client.get(
            "/api/tenants/datatable?page=2&rows=5&tenant_type=guard&tenant_status=pending_activation&keyword=acme&sort_by=name&sort_order=asc"
        )

    assert response.status_code == 200
    assert captured == {
        "page": 2,
        "rows": 5,
        "tenant_type": "guard",
        "tenant_status": "pending_activation",
        "keyword": "acme",
        "sort_by": "name",
        "sort_order": "asc",
    }


@pytest.mark.anyio
async def test_get_tenants_datatable_forbidden_for_tenant_admin(monkeypatch):
    class FakeManager:
        async def get_tenants_datatable(self, **kwargs):
            return {"items": []}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenants/datatable")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_verify_alias_calls_approve_activation(monkeypatch):
    calls = []

    class FakeManager:
        async def approve_tenant_activation(self, tenant_id: str, current_user=None):
            calls.append((tenant_id, getattr(current_user, "username", None)))
            return {"id": tenant_id, "status": "active", "message": "Tenant activated"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.patch("/api/tenants/507f1f77bcf86cd799439011/verify")

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert calls == [("507f1f77bcf86cd799439011", "tester")]


@pytest.mark.anyio
async def test_get_all_tenants_admin_only(monkeypatch):
    class FakeManager:
        async def get_all_tenant(self):
            return [{"id": "t1"}, {"id": "t2"}]

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenants")

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.anyio
async def test_get_all_tenants_forbidden_for_client_admin(monkeypatch):
    class FakeManager:
        async def get_all_tenant(self):
            return []

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenants")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_get_tenant_by_id_forwards_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_tenant_by_id(self, tenant_id: str):
            captured["tenant_id"] = tenant_id
            return {"id": tenant_id, "status": "active"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.COMPLIANCE_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenants/507f1f77bcf86cd799439011")

    assert response.status_code == 200
    assert response.json()["id"] == "507f1f77bcf86cd799439011"
    assert captured["tenant_id"] == "507f1f77bcf86cd799439011"


@pytest.mark.anyio
async def test_get_tenant_by_id_forbidden_for_guard_admin(monkeypatch):
    class FakeManager:
        async def get_tenant_by_id(self, tenant_id: str):
            return {"id": tenant_id}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/tenants/507f1f77bcf86cd799439011")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_tenant_forwards_payload_and_user(monkeypatch):
    captured = {}

    class FakeManager:
        async def upsert_tenant(self, data, current_user, is_update: bool):
            captured["tenant_type"] = data.tenant_type
            captured["status"] = data.status
            captured["current_user"] = current_user.username
            captured["is_update"] = is_update
            return {"status": "created", "tenant_type": data.tenant_type}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/tenant",
            json={
                "tenant_type": "client",
                "profile": {"company_name": "Acme Client"},
                "subscription": False,
                "verified": False,
                "user_quota": 2,
                "status": "onboarding",
                "approvals_required": 2,
                "approval_actors": [],
                "licenses": [],
                "iocs": [],
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "created"
    assert captured == {
        "tenant_type": TenantType.CLIENT,
        "status": TenantStatus.ONBOARDING,
        "current_user": "tester",
        "is_update": False,
    }


@pytest.mark.anyio
async def test_update_tenant_forwards_payload_and_marks_update(monkeypatch):
    captured = {}
    current_user = SimpleNamespace(
        username="clientadmin1",
        role=user_role.CLIENT_ADMIN,
        tenant_uuid="507f1f77bcf86cd799439011",
    )

    class FakeManager:
        async def upsert_tenant(self, data, current_user, is_update: bool):
            captured["tenant_type"] = data.tenant_type
            captured["status"] = data.status
            captured["current_user"] = current_user.username
            captured["is_update"] = is_update
            return {"status": "updated", "tenant_type": data.tenant_type}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(
        transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN, current_user)),
        base_url="http://test",
    ) as client:
        response = await client.put(
            "/api/tenant",
            json={
                "tenant_type": "client",
                "profile": {"company_name": "Acme Client"},
                "subscription": False,
                "verified": False,
                "user_quota": 2,
                "status": "pending_activation",
                "approvals_required": 2,
                "approval_actors": ["admin1"],
                "licenses": [],
                "iocs": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "updated"
    assert captured == {
        "tenant_type": TenantType.CLIENT,
        "status": TenantStatus.PENDING_ACTIVATION,
        "current_user": "clientadmin1",
        "is_update": True,
    }


@pytest.mark.anyio
async def test_get_activity_logs_forwards_filters(monkeypatch):
    captured = {}

    class FakeActivityManager:
        async def list_events(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    from routes import tenant_routes as tenant_routes_module

    monkeypatch.setattr(
        tenant_routes_module.ActivityManager,
        "get_instance",
        staticmethod(lambda: FakeActivityManager()),
    )

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.get(
            "/api/activity?module=tenant&entity_type=tenant&entity_id=t1&action=approve&actor_username=tester&page=3&rows=15"
        )

    assert response.status_code == 200
    assert captured == {
        "module": "tenant",
        "entity_type": "tenant",
        "entity_id": "t1",
        "action": "approve",
        "actor_username": "tester",
        "page": 3,
        "rows": 15,
    }


@pytest.mark.anyio
async def test_get_activity_logs_forbidden_for_client_admin(monkeypatch):
    class FakeActivityManager:
        async def list_events(self, **kwargs):
            return {"items": []}

    from routes import tenant_routes as tenant_routes_module

    monkeypatch.setattr(
        tenant_routes_module.ActivityManager,
        "get_instance",
        staticmethod(lambda: FakeActivityManager()),
    )

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/activity")

    assert response.status_code == 403


@pytest.mark.anyio
async def test_get_current_user_info_forwards_to_account_manager(monkeypatch):
    class FakeManager:
        async def get_node(self, current_user):
            assert current_user.username == "tester"
            return {"username": current_user.username, "role": str(current_user.role)}

    monkeypatch.setattr(AccountManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["username"] == "tester"
