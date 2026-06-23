from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from orion.api.interactive.tenant_manager.models.service_provider_guard_models import (
    ServiceProviderGuardOperationalCoveragePayload,
    ServiceProviderGuardStatusRequestPayload,
)
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
async def test_sp_activate_request_directly_approves_pending_guard(monkeypatch):
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={
            "operational_region_code": "ON",
            "operational_city_code": "TORONTO",
            "max_travel_radius_km": 15,
            "weekly_availability": {
                "Monday": [{"start": "09:00", "end": "17:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
        },
        status=TenantStatus.PENDING_ACTIVATION,
        approvals_required=2,
        approval_actors=[],
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(guard)

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

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

    assert result["message"] == "Tenant activated"
    assert result["requested_action"] == "activate"
    assert result["status"] == "active"
    assert result["approvals_required"] == 1
    assert result["approvals_done"] == 1
    assert guard.status == TenantStatus.ACTIVE
    assert len(manager._engine.saved) == 1


@pytest.mark.anyio
async def test_sp_activate_request_requires_managed_fields_before_approval(monkeypatch):
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.PENDING_ACTIVATION,
        approvals_required=2,
        approval_actors=[],
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(guard)

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

    from orion.api.interactive.activity_manager.activity_manager import ActivityManager
    monkeypatch.setattr(ActivityManager, "get_instance", staticmethod(lambda: FakeActivityManager()))

    with pytest.raises(HTTPException) as exc:
        await manager.request_guard_status_change(
            str(guard.id),
            ServiceProviderGuardStatusRequestPayload(action="activate", reason=None),
            current_user=SimpleNamespace(
                username="spadmin1",
                role=user_role.SP_ADMIN,
                tenant_uuid="507f1f77bcf86cd799439011",
            ),
        )

    assert exc.value.status_code == 400
    assert "configured by the owning service provider before approval" in str(exc.value.detail)


@pytest.mark.anyio
async def test_sp_deactivate_request_directly_deactivates_guard(monkeypatch):
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ACTIVE,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id="507f1f77bcf86cd799439011",
    )
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(guard)

    async def _noop_post_change(*_args, **_kwargs):
        return None

    manager._post_status_change = _noop_post_change

    from orion.api.interactive.activity_manager.activity_manager import ActivityManager
    monkeypatch.setattr(ActivityManager, "get_instance", staticmethod(lambda: FakeActivityManager()))

    result = await manager.request_guard_status_change(
        str(guard.id),
        ServiceProviderGuardStatusRequestPayload(action="deactivate", reason="Offboarded"),
        current_user=SimpleNamespace(
            username="spadmin1",
            role=user_role.SP_ADMIN,
            tenant_uuid="507f1f77bcf86cd799439011",
        ),
    )

    assert result["message"] == "Tenant status updated"
    assert result["requested_action"] == "deactivate"
    assert result["status"] == "inactive"
    assert result["reason"] == "Offboarded"
    assert guard.status == TenantStatus.INACTIVE


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


@pytest.mark.anyio
async def test_sp_updates_guard_operational_coverage_with_provider_region(monkeypatch):
    provider = db_tenant_model(
        tenant_type=TenantType.SERVICE_PROVIDER,
        profile={
            "operating_regions": [
                {
                    "region_code": "ON",
                    "region_label": "Ontario",
                    "city_codes": ["TORONTO"],
                    "city_entries": [
                        {
                            "city_code": "TORONTO",
                            "city": "Toronto",
                            "coverage_radius_km": 25,
                            "latitude": 43.6532,
                            "longitude": -79.3832,
                        }
                    ],
                    "coverage_radius_km": 25,
                    "latitude": 43.6532,
                    "longitude": -79.3832,
                }
            ]
        },
        status=TenantStatus.ACTIVE,
    )
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={},
        status=TenantStatus.ACTIVE,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id=str(provider.id),
    )
    saved: list[db_tenant_model] = []

    async def _save(model):
        saved.append(model)

    manager = object.__new__(TenantManager)
    manager._engine = SimpleNamespace(save=_save)
    manager._get_guard_tenant = lambda _guard_id: None
    manager._get_tenant = lambda _tenant_id: None

    async def _fake_get_guard_tenant(_guard_id):
        return guard

    async def _fake_get_tenant(tenant_id):
        return provider if str(tenant_id) == str(provider.id) else None

    async def _fake_serialize_tenant(tenant):
        return {
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "status": "active",
            "profile": tenant.profile,
        }

    manager._get_guard_tenant = _fake_get_guard_tenant
    manager._get_tenant = _fake_get_tenant
    manager._serialize_tenant = _fake_serialize_tenant

    from orion.api.interactive.activity_manager.activity_manager import ActivityManager
    monkeypatch.setattr(ActivityManager, "get_instance", staticmethod(lambda: FakeActivityManager()))

    result = await manager.update_service_provider_guard_operational_coverage(
        str(guard.id),
        ServiceProviderGuardOperationalCoveragePayload(
            operational_region_code="ON",
            operational_city_code="TORONTO",
            max_travel_radius_km=20,
            weekly_availability={
                "Monday": [{"start": "09:00", "end": "17:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
        ),
        current_user=SimpleNamespace(
            username="spadmin1",
            role=user_role.SP_ADMIN,
            tenant_uuid=str(provider.id),
        ),
    )

    assert result["message"] == "Guard operational coverage and weekly availability updated"
    assert guard.profile["operational_region_code"] == "ON"
    assert guard.profile["operational_city_code"] == "TORONTO"
    assert guard.profile["max_travel_radius_km"] == 20
    assert guard.profile["weekly_availability"]["Monday"][0]["start"] == "09:00"
    assert len(saved) == 1


@pytest.mark.anyio
async def test_sp_guard_operational_coverage_round_trips_on_detail_fetch(monkeypatch):
    provider = db_tenant_model(
        tenant_type=TenantType.SERVICE_PROVIDER,
        profile={
            "operating_regions": [
                {
                    "region_code": "AB",
                    "region_label": "Alberta",
                    "city_codes": ["AIRDRIE"],
                    "city_entries": [
                        {
                            "city_code": "AIRDRIE",
                            "city": "Airdrie",
                            "coverage_radius_km": 10,
                            "latitude": 51.2917,
                            "longitude": -114.0144,
                        }
                    ],
                    "coverage_radius_km": 10,
                }
            ]
        },
        status=TenantStatus.ACTIVE,
    )
    guard = db_tenant_model(
        tenant_type=TenantType.GUARD,
        profile={"full_name": "Local Test Guard"},
        status=TenantStatus.ACTIVE,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id=str(provider.id),
    )

    async def _save(_model):
        return None

    async def _fake_get_guard_tenant(_guard_id):
        return guard

    async def _fake_get_tenant(tenant_id):
        return provider if str(tenant_id) == str(provider.id) else None

    async def _fake_serialize_tenant(tenant):
        return {
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "status": "active",
            "profile": tenant.profile,
        }

    manager = object.__new__(TenantManager)
    manager._engine = SimpleNamespace(save=_save)
    manager._get_guard_tenant = _fake_get_guard_tenant
    manager._get_tenant = _fake_get_tenant
    manager._serialize_tenant = _fake_serialize_tenant

    from orion.api.interactive.activity_manager.activity_manager import ActivityManager
    monkeypatch.setattr(ActivityManager, "get_instance", staticmethod(lambda: FakeActivityManager()))

    current_user = SimpleNamespace(
        username="spadmin1",
        role=user_role.SP_ADMIN,
        tenant_uuid=str(provider.id),
    )

    await manager.update_service_provider_guard_operational_coverage(
        str(guard.id),
        ServiceProviderGuardOperationalCoveragePayload(
            operational_region_code="AB",
            operational_city_code="AIRDRIE",
            max_travel_radius_km=8,
            weekly_availability={
                "Monday": [{"start": "10:00", "end": "18:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
        ),
        current_user=current_user,
    )

    detail = await manager.get_service_provider_guard(str(guard.id), current_user)

    assert detail["profile"]["operational_region_code"] == "AB"
    assert detail["profile"]["operational_city_code"] == "AIRDRIE"
    assert detail["profile"]["max_travel_radius_km"] == 8
    assert detail["profile"]["weekly_availability"]["Monday"][0]["start"] == "10:00"


async def _raise_mail_error(*_args, **_kwargs):
    raise RuntimeError("smtp unavailable")
