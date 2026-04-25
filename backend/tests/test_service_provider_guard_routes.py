from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.tenant_routes import tenant_routes


def _app(role=user_role.SP_ADMIN):
    app = FastAPI()
    app.include_router(tenant_routes)
    current_user = SimpleNamespace(
        username="spadmin1",
        role=role,
        tenant_uuid="507f1f77bcf86cd799439011",
    )

    async def _current_user():
        return current_user

    async def _current_role():
        return role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


@pytest.mark.anyio
async def test_sp_invite_guard_route_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def invite_guard_for_service_provider(self, data, current_user):
            captured["email"] = data.email
            captured["user"] = current_user.username
            return {"message": "Guard invite sent"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.SP_ADMIN)), base_url="http://test") as client:
        response = await client.post("/api/sp/guards/invite", json={"email": "guard1@example.com"})

    assert response.status_code == 201
    assert response.json()["message"] == "Guard invite sent"
    assert captured == {"email": "guard1@example.com", "user": "spadmin1"}


@pytest.mark.anyio
async def test_sp_list_guards_route_forwards_pagination(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_service_provider_guards(self, current_user, page, rows):
            captured["user"] = current_user.username
            captured["page"] = page
            captured["rows"] = rows
            return {"items": [], "pagination": {"page": page, "rows": rows}}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.SP_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/sp/guards?page=2&rows=10")

    assert response.status_code == 200
    assert captured == {"user": "spadmin1", "page": 2, "rows": 10}


@pytest.mark.anyio
async def test_sp_status_request_route_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def request_guard_status_change(self, guard_tenant_id, payload, current_user):
            captured["guard_tenant_id"] = guard_tenant_id
            captured["action"] = payload.action.value
            captured["reason"] = payload.reason
            captured["user"] = current_user.username
            return {"message": "Status request submitted"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.SP_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/sp/guards/507f1f77bcf86cd799439012/status-request",
            json={"action": "deactivate", "reason": "Repeated no-shows"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Status request submitted"
    assert captured["action"] == "deactivate"


@pytest.mark.anyio
async def test_sp_status_request_route_requires_reason_for_deactivate(monkeypatch):
    class FakeManager:
        async def request_guard_status_change(self, guard_tenant_id, payload, current_user):
            return {"message": "Status request submitted"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.SP_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/sp/guards/507f1f77bcf86cd799439012/status-request",
            json={"action": "deactivate"},
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_admin_approve_status_request_route_forwards_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def approve_guard_status_request(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["comment"] = payload.comment
            captured["user"] = current_user.username
            return {"message": "Status request approved"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/guard-status-requests/507f1f77bcf86cd799439013/approve",
            json={"comment": "Approved"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Status request approved"
    assert captured["request_id"] == "507f1f77bcf86cd799439013"
