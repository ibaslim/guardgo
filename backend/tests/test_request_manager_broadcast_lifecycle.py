from datetime import datetime
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestCreatePayload,
    ClientRequestRecord,
    ClientRequestSoftDeletePayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestAssignmentStatusUpdatePayload,
    RequestAssignmentScope,
    RequestLockReason,
    RequestStaffingStatus,
    RequestStatus,
    RequestTargetType,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantType


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

    @staticmethod
    def _matches(doc, query):
        for key, expected in (query or {}).items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if actual not in expected["$in"]:
                        return False
                    continue
                return False
            if actual != expected:
                return False
        return True

    def find(self, query):
        return _FakeCursor([doc for doc in self._docs if self._matches(doc, query)])

    async def update_one(self, query, update):
        target_id = query.get("_id")
        set_values = (update or {}).get("$set", {})
        for doc in self._docs:
            if doc.get("_id") == target_id:
                doc.update(set_values)
                break


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
async def test_list_requests_filters_client_tenant_and_sets_tenant_label():
    manager = object.__new__(RequestManager)

    async def _resolve_request_docs_for_role(_current_user):
        return [
            {
                "_id": ObjectId(),
                "client_tenant_id": "client-1",
                "created_by_user_id": "creator-1",
                "created_by_username": "creator",
                "title": "Toronto Warehouse",
                "fulfillment_mode": "individual_only",
                "target_type": "guard",
                "requested_guard_type": "unarmed",
                "guards_required": 2,
                "request_status": "submitted",
                "staffing_status": "open",
                "site_snapshot": {"site_name": "Warehouse A"},
                "accepted_slots": 0,
                "open_slots": 2,
                "created_at": datetime(2026, 5, 19, 10, 0),
                "updated_at": datetime(2026, 5, 19, 10, 0),
            },
            {
                "_id": ObjectId(),
                "client_tenant_id": "client-2",
                "created_by_user_id": "creator-2",
                "created_by_username": "creator",
                "title": "Vancouver Harbour",
                "fulfillment_mode": "hybrid",
                "target_type": "guard",
                "requested_guard_type": "tactical",
                "guards_required": 3,
                "request_status": "submitted",
                "staffing_status": "pending_review",
                "site_snapshot": {"site_name": "Harbour Site"},
                "accepted_slots": 0,
                "open_slots": 3,
                "created_at": datetime(2026, 5, 19, 11, 0),
                "updated_at": datetime(2026, 5, 19, 11, 0),
            },
        ]

    async def _build_client_tenant_label_lookup(_tenant_ids):
        return {
            "client-1": "Alpha Client",
            "client-2": "Coastal Client",
        }

    manager._resolve_request_docs_for_role = _resolve_request_docs_for_role
    manager._build_client_tenant_label_lookup = _build_client_tenant_label_lookup

    result = await manager.list_requests(
        current_user=SimpleNamespace(username="platform", role="ops_admin"),
        page=1,
        rows=20,
        keyword="harbour",
        request_status="submitted",
        fulfillment_mode="hybrid",
        client_tenant_id="client-2",
    )

    assert result["pagination"]["total_items"] == 1
    assert result["filters"]["client_tenant_id"] == "client-2"
    assert result["items"][0]["title"] == "Vancouver Harbour"
    assert result["items"][0]["client_tenant_label"] == "Coastal Client"


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
async def test_sync_request_runtime_state_closes_request_once_committed_work_is_completed():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    async def _get_assignments(_request_id):
        return [
            SimpleNamespace(
                assignment_scope=RequestAssignmentScope.REQUEST,
                assignment_status=RequestAssignmentStatus.COMPLETED,
                slots_committed=1,
            )
        ]

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    record = _make_request_record(
        guards_required=1,
        accepted_slots=1,
        open_slots=0,
        staffing_status=RequestStaffingStatus.FILLED,
        request_status=RequestStatus.IN_PROGRESS,
        requested_end_at=datetime(2026, 5, 25, 20, 0),
    )

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.FILLED
    assert updated.request_status == RequestStatus.CLOSED
    assert updated.closed_at is not None
    assert updated.lock_reason == RequestLockReason.REQUEST_CLOSED


