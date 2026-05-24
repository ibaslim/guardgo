from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId

from orion.management.managers.request_shift_maintenance_manager import request_shift_maintenance_manager
from orion.services.mongo_manager.shared_model.db_notification_model import NotificationRecord
from orion.services.mongo_manager.shared_model.db_request_model import (
    RequestScheduleTemplateRecord,
    RequestStatus,
    ShiftInstanceRecord,
    ShiftInstanceStatus,
    ShiftSlotRecord,
    ShiftSlotStatus,
)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        docs = list(self._docs)
        if length is not None:
            docs = docs[:length]
        return docs


class _FakeShiftCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, query):
        start_query = query.get("shift_start_at_utc", {})
        allowed_statuses = set(query.get("instance_status", {}).get("$in", []))
        matched = []
        for doc in self._docs:
            if start_query.get("$gte") and doc["shift_start_at_utc"] < start_query["$gte"]:
                continue
            if start_query.get("$lte") and doc["shift_start_at_utc"] > start_query["$lte"]:
                continue
            if allowed_statuses and doc.get("instance_status") not in allowed_statuses:
                continue
            matched.append(doc)
        return _FakeCursor(matched)


class _FakeSlotCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, query):
        shift_ids = set(query.get("shift_instance_id", {}).get("$in", []))
        allowed_statuses = set(query.get("slot_status", {}).get("$in", []))
        matched = []
        for doc in self._docs:
            if shift_ids and doc.get("shift_instance_id") not in shift_ids:
                continue
            if allowed_statuses and doc.get("slot_status") not in allowed_statuses:
                continue
            if query.get("assigned_guard_tenant_id", {}).get("$ne") is None and doc.get("assigned_guard_tenant_id") is None:
                continue
            if "arrived_at" in query and doc.get("arrived_at") != query.get("arrived_at"):
                continue
            matched.append(doc)
        return _FakeCursor(matched)


class _FakeNotificationCollection:
    async def count_documents(self, _query):
        return 0


class _FakeScheduleCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, query):
        active_filter = query.get("active")
        matched = [
            doc
            for doc in self._docs
            if active_filter is None or bool(doc.get("active")) == bool(active_filter)
        ]
        return _FakeCursor(matched)


class _FakeEngine:
    def __init__(self, shift_docs, slot_docs, schedule_docs=None):
        self._shift_docs = list(shift_docs)
        self._slot_docs = list(slot_docs)
        self._schedule_docs = list(schedule_docs or [])

    def get_collection(self, model):
        if model is ShiftInstanceRecord:
            return _FakeShiftCollection(self._shift_docs)
        if model is ShiftSlotRecord:
            return _FakeSlotCollection(self._slot_docs)
        if model is RequestScheduleTemplateRecord:
            return _FakeScheduleCollection(self._schedule_docs)
        if model is NotificationRecord:
            return _FakeNotificationCollection()
        raise AssertionError(f"Unexpected collection request: {model}")


