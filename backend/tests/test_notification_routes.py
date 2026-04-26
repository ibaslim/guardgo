from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.notification_routes import notification_routes


def _app():
    app = FastAPI()
    app.include_router(notification_routes)

    async def _current_user():
        return SimpleNamespace(username="tenantadmin", role=user_role.CLIENT_ADMIN)

    async def _current_role():
        return user_role.CLIENT_ADMIN

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


@pytest.mark.anyio
async def test_get_latest_notifications_forwards_limit(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_latest(self, current_user, limit):
            captured["user"] = current_user.username
            captured["limit"] = limit
            return {"items": [], "unread_count": 0}

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/notifications/latest?limit=7")

    assert response.status_code == 200
    assert captured == {"user": "tenantadmin", "limit": 7}


@pytest.mark.anyio
async def test_mark_notification_read_forwards_notification_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def mark_read(self, notification_id, current_user):
            captured["notification_id"] = notification_id
            captured["user"] = current_user.username
            return {"id": notification_id, "read": True}

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.patch("/api/notifications/notif-10/read")

    assert response.status_code == 200
    assert captured == {"notification_id": "notif-10", "user": "tenantadmin"}


@pytest.mark.anyio
async def test_get_unread_notification_count_calls_manager(monkeypatch):
    class FakeManager:
        async def get_unread_count(self, current_user):
            assert current_user.username == "tenantadmin"
            return {"unread_count": 3}

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/notifications/unread-count")

    assert response.status_code == 200
    assert response.json()["unread_count"] == 3


@pytest.mark.anyio
async def test_mark_all_notifications_read_calls_manager(monkeypatch):
    class FakeManager:
        async def mark_all_read(self, current_user):
            assert current_user.username == "tenantadmin"
            return {"updated": 4, "unread_count": 0}

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.patch("/api/notifications/read-all")

    assert response.status_code == 200
    assert response.json()["unread_count"] == 0
