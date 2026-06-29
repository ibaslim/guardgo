from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestCreatePayload,
    ClientRequestRecord,
    ClientRequestStatusUpdatePayload,
    ClientRequestSoftDeletePayload,
    GuardPlannedLeaveRecord,
    RequestAdditionalCoveragePayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestAssignmentStatusUpdatePayload,
    RequestAssignmentScope,
    RequestInvoiceRecord,
    RequestInvoiceDeliveryStatus,
    RequestInvoiceStatus,
    RequestInvoiceTrigger,
    RequestLockReason,
    RequestFulfillmentMode,
    RequestPayoutAdjustmentCreatePayload,
    RequestPayoutAdjustmentDecisionPayload,
    RequestPayoutAdjustmentRecord,
    RequestPayoutAdjustmentUpdatePayload,
    RequestPricingPreviewPayload,
    RequestPublishUpdatePayload,
    RequestScheduleTemplateRecord,
    RequestStaffingStatus,
    RequestStatus,
    RequestTargetType,
    RequestWaveTrigger,
    RequestWaveStatus,
    ShiftCoverageSourceType,
    ShiftInstanceRecord,
    ShiftSlotRecord,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import GuardOwnershipType, TenantType


class FakeEngine:
    def __init__(self):
        self.saved = []

    async def save(self, model):
        self.saved.append(model)
        return model

    async def find_one(self, *_args, **_kwargs):
        return None


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key=None, direction=1):
        reverse = direction == -1
        sort_key = str(key or "").strip()
        if sort_key:
            self._docs = sorted(
                self._docs,
                key=lambda item: item.get(sort_key) or datetime.min,
                reverse=reverse,
            )
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
    def __init__(self, assignment_docs, request_docs, schedule_docs=None, invoice_docs=None, shift_docs=None, slot_docs=None, adjustment_docs=None, planned_leave_docs=None):
        super().__init__()
        self._assignment_docs = assignment_docs
        self._request_docs = request_docs
        self._schedule_docs = schedule_docs or []
        self._invoice_docs = invoice_docs or []
        self._shift_docs = shift_docs or []
        self._slot_docs = slot_docs or []
        self._adjustment_docs = adjustment_docs or []
        self._planned_leave_docs = planned_leave_docs or []

    def get_collection(self, model):
        if model is RequestAssignmentRecord:
            return _FakeCollection(self._assignment_docs)
        if model is ClientRequestRecord:
            return _FakeCollection(self._request_docs)
        if model is RequestScheduleTemplateRecord:
            return _FakeCollection(self._schedule_docs)
        if model is RequestInvoiceRecord:
            return _FakeCollection(self._invoice_docs)
        if model is RequestPayoutAdjustmentRecord:
            return _FakeCollection(self._adjustment_docs)
        if model is GuardPlannedLeaveRecord:
            return _FakeCollection(self._planned_leave_docs)
        if model is ShiftInstanceRecord:
            return _FakeCollection(self._shift_docs)
        if model is ShiftSlotRecord:
            return _FakeCollection(self._slot_docs)
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
        "deleted_at": None,
        "deleted_by_user_id": None,
        "deleted_by_username": None,
        "deleted_reason": None,
        "guards_required": 2,
        "accepted_slots": 0,
        "open_slots": 2,
        "created_at": None,
        "updated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def _async_return(value):
    return value


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
async def test_get_request_by_id_strips_matching_candidates_for_provider_viewer():
    manager = object.__new__(RequestManager)
    record = _make_request_record(
        client_tenant_id="client-1",
        pricing_snapshot={"client_hourly_quote": 32.5},
        matched_candidates=[{"candidate_id": "guard-1", "candidate_name": "Guard One", "eligible": True}],
    )

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _sync_request_runtime_state(_record):
        return None

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="provider-1", tenant_type=TenantType.SERVICE_PROVIDER)

    async def _resolve_viewer_assignment_for_request(_request_id, _current_user):
        return None

    async def _build_client_tenant_label_lookup(_tenant_ids):
        return {"client-1": "Client One"}

    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._refresh_request_finance_snapshot = _async_return
    manager._get_session_tenant = _get_session_tenant
    manager._resolve_viewer_assignment_for_request = _resolve_viewer_assignment_for_request
    manager._build_client_tenant_label_lookup = _build_client_tenant_label_lookup
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_role = lambda _role: False

    response = await manager.get_request_by_id("req-1", current_user=SimpleNamespace())

    assert response["matched_candidates"] == []
    assert response["client_tenant_label"] == "Client One"


@pytest.mark.anyio
async def test_get_request_wave_by_id_strips_candidate_snapshots_for_provider_viewer():
    manager = object.__new__(RequestManager)
    record = _make_request_record(id="req-1", client_tenant_id="client-1")
    wave = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        request_revision=2,
        wave_number=1,
        trigger=RequestWaveTrigger.INITIAL_PUBLISH,
        wave_status=RequestWaveStatus.ACTIVE,
        request_snapshot={"title": "Night Patrol"},
        match_summary_snapshot={"eligible_count": 4},
        candidate_snapshots=[{"candidate_id": "guard-1", "candidate_name": "Guard One"}],
        review_reason_codes=["needs_review"],
        review_findings=[{"reason_code": "needs_review"}],
        review_note="Internal note",
        reviewed_by_user_id=None,
        reviewed_by_username=None,
        review_requested_at=None,
        reviewed_at=None,
        returned_at=None,
        activated_at=None,
        wave_expires_at=None,
        filled_at=None,
        expired_at=None,
        superseded_at=None,
        cancelled_at=None,
        open_slots_at_send=2,
        offer_count=1,
        accepted_slots_at_close=0,
        created_at=None,
        updated_at=None,
    )

    async def _get_wave_or_404(_wave_id):
        return wave

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _sync_request_runtime_state(_record):
        return None

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="provider-1", tenant_type=TenantType.SERVICE_PROVIDER)

    manager._get_wave_or_404 = _get_wave_or_404
    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._get_session_tenant = _get_session_tenant
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_role = lambda _role: False

    response = await manager.get_request_wave_by_id("wave-1", current_user=SimpleNamespace())

    assert response["candidate_snapshots"] == []
    assert response["review_reason_codes"] == []
    assert response["review_findings"] == []
    assert response["review_note"] is None


@pytest.mark.anyio
async def test_list_request_waves_strips_review_data_for_provider_viewer():
    manager = object.__new__(RequestManager)
    record = _make_request_record(id="req-1", client_tenant_id="client-1")
    wave_id = ObjectId()

    class _WaveEngine:
        @staticmethod
        def get_collection(_model):
            return _FakeCollection([
                {
                    "_id": wave_id,
                    "request_id": "req-1",
                    "client_tenant_id": "client-1",
                    "request_revision": 2,
                    "wave_number": 1,
                    "trigger": RequestWaveTrigger.INITIAL_PUBLISH.value,
                    "wave_status": RequestWaveStatus.ACTIVE.value,
                    "request_snapshot": {"title": "Night Patrol"},
                    "match_summary_snapshot": {"eligible_count": 4},
                    "candidate_snapshots": [{"candidate_id": "guard-1"}],
                    "review_reason_codes": ["needs_review"],
                    "review_findings": [{"reason_code": "needs_review"}],
                    "review_note": "Internal note",
                    "open_slots_at_send": 2,
                    "offer_count": 1,
                    "accepted_slots_at_close": 0,
                    "created_at": datetime(2026, 6, 29, 10, 0),
                    "updated_at": datetime(2026, 6, 29, 10, 0),
                }
            ])

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="provider-1", tenant_type=TenantType.SERVICE_PROVIDER)

    manager._engine = _WaveEngine()
    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._get_session_tenant = _get_session_tenant
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_role = lambda _role: False

    response = await manager.list_request_waves("req-1", current_user=SimpleNamespace(), page=1, rows=20)

    assert response["items"][0]["candidate_snapshots"] == []
    assert response["items"][0]["review_reason_codes"] == []
    assert response["items"][0]["review_findings"] == []
    assert response["items"][0]["review_note"] is None


@pytest.mark.anyio
async def test_get_request_by_id_strips_matching_candidates_for_platform_viewer():
    manager = object.__new__(RequestManager)
    record = _make_request_record(
        client_tenant_id="client-1",
        pricing_snapshot={"client_hourly_quote": 32.5},
        matched_candidates=[{"candidate_id": "guard-1", "candidate_name": "Guard One", "eligible": True}],
    )

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _sync_request_runtime_state(_record):
        return None

    async def _resolve_viewer_assignment_for_request(_request_id, _current_user):
        return None

    async def _build_client_tenant_label_lookup(_tenant_ids):
        return {"client-1": "Client One"}

    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._refresh_request_finance_snapshot = _async_return
    manager._resolve_viewer_assignment_for_request = _resolve_viewer_assignment_for_request
    manager._build_client_tenant_label_lookup = _build_client_tenant_label_lookup
    manager._role_value = lambda _user: "ops_admin"

    response = await manager.get_request_by_id("req-1", current_user=SimpleNamespace())

    assert response["matched_candidates"] == []
    assert response["client_tenant_label"] == "Client One"


@pytest.mark.anyio
async def test_get_request_wave_by_id_strips_candidate_snapshots_for_platform_viewer():
    manager = object.__new__(RequestManager)
    record = _make_request_record(id="req-1", client_tenant_id="client-1")
    wave = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        request_revision=2,
        wave_number=1,
        trigger=RequestWaveTrigger.INITIAL_PUBLISH,
        wave_status=RequestWaveStatus.ACTIVE,
        request_snapshot={"title": "Night Patrol"},
        match_summary_snapshot={"eligible_count": 4},
        candidate_snapshots=[{"candidate_id": "guard-1", "candidate_name": "Guard One"}],
        review_reason_codes=["needs_review"],
        review_findings=[{"reason_code": "needs_review"}],
        review_note="Internal note",
        reviewed_by_user_id=None,
        reviewed_by_username=None,
        review_requested_at=None,
        reviewed_at=None,
        returned_at=None,
        activated_at=None,
        wave_expires_at=None,
        filled_at=None,
        expired_at=None,
        superseded_at=None,
        cancelled_at=None,
        open_slots_at_send=2,
        offer_count=1,
        accepted_slots_at_close=0,
        created_at=None,
        updated_at=None,
    )

    async def _get_wave_or_404(_wave_id):
        return wave

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _sync_request_runtime_state(_record):
        return None

    manager._get_wave_or_404 = _get_wave_or_404
    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._role_value = lambda _user: "ops_admin"

    response = await manager.get_request_wave_by_id("wave-1", current_user=SimpleNamespace())

    assert response["candidate_snapshots"] == []
    assert response["review_reason_codes"] == []
    assert response["review_findings"] == []
    assert response["review_note"] is None


