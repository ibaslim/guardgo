from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from orion.api.interactive.signup_manager.model.signup_request_model import SignupRequest
from orion.api.interactive.signup_manager.signup_manager import SignupManager
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.constants import constant
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType
from orion.services.session_manager.session_manager import session_manager
from orion.services.mail_manager.mail_manager import mail_manager
from orion.helper_manager.env_handler import env_handler


class FakeEngine:
    def __init__(self, existing_user=None):
        self.existing_user = existing_user
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        return self.existing_user

    async def save(self, model):
        self.saved.append(model)


@pytest.mark.anyio
async def test_signup_user_maps_guard_role_and_tenant_type(monkeypatch):
    engine = FakeEngine(existing_user=None)
    captured = {}

    class FakeMongo:
        def get_engine(self):
            return engine

    class FakeTenantManager:
        async def create_tenant(self, tenant):
            captured["tenant"] = tenant
            return None

    class FakeSession:
        def generate_verification_token(self):
            return "verify-token-1"

    class FakeMail:
        async def send_verification_mail(self, **_kwargs):
            return None

    class FakeTemplate:
        def render(self, **_kwargs):
            return "<html>ok</html>"

    class FakeEnv:
        def env(self, key, default=None):
            if key == "PRODUCTION":
                return "0"
            if key == "APP_URL":
                return "http://app.local"
            return default

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))
    monkeypatch.setattr(TenantManager, "get_instance", staticmethod(lambda: FakeTenantManager()))
    monkeypatch.setattr(session_manager, "get_instance", staticmethod(lambda: FakeSession()))
    monkeypatch.setattr(mail_manager, "get_instance", staticmethod(lambda: FakeMail()))
    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))
    monkeypatch.setattr(constant, "mail_template", FakeTemplate())

    payload = SignupRequest(
        username="guarduser1",
        email="guard@company.com",
        password="StrongPass1!",
        tenant_type="guard",
    )
    result = await SignupManager.signup_user(payload)

    assert result["status"] == "pending"
    tenant = captured["tenant"]
    assert tenant.tenant_type == TenantType.GUARD
    assert tenant.status == TenantStatus.ONBOARDING
    user = engine.saved[0]
    assert user.role == user_role.GUARD_ADMIN


@pytest.mark.anyio
async def test_signup_user_rejects_invalid_username(monkeypatch):
    class FakeMongo:
        def get_engine(self):
            return FakeEngine()

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    payload = SignupRequest(
        username="bad",
        email="user@company.com",
        password="StrongPass1!",
        tenant_type="client",
    )
    with pytest.raises(HTTPException) as exc:
        await SignupManager.signup_user(payload)

    assert exc.value.status_code == 422


@pytest.mark.anyio
async def test_signup_user_rejects_duplicate_user(monkeypatch):
    existing = SimpleNamespace(id="u1")
    engine = FakeEngine(existing_user=existing)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    payload = SignupRequest(
        username="clientusr1",
        email="user@company.com",
        password="StrongPass1!",
        tenant_type="client",
    )
    with pytest.raises(HTTPException) as exc:
        await SignupManager.signup_user(payload)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Username or email already exists"
