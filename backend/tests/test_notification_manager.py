from types import SimpleNamespace

import pytest

from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role


class _FakeNotificationEngine:
    def __init__(self, users):
        self._users = users

    async def find(self, *_args, **_kwargs):
        return list(self._users)


@pytest.mark.anyio
async def test_active_tenant_admin_user_ids_accept_enum_status_values():
    manager = object.__new__(NotificationManager)
    manager._engine = _FakeNotificationEngine([
        SimpleNamespace(id="guard-user-1", role=user_role.GUARD_ADMIN, status=UserStatus.ACTIVE),
        SimpleNamespace(id="guard-user-2", role=user_role.GUARD_ADMIN, status=UserStatus.INACTIVE),
        SimpleNamespace(id="member-user-1", role=user_role.ADMIN, status=UserStatus.ACTIVE),
    ])

    result = await manager._active_tenant_admin_user_ids("guard-tenant-1")

    assert result == ["guard-user-1"]


@pytest.mark.anyio
async def test_create_for_tenant_admin_users_falls_back_to_active_tenant_users():
    manager = object.__new__(NotificationManager)
    manager._engine = _FakeNotificationEngine([])

    async def _active_admin_ids(_tenant_id):
        return []

    async def _active_user_ids(_tenant_id, *, admin_only=False):
        assert admin_only is False
        return ["guard-user-1"]

    captured = {}

    async def _create_for_users(**kwargs):
        captured.update(kwargs)
        return len(kwargs.get("recipient_user_ids") or [])

    manager._active_tenant_admin_user_ids = _active_admin_ids
    manager._active_tenant_user_ids = _active_user_ids
    manager.create_for_users = _create_for_users

    saved_count = await manager.create_for_tenant_admin_users(
        tenant_id="guard-tenant-1",
        title="New request offer",
        message="Corporate Campus Patrol is available for review.",
        category="info",
        source_module="requests",
        action_url="/dashboard/requests?tab=requests&request=req-1",
        action_label="Review offer",
        metadata={"request_id": "req-1"},
    )

    assert saved_count == 1
    assert captured["recipient_user_ids"] == ["guard-user-1"]
    assert captured["recipient_tenant_id"] == "guard-tenant-1"


@pytest.mark.anyio
async def test_create_for_platform_admin_users_targets_active_platform_roles():
    manager = object.__new__(NotificationManager)
    manager._engine = _FakeNotificationEngine([
        SimpleNamespace(id="admin-1", role=user_role.ADMIN, status=UserStatus.ACTIVE),
        SimpleNamespace(id="ops-1", role=user_role.OPS_ADMIN, status=UserStatus.ACTIVE),
        SimpleNamespace(id="client-1", role=user_role.CLIENT_ADMIN, status=UserStatus.ACTIVE),
        SimpleNamespace(id="support-1", role=user_role.SUPPORT_ADMIN, status=UserStatus.INACTIVE),
    ])

    captured = {}

    async def _create_for_users(**kwargs):
        captured.update(kwargs)
        return len(kwargs.get("recipient_user_ids") or [])

    manager.create_for_users = _create_for_users

    saved_count = await manager.create_for_platform_admin_users(
        title="Late arrival escalation",
        message="A guard missed the grace period.",
        category="warning",
        source_module="requests",
        action_url="/dashboard/requests?tab=shifts&slot=slot-1",
        action_label="Open shift slot",
        metadata={"slot_id": "slot-1"},
    )

    assert saved_count == 2
    assert captured["recipient_user_ids"] == ["admin-1", "ops-1"]
    assert captured["recipient_tenant_id"] is None