@pytest.mark.anyio
async def test_list_requests_backfills_missing_pricing_snapshot_for_response_docs():
    manager = object.__new__(RequestManager)

    async def _resolve_request_docs_for_role(_current_user):
        return [
            {
                "_id": ObjectId(),
                "client_tenant_id": "client-1",
                "title": "Legacy Offer",
                "request_status": "submitted",
                "staffing_status": "open",
                "fulfillment_mode": "individual_only",
                "guards_required": 1,
                "site_snapshot": {
                    "site_name": "Downtown Site",
                    "site_address": {"province": "British Columbia", "city": "Vancouver"},
                },
                "requested_start_at": datetime(2026, 5, 24, 9, 0),
                "requested_end_at": datetime(2026, 5, 24, 17, 0),
                "created_at": datetime(2026, 5, 19, 11, 0),
                "updated_at": datetime(2026, 5, 19, 11, 0),
                "invoicing_snapshot": {"contract_type": "short_term"},
            },
        ]

    async def _build_client_tenant_label_lookup(_tenant_ids):
        return {"client-1": "Alpha Client"}

    async def _build_request_pricing_and_invoicing(**_kwargs):
        return {
            "pricing_snapshot": {
                "client_hourly_quote": 39.0,
                "guard_hourly_pay": 25.5,
                "guard_company_margin": 13.5,
                "estimated_client_charge": 312.0,
            },
            "invoicing_snapshot": {
                "contract_type": "short_term",
                "billing_cycle": "per_request",
            },
        }

    manager._resolve_request_docs_for_role = _resolve_request_docs_for_role
    manager._build_client_tenant_label_lookup = _build_client_tenant_label_lookup
    manager._build_request_pricing_and_invoicing = _build_request_pricing_and_invoicing

    result = await manager.list_requests(
        current_user=SimpleNamespace(username="guard", role="guard_admin"),
        page=1,
        rows=20,
    )

    assert result["items"][0]["pricing_snapshot"]["client_hourly_quote"] == 39.0
    assert result["items"][0]["pricing_snapshot"]["guard_company_margin"] == 13.5
    assert result["items"][0]["invoicing_snapshot"]["billing_cycle"] == "per_request"


@pytest.mark.anyio
async def test_list_request_invoices_returns_newest_first_for_client_admin():
    manager = object.__new__(RequestManager)
    request_record = _make_request_record(id=ObjectId(), client_tenant_id="tenant-1")
    invoice_docs = [
        {
            "_id": ObjectId(),
            "request_id": str(request_record.id),
            "client_tenant_id": "tenant-1",
            "request_revision": 1,
            "trigger": "initial_publish",
            "invoice_number": "INV-202605-OLD",
            "contract_type": "short_term",
            "billing_cycle": "per_request",
            "charge_timing": "on_the_go",
            "currency": "CAD",
            "guards_required": 2,
            "invoice_status": "issued",
            "payment_status": "pending_capture",
            "email_delivery_status": "sent",
            "created_at": datetime(2026, 5, 20, 10, 0),
            "updated_at": datetime(2026, 5, 20, 10, 0),
        },
        {
            "_id": ObjectId(),
            "request_id": str(request_record.id),
            "client_tenant_id": "tenant-1",
            "request_revision": 2,
            "trigger": "publish_update",
            "invoice_number": "INV-202606-NEW",
            "contract_type": "long_term",
            "billing_cycle": "weekly",
            "charge_timing": "advance_weekly",
            "currency": "CAD",
            "guards_required": 3,
            "invoice_status": "revised",
            "payment_status": "pending_capture",
            "email_delivery_status": "sent",
            "created_at": datetime(2026, 5, 21, 10, 0),
            "updated_at": datetime(2026, 5, 21, 10, 0),
        },
    ]

    manager._engine = _FakeListJobsEngine([], [], invoice_docs=invoice_docs)
    manager._get_request_or_404 = lambda _request_id: _async_return(request_record)
    manager._assert_not_soft_deleted = lambda _record: None
    manager._role_value = lambda _user: "client_admin"
    manager._is_platform_role = lambda _role: False
    manager._get_session_tenant = lambda _user: _async_return(SimpleNamespace(id="tenant-1", tenant_type=TenantType.CLIENT))

    result = await manager.list_request_invoices(
        request_id=str(request_record.id),
        current_user=SimpleNamespace(role="client_admin", tenant_uuid="tenant-1"),
        page=1,
        rows=10,
    )

    assert result["pagination"]["total_items"] == 2
    assert [item["invoice_number"] for item in result["items"]] == ["INV-202606-NEW", "INV-202605-OLD"]


@pytest.mark.anyio
async def test_get_request_invoice_by_id_returns_invoice_for_client_admin():
    manager = object.__new__(RequestManager)
    request_record = _make_request_record(id=ObjectId(), client_tenant_id="tenant-1")
    invoice_id = ObjectId()
    invoice_docs = [{
        "_id": invoice_id,
        "request_id": str(request_record.id),
        "client_tenant_id": "tenant-1",
        "request_revision": 2,
        "trigger": "weekly_advance",
        "invoice_number": "INV-202606-NEW",
        "contract_type": "long_term",
        "billing_cycle": "weekly",
        "charge_timing": "advance_weekly",
        "billing_period_start_local": "2026-06-01",
        "billing_period_end_local": "2026-06-30",
        "billing_period_label": "June 2026",
        "currency": "CAD",
        "guards_required": 3,
        "invoice_status": "issued",
        "payment_status": "pending_capture",
        "email_delivery_status": "sent",
        "line_items": [{"description": "Night Patrol - 2026-06-01"}],
        "created_at": datetime(2026, 5, 21, 10, 0),
        "updated_at": datetime(2026, 5, 21, 10, 0),
    }]

    manager._engine = _FakeListJobsEngine([], [], invoice_docs=invoice_docs)
    manager._get_request_or_404 = lambda _request_id: _async_return(request_record)
    manager._assert_not_soft_deleted = lambda _record: None
    manager._get_session_tenant = lambda _user: _async_return(SimpleNamespace(id="tenant-1", tenant_type=TenantType.CLIENT))

    result = await manager.get_request_invoice_by_id(
        request_id=str(request_record.id),
        invoice_id=str(invoice_id),
        current_user=SimpleNamespace(role="client_admin", tenant_uuid="tenant-1"),
    )

    assert result["id"] == str(invoice_id)
    assert result["invoice_number"] == "INV-202606-NEW"
    assert result["billing_period_label"] == "June 2026"


@pytest.mark.anyio
async def test_list_my_invoices_returns_guard_payout_share():
    manager = object.__new__(RequestManager)
    request_id = ObjectId()
    shift_id = ObjectId()
    request_docs = [{
        "_id": request_id,
        "title": "Weekend Patrol",
        "timezone": "America/Vancouver",
        "guards_required": 2,
        "pricing_snapshot": {"currency": "CAD", "guard_hourly_pay": 25, "guards_required": 2},
        "invoicing_snapshot": {"contract_type": "short_term"},
        "site_snapshot": {"site_name": "Harbour Centre"},
    }]
    assignment_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "assignee_tenant_id": "guard-tenant-1",
        "assignee_tenant_type": "guard",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": 1,
    }]
    invoice_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "client_tenant_id": "client-1",
        "request_revision": 1,
        "trigger": "initial_publish",
        "invoice_number": "INV-202606-GUARD",
        "contract_type": "short_term",
        "billing_cycle": "per_request",
        "charge_timing": "on_the_go",
        "billing_period_start_local": "2026-06-12",
        "billing_period_end_local": "2026-06-12",
        "billing_period_label": "Jun 12, 2026",
        "currency": "CAD",
        "estimated_total_hours": 16,
        "estimated_guard_payout": 400,
        "invoice_status": "issued",
        "line_items": [{
            "description": "Weekend Patrol",
            "service_date_local": "2026-06-12",
            "unit": "hour",
            "quantity": 16,
            "unit_rate": 39,
            "amount": 624,
            "metadata": {
                "guards_required": 2,
                "hours_per_position": 8,
                "start_at_local": "2026-06-12T08:00:00-07:00",
                "end_at_local": "2026-06-12T16:00:00-07:00",
            },
        }],
        "created_at": datetime(2026, 6, 10, 10, 0),
        "updated_at": datetime(2026, 6, 10, 10, 0),
    }]
    shift_docs = [{
        "_id": shift_id,
        "request_id": str(request_id),
        "shift_date_local": "2026-06-12",
        "shift_start_at_utc": datetime(2026, 6, 12, 15, 0),
        "shift_end_at_utc": datetime(2026, 6, 12, 23, 0),
        "timezone": "America/Vancouver",
    }]
    slot_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "shift_instance_id": str(shift_id),
        "assigned_guard_tenant_id": "guard-tenant-1",
        "completed_at": datetime(2026, 6, 12, 21, 5),
        "actual_start_at": datetime(2026, 6, 12, 15, 0),
        "actual_end_at": datetime(2026, 6, 12, 21, 0),
    }]

    manager._engine = _FakeListJobsEngine(
        assignment_docs,
        request_docs,
        invoice_docs=invoice_docs,
        shift_docs=shift_docs,
        slot_docs=slot_docs,
    )
    manager._get_assignee_invoice_scope = lambda _user: _async_return({
        "tenant_id": "guard-tenant-1",
        "assignee_tenant_type": "guard",
    })

    result = await manager.list_my_invoices(
        current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-tenant-1"),
        page=1,
        rows=10,
    )

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["invoice_number"] == "INV-202606-GUARD"
    assert result["items"][0]["request_title"] == "Weekend Patrol"
    assert result["items"][0]["site_name"] == "Harbour Centre"
    assert result["items"][0]["payout_hourly_rate"] == 25.0
    assert result["items"][0]["estimated_total_hours"] == 6.0
    assert result["items"][0]["estimated_amount"] == 150.0
    assert result["items"][0]["committed_slots"] == 1


