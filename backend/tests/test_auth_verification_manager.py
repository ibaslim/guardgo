from datetime import datetime, timedelta, timezone

import pytest

from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.constants.constant import CONSTANTS
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import LicenseName, UserStatus, db_user_account, user_role
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model


class FakeEngine:
    def __init__(self, user: db_user_account, tenant: db_tenant_model | None):
        self.user = user
        self.tenant = tenant
        self.saved = []

    async def find_one(self, model, *_args, **_kwargs):
        if model is db_user_account:
            return self.user
        if model is db_tenant_model:
            return self.tenant
        return None

    async def save(self, model):
        self.saved.append(model)


@pytest.mark.anyio
async def test_verify_user_auto_activates_client_tenant(monkeypatch):
    tenant = db_tenant_model(
        tenant_type=TenantType.CLIENT,
        profile={},
        status=TenantStatus.ONBOARDING,
        verified=False,
    )
    user = db_user_account(
        username="clientusr1",
        email="client@example.com",
        password=CONSTANTS.S_AUTH_PWD_CONTEXT.hash("StrongPass1!"),
        role=user_role.CLIENT_ADMIN,
        status=UserStatus.INACTIVE,
        tenant_uuid=str(tenant.id),
        verification_token="token-123",
        verification_expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        licenses=[LicenseName.MAINTAINER],
    )
    engine = FakeEngine(user=user, tenant=tenant)

    class FakeMongo:
        def get_engine(self):
            return engine

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    response = await auth_manager.verify_user("token-123")

    assert response["message"] == "Email verified successfully. Your account is active."
    assert user.status == UserStatus.ACTIVE
    assert user.verification_token is None
    assert tenant.status == TenantStatus.ACTIVE
    assert tenant.verified is True
