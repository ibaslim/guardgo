from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.billing_manager.billing_manager import BillingManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.billing_routes import billing_routes


def _app(role=user_role.ADMIN):
    app = FastAPI()
    app.include_router(billing_routes)
    current_user = SimpleNamespace(username="platformadmin", role=role)

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
async def test_get_billing_metadata_calls_manager(monkeypatch):
    class FakeManager:
        async def get_billing_location_metadata(self):
            return {"provinces": ["ON"], "cities": {"ON": ["Toronto"]}}

    monkeypatch.setattr(BillingManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/billing/metadata")

    assert response.status_code == 200
    assert response.json()["provinces"] == ["ON"]


@pytest.mark.anyio
async def test_save_guard_rates_forwards_payload_and_current_user(monkeypatch):
    captured = {}

    class FakeManager:
        async def save_guard_rates(self, payload, current_user):
            captured["payload"] = payload
            captured["user"] = current_user.username
            return {"updated": len(payload)}

    monkeypatch.setattr(BillingManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.put("/api/billing/guards", json=[{"province": "ON", "city": "Toronto", "rate": 25.0}])

    assert response.status_code == 200
    assert response.json()["updated"] == 1
    assert captured["user"] == "platformadmin"


@pytest.mark.anyio
async def test_sync_provider_defaults_forwards_id_and_user(monkeypatch):
    captured = {}

    class FakeManager:
        async def sync_provider_override_with_defaults(self, provider_id, current_user):
            captured["provider_id"] = provider_id
            captured["user"] = current_user.username
            return {"provider_id": provider_id, "synced": True}

    monkeypatch.setattr(BillingManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post("/api/billing/providers/provider-1/sync-defaults")

    assert response.status_code == 200
    assert captured == {"provider_id": "provider-1", "user": "platformadmin"}


@pytest.mark.anyio
async def test_get_provider_default_rates_calls_manager(monkeypatch):
    class FakeManager:
        async def get_provider_default_rates(self):
            return [{"province": "ON", "city": "Toronto", "rate": 30.0}]

    monkeypatch.setattr(BillingManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/billing/providers/defaults")

    assert response.status_code == 200
    assert response.json()[0]["province"] == "ON"
