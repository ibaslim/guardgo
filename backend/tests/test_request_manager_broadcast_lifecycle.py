from datetime import datetime
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord,
    ClientRequestSoftDeletePayload,
    RequestAssignmentRecord,
    RequestLockReason,
    RequestStaffingStatus,
    RequestStatus,
)


class FakeEngine:
    def __init__(self):
        self.saved = []

    async def save(self, model):
        self.saved.append(model)
        return model


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query):
        return _FakeCursor(self._docs)


class _FakeListJobsEngine(FakeEngine):
    def __init__(self, assignment_docs, request_docs):
        super().__init__()
        self._assignment_docs = assignment_docs
        self._request_docs = request_docs

    def get_collection(self, model):
        if model is RequestAssignmentRecord:
            return _FakeCollection(self._assignment_docs)
        if model is ClientRequestRecord:
            return _FakeCollection(self._request_docs)
        raise AssertionError(f"Unexpected collection request: {model}")


def _make_request_record(**overrides):
    base = {
        "id": ObjectId(),
        "client_tenant_id": "tenant-1",
        "created_by_user_id": "creator-1",
        "created_by_username": "creator",
        "title": "Request",
        "fulfillment_mode": "individual_only",
        "target_type": "guard",
        "requested_guard_type": None,
        "site_snapshot": {},
        "special_instructions": None,
        "requested_start_at": None,
        "requested_end_at": None,
        "request_expires_at": None,
        "published_at": None,
        "published_by_user_id": None,
        "published_by_username": None,
        "request_revision": 1,
        "request_status": RequestStatus.SUBMITTED,
        "staffing_status": RequestStaffingStatus.OPEN,
        "lock_reason": None,
        "expired_at": None,
        "active_wave_id": None,
        "last_wave_number": 0,
        "match_summary": {},
        "matched_candidates": [],
        "cancelled_at": None,
        "closed_at": None,
        "guards_required": 2,
        "accepted_slots": 0,
        "open_slots": 2,
        "created_at": None,
        "updated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.anyio
async def test_sync_request_runtime_state_preserves_pending_review():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._get_assignments_for_request = lambda _request_id: []
    manager._close_open_offers_for_request = lambda *_args, **_kwargs: 0

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.PENDING_REVIEW,
        lock_reason=RequestLockReason.REVIEW_PENDING,
    )

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.PENDING_REVIEW
    assert updated.lock_reason == RequestLockReason.REVIEW_PENDING


@pytest.mark.anyio
async def test_sync_request_runtime_state_preserves_review_returned_without_active_wave():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.REVIEW_RETURNED,
        lock_reason=None,
        active_wave_id=None,
    )

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.REVIEW_RETURNED
    assert updated.lock_reason is None


@pytest.mark.anyio
async def test_sync_request_runtime_state_reopens_review_returned_request_once_new_wave_is_active():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.REVIEW_RETURNED,
        lock_reason=None,
        active_wave_id="wave-1",
    )

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.OPEN
    assert updated.lock_reason is None


@pytest.mark.anyio
async def test_soft_delete_request_marks_terminal_request_deleted(monkeypatch):
    manager = object.__new__(RequestManager)
    engine = FakeEngine()
    manager._engine = engine
    manager._role_value = lambda _user: "admin"
    manager._is_platform_write_role = lambda role: role == "admin"
    manager._sync_request_runtime_state = lambda record: record
    manager._write_activity = lambda *args, **kwargs: None

    record = _make_request_record(
        request_status=RequestStatus.CLOSED,
        title="Downtown patrol",
        client_tenant_id="tenant-1",
        deleted_at=None,
        deleted_by_user_id=None,
        deleted_by_username=None,
        deleted_reason=None,
    )

    async def _get_request(_request_id):
        return record

    async def _sync_request(record_to_sync):
        return record_to_sync

    async def _write_activity(*_args, **_kwargs):
        return None

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return None

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )

    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request
    manager._write_activity = _write_activity

    current_user = SimpleNamespace(id="user-1", username="admin-user", role="admin")
    response = await manager.soft_delete_request(
        "507f1f77bcf86cd799439011",
        ClientRequestSoftDeletePayload(reason="Duplicate closed request"),
        current_user,
    )

    assert response["message"] == "Client request removed from the dashboard"
    assert record.deleted_reason == "Duplicate closed request"
    assert record.deleted_by_user_id == "user-1"
    assert record.deleted_by_username == "admin-user"
    assert isinstance(record.deleted_at, datetime)
    assert engine.saved[-1] is record