@pytest.mark.anyio
async def test_list_my_invoices_returns_paid_leave_adjustment_for_direct_guard_without_completed_attendance():
    manager = object.__new__(RequestManager)
    request_id = ObjectId()
    shift_id = ObjectId()
    leave_id = ObjectId()
    request_docs = [{
        "_id": request_id,
        "title": "Reception Coverage",
        "timezone": "America/Vancouver",
        "guards_required": 1,
        "pricing_snapshot": {"currency": "CAD", "guard_hourly_pay": 25, "guards_required": 1},
        "invoicing_snapshot": {"contract_type": "short_term"},
        "site_snapshot": {"site_name": "Pacific Tower"},
    }]
    assignment_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "assignee_tenant_id": "guard-tenant-9",
        "assignee_tenant_type": "guard",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": 1,
    }]
    invoice_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "client_tenant_id": "client-1",
        "request_revision": 1,
        "trigger": "initial_publish",
        "invoice_number": "INV-202606-LEAVE",
        "contract_type": "short_term",
        "billing_cycle": "per_request",
        "charge_timing": "on_the_go",
        "billing_period_start_local": "2026-06-20",
        "billing_period_end_local": "2026-06-20",
        "billing_period_label": "Jun 20, 2026",
        "currency": "CAD",
        "estimated_total_hours": 8,
        "estimated_guard_payout": 200,
        "invoice_status": "issued",
        "line_items": [{
            "description": "Reception Coverage",
            "service_date_local": "2026-06-20",
            "unit": "hour",
            "quantity": 8,
            "unit_rate": 39,
            "amount": 312,
            "metadata": {
                "guards_required": 1,
                "hours_per_position": 8,
                "start_at_local": "2026-06-20T08:00:00-07:00",
                "end_at_local": "2026-06-20T16:00:00-07:00",
            },
        }],
        "created_at": datetime(2026, 6, 18, 10, 0),
        "updated_at": datetime(2026, 6, 18, 10, 0),
    }]
    shift_docs = [{
        "_id": shift_id,
        "request_id": str(request_id),
        "shift_date_local": "2026-06-20",
        "shift_start_at_utc": datetime(2026, 6, 20, 15, 0),
        "shift_end_at_utc": datetime(2026, 6, 20, 23, 0),
        "timezone": "America/Vancouver",
    }]
    slot_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "shift_instance_id": str(shift_id),
        "assigned_guard_tenant_id": "guard-tenant-9",
    }]
    planned_leave_docs = [{
        "_id": leave_id,
        "guard_tenant_id": "guard-tenant-9",
        "request_status": "approved",
        "leave_type": "paid",
        "start_at_utc": datetime(2026, 6, 20, 15, 0),
        "end_at_utc": datetime(2026, 6, 20, 23, 0),
        "approved_by_user_id": "ops-1",
        "approved_by_username": "ops",
        "approved_at": datetime(2026, 6, 19, 9, 0),
        "created_at": datetime(2026, 6, 18, 8, 0),
        "updated_at": datetime(2026, 6, 19, 9, 0),
    }]

    manager._engine = _FakeListJobsEngine(
        assignment_docs,
        request_docs,
        invoice_docs=invoice_docs,
        shift_docs=shift_docs,
        slot_docs=slot_docs,
        planned_leave_docs=planned_leave_docs,
    )
    manager._get_assignee_invoice_scope = lambda _user: _async_return({
        "tenant_id": "guard-tenant-9",
        "assignee_tenant_type": "guard",
    })

    result = await manager.list_my_invoices(
        current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-tenant-9"),
        page=1,
        rows=10,
    )

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["invoice_number"] == "INV-202606-LEAVE"
    assert result["items"][0]["baseline_estimated_amount"] == 0.0
    assert result["items"][0]["payout_adjustment_total"] == 200.0
    assert result["items"][0]["estimated_amount"] == 200.0
    assert result["items"][0]["payout_adjustment_count"] == 1
    assert result["items"][0]["payout_adjustments"][0]["reason"] == "Approved paid leave coverage for 2026-06-20"


@pytest.mark.anyio
async def test_service_provider_owned_guard_cannot_access_my_invoices():
    manager = object.__new__(RequestManager)
    manager._get_session_tenant = lambda _user: _async_return(SimpleNamespace(
        id="guard-tenant-2",
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER.value,
    ))

    with pytest.raises(HTTPException) as exc_info:
        await manager._get_assignee_invoice_scope(
            current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-tenant-2"),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Payout invoices are managed by the service provider"


@pytest.mark.anyio
async def test_get_my_invoice_by_id_returns_provider_weekly_completed_share(monkeypatch):
    manager = object.__new__(RequestManager)
    request_id = ObjectId()
    request_record = _make_request_record(
        id=request_id,
        title="Monthly Concierge",
        timezone="America/Vancouver",
        site_snapshot={"site_name": "Pacific Tower"},
        pricing_snapshot={
            "currency": "CAD",
            "provider_hourly_pay": 22,
            "guards_required": 3,
        },
        invoicing_snapshot={"contract_type": "long_term"},
    )
    assignment_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "assignee_tenant_id": "sp-tenant-1",
        "assignee_tenant_type": "service_provider",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": 2,
    }]
    shift_id = ObjectId()
    shift_docs = [{
        "_id": shift_id,
        "request_id": str(request_id),
        "shift_date_local": "2026-06-08",
        "shift_start_at_utc": datetime(2026, 6, 8, 16, 0),
        "shift_end_at_utc": datetime(2026, 6, 8, 22, 0),
        "timezone": "America/Vancouver",
    }]
    slot_docs = [
        {
            "_id": ObjectId(),
            "request_id": str(request_id),
            "shift_instance_id": str(shift_id),
            "service_provider_tenant_id": "sp-tenant-1",
            "completed_at": datetime(2026, 6, 8, 22, 5),
            "actual_start_at": datetime(2026, 6, 8, 16, 0),
            "actual_end_at": datetime(2026, 6, 8, 22, 0),
        },
        {
            "_id": ObjectId(),
            "request_id": str(request_id),
            "shift_instance_id": str(shift_id),
            "service_provider_tenant_id": "sp-tenant-1",
            "completed_at": datetime(2026, 6, 8, 22, 6),
            "actual_start_at": datetime(2026, 6, 8, 16, 0),
            "actual_end_at": datetime(2026, 6, 8, 22, 0),
        },
    ]

    class _FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 6, 16, 12, 0)

        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 6, 16, 12, 0, tzinfo=tz)
            if tz is None:
                return value.replace(tzinfo=None)
            return value

        @classmethod
        def strptime(cls, value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.datetime",
        _FrozenDateTime,
    )

    manager._engine = _FakeListJobsEngine(assignment_docs, [{
        "_id": request_id,
        "title": "Monthly Concierge",
        "timezone": "America/Vancouver",
        "guards_required": 3,
        "site_snapshot": {"site_name": "Pacific Tower"},
        "pricing_snapshot": {"currency": "CAD", "provider_hourly_pay": 22, "guards_required": 3},
        "invoicing_snapshot": {"contract_type": "long_term"},
    }], shift_docs=shift_docs, slot_docs=slot_docs)
    manager._get_assignee_invoice_scope = lambda _user: _async_return({
        "tenant_id": "sp-tenant-1",
        "assignee_tenant_type": "service_provider",
    })
    weekly_items = await manager.list_my_invoices(
        current_user=SimpleNamespace(role="sp_admin", tenant_uuid="sp-tenant-1"),
        page=1,
        rows=10,
    )
    assert weekly_items["pagination"]["total_items"] == 1
    invoice_id = weekly_items["items"][0]["id"]

    result = await manager.get_my_invoice_by_id(invoice_id=invoice_id, current_user=SimpleNamespace(role="sp_admin", tenant_uuid="sp-tenant-1"))

    assert result["id"] == invoice_id
    assert result["request_title"] == "Monthly Concierge"
    assert result["site_name"] == "Pacific Tower"
    assert result["committed_slots"] == 2
    assert result["payout_hourly_rate"] == 22.0
    assert result["estimated_total_hours"] == 12.0
    assert result["estimated_amount"] == 264.0
    assert result["line_items"][0]["quantity"] == 12.0
    assert result["line_items"][0]["amount"] == 264.0
    assert result["billing_cycle"] == "weekly"
    assert result["billing_period_start_local"] == "2026-06-08"
    assert result["billing_period_end_local"] == "2026-06-14"


@pytest.mark.anyio
async def test_list_platform_payout_invoices_returns_enriched_items(monkeypatch):
    manager = object.__new__(RequestManager)
    request_id = ObjectId()
    shift_id = ObjectId()
    request_docs = [{
        "_id": request_id,
        "client_tenant_id": "client-1",
        "title": "Weekly Patrol",
        "timezone": "America/Vancouver",
        "guards_required": 1,
        "site_snapshot": {"site_name": "Pacific Centre"},
        "pricing_snapshot": {"currency": "CAD", "guard_hourly_pay": 25.5, "client_hourly_quote": 39, "guards_required": 1},
        "invoicing_snapshot": {"contract_type": "short_term"},
    }]
    assignment_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "assignee_tenant_id": "guard-tenant-1",
        "assignee_tenant_type": "guard",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": 1,
    }]
    invoice_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "client_tenant_id": "client-1",
        "request_revision": 1,
        "trigger": "initial_publish",
        "invoice_number": "INV-202606-GUARD",
        "contract_type": "short_term",
        "billing_cycle": "per_request",
        "charge_timing": "on_the_go",
        "billing_period_start_local": "2026-06-12",
        "billing_period_end_local": "2026-06-12",
        "billing_period_label": "Jun 12, 2026",
        "currency": "CAD",
        "client_hourly_quote": 39,
        "estimated_total_hours": 8,
        "estimated_guard_payout": 204,
        "invoice_status": "issued",
        "payment_status": "pending_capture",
        "line_items": [{
            "description": "Weekly Patrol",
            "service_date_local": "2026-06-12",
            "unit": "hour",
            "quantity": 8,
            "unit_rate": 39,
            "amount": 312,
            "metadata": {
                "guards_required": 1,
                "hours_per_position": 8,
                "start_at_local": "2026-06-12T08:00:00-07:00",
                "end_at_local": "2026-06-12T16:00:00-07:00",
            },
        }],
        "created_at": datetime(2026, 6, 10, 10, 0),
        "updated_at": datetime(2026, 6, 10, 10, 0),
    }]
    shift_docs = [{
        "_id": shift_id,
        "request_id": str(request_id),
        "shift_date_local": "2026-06-12",
        "shift_start_at_utc": datetime(2026, 6, 12, 15, 0),
        "shift_end_at_utc": datetime(2026, 6, 12, 23, 0),
        "timezone": "America/Vancouver",
    }]
    slot_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "shift_instance_id": str(shift_id),
        "assigned_guard_tenant_id": "guard-tenant-1",
        "completed_at": datetime(2026, 6, 12, 23, 5),
        "actual_start_at": datetime(2026, 6, 12, 15, 0),
        "actual_end_at": datetime(2026, 6, 12, 23, 0),
    }]

    manager._engine = _FakeListJobsEngine(
        assignment_docs,
        request_docs,
        invoice_docs=invoice_docs,
        shift_docs=shift_docs,
        slot_docs=slot_docs,
    )
    manager._role_value = lambda _user: "ops_admin"
    manager._is_platform_role = lambda role: role in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}
    manager._build_tenant_label_lookup = lambda tenant_ids: _async_return({"guard-tenant-1": "Guard One"})

    result = await manager.list_platform_payout_invoices(
        current_user=SimpleNamespace(role="ops_admin"),
        page=1,
        rows=10,
        keyword="guard one",
        assignee_tenant_type="guard",
    )

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["assignee_tenant_id"] == "guard-tenant-1"
    assert result["items"][0]["assignee_label"] == "Guard One"
    assert result["items"][0]["invoice_number"] == "INV-202606-GUARD"
    assert result["items"][0]["estimated_client_revenue"] == 312.0
    assert result["items"][0]["estimated_platform_earning"] == 108.0
    assert result["items"][0]["linked_client_invoice_number"] == "INV-202606-GUARD"
    assert result["summary"]["total_client_revenue"] == 312.0
    assert result["summary"]["total_payout"] == 204.0
    assert result["summary"]["total_platform_earning"] == 108.0