class _FrozenDateTime(datetime):
    current = datetime(2026, 5, 23, 10, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.current.astimezone(tz)
        return cls.current.replace(tzinfo=None)


@pytest.mark.anyio
async def test_guard_checkin_reminder_only_targets_slots_in_final_five_minutes(monkeypatch):
    now = _FrozenDateTime.current.replace(tzinfo=None)
    shift_due_id = str(ObjectId())
    shift_later_id = str(ObjectId())
    slot_due_id = str(ObjectId())
    slot_later_id = str(ObjectId())

    engine = _FakeEngine(
        shift_docs=[
            {
                "_id": shift_due_id,
                "request_id": "req-due",
                "shift_start_at_utc": now + timedelta(minutes=4),
                "instance_status": ShiftInstanceStatus.STAFFED.value,
            },
            {
                "_id": shift_later_id,
                "request_id": "req-later",
                "shift_start_at_utc": now + timedelta(minutes=20),
                "instance_status": ShiftInstanceStatus.STAFFED.value,
            },
        ],
        slot_docs=[
            {
                "_id": slot_due_id,
                "shift_instance_id": shift_due_id,
                "request_id": "req-due",
                "slot_status": ShiftSlotStatus.RESERVED.value,
                "assigned_guard_tenant_id": "guard-1",
                "arrived_at": None,
            },
            {
                "_id": slot_later_id,
                "shift_instance_id": shift_later_id,
                "request_id": "req-later",
                "slot_status": ShiftSlotStatus.RESERVED.value,
                "assigned_guard_tenant_id": "guard-2",
                "arrived_at": None,
            },
        ],
    )
    sent_notifications = []

    class _FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **kwargs):
            sent_notifications.append(kwargs)
            return 1

    class _FakeRequestManager:
        async def _get_request_or_404(self, request_id):
            title = "Retail Event Security – Vancouver" if request_id == "req-due" else "Later Shift"
            return SimpleNamespace(title=title)

    monkeypatch.setattr(
        "orion.management.managers.request_shift_maintenance_manager.datetime",
        _FrozenDateTime,
    )
    monkeypatch.setattr(
        "orion.management.managers.request_shift_maintenance_manager.NotificationManager.get_instance",
        staticmethod(lambda: _FakeNotificationManager()),
    )
    monkeypatch.setattr(
        "orion.management.managers.request_shift_maintenance_manager.RequestManager.get_instance",
        staticmethod(lambda: _FakeRequestManager()),
    )

    manager = object.__new__(request_shift_maintenance_manager)
    manager._engine = engine
    manager._task = None

    sent_count = await manager._send_guard_checkin_reminders()

    assert sent_count == 1
    assert len(sent_notifications) == 1
    assert sent_notifications[0]["tenant_id"] == "guard-1"
    assert sent_notifications[0]["title"] == "Shift starts in less than 5 minutes"
    assert sent_notifications[0]["action_url"] == f"/dashboard/requests?tab=shifts&slot={slot_due_id}"
    assert sent_notifications[0]["metadata"]["reminder_type"] == "guard_checkin_due"


@pytest.mark.anyio
async def test_sync_advance_request_invoices_only_counts_live_long_term_requests(monkeypatch):
    engine = _FakeEngine(
        shift_docs=[],
        slot_docs=[],
        schedule_docs=[
            {"request_id": "req-long", "active": True},
            {"request_id": "req-short", "active": True},
            {"request_id": "req-draft", "active": True},
        ],
    )
    synced = []

    request_lookup = {
        "req-long": SimpleNamespace(
            id="req-long",
            request_status=RequestStatus.SUBMITTED,
            expired_at=None,
            invoicing_snapshot={"contract_type": "long_term"},
        ),
        "req-short": SimpleNamespace(
            id="req-short",
            request_status=RequestStatus.SUBMITTED,
            expired_at=None,
            invoicing_snapshot={"contract_type": "short_term"},
        ),
        "req-draft": SimpleNamespace(
            id="req-draft",
            request_status=RequestStatus.DRAFT,
            expired_at=None,
            invoicing_snapshot={"contract_type": "long_term"},
        ),
    }

    class _FakeRequestManager:
        @staticmethod
        def _normalize_invoice_contract_type(value):
            return "long_term" if str(value or "").strip() == "long_term" else "short_term"

        async def _get_request_or_404(self, request_id):
            return request_lookup[request_id]

        async def _sync_request_invoice_state(self, record, *, current_user, reason):
            synced.append((record.id, current_user.username, getattr(reason, "value", reason)))
            return {"action": "created", "invoice": None}

    monkeypatch.setattr(
        "orion.management.managers.request_shift_maintenance_manager.RequestManager.get_instance",
        staticmethod(lambda: _FakeRequestManager()),
    )

    manager = object.__new__(request_shift_maintenance_manager)
    manager._engine = engine
    manager._task = None

    synced_count = await manager._sync_advance_request_invoices(limit=10)

    assert synced_count == 1
    assert synced == [("req-long", "system", "monthly_advance")]
