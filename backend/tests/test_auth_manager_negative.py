from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import LicenseName, UserStatus, db_user_account, user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantStatus, TenantType


class FakeEngine:
    def __init__(self, user):
        self.user = user
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_user_account:
            return self.user
        if model is db_tenant_model:
            return db_tenant_model(tenant_type=TenantType.CLIENT, profile={}, status=TenantStatus.ONBOARDING)
        return None

    async def save(self, model):
        self.saved.append(model)


def _build_user(**overrides):
    base = dict(
        username="tenantusr1",
        email="tenant@example.com",
        password="StrongPass1!",
        role=user_role.CLIENT_ADMIN,
        status=UserStatus.INACTIVE,
        tenant_uuid="507f1f77bcf86cd799439011",
        verification_token="token-1",
        verification_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        invite_pending=False,
        licenses=[LicenseName.MAINTAINER],
    )
    base.update(overrides)
    return db_user_account(**base)


@pytest.mark.anyio
async def test_get_password_reset_context_rejects_expired_token(monkeypatch):
    user = _build_user(verification_expiry=datetime.now(timezone.utc) - timedelta(minutes=1))
    engine = FakeEngine(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.get_password_reset_context("token-1")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Verification link expired"


@pytest.mark.anyio
async def test_get_invite_context_rejects_non_invite_tokens(monkeypatch):
    async def _ctx(_token):
        return {"invite_pending": False}

    monkeypatch.setattr(auth_manager, "get_password_reset_context", staticmethod(_ctx))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.get_invite_context("token-1")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid invite link"


@pytest.mark.anyio
async def test_update_password_rejects_same_as_old_password(monkeypatch):
    user = _build_user(password="StrongPass1!")
    engine = FakeEngine(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.update_password("token-1", "StrongPass1!")

    assert exc.value.status_code == 400
    assert exc.value.detail == "New password must be different from the old one."


@pytest.mark.anyio
async def test_activate_invited_user_rejects_non_invite_link(monkeypatch):
    user = _build_user(invite_pending=False)
    engine = FakeEngine(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.activate_invited_user(
            token="token-1",
            password="StrongPass1!",
            username="inviteusr1",
            full_name="Invite User",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid invite link"


@pytest.mark.anyio
async def test_verify_user_rejects_invalid_token(monkeypatch):
    engine = FakeEngine(user=None)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.verify_user("missing-token")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Invalid token"


@pytest.mark.anyio
async def test_verify_user_rejects_expired_token(monkeypatch):
    user = _build_user(verification_token="expired-token", verification_expiry=datetime.now(timezone.utc) - timedelta(minutes=1))
    engine = FakeEngine(user=user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.verify_user("expired-token")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Verification link expired"


@pytest.mark.anyio
async def test_activate_invited_user_rejects_missing_full_name(monkeypatch):
    user = _build_user(invite_pending=True)
    engine = FakeEngine(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.activate_invited_user(
            token="token-1",
            password="StrongPass1!",
            username="inviteusr1",
            full_name="",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Full name is required for invite activation"


@pytest.mark.anyio
async def test_activate_invited_user_rejects_invalid_username_format(monkeypatch):
    user = _build_user(invite_pending=True)
    engine = FakeEngine(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.activate_invited_user(
            token="token-1",
            password="StrongPass1!",
            username="1badname",
            full_name="Invite User",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Username must be 8-20 characters, start with letter"


@pytest.mark.anyio
async def test_activate_invited_user_rejects_duplicate_username(monkeypatch):
    user = _build_user(invite_pending=True)
    duplicate = _build_user(username="dupuser99", email="dup@example.com", verification_token="other-token")

    class FakeEngineDuplicate(FakeEngine):
        def __init__(self, user, duplicate_user):
            super().__init__(user)
            self.duplicate_user = duplicate_user
            self.calls = 0

        async def find_one(self, model, *_args, **_kwargs):
            if model is not db_user_account:
                return None
            self.calls += 1
            if self.calls == 1:
                return self.user
            return self.duplicate_user

    engine = FakeEngineDuplicate(user, duplicate)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.activate_invited_user(
            token="token-1",
            password="StrongPass1!",
            username="dupuser99",
            full_name="Invite User",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Username already exists"


@pytest.mark.anyio
async def test_activate_invited_user_success_updates_account_fields(monkeypatch):
    user = _build_user(invite_pending=True, status=UserStatus.INACTIVE)

    class FakeEngineInviteSuccess(FakeEngine):
        def __init__(self, user):
            super().__init__(user)
            self.calls = 0

        async def find_one(self, model, *_args, **_kwargs):
            if model is not db_user_account:
                return None
            self.calls += 1
            if self.calls == 1:
                return self.user
            return None  # no duplicate username

    engine = FakeEngineInviteSuccess(user)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    result = await auth_manager.activate_invited_user(
        token="token-1",
        password="NewStrongPass1!",
        username="inviteusr1",
        full_name="Invite User",
    )

    assert result["message"] == "Account activated successfully."
    assert user.status == UserStatus.ACTIVE
    assert user.invite_pending is False
    assert user.username == "inviteusr1"
    assert user.full_name == "Invite User"
    assert user.account_verify_at is not None
    assert user.verification_token is None
    assert user.verification_expiry is None
    assert len(engine.saved) == 1


@pytest.mark.anyio
async def test_login_rejects_unverified_email(monkeypatch):
    user = _build_user(
        status=UserStatus.ACTIVE,
        account_verify_at=None,
        invite_pending=False,
        verification_token=None,
    )

    class FakeManager:
        async def authenticate_user(self, _mail, _password):
            return user

    class FakeMongo:
        def get_engine(self):
            return FakeEngine(user)

    monkeypatch.setattr(auth_manager, "get_instance", staticmethod(lambda: FakeManager()))
    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.login("tenant@example.com", "StrongPass1!")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Email verification pending"


@pytest.mark.anyio
async def test_login_rejects_pending_invite_activation(monkeypatch):
    user = _build_user(
        status=UserStatus.ACTIVE,
        account_verify_at=None,
        invite_pending=True,
        verification_token="invite-token-1",
    )

    class FakeManager:
        async def authenticate_user(self, _mail, _password):
            return user

    class FakeMongo:
        def get_engine(self):
            return FakeEngine(user)

    monkeypatch.setattr(auth_manager, "get_instance", staticmethod(lambda: FakeManager()))
    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    with pytest.raises(HTTPException) as exc:
        await auth_manager.login("tenant@example.com", "StrongPass1!")

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invite activation pending"