@pytest.mark.anyio
async def test_soft_delete_request_rejects_live_request(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda _user: "admin"
    manager._is_platform_write_role = lambda role: role == "admin"

    record = _make_request_record(
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.OPEN,
        title="Open request",
        client_tenant_id="tenant-1",
        deleted_at=None,
        deleted_by_user_id=None,
        deleted_by_username=None,
        deleted_reason=None,
    )

    async def _get_request(_request_id):
        return record

    async def _sync_request(record_to_sync):
        return record_to_sync

    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request

    current_user = SimpleNamespace(id="user-1", username="admin-user", role="admin")
    with pytest.raises(HTTPException) as exc:
        await manager.soft_delete_request(
            "507f1f77bcf86cd799439011",
            ClientRequestSoftDeletePayload(reason="Trying to remove a live request"),
            current_user,
        )

    assert exc.value.status_code == 400
    assert "Only draft, cancelled, or closed requests" in exc.value.detail


@pytest.mark.anyio
async def test_list_jobs_platform_role_does_not_require_session_tenant():
    assignment_id = ObjectId()
    request_id = ObjectId()
    manager = object.__new__(RequestManager)
    manager._engine = _FakeListJobsEngine(
        assignment_docs=[
            {
                "_id": assignment_id,
                "request_id": str(request_id),
                "client_tenant_id": "client-1",
                "assignee_tenant_id": "guard-1",
                "assignee_tenant_type": "guard",
                "assignment_status": "offered",
                "candidate_snapshot": {"candidate_name": "Guard One"},
                "assigned_by_user_id": "user-1",
                "assigned_by_username": "admin",
                "created_at": None,
                "updated_at": None,
            }
        ],
        request_docs=[
            {
                "_id": request_id,
                "title": "Night Patrol",
                "site_snapshot": {"site_name": "Warehouse"},
                "fulfillment_mode": "individual_only",
                "target_type": "guard",
                "request_status": "submitted",
                "staffing_status": "open",
                "accepted_slots": 0,
                "open_slots": 1,
                "request_revision": 1,
            }
        ],
    )
    manager._role_value = lambda _user: "ops_admin"
    manager._is_platform_role = lambda role: role == "ops_admin"

    async def _get_session_tenant(_current_user):
        raise AssertionError("platform roles must not require a session tenant for jobs listing")

    manager._get_session_tenant = _get_session_tenant

    result = await manager.list_jobs(SimpleNamespace(role="ops_admin"), page=1, rows=10)

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["request"]["title"] == "Night Patrol"


@pytest.mark.anyio
async def test_activate_wave_with_no_created_assignments_does_not_crash(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._wave_shift_replacement_context = lambda _wave: None
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests"

    async def _has_active_assignment_for_candidate(*_args, **_kwargs):
        return False

    manager._has_active_assignment_for_candidate = _has_active_assignment_for_candidate

    notifications = []

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **kwargs):
            notifications.append(kwargs)
            return None

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )

    wave = SimpleNamespace(
        id=ObjectId(),
        candidate_snapshots=[
            {"candidate_id": "", "eligible": True, "broadcast_eligible": True, "target_type": "guard"},
            {"candidate_id": "guard-2", "eligible": False, "broadcast_eligible": True, "target_type": "guard"},
        ],
        wave_expires_at=None,
        wave_number=1,
        request_snapshot={},
        offer_count=None,
        updated_at=None,
    )
    record = _make_request_record(open_slots=1, title="Night Patrol", request_revision=2)
    current_user = SimpleNamespace(id="user-1", username="admin-user")

    created_count = await manager._activate_wave(wave, record, current_user)

    assert created_count == 0
    assert wave.offer_count == 0
    assert notifications == []
