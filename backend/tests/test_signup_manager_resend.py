from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.api.interactive.signup_manager.model.signup_request_model import SignupRequest
from orion.api.interactive.signup_manager.signup_manager import SignupManager
from orion.constants import constant
from orion.helper_manager.env_handler import env_handler
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.redis_manager.redis_controller import redis_controller
from orion.services.redis_manager.redis_enums import REDIS_COMMANDS
from orion.services.session_manager.session_manager import session_manager
from orion.services.mail_manager.mail_manager import mail_manager


class FakeEngine:
    def __init__(self):
        self.saved = []

    async def save(self, model):
        self.saved.append(model)


class FakeRedis:
    def __init__(self, current_value=0):
        self.current_value = current_value
        self.calls = []

    async def invoke_trigger(self, command, args):
        self.calls.append((command, args))
        if command == REDIS_COMMANDS.S_GET_INT:
            return self.current_value
        if command == REDIS_COMMANDS.S_SET_INT:
            return None
        return None


@pytest.mark.anyio
async def test_resend_verification_email_rejects_invalid_credentials(monkeypatch):
    engine = FakeEngine()

    class FakeMongo:
        def get_engine(self):
            return engine

    class FakeAuth:
        async def authenticate_user(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))
    monkeypatch.setattr(auth_manager, "get_instance", staticmethod(lambda: FakeAuth()))

    payload = SignupRequest(username="tenantusr1", email="tenant@company.com", password="StrongPass1!", tenant_type="client")
    with pytest.raises(HTTPException) as exc:
        await SignupManager.resend_verification_email(payload)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"


@pytest.mark.anyio
async def test_resend_verification_email_rejects_rate_limited(monkeypatch):
    engine = FakeEngine()
    user = SimpleNamespace(
        id="u1",
        username="tenantusr1",
        email="tenant@company.com",
        verification_token="old",
        verification_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    class FakeMongo:
        def get_engine(self):
            return engine

    class FakeAuth:
        async def authenticate_user(self, *_args, **_kwargs):
            return user

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))
    monkeypatch.setattr(auth_manager, "get_instance", staticmethod(lambda: FakeAuth()))
    monkeypatch.setattr(redis_controller, "getInstance", staticmethod(lambda: FakeRedis(current_value=1)))

    payload = SignupRequest(username="tenantusr1", email="tenant@company.com", password="StrongPass1!", tenant_type="client")
    with pytest.raises(HTTPException) as exc:
        await SignupManager.resend_verification_email(payload)

    assert exc.value.status_code == 429
    assert "Too many emails requested" in exc.value.detail


@pytest.mark.anyio
async def test_resend_verification_email_success_refreshes_token(monkeypatch):
    engine = FakeEngine()
    redis = FakeRedis(current_value=0)
    user = SimpleNamespace(
        id="u1",
        username="tenantusr1",
        email="tenant@company.com",
        verification_token="old",
        verification_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    class FakeMongo:
        def get_engine(self):
            return engine

    class FakeAuth:
        async def authenticate_user(self, *_args, **_kwargs):
            return user

    class FakeSession:
        def generate_verification_token(self):
            return "new-token-1"

    class FakeMail:
        async def send_verification_mail(self, **_kwargs):
            return None

    class FakeTemplate:
        def render(self, **_kwargs):
            return "<html>ok</html>"

    class FakeEnv:
        def env(self, key, default=None):
            if key == "APP_URL":
                return "http://app.local"
            return default

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))
    monkeypatch.setattr(auth_manager, "get_instance", staticmethod(lambda: FakeAuth()))
    monkeypatch.setattr(redis_controller, "getInstance", staticmethod(lambda: redis))
    monkeypatch.setattr(session_manager, "get_instance", staticmethod(lambda: FakeSession()))
    monkeypatch.setattr(mail_manager, "get_instance", staticmethod(lambda: FakeMail()))
    monkeypatch.setattr(constant, "mail_template", FakeTemplate())
    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))

    payload = SignupRequest(username="tenantusr1", email="tenant@company.com", password="StrongPass1!", tenant_type="client")
    result = await SignupManager.resend_verification_email(payload)

    assert result["message"] == "Verification email resent."
    assert user.verification_token == "new-token-1"
    assert len(engine.saved) == 1
    assert redis.calls[0][0] == REDIS_COMMANDS.S_GET_INT
    assert redis.calls[1][0] == REDIS_COMMANDS.S_SET_INT
