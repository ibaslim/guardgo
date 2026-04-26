from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.request_matching_routes import request_matching_routes


def _app(role=user_role.CLIENT_ADMIN):
    app = FastAPI()
    app.include_router(request_matching_routes)

    async def _current_user():
        return SimpleNamespace(username="clientadmin1", role=role)

    async def _current_role():
        return role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


@pytest.mark.anyio
async def test_preview_request_matching_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def preview_matches(self, payload):
            captured["target_type"] = payload.target_type
            captured["site_province"] = payload.site_address.province
            captured["max_results"] = payload.max_results
            return {"summary": {"eligible": 1}, "results": []}

    monkeypatch.setattr(RequestMatchingManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.post(
            "/api/request-matching/preview",
            json={
                "target_type": "guard",
                "site_address": {"province": "ON", "city": "Toronto", "country": "CA"},
                "max_results": 10,
            },
        )

    assert response.status_code == 200
    assert captured == {"target_type": "guard", "site_province": "ON", "max_results": 10}
    assert response.json()["summary"]["eligible"] == 1