@pytest.mark.anyio
async def test_get_platform_payout_invoice_by_id_returns_item(monkeypatch):
    manager = object.__new__(RequestManager)
    request_id = ObjectId()
    shift_id = ObjectId()
    assignment_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "assignee_tenant_id": "sp-tenant-1",
        "assignee_tenant_type": "service_provider",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": 2,
    }]
    request_docs = [{
        "_id": request_id,
        "client_tenant_id": "client-9",
        "title": "Concierge",
        "timezone": "America/Vancouver",
        "guards_required": 2,
        "site_snapshot": {"site_name": "Tower"},
        "pricing_snapshot": {"currency": "CAD", "provider_hourly_pay": 22, "client_hourly_quote": 28, "guards_required": 2},
        "invoicing_snapshot": {"contract_type": "long_term"},
    }]
    invoice_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "client_tenant_id": "client-9",
        "request_revision": 1,
        "trigger": "weekly_advance",
        "invoice_number": "INV-202606-CLIENT",
        "contract_type": "long_term",
        "billing_cycle": "weekly",
        "charge_timing": "advance_weekly",
        "billing_period_start_local": "2026-06-01",
        "billing_period_end_local": "2026-06-30",
        "billing_period_label": "Jun 2026",
        "currency": "CAD",
        "client_hourly_quote": 28,
        "invoice_status": "issued",
        "payment_status": "pending_capture",
        "created_at": datetime(2026, 5, 25, 9, 0),
        "updated_at": datetime(2026, 5, 25, 9, 0),
    }]
    shift_docs = [{
        "_id": shift_id,
        "request_id": str(request_id),
        "shift_date_local": "2026-06-02",
        "shift_start_at_utc": datetime(2026, 6, 2, 16, 0),
        "shift_end_at_utc": datetime(2026, 6, 2, 22, 0),
        "timezone": "America/Vancouver",
    }]
    slot_docs = [{
        "_id": ObjectId(),
        "request_id": str(request_id),
        "shift_instance_id": str(shift_id),
        "service_provider_tenant_id": "sp-tenant-1",
        "completed_at": datetime(2026, 6, 2, 22, 5),
        "actual_start_at": datetime(2026, 6, 2, 16, 0),
        "actual_end_at": datetime(2026, 6, 2, 22, 0),
    }]

    class _FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return datetime(2026, 6, 16, 12, 0)

        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 6, 16, 12, 0, tzinfo=tz)
            if tz is None:
                return value.replace(tzinfo=None)
            return value

        @classmethod
        def strptime(cls, value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.datetime",
        _FrozenDateTime,
    )

    manager._engine = _FakeListJobsEngine(assignment_docs, request_docs, invoice_docs=invoice_docs, shift_docs=shift_docs, slot_docs=slot_docs)
    manager._role_value = lambda _user: "read_only_admin"
    manager._is_platform_role = lambda role: role in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}
    manager._build_tenant_label_lookup = lambda tenant_ids: _async_return({
        "sp-tenant-1": "Provider One",
        "client-9": "Client Nine",
    })

    listing = await manager.list_platform_payout_invoices(
        current_user=SimpleNamespace(role="read_only_admin"),
        page=1,
        rows=10,
    )
    invoice_id = listing["items"][0]["id"]

    result = await manager.get_platform_payout_invoice_by_id(
        invoice_id=invoice_id,
        current_user=SimpleNamespace(role="read_only_admin"),
    )

    assert result["id"] == invoice_id
    assert result["assignee_label"] == "Provider One"
    assert result["billing_cycle"] == "weekly"
    assert result["client_label"] == "Client Nine"
    assert result["linked_client_invoice_number"] == "INV-202606-CLIENT"
    assert result["estimated_client_revenue"] == 168.0
    assert result["estimated_platform_earning"] == 36.0


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
async def test_update_request_status_closed_completes_started_request_scope_job(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda role_value: role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}
    manager._allowed_request_status_transition = lambda _current, _next: True
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests?tab=requests"

    record = _make_request_record(
        id="req-closed-1",
        request_status=RequestStatus.IN_PROGRESS,
        staffing_status=RequestStaffingStatus.FILLED,
    )
    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-closed-1",
        assignment_scope=RequestAssignmentScope.REQUEST,
        assignment_status=RequestAssignmentStatus.IN_PROGRESS,
        started_at=datetime(2026, 5, 23, 17, 0),
        completed_at=None,
        cancelled_at=None,
        updated_at=None,
    )

    async def _get_request(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _assert_write_access(_record, _current_user):
        return None

    async def _get_assignments(_request_id):
        return [assignment]

    async def _sync_request_runtime_state(request_record):
        return request_record

    async def _write_activity(**_kwargs):
        return None

    manager._get_request_or_404 = _get_request
    manager._can_view_request = _can_view_request
    manager._assert_request_write_access = _assert_write_access
    manager._get_assignments_for_request = _get_assignments
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._write_activity = _write_activity

    notifications = []

    class _FakeNotifications:
        async def create_for_tenant_admin_users(self, **kwargs):
            notifications.append(kwargs)
            return 1

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )

    response = await manager.update_request_status(
        "req-closed-1",
        ClientRequestStatusUpdatePayload(request_status=RequestStatus.CLOSED),
        current_user=SimpleNamespace(role="client_admin"),
    )

    assert record.request_status == RequestStatus.CLOSED
    assert record.closed_at is not None
    assert assignment.assignment_status == RequestAssignmentStatus.COMPLETED
    assert assignment.completed_at is not None
    assert response["item"]["request_status"] == "closed"
    assert len(notifications) == 1


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
async def test_publish_existing_request_syncs_invoice_record(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests"

    record = _make_request_record(
        request_status=RequestStatus.DRAFT,
        requested_start_at=datetime(2026, 5, 30, 13, 0),
        requested_end_at=datetime(2026, 5, 30, 17, 0),
        request_expires_at=datetime(2026, 5, 30, 12, 0),
        site_snapshot={
            "site_name": "Client HQ",
            "site_address": {
                "country": "CA",
                "province": "ON",
                "city": "Toronto",
                "latitude": 43.6532,
                "longitude": -79.3832,
            },
        },
        pricing_snapshot={"client_hourly_quote": 28, "estimated_client_charge": 224},
        invoicing_snapshot={
            "contract_type": "short_term",
            "invoice_recipient_email": "billing@example.com",
        },
    )

    invoice_calls = []

    async def _create_wave_from_current_snapshot(*_args, **_kwargs):
        return SimpleNamespace(id=ObjectId(), wave_status=RequestWaveStatus.ACTIVE)

    async def _sync_request_runtime_state(record_to_sync):
        return record_to_sync

    async def _write_activity(**_kwargs):
        return None

    async def _sync_request_invoice_state(record_to_invoice, *, current_user, reason):
        invoice_calls.append((
            str(record_to_invoice.id),
            getattr(reason, "value", reason),
            getattr(current_user, "username", ""),
        ))
        return {"action": "created", "invoice": SimpleNamespace(id=ObjectId(), invoice_number="INV-1")}

    class _FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: _FakeNotificationManager()))

    manager._create_wave_from_current_snapshot = _create_wave_from_current_snapshot
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._serialize_wave = lambda wave: {
        "id": str(wave.id),
        "wave_status": getattr(getattr(wave, "wave_status", None), "value", getattr(wave, "wave_status", None)),
    }
    manager._write_activity = _write_activity
    manager._sync_request_invoice_state = _sync_request_invoice_state
    manager._validate_request_expiry = lambda *_args, **_kwargs: None
    manager._validate_requested_window = lambda *_args, **_kwargs: None
    manager._validated_site_snapshot_coordinates = lambda *_args, **_kwargs: None

    result = await manager._publish_existing_request(
        record,
        current_user=SimpleNamespace(id="user-1", username="clientadmin"),
        max_match_results=25,
        trigger=RequestWaveTrigger.INITIAL_PUBLISH,
        increment_revision=False,
    )

    assert result["message"] == "Request published"
    assert record.request_status == RequestStatus.SUBMITTED
    assert invoice_calls == [(str(record.id), RequestWaveTrigger.INITIAL_PUBLISH.value, "clientadmin")]


