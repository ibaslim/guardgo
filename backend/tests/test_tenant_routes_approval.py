from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.tenant_routes import tenant_routes


def _app(role):
    app = FastAPI()
    app.include_router(tenant_routes)
    current_user = SimpleNamespace(username="tester", role=role, tenant_uuid="507f1f77bcf86cd799439011")
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
async def test_approve_route_allowed_for_compliance_admin(monkeypatch):
    class FakeManager:
        async def approve_tenant_activation(self, tenant_id: str, current_user=None):
            return {"id": tenant_id, "status": "active", "message": "Tenant activated"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.COMPLIANCE_ADMIN)), base_url="http://test") as client:
        response = await client.patch("/api/tenants/507f1f77bcf86cd799439011/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "active"


@pytest.mark.anyio
async def test_approve_route_forbidden_for_client_admin(monkeypatch):
    class FakeManager:
        async def approve_tenant_activation(self, tenant_id: str, current_user=None):
            return {"id": tenant_id, "status": "active"}

    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.patch("/api/tenants/507f1f77bcf86cd799439011/approve")

    assert response.status_code == 403