@pytest.mark.anyio
async def test_publish_existing_request_requires_requested_window():
    manager = object.__new__(RequestManager)

    record = _make_request_record(
        requested_start_at=None,
        requested_end_at=None,
        request_expires_at=datetime(2026, 5, 30, 12, 0),
        site_snapshot={
            "site_address": {
                "country": "CA",
                "province": "ON",
                "city": "Toronto",
                "latitude": 43.6532,
                "longitude": -79.3832,
            }
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager._publish_existing_request(
            record,
            current_user=SimpleNamespace(id="user-1", username="clientadmin"),
            max_match_results=25,
            trigger="initial_publish",
            increment_revision=False,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Requested start and end times are required before publishing"


@pytest.mark.anyio
async def test_publish_existing_request_requires_site_coordinates():
    manager = object.__new__(RequestManager)

    record = _make_request_record(
        requested_start_at=datetime(2026, 5, 30, 13, 0),
        requested_end_at=datetime(2026, 5, 30, 17, 0),
        request_expires_at=datetime(2026, 5, 30, 12, 0),
        site_snapshot={
            "site_address": {
                "country": "CA",
                "province": "ON",
                "city": "Toronto",
                "latitude": None,
                "longitude": None,
            }
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager._publish_existing_request(
            record,
            current_user=SimpleNamespace(id="user-1", username="clientadmin"),
            max_match_results=25,
            trigger="initial_publish",
            increment_revision=False,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Request site latitude and longitude are required"


@pytest.mark.anyio
async def test_create_request_uses_target_client_tenant_for_platform_user(monkeypatch):
    manager = object.__new__(RequestManager)
    engine = FakeEngine()
    manager._engine = engine

    target_tenant = SimpleNamespace(
        id=ObjectId("507f1f77bcf86cd799439099"),
        profile={
            "sites": [{
                "site_name": "Client HQ",
                "site_address": {
                    "street": "100 Main St",
                    "city": "Toronto",
                    "country": "CA",
                    "province": "ON",
                    "postal_code": "M5H 2N2",
                    "latitude": 43.6532,
                    "longitude": -79.3832,
                },
            }],
        },
    )

    async def _resolve_request_client_tenant(payload, current_user):
        assert payload.client_tenant_id == "507f1f77bcf86cd799439099"
        assert current_user.role == "admin"
        return target_tenant

    async def _preview_matches(*_args, **_kwargs):
        return {"summary": {"eligible_count": 0}, "results": []}

    manager._resolve_request_client_tenant = _resolve_request_client_tenant
    manager._resolve_site_snapshot = lambda payload, profile: {
        "site_index": 0,
        "site_source": "saved",
        "site_name": "Client HQ",
        "site_address": {
            "city": "Toronto",
            "country": "CA",
            "province": "ON",
            "latitude": 43.6532,
            "longitude": -79.3832,
        },
    }
    manager._preview_matches_for_request = _preview_matches
    manager._publish_existing_request = None

    async def _write_activity(*_args, **_kwargs):
        return None

    manager._write_activity = _write_activity

    class _FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: _FakeNotificationManager()))

    payload = ClientRequestCreatePayload(
        title="Platform-created request",
        fulfillment_mode="individual_only",
        client_tenant_id="507f1f77bcf86cd799439099",
        site_index=0,
        guards_required=2,
        commit=False,
    )

    result = await manager.create_request(
        payload=payload,
        current_user=SimpleNamespace(id="user-1", username="ops", role="admin", tenant_uuid=""),
    )

    assert result["item"]["client_tenant_id"] == "507f1f77bcf86cd799439099"
    assert engine.saved
    assert engine.saved[0].client_tenant_id == "507f1f77bcf86cd799439099"


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
async def test_list_jobs_guard_defaults_to_committed_work_and_auto_completes_elapsed_assignments():
    offered_assignment_id = ObjectId()
    accepted_assignment_id = ObjectId()
    request_offer_id = ObjectId()
    request_job_id = ObjectId()
    manager = object.__new__(RequestManager)
    assignment_docs = [
        {
            "_id": offered_assignment_id,
            "request_id": str(request_offer_id),
            "client_tenant_id": "client-1",
            "assignee_tenant_id": "guard-1",
            "assignee_tenant_type": "guard",
            "assignment_status": "offered",
            "candidate_snapshot": {"candidate_name": "Guard One"},
            "assigned_by_user_id": "user-1",
            "assigned_by_username": "admin",
            "created_at": None,
            "updated_at": datetime(2026, 5, 19, 9, 0),
        },
        {
            "_id": accepted_assignment_id,
            "request_id": str(request_job_id),
            "client_tenant_id": "client-1",
            "assignee_tenant_id": "guard-1",
            "assignee_tenant_type": "guard",
            "assignment_status": "accepted",
            "candidate_snapshot": {"candidate_name": "Guard One"},
            "assigned_by_user_id": "user-1",
            "assigned_by_username": "admin",
            "created_at": None,
            "updated_at": datetime(2026, 5, 19, 9, 30),
        },
    ]
    request_docs = [
        {
            "_id": request_offer_id,
            "title": "Fresh Offer",
            "site_snapshot": {"site_name": "Dock"},
            "fulfillment_mode": "individual_only",
            "target_type": "guard",
            "request_status": "submitted",
            "staffing_status": "open",
            "accepted_slots": 0,
            "open_slots": 1,
            "request_revision": 1,
            "requested_end_at": datetime(2026, 5, 20, 18, 0),
        },
        {
            "_id": request_job_id,
            "title": "Elapsed Patrol",
            "site_snapshot": {"site_name": "Campus"},
            "fulfillment_mode": "individual_only",
            "target_type": "guard",
            "request_status": "submitted",
            "staffing_status": "open",
            "accepted_slots": 1,
            "open_slots": 0,
            "request_revision": 1,
            "requested_end_at": datetime(2026, 5, 18, 18, 0),
        },
    ]
    manager._engine = _FakeListJobsEngine(assignment_docs=assignment_docs, request_docs=request_docs)
    manager._role_value = lambda _user: "guard_admin"
    manager._is_platform_role = lambda _role: False
    synced_request_ids = []

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="guard-1", tenant_type="guard")

    request_record = _make_request_record(
        id=str(request_job_id),
        title="Elapsed Patrol",
        request_status=RequestStatus.IN_PROGRESS,
        staffing_status=RequestStaffingStatus.FILLED,
        guards_required=1,
        accepted_slots=1,
        open_slots=0,
        requested_end_at=datetime(2026, 5, 18, 18, 0),
    )

    async def _get_request(_request_id):
        assert _request_id == str(request_job_id)
        return request_record

    async def _sync_request_runtime_state(record):
        synced_request_ids.append(str(record.id))
        record.request_status = RequestStatus.CLOSED
        record.closed_at = datetime(2026, 5, 19, 10, 0)
        return record

    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state

    result = await manager.list_jobs(SimpleNamespace(role="guard_admin"), page=1, rows=10)

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["request"]["title"] == "Elapsed Patrol"
    assert result["items"][0]["request"]["request_status"] == "closed"
    assert result["items"][0]["assignment_status"] == "completed"
    assert assignment_docs[1]["assignment_status"] == "completed"
    assert synced_request_ids == [str(request_job_id)]


@pytest.mark.anyio
async def test_list_jobs_client_defaults_to_committed_work_only():
    offered_assignment_id = ObjectId()
    accepted_assignment_id = ObjectId()
    request_offer_id = ObjectId()
    request_job_id = ObjectId()
    manager = object.__new__(RequestManager)
    manager._engine = _FakeListJobsEngine(
        assignment_docs=[
            {
                "_id": offered_assignment_id,
                "request_id": str(request_offer_id),
                "client_tenant_id": "client-1",
                "assignee_tenant_id": "guard-1",
                "assignee_tenant_type": "guard",
                "assignment_status": "offered",
                "candidate_snapshot": {"candidate_name": "Guard One"},
                "assigned_by_user_id": "user-1",
                "assigned_by_username": "admin",
                "created_at": None,
                "updated_at": datetime(2026, 5, 19, 9, 0),
            },
            {
                "_id": accepted_assignment_id,
                "request_id": str(request_job_id),
                "client_tenant_id": "client-1",
                "assignee_tenant_id": "guard-1",
                "assignee_tenant_type": "guard",
                "assignment_status": "accepted",
                "candidate_snapshot": {"candidate_name": "Guard One"},
                "assigned_by_user_id": "user-1",
                "assigned_by_username": "admin",
                "created_at": None,
                "updated_at": datetime(2026, 5, 19, 9, 30),
            },
        ],
        request_docs=[
            {
                "_id": request_offer_id,
                "title": "Offer Request",
                "site_snapshot": {"site_name": "Dock"},
                "fulfillment_mode": "individual_only",
                "target_type": "guard",
                "request_status": "submitted",
                "staffing_status": "open",
                "accepted_slots": 0,
                "open_slots": 1,
                "request_revision": 1,
                "requested_end_at": datetime(2026, 5, 20, 18, 0),
            },
            {
                "_id": request_job_id,
                "title": "Accepted Request",
                "site_snapshot": {"site_name": "Campus"},
                "fulfillment_mode": "individual_only",
                "target_type": "guard",
                "request_status": "submitted",
                "staffing_status": "open",
                "accepted_slots": 1,
                "open_slots": 0,
                "request_revision": 1,
                "requested_end_at": datetime(2026, 5, 20, 18, 0),
            },
        ],
    )
    manager._role_value = lambda _user: "client_admin"
    manager._is_platform_role = lambda _role: False

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="client-1", tenant_type="client")

    manager._get_session_tenant = _get_session_tenant

    result = await manager.list_jobs(SimpleNamespace(role="client_admin"), page=1, rows=10)

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["request"]["title"] == "Accepted Request"
    assert result["items"][0]["assignment_status"] == "accepted"


@pytest.mark.anyio
async def test_resolve_request_docs_for_guard_only_returns_actionable_offer_requests():
    request_offer_id = ObjectId()
    request_job_id = ObjectId()
    manager = object.__new__(RequestManager)
    manager._engine = _FakeListJobsEngine(
        assignment_docs=[
            {
                "_id": ObjectId(),
                "request_id": str(request_offer_id),
                "assignee_tenant_id": "guard-1",
                "assignment_status": "offered",
                "updated_at": datetime(2026, 5, 19, 10, 0),
            },
            {
                "_id": ObjectId(),
                "request_id": str(request_job_id),
                "assignee_tenant_id": "guard-1",
                "assignment_status": "accepted",
                "updated_at": datetime(2026, 5, 19, 11, 0),
            },
        ],
        request_docs=[
            {"_id": request_offer_id, "title": "Offer Request", "deleted_at": None},
            {"_id": request_job_id, "title": "Accepted Request", "deleted_at": None},
        ],
    )
    manager._role_value = lambda _user: "guard_admin"
    manager._is_platform_role = lambda _role: False

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="guard-1", tenant_type="guard", status="active")

    manager._get_session_tenant = _get_session_tenant

    docs = await manager._resolve_request_docs_for_role(SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"))

    assert len(docs) == 1
    assert str(docs[0]["_id"]) == str(request_offer_id)
    assert docs[0]["viewer_assignment"]["assignment_status"] == "offered"


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


@pytest.mark.anyio
async def test_mark_assignments_reconfirmation_required_notifies_assignee(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests?tab=requests&request=req-1"
    manager._compute_reconfirmation_due_at = lambda _record, now: now

    assignment = SimpleNamespace(
        id=ObjectId(),
        assignee_tenant_id="guard-1",
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        started_at=None,
        reconfirmation_requested_at=None,
        reconfirmation_due_at=None,
        updated_at=None,
    )

    async def _get_assignments(_request_id):
        return [assignment]

    manager._get_assignments_for_request = _get_assignments

    notifications = []

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **kwargs):
            notifications.append(kwargs)
            return None

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )

    record = _make_request_record(id="req-1", title="Updated Patrol", request_revision=3)

    await manager._mark_assignments_reconfirmation_required(record)

    assert assignment.assignment_status == RequestAssignmentStatus.RECONFIRMATION_REQUIRED
    assert notifications[0]["tenant_id"] == "guard-1"
    assert notifications[0]["metadata"]["assignment_status"] == "reconfirmation_required"


@pytest.mark.anyio
async def test_evaluate_broadcast_snapshot_normalizes_request_province_for_travel_policy(monkeypatch):
    manager = object.__new__(RequestManager)

    class _FakeBillingManager:
        async def resolve_travel_policy(self, scope: str, region_code: str, city: str):
            assert scope == "guard_travel_default"
            assert region_code == "BC"
            assert city == "Vancouver"
            return {
                "scope": scope,
                "region_code": region_code,
                "city_code": "VANCOUVER",
                "included_radius_km": 10.0,
                "rate_per_km": 0.45,
                "max_auto_match_radius_km": 50.0,
                "manual_review_over_km": 40.0,
                "source": "region_default",
            }

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.BillingManager.get_instance",
        staticmethod(lambda: _FakeBillingManager()),
    )

    record = _make_request_record(
        site_snapshot={
            "site_address": {
                "country": "CA",
                "province": "British Columbia",
                "city": "Vancouver",
                "latitude": 49.282445,
                "longitude": -123.123067,
            }
        },
        matched_candidates=[
            {
                "candidate_id": "guard-1",
                "candidate_name": "Borris Johnson",
                "target_type": "guard",
                "province": "BC",
                "city": "VANCOUVER",
                "eligible": True,
                "reason_code": "within_radius",
                "distance_source": "haversine",
                "distance_km": 0.25,
            }
        ],
    )

    evaluation = await manager._evaluate_broadcast_snapshot(record)

    assert evaluation["requires_review"] is False
    assert evaluation["review_reason_codes"] == []
    assert evaluation["candidate_snapshots"][0]["broadcast_eligible"] is True
    assert evaluation["candidate_snapshots"][0]["broadcast_outcome"] == "auto_broadcast"
    assert evaluation["candidate_snapshots"][0]["broadcast_reason_code"] == "within_policy"