@pytest.mark.anyio
async def test_sync_request_invoice_state_creates_and_revises_long_term_invoice(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    record = _make_request_record(
        request_revision=2,
        guards_required=3,
        accepted_slots=3,
        title="Downtown Patrol",
        pricing_snapshot={
            "currency": "CAD",
            "rate_basis": "hourly",
            "guards_required": 3,
            "client_hourly_quote": 28,
            "requested_hours_per_position": 8,
            "estimated_total_hours": 24,
            "estimated_client_charge": 672,
            "estimated_guard_payout": 432,
            "estimated_provider_payout": 528,
            "estimated_company_margin_with_guard": 240,
            "estimated_company_margin_with_provider": 144,
            "mock_payment_status": "pending_capture",
            "calculation_version": "mock_v1",
        },
        invoicing_snapshot={
            "contract_type": "long_term",
            "billing_cycle": "weekly",
            "charge_timing": "advance_weekly",
            "monthly_cutoff_day": None,
            "invoice_recipient_email": "billing@example.com",
        },
    )

    schedule_record = RequestScheduleTemplateRecord(
        request_id=str(record.id),
        client_tenant_id=record.client_tenant_id,
        timezone="UTC",
        schedule_type="date_range",
        start_date_local="2026-06-01",
        end_date_local="2026-06-03",
        start_time_local="08:00",
        end_time_local="16:00",
        active=True,
    )

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 5, 24, 10, 0, tzinfo=tz)
            if tz is None:
                return value.replace(tzinfo=None)
            return value

        @classmethod
        def utcnow(cls):
            return datetime(2026, 5, 24, 10, 0)

        @classmethod
        def strptime(cls, value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.datetime",
        _FrozenDateTime,
    )

    async def _send_request_invoice_email(_record, invoice_record, *, reason, is_revision):
        assert getattr(reason, "value", reason) == RequestInvoiceTrigger.PUBLISH_UPDATE.value
        assert invoice_record.billing_period_label == "Week of Jun 01, 2026"
        assert is_revision in {False, True}
        return True

    manager._get_active_schedule_template = lambda _request_id: _async_return(schedule_record)

    async def _find_existing_invoice(*_args, **kwargs):
        billing_period_start_local = str(kwargs.get("billing_period_start_local") or "").strip()
        billing_period_end_local = str(kwargs.get("billing_period_end_local") or "").strip()
        for item in reversed(manager._engine.saved):
            if (
                isinstance(item, RequestInvoiceRecord)
                and str(getattr(item, "billing_period_start_local", "") or "").strip() == billing_period_start_local
                and str(getattr(item, "billing_period_end_local", "") or "").strip() == billing_period_end_local
            ):
                return item
        return None

    manager._find_existing_invoice = _find_existing_invoice
    manager._send_request_invoice_email = _send_request_invoice_email

    first_result = await manager._sync_request_invoice_state(
        record,
        current_user=SimpleNamespace(id="user-1", username="ops"),
        reason=RequestInvoiceTrigger.PUBLISH_UPDATE,
    )

    invoice = first_result["invoice"]
    assert first_result["action"] == "created"
    assert isinstance(invoice, RequestInvoiceRecord)
    assert invoice.invoice_status == RequestInvoiceStatus.ISSUED
    assert invoice.email_delivery_status == RequestInvoiceDeliveryStatus.SENT
    assert invoice.invoice_recipient_email == "billing@example.com"
    assert invoice.billing_period_start_local == "2026-06-01"
    assert invoice.billing_period_end_local == "2026-06-03"
    assert invoice.estimated_amount == 2016.0
    assert len(invoice.line_items) == 3
    assert record.invoicing_snapshot["invoice_status"] == RequestInvoiceStatus.ISSUED.value
    assert record.invoicing_snapshot["latest_invoice_id"] == str(invoice.id)
    assert record.invoicing_snapshot["latest_invoice_number"] == invoice.invoice_number
    assert record.invoicing_snapshot["email_delivery_status"] == RequestInvoiceDeliveryStatus.SENT.value

    record.request_revision = 3
    record.guards_required = 4
    record.pricing_snapshot["guards_required"] = 4

    second_result = await manager._sync_request_invoice_state(
        record,
        current_user=SimpleNamespace(id="user-1", username="ops"),
        reason=RequestInvoiceTrigger.PUBLISH_UPDATE,
    )

    revised_invoice = second_result["invoice"]
    assert second_result["action"] == "updated"
    assert revised_invoice.id == invoice.id
    assert revised_invoice.invoice_status == RequestInvoiceStatus.REVISED
    assert revised_invoice.estimated_amount == 2688.0
    assert revised_invoice.estimated_total_hours == 96.0
    assert record.invoicing_snapshot["invoice_status"] == RequestInvoiceStatus.REVISED.value


@pytest.mark.anyio
async def test_sync_request_invoice_state_skips_first_long_term_invoice_until_full_coverage(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    record = _make_request_record(
        request_revision=1,
        guards_required=2,
        accepted_slots=1,
        title="Harbour Patrol",
        pricing_snapshot={
            "currency": "CAD",
            "rate_basis": "hourly",
            "guards_required": 2,
            "client_hourly_quote": 28,
            "requested_hours_per_position": 8,
            "estimated_total_hours": 16,
            "estimated_client_charge": 448,
            "mock_payment_status": "pending_capture",
            "calculation_version": "mock_v1",
        },
        invoicing_snapshot={
            "contract_type": "long_term",
            "billing_cycle": "weekly",
            "charge_timing": "advance_weekly",
            "monthly_cutoff_day": None,
            "invoice_recipient_email": None,
        },
    )

    schedule_record = RequestScheduleTemplateRecord(
        request_id=str(record.id),
        client_tenant_id=record.client_tenant_id,
        timezone="UTC",
        schedule_type="date_range",
        start_date_local="2026-06-01",
        end_date_local="2026-06-30",
        start_time_local="08:00",
        end_time_local="16:00",
        active=True,
    )

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 6, 1, 9, 0, tzinfo=tz)
            return value.replace(tzinfo=None) if tz is None else value

        @classmethod
        def utcnow(cls):
            return datetime(2026, 6, 1, 9, 0)

        @classmethod
        def strptime(cls, value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.datetime",
        _FrozenDateTime,
    )

    manager._get_active_schedule_template = lambda _request_id: _async_return(schedule_record)

    result = await manager._sync_request_invoice_state(
        record,
        current_user=SimpleNamespace(id="user-1", username="ops"),
        reason=RequestInvoiceTrigger.PUBLISH_UPDATE,
    )

    assert result == {"action": "skipped", "invoice": None}
    assert not any(isinstance(item, RequestInvoiceRecord) for item in manager._engine.saved)


@pytest.mark.anyio
async def test_sync_request_invoice_state_advances_long_term_weekly_period_after_current_invoice_exists(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    record = _make_request_record(
        request_revision=1,
        guards_required=2,
        accepted_slots=2,
        title="Campus Security",
        pricing_snapshot={
            "currency": "CAD",
            "rate_basis": "hourly",
            "guards_required": 2,
            "client_hourly_quote": 30,
            "requested_hours_per_position": 8,
            "estimated_total_hours": 16,
            "estimated_client_charge": 480,
            "mock_payment_status": "pending_capture",
            "calculation_version": "mock_v1",
        },
        invoicing_snapshot={
            "contract_type": "long_term",
            "billing_cycle": "weekly",
            "charge_timing": "advance_weekly",
            "monthly_cutoff_day": None,
            "invoice_recipient_email": None,
        },
    )

    schedule_record = RequestScheduleTemplateRecord(
        request_id=str(record.id),
        client_tenant_id=record.client_tenant_id,
        timezone="UTC",
        schedule_type="date_range",
        start_date_local="2026-06-01",
        end_date_local="2026-06-30",
        start_time_local="08:00",
        end_time_local="16:00",
        active=True,
    )

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 6, 3, 10, 0, tzinfo=tz)
            return value.replace(tzinfo=None) if tz is None else value

        @classmethod
        def utcnow(cls):
            return datetime(2026, 6, 3, 10, 0)

        @classmethod
        def strptime(cls, value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.datetime",
        _FrozenDateTime,
    )

    manager._get_active_schedule_template = lambda _request_id: _async_return(schedule_record)
    manager._send_request_invoice_email = lambda *_args, **_kwargs: _async_return(False)

    async def _find_existing_invoice(*_args, **kwargs):
        billing_period_start_local = str(kwargs.get("billing_period_start_local") or "").strip()
        billing_period_end_local = str(kwargs.get("billing_period_end_local") or "").strip()
        for item in reversed(manager._engine.saved):
            if (
                isinstance(item, RequestInvoiceRecord)
                and str(getattr(item, "billing_period_start_local", "") or "").strip() == billing_period_start_local
                and str(getattr(item, "billing_period_end_local", "") or "").strip() == billing_period_end_local
            ):
                return item
        return None

    manager._find_existing_invoice = _find_existing_invoice

    first_result = await manager._sync_request_invoice_state(
        record,
        current_user=SimpleNamespace(id="user-1", username="ops"),
        reason=RequestInvoiceTrigger.PUBLISH_UPDATE,
    )
    second_result = await manager._sync_request_invoice_state(
        record,
        current_user=SimpleNamespace(id="user-1", username="ops"),
        reason=RequestInvoiceTrigger.WEEKLY_ADVANCE,
    )

    first_invoice = first_result["invoice"]
    second_invoice = second_result["invoice"]
    assert first_result["action"] == "created"
    assert second_result["action"] == "created"
    assert first_invoice.billing_period_start_local == "2026-06-01"
    assert first_invoice.billing_period_end_local == "2026-06-07"
    assert second_invoice.billing_period_start_local == "2026-06-08"
    assert second_invoice.billing_period_end_local == "2026-06-14"


@pytest.mark.anyio
async def test_create_shift_replacement_wave_for_direct_guard_requires_platform_review():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._request_snapshot = lambda record: {"id": str(record.id), "title": record.title}
    manager._compute_wave_expires_at = lambda _record, now=None: (now or datetime.utcnow()) + timedelta(hours=2)

    async def _evaluate_broadcast_snapshot(_record):
        return {
            "requires_review": False,
            "candidate_snapshots": [],
            "review_reason_codes": [],
            "review_findings": [],
        }

    manager._evaluate_broadcast_snapshot = _evaluate_broadcast_snapshot

    record = _make_request_record(
        id="req-1",
        title="Direct Guard Replacement",
        request_revision=3,
        last_wave_number=1,
        client_tenant_id="client-1",
        match_summary={"returned_count": 12},
    )

    wave = await manager.create_shift_replacement_wave(
        record,
        shift_instance_id="shift-1",
        original_slot_id="slot-1",
        replacement_slot_id="slot-2",
        original_coverage_source_type=ShiftCoverageSourceType.DIRECT_GUARD.value,
        original_coverage_tenant_id="guard-1",
        current_user=SimpleNamespace(id="ops-1", username="ops"),
        max_match_results=25,
    )

    assert wave.wave_status == RequestWaveStatus.PENDING_REVIEW
    assert wave.review_requested_at is not None
    context = wave.request_snapshot["shift_replacement"]
    assert context["platform_review_required"] is True
    assert context["original_coverage_source_type"] == ShiftCoverageSourceType.DIRECT_GUARD.value
    assert context["original_coverage_tenant_id"] == "guard-1"


