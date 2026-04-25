from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from orion.api.interactive.tenant_manager.models.service_provider_guard_models import ServiceProviderGuardStatusRequestPayload
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_auth_models import user_role, db_user_account
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    db_tenant_model,
    TenantType,
    TenantStatus,
    GuardOwnershipType,
    GuardStatusChangeRequest,
)


class FakeEngine:
    def __init__(self, guard):
        self.guard = guard
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_tenant_model:
            return self.guard
        if model is GuardStatusChangeRequest:
            return None
        return None

    async def save(self, model):
        self.saved.append(model)

    async def delete(self, model):
        return None


class FakeActivityManager:
    async def log_event(self, **_kwargs):
        return None


class FakeInviteEngine:
    def __init__(self):
        self.provider = db_tenant_model(
            tenant_type=TenantType.SERVICE_PROVIDER,
            profile={"name": "SP One"},
            status=TenantStatus.ACTIVE,
        )
        self.saved = []
        self.deleted = []

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_tenant_model:
            return self.provider
        if model is db_user_account:
            return None
        return None

    async def save(self, model):
        self.saved.append(model)

    async def delete(self, model):
        self.deleted.append(model)


@pytest.mark.anyio
async def test_sp_deactivate_request_requires_reason():
    with pytest.raises(ValidationError) as exc:
        ServiceProviderGuardStatusRequestPayload(action="deactivate", reason=None)

    assert "reason is required when action is 'deactivate'" in str(exc.value)


@pytest.mark.anyio
async def test_sp_activate_request_creates_pending_request(monkeypatch):
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.INACTIVE,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(guard)

    from orion.api.interactive.activity_manager.activity_manager import ActivityManager
    monkeypatch.setattr(ActivityManager, "get_instance", staticmethod(lambda: FakeActivityManager()))

    result = await manager.request_guard_status_change(
        str(guard.id),
        ServiceProviderGuardStatusRequestPayload(action="activate", reason=None),
        current_user=SimpleNamespace(
            username="spadmin1",
            role=user_role.SP_ADMIN,
            tenant_uuid="507f1f77bcf86cd799439011",
        ),
    )

    assert result["message"] == "Status request submitted"
    assert result["requested_action"] == "activate"
    assert len(manager._engine.saved) == 1


@pytest.mark.anyio
async def test_sp_invite_rolls_back_when_mail_fails(monkeypatch):
    manager = object.__new__(TenantManager)
    engine = FakeInviteEngine()
    manager._engine = engine

    async def _fake_create_tenant(tenant):
        return tenant

    manager.create_tenant = _fake_create_tenant

    from orion.helper_manager.env_handler import env_handler
    monkeypatch.setattr(
        env_handler,
        "get_instance",
        staticmethod(lambda: SimpleNamespace(env=lambda key, default=None: "http://localhost:4200" if key == "APP_URL" else default)),
    )

    from orion.services.mail_manager.mail_manager import mail_manager
    monkeypatch.setattr(
        mail_manager,
        "get_instance",
        staticmethod(lambda: SimpleNamespace(send_verification_mail=_raise_mail_error)),
    )
    from orion.services.session_manager.session_manager import session_manager
    monkeypatch.setattr(
        session_manager,
        "get_instance",
        staticmethod(lambda: SimpleNamespace(generate_verification_token=lambda: "invite-token")),
    )

    with pytest.raises(HTTPException) as exc:
        await manager.invite_guard_for_service_provider(
            SimpleNamespace(email="new.guard@example.com"),
            current_user=SimpleNamespace(
                username="spadmin1",
                role=user_role.SP_ADMIN,
                tenant_uuid=str(engine.provider.id),
            ),
        )

    assert exc.value.status_code == 503
    assert "Failed to send invite email" in exc.value.detail
    assert len(engine.saved) == 1
    assert len(engine.deleted) == 2


async def _raise_mail_error(*_args, **_kwargs):
    raise RuntimeError("smtp unavailable")