@pytest.mark.anyio
async def test_update_job_status_rejects_provider_acceptance_beyond_linked_guard_capacity(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: (
        current == RequestAssignmentStatus.OFFERED and nxt == RequestAssignmentStatus.ACCEPTED
    )
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="provider-1",
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        assignment_status=RequestAssignmentStatus.OFFERED,
        slots_committed=None,
        lock_reason=None,
    )
    record = _make_request_record(
        title="Night Patrol",
        requested_guard_type="armed",
        requested_start_at=datetime(2026, 5, 20, 10, 0),
        requested_end_at=datetime(2026, 5, 20, 14, 0),
        site_snapshot={
            "site_address": {
                "country": "CA",
                "province": "ON",
                "city": "Toronto",
                "latitude": 43.6532,
                "longitude": -79.3832,
            }
        },
        open_slots=4,
    )
    session_tenant = SimpleNamespace(id="provider-1", tenant_type="service_provider")

    async def _get_assignment(_assignment_id):
        return assignment

    async def _get_session_tenant(_current_user):
        return session_tenant

    async def _get_request(_request_id):
        return record

    async def _sync_request_runtime_state(request_record):
        return request_record

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state

    class _FakeMatchingManager:
        async def provider_available_guard_capacity(self, provider_tenant_id, payload):
            assert provider_tenant_id == "provider-1"
            assert payload.requested_guard_type == "armed"
            return {"linked_guard_count": 2, "available_guard_count": 1}

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.RequestMatchingManager.get_instance",
        staticmethod(lambda: _FakeMatchingManager()),
    )

    payload = RequestAssignmentStatusUpdatePayload(
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        slots_committed=2,
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="sp_admin", tenant_uuid="provider-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Service provider only has 1 available linked guard(s) for this request window"


@pytest.mark.anyio
async def test_update_job_status_guard_accepts_offer(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda role_value: role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests?tab=jobs&job=assign-1"
    manager._request_snapshot = lambda record: {"id": str(record.id), "title": record.title}
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.OFFERED,
        assignment_origin="broadcast",
        assignment_scope=RequestAssignmentScope.REQUEST,
        broadcast_wave_id=None,
        shift_instance_id=None,
        shift_slot_id=None,
        request_revision_at_offer=1,
        slots_committed=None,
        response_due_at=None,
        reconfirmation_due_at=None,
        lock_reason=None,
        candidate_snapshot={},
        assigned_by_user_id="user-1",
        assigned_by_username="ops",
        offered_at=None,
        accepted_at=None,
        reconfirmed_at=None,
        declined_at=None,
        expired_at=None,
        reconfirmation_requested_at=None,
        closed_filled_at=None,
        superseded_at=None,
        started_at=None,
        completed_at=None,
        cancelled_at=None,
        created_at=None,
        updated_at=None,
        note=None,
    )
    record = _make_request_record(
        id="req-1",
        title="Night Patrol",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.OPEN,
        open_slots=1,
    )
    session_tenant = SimpleNamespace(id="guard-1", tenant_type=TenantType.GUARD)

    async def _get_assignment(_assignment_id):
        return assignment

    async def _get_session_tenant(_current_user):
        return session_tenant

    async def _get_request(_request_id):
        return record

    async def _sync_request_runtime_state(request_record):
        return request_record

    async def _write_activity(**_kwargs):
        return None

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._write_activity = _write_activity

    notifications = []

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **kwargs):
            notifications.append(kwargs)
            return 1

    class _FakeShiftManager:
        async def sync_shift_slots_for_request(self, request_record):
            assert request_record is record
            return {"shift_count": 0, "slot_count": 0}

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestShiftManager.get_instance",
        staticmethod(lambda: _FakeShiftManager()),
    )

    payload = RequestAssignmentStatusUpdatePayload(assignment_status=RequestAssignmentStatus.ACCEPTED)

    response = await manager.update_job_status(
        str(assignment.id),
        payload,
        current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
    )

    assert assignment.assignment_status == RequestAssignmentStatus.ACCEPTED
    assert assignment.slots_committed == 1
    assert assignment.accepted_at is not None
    assert response["item"]["assignment_status"] == "accepted"
    assert len(notifications) == 2