@pytest.mark.anyio
async def test_create_request_uses_target_client_tenant_for_platform_user(monkeypatch):
    manager = object.__new__(RequestManager)
    engine = FakeEngine()
    manager._engine = engine

    target_tenant = SimpleNamespace(
        id=ObjectId("507f1f77bcf86cd799439099"),
        profile={
            "billing_method": {
                "method": "credit_card",
                "cardholder_name": "Client Billing",
                "last4": "4242",
                "expiry_month": "12",
                "expiry_year": "29",
            },
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

        async def create_for_platform_admin_users(self, **_kwargs):
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
async def test_create_request_requires_client_billing_method(monkeypatch):
    manager = object.__new__(RequestManager)

    async def _resolve_request_client_tenant(*_args, **_kwargs):
        return SimpleNamespace(
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

    manager._resolve_request_client_tenant = _resolve_request_client_tenant

    payload = ClientRequestCreatePayload(
        title="Billing missing request",
        fulfillment_mode="individual_only",
        client_tenant_id="507f1f77bcf86cd799439099",
        site_index=0,
        guards_required=2,
        commit=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager.create_request(
            payload=payload,
            current_user=SimpleNamespace(id="user-1", username="ops", role="admin", tenant_uuid=""),
        )

    assert exc_info.value.status_code == 403
    assert "billing method" in str(exc_info.value.detail).lower()


@pytest.mark.anyio
async def test_create_request_manual_site_is_saved_to_client_profile(monkeypatch):
    manager = object.__new__(RequestManager)
    engine = FakeEngine()
    manager._engine = engine

    client_tenant = SimpleNamespace(
        id=ObjectId("507f1f77bcf86cd799439099"),
        profile={
            "billing_method": {
                "method": "credit_card",
                "cardholder_name": "Client Ops",
                "last4": "4242",
                "expiry_month": "12",
                "expiry_year": "2030",
            },
            "sites": [],
        },
    )

    async def _resolve_request_client_tenant(*_args, **_kwargs):
        return client_tenant

    async def _preview_matches(*_args, **_kwargs):
        return {"summary": {"eligible_count": 0}, "results": []}

    async def _build_request_pricing_and_invoicing(**_kwargs):
        return {
            "pricing_snapshot": {"client_hourly_quote": 28},
            "invoicing_snapshot": {"contract_type": "short_term"},
        }

    async def _write_activity(*_args, **_kwargs):
        return None

    manager._resolve_request_client_tenant = _resolve_request_client_tenant
    manager._preview_matches_for_request = _preview_matches
    manager._build_request_pricing_and_invoicing = _build_request_pricing_and_invoicing
    manager._write_activity = _write_activity

    class _FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: _FakeNotificationManager()))

    payload = ClientRequestCreatePayload(
        title="Manual Site Request",
        fulfillment_mode="individual_only",
        guards_required=2,
        commit=False,
        site={
            "site_name": "Temporary Coverage Site",
            "site_manager_contact": "Ops Desk",
            "manager_email": "ops@example.com",
            "site_type": "event",
            "google_maps_url": "https://maps.google.com/?q=43.6532,-79.3832",
            "site_address": {
                "street": "100 Main St",
                "city": "Toronto",
                "country": "CA",
                "province": "ON",
                "postal_code": "M5H 2N2",
                "latitude": 43.6532,
                "longitude": -79.3832,
            },
        },
    )

    result = await manager.create_request(
        payload=payload,
        current_user=SimpleNamespace(id="user-1", username="clientadmin", role="client_admin", tenant_uuid=str(client_tenant.id)),
    )

    assert result["item"]["site_snapshot"]["site_source"] == "request"
    assert len(client_tenant.profile["sites"]) == 1
    saved_site = client_tenant.profile["sites"][0]
    assert saved_site["site_name"] == "Temporary Coverage Site"
    assert saved_site["manager_email"] == "ops@example.com"
    assert saved_site["site_address"]["latitude"] == 43.6532
    assert len(engine.saved) == 2
    assert getattr(engine.saved[0], "client_tenant_id", "") == str(client_tenant.id)


@pytest.mark.anyio
async def test_preview_request_pricing_returns_mock_snapshots():
    manager = object.__new__(RequestManager)

    async def _resolve_request_client_tenant(*_args, **_kwargs):
        return SimpleNamespace(
            id=ObjectId("507f1f77bcf86cd799439099"),
            profile={
                "billing_method": {
                    "method": "credit_card",
                    "cardholder_name": "Client Ops",
                    "last4": "4242",
                    "expiry_month": "12",
                    "expiry_year": "2030",
                },
                "sites": [{
                    "site_name": "Client HQ",
                    "manager_email": "ops@example.com",
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

    async def _build_request_pricing_and_invoicing(**kwargs):
        assert kwargs["guards_required"] == 3
        assert kwargs["invoice_contract_type"] == "long_term"
        assert kwargs["invoice_cutoff_day"] == 12
        assert kwargs["invoice_recipient_email"] == "billing@example.com"
        return {
            "pricing_snapshot": {"client_hourly_quote": 28, "guard_hourly_pay": 18},
            "invoicing_snapshot": {"contract_type": "long_term", "monthly_cutoff_day": 12},
        }

    manager._resolve_request_client_tenant = _resolve_request_client_tenant
    manager._build_request_pricing_and_invoicing = _build_request_pricing_and_invoicing

    result = await manager.preview_request_pricing(
        payload=RequestPricingPreviewPayload(
            client_tenant_id="507f1f77bcf86cd799439099",
            site_index=0,
            guards_required=3,
            requested_start_at=datetime(2026, 5, 16, 18, 0),
            requested_end_at=datetime(2026, 5, 16, 22, 0),
            invoice_contract_type="long_term",
            invoice_cutoff_day=12,
            invoice_recipient_email="billing@example.com",
        ),
        current_user=SimpleNamespace(id="user-1", username="ops", role="admin", tenant_uuid=""),
    )

    assert result["pricing"]["client_hourly_quote"] == 28
    assert result["invoicing"]["contract_type"] == "long_term"


@pytest.mark.anyio
async def test_build_request_pricing_and_invoicing_uses_guard_baseline_for_hybrid():
    manager = object.__new__(RequestManager)

    async def _resolve_scoped_rate(scopes, _province, _city, _rate_field):
        scope = tuple(scopes or [])
        if "guard_default" in scope or "guard_default_legacy" in scope:
            return 20.0
        if "provider_default" in scope:
            return 28.0
        if "guard_margin_default" in scope:
            return 8.0
        if "provider_commission_default" in scope:
            return 10.0
        return 0.0

    manager._resolve_scoped_rate = _resolve_scoped_rate
    manager._resolve_rate_field = lambda *_args, **_kwargs: "default_hourly_rate"
    manager._normalize_province_code = lambda *_args, **_kwargs: "ON"
    manager._normalize_city_code = lambda *_args, **_kwargs: "TORONTO"

    result = await manager._build_request_pricing_and_invoicing(
        fulfillment_mode=RequestFulfillmentMode.HYBRID,
        site_snapshot={"site_address": {"province": "ON", "city": "Toronto"}},
        requested_start_at=datetime(2026, 5, 16, 18, 0),
        requested_end_at=datetime(2026, 5, 16, 22, 0),
        guards_required=3,
        invoice_contract_type="short_term",
        invoice_cutoff_day=None,
        invoice_recipient_email="billing@example.com",
    )

    pricing = result["pricing_snapshot"]
    assert pricing["pricing_strategy"] == "guard_baseline"
    assert pricing["client_hourly_quote"] == 28.0
    assert pricing["guard_company_margin"] == 8.0
    assert pricing["provider_company_commission"] == 0.0
    assert pricing["provider_adjustment_policy"] == "platform_payout_adjustment_required"


@pytest.mark.anyio
async def test_build_request_pricing_and_invoicing_uses_weekly_advance_for_long_term():
    manager = object.__new__(RequestManager)

    async def _resolve_scoped_rate(scopes, _province, _city, _rate_field):
        scope = tuple(scopes or [])
        if "guard_default" in scope or "guard_default_legacy" in scope:
            return 20.0
        if "provider_default" in scope:
            return 28.0
        if "guard_margin_default" in scope:
            return 8.0
        if "provider_commission_default" in scope:
            return 10.0
        return 0.0

    manager._resolve_scoped_rate = _resolve_scoped_rate
    manager._resolve_rate_field = lambda *_args, **_kwargs: "default_hourly_rate"
    manager._normalize_province_code = lambda *_args, **_kwargs: "ON"
    manager._normalize_city_code = lambda *_args, **_kwargs: "TORONTO"

    result = await manager._build_request_pricing_and_invoicing(
        fulfillment_mode=RequestFulfillmentMode.INDIVIDUAL_ONLY,
        site_snapshot={"site_address": {"province": "ON", "city": "Toronto"}},
        requested_start_at=datetime(2026, 5, 16, 18, 0),
        requested_end_at=datetime(2026, 5, 16, 22, 0),
        guards_required=2,
        invoice_contract_type="long_term",
        invoice_cutoff_day=12,
        invoice_recipient_email="billing@example.com",
    )

    invoicing = result["invoicing_snapshot"]
    assert invoicing["contract_type"] == "long_term"
    assert invoicing["billing_cycle"] == "weekly"
    assert invoicing["charge_timing"] == "advance_weekly"
    assert invoicing["monthly_cutoff_day"] is None


@pytest.mark.anyio
async def test_serialize_assignee_invoice_uses_assignee_specific_short_term_identity():
    invoice = RequestManager._serialize_assignee_invoice(
        {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "request_id": "req-7",
            "invoice_number": "INV-202606-0007",
            "contract_type": "short_term",
            "billing_cycle": "per_request",
            "charge_timing": "on_the_go",
            "currency": "CAD",
            "estimated_total_hours": 8.0,
            "estimated_guard_payout": 160.0,
            "estimated_provider_payout": 224.0,
            "line_items": [{
                "description": "Coverage payout",
                "quantity": 8.0,
                "metadata": {"guards_required": 2, "hours_per_position": 4.0},
            }],
            "invoice_status": "issued",
            "created_at": datetime(2026, 6, 1, 9, 0),
            "updated_at": datetime(2026, 6, 1, 9, 0),
        },
        assignee_tenant_id="sp-1",
        assignee_tenant_type="service_provider",
        committed_slots=2,
        coverage_status="accepted",
        request_title="Hybrid request",
        site_name="Client HQ",
    )

    assert invoice["id"] == "payout:service_provider:sp-1:507f1f77bcf86cd799439011"
    assert invoice["invoice_number"] == "INV-202606-0007"
    assert invoice["source_request_invoice_id"] == "507f1f77bcf86cd799439011"


@pytest.mark.anyio
async def test_create_platform_payout_adjustment_persists_and_returns_updated_invoice():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    responses = [
        {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_id": "sp-1",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "currency": "CAD",
            "estimated_amount": 300.0,
        },
        {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_id": "sp-1",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "currency": "CAD",
            "estimated_amount": 300.0,
            "payout_adjustment_total": 0.0,
        },
    ]

    async def _get_platform_payout_invoice_by_id(*, invoice_id, current_user):
        assert invoice_id == "pinv-77"
        assert current_user.username == "ops"
        return responses.pop(0)

    manager.get_platform_payout_invoice_by_id = _get_platform_payout_invoice_by_id

    result = await manager.create_platform_payout_adjustment(
        invoice_id="pinv-77",
        payload=RequestPayoutAdjustmentCreatePayload(
            amount=42.5,
            reason="Hybrid provider compensation",
        ),
        current_user=SimpleNamespace(id="user-1", username="ops", role="ops_admin"),
    )

    assert result["payout_adjustment_total"] == 0.0
    assert len(manager._engine.saved) == 1
    saved = manager._engine.saved[0]
    assert saved.payout_invoice_id == "pinv-77"
    assert saved.request_id == "req-7"
    assert saved.assignee_tenant_id == "sp-1"
    assert saved.amount == 42.5
    assert saved.reason == "Hybrid provider compensation"
    assert saved.adjustment_status == "draft"


@pytest.mark.anyio
async def test_update_platform_payout_adjustment_edits_draft_only():
    adjustment = RequestPayoutAdjustmentRecord(
        id=ObjectId(),
        payout_invoice_id="pinv-77",
        request_id="req-7",
        assignee_tenant_id="sp-1",
        assignee_tenant_type="service_provider",
        amount=42.5,
        reason="Original reason",
        adjustment_status="draft",
    )

    class _Engine(FakeEngine):
        async def find_one(self, *_args, **_kwargs):
            return adjustment

    manager = object.__new__(RequestManager)
    manager._engine = _Engine()

    async def _get_platform_payout_invoice_by_id(*, invoice_id, current_user):
        assert invoice_id == "pinv-77"
        return {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "baseline_estimated_amount": 300.0,
            "estimated_amount": 300.0,
        }

    manager.get_platform_payout_invoice_by_id = _get_platform_payout_invoice_by_id

    result = await manager.update_platform_payout_adjustment(
        adjustment_id=str(adjustment.id),
        payload=RequestPayoutAdjustmentUpdatePayload(amount=50.0, reason="Revised provider uplift"),
        current_user=SimpleNamespace(id="user-1", username="ops", role="ops_admin"),
    )

    assert result["id"] == "pinv-77"
    assert adjustment.amount == 50.0
    assert adjustment.reason == "Revised provider uplift"
    assert adjustment.updated_by_username == "ops"


@pytest.mark.anyio
async def test_approve_platform_payout_adjustment_marks_record_approved():
    adjustment = RequestPayoutAdjustmentRecord(
        id=ObjectId(),
        payout_invoice_id="pinv-77",
        request_id="req-7",
        assignee_tenant_id="sp-1",
        assignee_tenant_type="service_provider",
        amount=42.5,
        reason="Provider uplift",
        adjustment_status="draft",
    )

    class _Engine(FakeEngine):
        async def find_one(self, *_args, **_kwargs):
            return adjustment

    manager = object.__new__(RequestManager)
    manager._engine = _Engine()

    responses = [
        {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "baseline_estimated_amount": 300.0,
            "estimated_amount": 300.0,
        },
        {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "estimated_amount": 342.5,
            "payout_adjustment_total": 42.5,
        },
    ]

    async def _get_platform_payout_invoice_by_id(*, invoice_id, current_user):
        return responses.pop(0)

    manager.get_platform_payout_invoice_by_id = _get_platform_payout_invoice_by_id

    result = await manager.approve_platform_payout_adjustment(
        adjustment_id=str(adjustment.id),
        payload=RequestPayoutAdjustmentDecisionPayload(note="Approved after review"),
        current_user=SimpleNamespace(id="user-1", username="ops", role="ops_admin"),
    )

    assert result["payout_adjustment_total"] == 42.5
    assert adjustment.adjustment_status == "approved"
    assert adjustment.approved_by_username == "ops"
    assert adjustment.status_note == "Approved after review"


@pytest.mark.anyio
async def test_void_platform_payout_adjustment_marks_record_voided():
    adjustment = RequestPayoutAdjustmentRecord(
        id=ObjectId(),
        payout_invoice_id="pinv-77",
        request_id="req-7",
        assignee_tenant_id="sp-1",
        assignee_tenant_type="service_provider",
        amount=42.5,
        reason="Provider uplift",
        adjustment_status="approved",
    )

    class _Engine(FakeEngine):
        async def find_one(self, *_args, **_kwargs):
            return adjustment

    manager = object.__new__(RequestManager)
    manager._engine = _Engine()

    async def _get_platform_payout_invoice_by_id(*, invoice_id, current_user):
        return {
            "id": "pinv-77",
            "request_id": "req-7",
            "assignee_tenant_type": "service_provider",
            "request_fulfillment_mode": "hybrid",
            "estimated_amount": 300.0,
            "payout_adjustment_total": 0.0,
        }

    manager.get_platform_payout_invoice_by_id = _get_platform_payout_invoice_by_id

    result = await manager.void_platform_payout_adjustment(
        adjustment_id=str(adjustment.id),
        payload=RequestPayoutAdjustmentDecisionPayload(note="Superseded"),
        current_user=SimpleNamespace(id="user-1", username="ops", role="ops_admin"),
    )

    assert result["payout_adjustment_total"] == 0.0
    assert adjustment.adjustment_status == "voided"
    assert adjustment.voided_by_username == "ops"


@pytest.mark.anyio
async def test_publish_request_update_recalculates_finance_snapshot_for_invoice_changes():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    record = _make_request_record(
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.OPEN,
        site_snapshot={
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
        },
        requested_start_at=datetime(2026, 5, 16, 18, 0),
        requested_end_at=datetime(2026, 5, 16, 22, 0),
        request_expires_at=datetime(2026, 5, 16, 16, 0),
        pricing_snapshot={"client_hourly_quote": 28},
        invoicing_snapshot={
            "contract_type": "short_term",
            "monthly_cutoff_day": None,
            "invoice_recipient_email": "old@example.com",
        },
    )

    captured = {}

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _assert_request_write_access(_record, _current_user):
        return None

    async def _sync_request_runtime_state(record_to_sync):
        return record_to_sync

    async def _build_request_pricing_and_invoicing(**kwargs):
        captured.update(kwargs)
        return {
            "pricing_snapshot": {"client_hourly_quote": 31},
            "invoicing_snapshot": {
                "contract_type": "long_term",
                "monthly_cutoff_day": 9,
                "invoice_recipient_email": "billing@example.com",
            },
        }

    async def _supersede_previous_waves(_record):
        return None

    async def _mark_assignments_reconfirmation_required(_record):
        return None

    async def _publish_existing_request(record_to_publish, **_kwargs):
        return {"message": "Request updated", "item": RequestManager._serialize(record_to_publish)}

    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._assert_request_write_access = _assert_request_write_access
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._build_request_pricing_and_invoicing = _build_request_pricing_and_invoicing
    manager._supersede_previous_waves = _supersede_previous_waves
    manager._mark_assignments_reconfirmation_required = _mark_assignments_reconfirmation_required
    manager._publish_existing_request = _publish_existing_request
    manager._validate_requested_window = lambda *_args, **_kwargs: None
    manager._validate_request_expiry = lambda *_args, **_kwargs: None

    result = await manager.publish_request_update(
        request_id="req-1",
        payload=RequestPublishUpdatePayload(
            invoice_contract_type="long_term",
            invoice_cutoff_day=9,
            invoice_recipient_email="billing@example.com",
            max_match_results=25,
        ),
        current_user=SimpleNamespace(id="user-1", username="ops", role="admin", tenant_uuid=""),
    )

    assert result["message"] == "Request updated"
    assert captured["invoice_contract_type"] == "long_term"
    assert captured["invoice_cutoff_day"] == 9
    assert captured["invoice_recipient_email"] == "billing@example.com"
    assert record.pricing_snapshot["client_hourly_quote"] == 31
    assert record.invoicing_snapshot["contract_type"] == "long_term"


@pytest.mark.anyio
async def test_request_additional_coverage_recalculates_finance_snapshot(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests"

    record = _make_request_record(
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.OPEN,
        request_revision=1,
        guards_required=2,
        site_snapshot={
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
        },
        requested_start_at=datetime(2026, 5, 16, 18, 0),
        requested_end_at=datetime(2026, 5, 16, 22, 0),
        request_expires_at=datetime(2026, 5, 16, 16, 0),
        pricing_snapshot={"client_hourly_quote": 28},
        invoicing_snapshot={
            "contract_type": "short_term",
            "monthly_cutoff_day": None,
            "invoice_recipient_email": "billing@example.com",
        },
    )

    captured = {}
    invoice_calls = []

    async def _get_request_or_404(_request_id):
        return record

    async def _can_view_request(_record, _current_user):
        return True

    async def _assert_request_write_access(_record, _current_user):
        return None

    async def _sync_request_runtime_state(record_to_sync):
        return record_to_sync

    async def _build_request_pricing_and_invoicing(**kwargs):
        captured.update(kwargs)
        return {
            "pricing_snapshot": {"client_hourly_quote": 28, "guards_required": kwargs["guards_required"]},
            "invoicing_snapshot": {"contract_type": "short_term", "invoice_recipient_email": "billing@example.com"},
        }

    async def _refresh_request_matching(_record, _max_match_results):
        return None

    async def _create_wave_from_current_snapshot(*_args, **_kwargs):
        return None

    async def _sync_request_invoice_state(record_to_invoice, *, current_user, reason):
        invoice_calls.append((
            str(record_to_invoice.id),
            getattr(reason, "value", reason),
            getattr(current_user, "username", ""),
        ))
        return {"action": "updated", "invoice": SimpleNamespace(id=ObjectId(), invoice_number="INV-2")}

    class _FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **_kwargs):
            return None

    class _FakeShiftManager:
        async def sync_shift_slots_for_request(self, _record):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: _FakeNotificationManager()))
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestShiftManager.get_instance",
        staticmethod(lambda: _FakeShiftManager()),
    )

    manager._get_request_or_404 = _get_request_or_404
    manager._can_view_request = _can_view_request
    manager._assert_request_write_access = _assert_request_write_access
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._build_request_pricing_and_invoicing = _build_request_pricing_and_invoicing
    manager._refresh_request_matching = _refresh_request_matching
    manager._create_wave_from_current_snapshot = _create_wave_from_current_snapshot
    manager._sync_request_invoice_state = _sync_request_invoice_state
    manager._validate_request_expiry = lambda *_args, **_kwargs: None

    result = await manager.request_additional_coverage(
        request_id="req-1",
        payload=RequestAdditionalCoveragePayload(additional_slots=2, max_match_results=25),
        current_user=SimpleNamespace(id="user-1", username="ops", role="admin", tenant_uuid=""),
    )

    assert result["message"] == "Additional coverage requested"
    assert record.guards_required == 4
    assert captured["guards_required"] == 4
    assert record.pricing_snapshot["guards_required"] == 4
    assert invoice_calls == [(str(record.id), RequestInvoiceTrigger.ADDITIONAL_COVERAGE.value, "ops")]


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
async def test_list_jobs_excludes_soft_deleted_requests():
    deleted_request_id = ObjectId()
    manager = object.__new__(RequestManager)
    manager._engine = _FakeListJobsEngine(
        assignment_docs=[
            {
                "_id": ObjectId(),
                "request_id": str(deleted_request_id),
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
                "_id": deleted_request_id,
                "title": "Deleted Request",
                "site_snapshot": {"site_name": "Campus"},
                "fulfillment_mode": "individual_only",
                "target_type": "guard",
                "request_status": "closed",
                "staffing_status": "filled",
                "accepted_slots": 1,
                "open_slots": 0,
                "request_revision": 1,
                "requested_end_at": datetime(2026, 5, 18, 18, 0),
                "deleted_at": datetime(2026, 5, 20, 10, 0),
            },
        ],
        schedule_docs=[],
    )
    manager._role_value = lambda _user: "guard_admin"
    manager._is_platform_role = lambda _role: False

    async def _get_session_tenant(_current_user):
        return SimpleNamespace(id="guard-1", tenant_type="guard")

    manager._get_session_tenant = _get_session_tenant

    result = await manager.list_jobs(SimpleNamespace(role="guard_admin"), page=1, rows=10)

    assert result["pagination"]["total_items"] == 0
    assert result["items"] == []


@pytest.mark.anyio
async def test_list_jobs_guard_defaults_to_committed_work_without_auto_completing_shift_backed_jobs():
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
            "guards_required": 1,
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
            "guards_required": 1,
            "request_status": "submitted",
            "staffing_status": "open",
            "accepted_slots": 1,
            "open_slots": 0,
            "request_revision": 1,
            "requested_end_at": datetime(2026, 5, 18, 18, 0),
            "pricing_snapshot": {
                "client_hourly_quote": 39.0,
                "guard_hourly_pay": 25.5,
                "guard_company_margin": 13.5,
                "requested_hours_per_position": 8.0,
            },
            "invoicing_snapshot": {
                "contract_type": "short_term",
            },
        },
    ]
    manager._engine = _FakeListJobsEngine(
        assignment_docs=assignment_docs,
        request_docs=request_docs,
        schedule_docs=[
            {
                "_id": ObjectId(),
                "request_id": str(request_job_id),
                "active": True,
            },
        ],
    )
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
    assert result["items"][0]["request"]["has_schedule"] is True
    assert result["items"][0]["request"]["request_status"] == "submitted"
    assert result["items"][0]["request"]["pricing_snapshot"]["client_hourly_quote"] == 39.0
    assert result["items"][0]["request"]["pricing_snapshot"]["guard_company_margin"] == 13.5
    assert result["items"][0]["request"]["invoicing_snapshot"]["contract_type"] == "short_term"
    assert result["items"][0]["assignment_status"] == "accepted"
    assert assignment_docs[1]["assignment_status"] == "accepted"
    assert synced_request_ids == []


@pytest.mark.anyio
async def test_list_jobs_guard_auto_completes_elapsed_non_scheduled_jobs():
    accepted_assignment_id = ObjectId()
    request_job_id = ObjectId()
    manager = object.__new__(RequestManager)
    assignment_docs = [
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
    manager._engine = _FakeListJobsEngine(
        assignment_docs=assignment_docs,
        request_docs=[
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
        ],
        schedule_docs=[],
    )
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
        return record

    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state

    result = await manager.list_jobs(SimpleNamespace(role="guard_admin"), page=1, rows=10)

    assert result["pagination"]["total_items"] == 1
    assert result["items"][0]["request"]["has_schedule"] is False
    assert result["items"][0]["assignment_status"] == "completed"
    assert assignment_docs[0]["assignment_status"] == "completed"
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
                    "requested_end_at": datetime(2026, 5, 30, 18, 0),
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
async def test_update_job_status_provider_can_increase_committed_coverage(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: False
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)
    manager._dashboard_requests_url = lambda **_kwargs: "/dashboard/requests?tab=jobs&job=assign-1"
    manager._request_snapshot = lambda record: {"id": str(record.id), "title": record.title}
    manager._request_has_active_schedule = lambda _request_id: _async_return(False)

    accepted_at = datetime.utcnow() - timedelta(hours=1)
    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="provider-1",
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        assignment_origin="broadcast",
        assignment_scope=RequestAssignmentScope.REQUEST,
        broadcast_wave_id=None,
        shift_instance_id=None,
        shift_slot_id=None,
        request_revision_at_offer=1,
        slots_committed=2,
        response_due_at=None,
        reconfirmation_due_at=None,
        lock_reason=None,
        candidate_snapshot={},
        assigned_by_user_id="user-1",
        assigned_by_username="ops",
        offered_at=None,
        accepted_at=accepted_at,
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
        staffing_status=RequestStaffingStatus.PARTIALLY_FILLED,
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
        accepted_slots=2,
        open_slots=1,
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
            return {"shift_count": 1, "slot_count": 3}

    class _FakeMatchingManager:
        async def provider_available_guard_capacity(self, provider_tenant_id, payload):
            assert provider_tenant_id == "provider-1"
            assert payload.requested_guard_type == "armed"
            return {"linked_guard_count": 3, "available_guard_count": 1}

    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotifications()),
    )
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestShiftManager.get_instance",
        staticmethod(lambda: _FakeShiftManager()),
    )
    monkeypatch.setattr(
        "orion.api.interactive.request_manager.request_manager.RequestMatchingManager.get_instance",
        staticmethod(lambda: _FakeMatchingManager()),
    )

    payload = RequestAssignmentStatusUpdatePayload(
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        slots_committed=3,
    )

    response = await manager.update_job_status(
        str(assignment.id),
        payload,
        current_user=SimpleNamespace(role="sp_admin", tenant_uuid="provider-1"),
    )

    assert assignment.assignment_status == RequestAssignmentStatus.ACCEPTED
    assert assignment.slots_committed == 3
    assert assignment.accepted_at == accepted_at
    assert response["item"]["assignment_status"] == "accepted"
    assert response["item"]["slots_committed"] == 3
    assert len(notifications) == 2


