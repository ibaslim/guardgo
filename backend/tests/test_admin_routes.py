from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.api.server.config_manager.config_controller import config_controller
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.admin_routes import admin_routes


def _app(role=user_role.ADMIN):
    app = FastAPI()
    app.include_router(admin_routes)

    async def _current_user():
        return SimpleNamespace(username="admin1", role=role)

    async def _current_role():
        return role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


@pytest.mark.anyio
async def test_block_row_action_rejects_delete():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/admin/api/db_system_model/row-action?name=delete")

    assert response.status_code == 403
    assert response.json()["detail"] == "Deletion of system settings is not allowed"


@pytest.mark.anyio
async def test_custom_edit_api_returns_redirect_and_calls_auth_manager(monkeypatch):
    captured = {}

    async def _edit(user_id, _request):
        captured["id"] = user_id

    monkeypatch.setattr(auth_manager, "edit_userStatus_and_sendMail_from_admin", staticmethod(_edit))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test", follow_redirects=False) as client:
        response = await client.post("/admin/api/db_user_account/edit/507f1f77bcf86cd799439011")

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/db_user_account/list"
    assert captured["id"] == "507f1f77bcf86cd799439011"


@pytest.mark.anyio
async def test_update_public_config_forwards_payload(monkeypatch):
    captured = {}

    class FakeConfig:
        async def update_public_config(self, param):
            captured["settings"] = param.settings
            return {"settings": param.settings}

    monkeypatch.setattr(config_controller, "getInstance", staticmethod(lambda: FakeConfig()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/public/update", json={"settings": {"app_name": "GuardGo"}})

    assert response.status_code == 200
    assert response.json()["settings"]["app_name"] == "GuardGo"
    assert captured["settings"]["app_name"] == "GuardGo"


@pytest.mark.anyio
async def test_list_platform_users_calls_account_manager(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_platform_admin_users(self, current_user):
            captured["user"] = current_user.username
            return [{"id": "u1", "email": "ops@example.com"}]

    monkeypatch.setattr(AccountManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/admin/platform-users")

    assert response.status_code == 200
    assert captured["user"] == "admin1"
    assert response.json()[0]["id"] == "u1"


@pytest.mark.anyio
async def test_get_platform_roles_returns_value_and_label():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/admin/platform-roles")

    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert all("value" in item and "label" in item for item in items)


@pytest.mark.anyio
async def test_resend_platform_invite_forwards_user_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def resend_platform_admin_invite(self, user_id, current_user):
            captured["user_id"] = user_id
            captured["actor"] = current_user.username
            return {"id": user_id, "message": "Invite resent"}

    monkeypatch.setattr(AccountManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/admin/platform-users/u-22/resend-invite")

    assert response.status_code == 200
    assert captured == {"user_id": "u-22", "actor": "admin1"}
