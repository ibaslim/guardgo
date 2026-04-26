import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from orion.api.server.config_manager.config_controller import config_controller
from routes.public_api_routes import public_routes


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(public_routes)
    return app


@pytest.mark.anyio
async def test_get_public_config_calls_config_controller(monkeypatch):
    class FakeConfig:
        async def get_system_info(self):
            return {"app_name": "GuardGo"}

    monkeypatch.setattr(config_controller, "getInstance", staticmethod(lambda: FakeConfig()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/public")

    assert response.status_code == 200
    assert response.json()["app_name"] == "GuardGo"


@pytest.mark.anyio
async def test_get_guard_metadata_has_expected_keys():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/public/guard-metadata")

    assert response.status_code == 200
    data = response.json()
    assert "countries" in data
    assert "identityDocumentTypes" in data
    assert "guardTypeOptions" in data


@pytest.mark.anyio
async def test_get_role_metadata_returns_role_groups():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/public/role-metadata")

    assert response.status_code == 200
    data = response.json()
    assert "platformRoles" in data
    assert "tenantSettingsRoles" in data


@pytest.mark.anyio
async def test_get_client_metadata_has_expected_keys():
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/public/client-metadata")

    assert response.status_code == 200
    data = response.json()
    assert "billingLocationOptions" in data
    assert "siteTypeOptions" in data