@pytest.mark.anyio
async def test_update_job_status_provider_cannot_reduce_committed_coverage(monkeypatch):
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda _user: "sp_admin"
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: False
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="provider-1",
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        assignment_scope=RequestAssignmentScope.REQUEST,
        slots_committed=2,
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
        accepted_slots=2,
        open_slots=1,
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

    payload = RequestAssignmentStatusUpdatePayload(
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        slots_committed=1,
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="sp_admin", tenant_uuid="provider-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Committed provider coverage cannot be reduced from the currently accepted total"


@pytest.mark.anyio
async def test_update_job_status_rejects_scheduled_request_start():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: (
        current == RequestAssignmentStatus.ACCEPTED and nxt == RequestAssignmentStatus.IN_PROGRESS
    )
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        assignment_scope=RequestAssignmentScope.REQUEST,
        slots_committed=1,
        lock_reason=None,
    )
    record = _make_request_record(
        id="req-1",
        title="Scheduled Night Patrol",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.FILLED,
        open_slots=0,
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

    async def _request_has_active_schedule(_request_id):
        return True

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._request_has_active_schedule = _request_has_active_schedule

    payload = RequestAssignmentStatusUpdatePayload(assignment_status=RequestAssignmentStatus.IN_PROGRESS)

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Scheduled request jobs must use shift attendance actions instead of generic job status actions"


@pytest.mark.anyio
async def test_update_job_status_rejects_one_time_request_start_before_scheduled_start():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: (
        current == RequestAssignmentStatus.ACCEPTED and nxt == RequestAssignmentStatus.IN_PROGRESS
    )
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        assignment_scope=RequestAssignmentScope.REQUEST,
        slots_committed=1,
        lock_reason=None,
    )
    record = _make_request_record(
        id="req-1",
        title="One-Time Patrol",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.FILLED,
        open_slots=0,
        requested_start_at=datetime.utcnow() + timedelta(hours=2),
        requested_end_at=datetime.utcnow() + timedelta(hours=6),
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

    async def _request_has_active_schedule(_request_id):
        return False

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._request_has_active_schedule = _request_has_active_schedule

    payload = RequestAssignmentStatusUpdatePayload(assignment_status=RequestAssignmentStatus.IN_PROGRESS)

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Cannot start this job before its scheduled start time"


@pytest.mark.anyio
async def test_update_job_status_rejects_one_time_request_start_after_scheduled_end():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: (
        current == RequestAssignmentStatus.ACCEPTED and nxt == RequestAssignmentStatus.IN_PROGRESS
    )
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        assignment_scope=RequestAssignmentScope.REQUEST,
        slots_committed=1,
        lock_reason=None,
    )
    record = _make_request_record(
        id="req-1",
        title="Expired Patrol Window",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.FILLED,
        open_slots=0,
        requested_start_at=datetime.utcnow() - timedelta(hours=6),
        requested_end_at=datetime.utcnow() - timedelta(hours=1),
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

    async def _request_has_active_schedule(_request_id):
        return False

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._request_has_active_schedule = _request_has_active_schedule

    payload = RequestAssignmentStatusUpdatePayload(assignment_status=RequestAssignmentStatus.IN_PROGRESS)

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Cannot start this job after its scheduled end time"


@pytest.mark.anyio
async def test_update_job_status_rejects_one_time_request_completion_before_scheduled_start():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._role_value = lambda current_user: str(getattr(current_user, "role", "") or "")
    manager._is_platform_write_role = lambda _role: False
    manager._allowed_assignment_transition = lambda current, nxt: (
        current == RequestAssignmentStatus.IN_PROGRESS and nxt == RequestAssignmentStatus.COMPLETED
    )
    manager._assignment_scope_value = lambda _assignment: RequestAssignmentScope.REQUEST.value
    manager._assignment_slots = lambda assignment: int(getattr(assignment, "slots_committed", None) or 1)

    assignment = SimpleNamespace(
        id=ObjectId(),
        request_id="req-1",
        client_tenant_id="client-1",
        assignee_tenant_id="guard-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_status=RequestAssignmentStatus.IN_PROGRESS,
        assignment_scope=RequestAssignmentScope.REQUEST,
        slots_committed=1,
        lock_reason=None,
    )
    record = _make_request_record(
        id="req-1",
        title="Future Patrol",
        request_status=RequestStatus.SUBMITTED,
        staffing_status=RequestStaffingStatus.FILLED,
        open_slots=0,
        requested_start_at=datetime.utcnow() + timedelta(hours=3),
        requested_end_at=datetime.utcnow() + timedelta(hours=8),
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

    async def _request_has_active_schedule(_request_id):
        return False

    manager._get_assignment_or_404 = _get_assignment
    manager._get_session_tenant = _get_session_tenant
    manager._get_request_or_404 = _get_request
    manager._sync_request_runtime_state = _sync_request_runtime_state
    manager._request_has_active_schedule = _request_has_active_schedule

    payload = RequestAssignmentStatusUpdatePayload(assignment_status=RequestAssignmentStatus.COMPLETED)

    with pytest.raises(HTTPException) as exc_info:
        await manager.update_job_status(
            str(assignment.id),
            payload,
            current_user=SimpleNamespace(role="guard_admin", tenant_uuid="guard-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Cannot complete this job before its scheduled start time"


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
    manager._request_has_active_schedule = lambda _request_id: _async_return(False)

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
    manager._request_has_active_schedule = lambda _request_id: _async_return(False)

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