@pytest.mark.anyio
async def test_update_job_status_guard_declines_offer_with_reason(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda role_value: role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests?tab=requests"
    manager._request_snapshot = lambda record: {"id": str(record.id), "title": record.title}
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.OFFERED,
        assignment_origin="broadcast",
        assignment_scope=RequestAssignmentScope.REQUEST,
        broadcast_wave_id=None,
        shift_instance_id=None,
        shift_slot_id=None,
        request_revision_at_offer=1,
        slots_committed=None,
        response_due_at=None,
        reconfirmation_due_at=None,
        lock_reason=None,
        candidate_snapshot={},
        assigned_by_user_id="user-1",
        assigned_by_username="ops",
        offered_at=None,
        accepted_at=None,
        reconfirmed_at=None,
        declined_at=None,
        expired_at=None,
        reconfirmation_requested_at=None,
        closed_filled_at=None,
        superseded_at=None,
        started_at=None,
        completed_at=None,
        cancelled_at=None,
        created_at=None,
        updated_at=None,
        note=None,
    )
    record = _make_request_record(
        id="req-1",
        title="Night Patrol",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.OPEN,
        open_slots=1,
    )
    session_tenant = SimpleNamespace(id="guard-1", tenant_type=TenantType.GUARD)

    async def _get_assignment(_assignment_id):
        return assignment

    async def _get_session_tenant(_current_user):
        return session_tenant

    async def _get_request(_request_id):
        return record

    async def _sync_request_runtime_state(request_record):
        return request_record

    async def _write_activity(**_kwargs):
        return None

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._write_activity = _write_activity

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return 1

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )

    payload = RequestAssignmentStatusUpdatePayload(
        assignment_status=RequestAssignmentStatus.DECLINED,
        reason="Not available for this shift",
    )

    response = await manager.update_job_status(
        str(assignment.id),
        payload,
        current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
    )

    assert assignment.assignment_status == RequestAssignmentStatus.DECLINED
    assert assignment.declined_at is not None
    assert assignment.note == "Not available for this shift"
    assert response["item"]["assignment_status"] == "declined"


def test_serialize_assignment_tolerates_legacy_missing_fields():
    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.OFFERED,
    )

    serialized = RequestManager._serialize_assignment(assignment, request_snapshot={"title": "Night Patrol"})

    assert serialized["id"]
    assert serialized["assignment_status"] == "offered"
    assert serialized["assignment_origin"] == ""
    assert serialized["assigned_by_user_id"] == ""
    assert serialized["request"]["title"] == "Night Patrol"
