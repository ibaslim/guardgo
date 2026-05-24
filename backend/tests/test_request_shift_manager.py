from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord,
    ProviderRosterPayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestAssignmentScope,
    RequestBroadcastWaveRecord,
    RequestInvoiceTrigger,
    RequestWaveStatus,
    RequestScheduleTemplateRecord,
    RequestScheduleType,
    RequestScheduleUpsertPayload,
    RequestStatus,
    RequestTargetType,
    ShiftAttendanceEventRecord,
    ShiftAttendanceEventType,
    ShiftGuardLeaveCreatePayload,
    ShiftGuardLeaveReconcilePayload,
    ShiftGuardLeaveRecord,
    ShiftGuardLeaveReturnDecisionAction,
    ShiftGuardLeaveReturnPayload,
    ShiftGuardLeaveStatus,
    ShiftCoverageSourceType,
    ShiftInstanceRecord,
    ShiftSlotCheckInPayload,
    ShiftSlotCheckOutPayload,
    ShiftSlotClientConfirmPayload,
    ShiftSlotReopenPayload,
    ShiftSlotRecord,
    ShiftSlotStartPayload,
    ShiftSlotUnavailablePayload,
    ShiftSlotStatus,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import GuardOwnershipType, TenantStatus, TenantType, db_tenant_model


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)
        self._skip = 0
        self._limit = None

    def sort(self, key, direction):
        reverse = direction == -1
        self._docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def skip(self, value):
        self._skip = max(int(value or 0), 0)
        return self

    def limit(self, value):
        self._limit = max(int(value or 0), 0)
        return self

    async def to_list(self, length=None):
        docs = self._docs[self._skip:]
        limit = self._limit if self._limit is not None else length
        if limit is not None:
            docs = docs[:limit]
        return docs


class FakeShiftCollection:
    def __init__(self, engine):
        self.engine = engine

    async def delete_many(self, query):
        remaining = []
        for shift in self.engine.shift_instances:
            if shift.request_id != query.get("request_id"):
                remaining.append(shift)
                continue
            if shift.schedule_template_id != query.get("schedule_template_id"):
                remaining.append(shift)
                continue
            threshold = query.get("shift_end_at_utc", {}).get("$gte")
            if threshold and shift.shift_end_at_utc < threshold:
                remaining.append(shift)
        self.engine.shift_instances = remaining

    async def count_documents(self, query):
        return len(self._matching_docs(query))

    def find(self, query):
        return FakeCursor(self._matching_docs(query))

    def _matching_docs(self, query):
        request_value = query.get("request_id", {})
        request_ids = set(request_value.get("$in", [])) if isinstance(request_value, dict) else set()
        id_filter = query.get("_id", {}).get("$in", [])
        client_tenant_id = query.get("client_tenant_id")
        status_value = query.get("instance_status")
        date_filter = query.get("shift_date_local", {})
        date_gte = date_filter.get("$gte")
        date_lte = date_filter.get("$lte")
        docs = []
        for shift in self.engine.shift_instances:
            if id_filter and shift.id not in id_filter:
                continue
            if request_ids and shift.request_id not in request_ids:
                continue
            if query.get("request_id") and not isinstance(query.get("request_id"), dict) and shift.request_id != query.get("request_id"):
                continue
            if client_tenant_id and shift.client_tenant_id != client_tenant_id:
                continue
            if status_value and getattr(shift.instance_status, "value", shift.instance_status) != status_value:
                continue
            if date_gte and shift.shift_date_local < date_gte:
                continue
            if date_lte and shift.shift_date_local > date_lte:
                continue
            docs.append(
                {
                    "_id": shift.id,
                    "request_id": shift.request_id,
                    "client_tenant_id": shift.client_tenant_id,
                    "schedule_template_id": shift.schedule_template_id,
                    "shift_date_local": shift.shift_date_local,
                    "shift_start_at_utc": shift.shift_start_at_utc,
                    "shift_end_at_utc": shift.shift_end_at_utc,
                    "timezone": shift.timezone,
                    "instance_status": shift.instance_status.value,
                    "slots_required": shift.slots_required,
                    "slots_staffed": shift.slots_staffed,
                    "slots_checked_in": shift.slots_checked_in,
                    "slots_completed": shift.slots_completed,
                    "client_action_required": shift.client_action_required,
                    "roster_due_at": shift.roster_due_at,
                    "created_from_revision": shift.created_from_revision,
                    "cancel_reason": shift.cancel_reason,
                    "reduction_reason": shift.reduction_reason,
                    "created_at": shift.created_at,
                    "updated_at": shift.updated_at,
                }
            )
        return docs


class FakeSlotCollection:
    def __init__(self, engine):
        self.engine = engine

    async def count_documents(self, query):
        return len(self._matching_docs(query))

    def find(self, query):
        return FakeCursor(self._matching_docs(query))

    def _matching_docs(self, query):
        docs = []
        id_filter = query.get("_id", {}).get("$in", [])
        shift_id = query.get("shift_instance_id")
        shift_id_in = shift_id.get("$in", []) if isinstance(shift_id, dict) else []
        coverage_tenant_id = query.get("coverage_tenant_id")
        request_id = query.get("request_id")
        slot_status = query.get("slot_status")
        slot_status_in = slot_status.get("$in", []) if isinstance(slot_status, dict) else []
        or_filter = query.get("$or") or []
        for slot in self.engine.shift_slots:
            if id_filter and slot.id not in id_filter:
                continue
            if shift_id_in and slot.shift_instance_id not in shift_id_in:
                continue
            if shift_id and not isinstance(shift_id, dict) and slot.shift_instance_id != shift_id:
                continue
            if coverage_tenant_id and slot.coverage_tenant_id != coverage_tenant_id:
                continue
            if request_id and slot.request_id != request_id:
                continue
            if slot_status_in and slot.slot_status.value not in slot_status_in:
                continue
            if slot_status and not isinstance(slot_status, dict) and slot.slot_status.value != slot_status:
                continue
            if or_filter:
                matched = False
                for branch in or_filter:
                    branch_guard = branch.get("assigned_guard_tenant_id")
                    branch_coverage = branch.get("coverage_tenant_id")
                    if branch_guard and slot.assigned_guard_tenant_id == branch_guard:
                        matched = True
                    if branch_coverage and slot.coverage_tenant_id == branch_coverage:
                        matched = True
                if not matched:
                    continue
            docs.append(
                {
                    "_id": slot.id,
                    "shift_instance_id": slot.shift_instance_id,
                    "request_id": slot.request_id,
                    "client_tenant_id": slot.client_tenant_id,
                    "parent_assignment_id": slot.parent_assignment_id,
                    "slot_number": slot.slot_number,
                    "coverage_slot_index": slot.coverage_slot_index,
                    "coverage_source_type": slot.coverage_source_type.value if slot.coverage_source_type else None,
                    "coverage_tenant_id": slot.coverage_tenant_id,
                    "service_provider_tenant_id": slot.service_provider_tenant_id,
                    "assigned_guard_tenant_id": slot.assigned_guard_tenant_id,
                    "slot_status": slot.slot_status.value,
                    "replacement_of_slot_id": slot.replacement_of_slot_id,
                    "rostered_at": slot.rostered_at,
                    "roster_due_at": slot.roster_due_at,
                    "guard_unavailable_reported_at": slot.guard_unavailable_reported_at,
                    "arrived_at": slot.arrived_at,
                    "client_confirmed_at": slot.client_confirmed_at,
                    "started_at": slot.started_at,
                    "checked_out_at": slot.checked_out_at,
                    "completed_at": slot.completed_at,
                    "no_show_confirmed_at": slot.no_show_confirmed_at,
                    "geo_check_passed": slot.geo_check_passed,
                    "actual_start_at": slot.actual_start_at,
                    "actual_end_at": slot.actual_end_at,
                    "created_at": slot.created_at,
                    "updated_at": slot.updated_at,
                }
            )
        return docs


class FakeEventCollection:
    def __init__(self, engine):
        self.engine = engine

    def find(self, query):
        docs = []
        shift_slot_id = query.get("shift_slot_id")
        for event in self.engine.shift_events:
            if shift_slot_id and event.shift_slot_id != shift_slot_id:
                continue
            docs.append(
                {
                    "_id": event.id,
                    "shift_slot_id": event.shift_slot_id,
                    "shift_instance_id": event.shift_instance_id,
                    "request_id": event.request_id,
                    "event_type": event.event_type.value,
                    "actor_user_id": event.actor_user_id,
                    "actor_role": event.actor_role,
                    "guard_tenant_id": event.guard_tenant_id,
                    "service_provider_tenant_id": event.service_provider_tenant_id,
                    "client_tenant_id": event.client_tenant_id,
                    "timestamp": event.timestamp,
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "distance_meters": event.distance_meters,
                    "note": event.note,
                    "metadata": event.metadata,
                }
            )
        return FakeCursor(docs)


class FakeRequestCollection:
    def __init__(self, engine):
        self.engine = engine

    def find(self, query):
        docs = []
        id_filter = query.get("_id", {}).get("$in", [])
        deleted_at = query.get("deleted_at") if isinstance(query, dict) else None
        request_records = [self.engine.request_record] if self.engine.request_record else []
        for record in request_records:
            if record is None:
                continue
            if id_filter and getattr(record, "id", None) not in id_filter:
                continue
            if deleted_at is None and getattr(record, "deleted_at", None) is not None:
                continue
            docs.append({
                "_id": record.id,
                "title": getattr(record, "title", None),
                "site_snapshot": getattr(record, "site_snapshot", None),
                "deleted_at": getattr(record, "deleted_at", None),
            })
        return FakeCursor(docs)


class FakeAssignmentCollection:
    def __init__(self, engine):
        self.engine = engine

    def find(self, query):
        docs = []
        assignment_scope = query.get("assignment_scope")
        assignment_status_filter = query.get("assignment_status", {})
        allowed_statuses = assignment_status_filter.get("$in", []) if isinstance(assignment_status_filter, dict) else []
        client_tenant_id = query.get("client_tenant_id")
        assignee_tenant_id = query.get("assignee_tenant_id")
        for assignment in self.engine.request_assignments:
            current_scope = getattr(getattr(assignment, "assignment_scope", None), "value", getattr(assignment, "assignment_scope", None))
            current_status = getattr(getattr(assignment, "assignment_status", None), "value", getattr(assignment, "assignment_status", None))
            if assignment_scope and current_scope != assignment_scope:
                continue
            if allowed_statuses and current_status not in allowed_statuses:
                continue
            if client_tenant_id and getattr(assignment, "client_tenant_id", None) != client_tenant_id:
                continue
            if assignee_tenant_id and getattr(assignment, "assignee_tenant_id", None) != assignee_tenant_id:
                continue
            docs.append(
                {
                    "_id": assignment.id,
                    "request_id": assignment.request_id,
                    "client_tenant_id": assignment.client_tenant_id,
                    "assignee_tenant_id": assignment.assignee_tenant_id,
                    "assignment_scope": current_scope,
                    "assignment_status": current_status,
                }
            )
        return FakeCursor(docs)


class FakeEngine:
    def __init__(self):
        self.request_record = None
        self.schedule_record = None
        self.shift_instances = []
        self.shift_slots = []
        self.shift_events = []
        self.shift_guard_leaves = []
        self.tenants = []
        self.request_assignments = []
        self.request_waves = []

    async def save(self, model):
        if getattr(model, "id", None) is None:
            object.__setattr__(model, "id", ObjectId())
        if isinstance(model, RequestScheduleTemplateRecord):
            self.schedule_record = model
            return model
        if isinstance(model, ShiftInstanceRecord):
            self.shift_instances = [item for item in self.shift_instances if str(item.id) != str(model.id)]
            self.shift_instances.append(model)
            return model
        if isinstance(model, ShiftSlotRecord):
            self.shift_slots = [item for item in self.shift_slots if str(item.id) != str(model.id)]
            self.shift_slots.append(model)
            return model
        if isinstance(model, ShiftAttendanceEventRecord):
            self.shift_events = [item for item in self.shift_events if str(item.id) != str(model.id)]
            self.shift_events.append(model)
            return model
        if isinstance(model, ShiftGuardLeaveRecord):
            self.shift_guard_leaves = [item for item in self.shift_guard_leaves if str(item.id) != str(model.id)]
            self.shift_guard_leaves.append(model)
            return model
        if isinstance(model, RequestAssignmentRecord):
            self.request_assignments = [item for item in self.request_assignments if str(item.id) != str(model.id)]
            self.request_assignments.append(model)
            return model
        if isinstance(model, RequestBroadcastWaveRecord):
            self.request_waves = [item for item in self.request_waves if str(item.id) != str(model.id)]
            self.request_waves.append(model)
            return model
        if isinstance(model, db_tenant_model):
            self.tenants = [item for item in self.tenants if str(item.id) != str(model.id)]
            self.tenants.append(model)
            return model
        if self.request_record and str(getattr(model, "id", "")) == str(getattr(self.request_record, "id", "")):
            self.request_record = model
        return model

    async def find_one(self, model, _condition):
        query = dict(_condition) if isinstance(_condition, dict) else {}
        if model is RequestScheduleTemplateRecord:
            return self.schedule_record
        if model is ShiftInstanceRecord:
            target_id = query.get("_id", {}).get("$eq")
            if target_id is not None:
                for item in self.shift_instances:
                    if item.id == target_id:
                        return item
            return self.shift_instances[0] if self.shift_instances else None
        if model is ShiftSlotRecord:
            target_id = query.get("_id", {}).get("$eq")
            if target_id is not None:
                for item in self.shift_slots:
                    if item.id == target_id:
                        return item
            return self.shift_slots[0] if self.shift_slots else None
        if model is ShiftAttendanceEventRecord:
            return self.shift_events[0] if self.shift_events else None
        if model is ShiftGuardLeaveRecord:
            target_id = query.get("_id", {}).get("$eq")
            if target_id is not None:
                for item in self.shift_guard_leaves:
                    if item.id == target_id:
                        return item
            return self.shift_guard_leaves[0] if self.shift_guard_leaves else None
        if model is db_tenant_model:
            target_id = query.get("_id", {}).get("$eq")
            if target_id is not None:
                for item in self.tenants:
                    if item.id == target_id:
                        return item
            return self.tenants[0] if self.tenants else None
        return None

    async def find(self, model, _condition):
        if model is ShiftInstanceRecord:
            return list(self.shift_instances)
        if model is ShiftSlotRecord:
            return list(self.shift_slots)
        if model is ShiftAttendanceEventRecord:
            return list(self.shift_events)
        if model is ShiftGuardLeaveRecord:
            items = list(self.shift_guard_leaves)
            query = dict(_condition) if isinstance(_condition, dict) else {}
            guard_id = query.get("guard_tenant_id", {}).get("$eq") if isinstance(query.get("guard_tenant_id"), dict) else query.get("guard_tenant_id")
            leave_status = query.get("leave_status", {}).get("$eq") if isinstance(query.get("leave_status"), dict) else query.get("leave_status")
            if guard_id is not None:
                items = [item for item in items if item.guard_tenant_id == guard_id]
            if leave_status is not None:
                normalized_status = getattr(leave_status, "value", leave_status)
                items = [item for item in items if item.leave_status.value == normalized_status]
            return items
        if model is RequestBroadcastWaveRecord:
            return list(self.request_waves)
        return []

    async def delete(self, model):
        if isinstance(model, ShiftSlotRecord):
            self.shift_slots = [item for item in self.shift_slots if str(item.id) != str(model.id)]
        if isinstance(model, ShiftInstanceRecord):
            self.shift_instances = [item for item in self.shift_instances if str(item.id) != str(model.id)]
        if isinstance(model, ShiftGuardLeaveRecord):
            self.shift_guard_leaves = [item for item in self.shift_guard_leaves if str(item.id) != str(model.id)]

    def get_collection(self, model):
        if model is ShiftInstanceRecord:
            return FakeShiftCollection(self)
        if model is ShiftSlotRecord:
            return FakeSlotCollection(self)
        if model is ShiftAttendanceEventRecord:
            return FakeEventCollection(self)
        if model is ClientRequestRecord:
            return FakeRequestCollection(self)
        if model is RequestAssignmentRecord:
            return FakeAssignmentCollection(self)
        raise AssertionError(f"Unexpected collection request: {model}")


def _make_request(**overrides):
    base = {
        "id": ObjectId(),
        "client_tenant_id": "tenant-client-1",
        "title": "Mall day shift",
        "request_status": RequestStatus.DRAFT,
        "deleted_at": None,
        "expired_at": None,
        "guards_required": 2,
        "request_revision": 1,
        "site_snapshot": {
            "site_name": "Demo site",
            "site_address": {
                "latitude": 24.8607,
                "longitude": 67.0011,
            }
        },
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_assignment(**overrides):
    base = {
        "id": ObjectId(),
        "request_id": "unused",
        "client_tenant_id": "tenant-client-1",
        "assignee_tenant_id": "tenant-guard-1",
        "assignee_tenant_type": RequestTargetType.GUARD,
        "assignment_status": RequestAssignmentStatus.ACCEPTED,
        "slots_committed": 1,
        "assigned_by_user_id": "admin-1",
        "assigned_by_username": "admin",
        "accepted_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }
    base.update(overrides)
    return RequestAssignmentRecord(**base)


def _fake_request_manager(
    request_record,
    assignments=None,
    tenants=None,
    engine=None,
    schedule_finance_sync=None,
    invoice_sync=None,
):
    assignments = list(assignments or [])
    tenants = dict(tenants or {})

    class FakeRequestManager:
        _engine = engine

        async def _get_request_or_404(self, _request_id):
            return request_record

        async def _sync_request_runtime_state(self, record):
            return record

        async def _assert_request_write_access(self, record, current_user):
            return None

        async def _can_view_request(self, record, current_user):
            return True

        async def _resolve_request_docs_for_role(self, current_user):
            return [{"_id": request_record.id}]

        async def _get_assignments_for_request(self, _request_id):
            return list(assignments)

        async def _get_assignment_or_404(self, assignment_id):
            for assignment in assignments:
                if str(getattr(assignment, "id", "") or "") == str(assignment_id):
                    return assignment
            raise AssertionError(f"Assignment not found: {assignment_id}")

        async def _get_tenant(self, tenant_id):
            return tenants.get(str(tenant_id))

        async def _write_activity(self, **kwargs):
            return None

        async def _sync_request_finance_snapshot_for_schedule(self, record, schedule_record):
            if schedule_finance_sync is None:
                return None
            return await schedule_finance_sync(record, schedule_record)

        async def _sync_request_invoice_state(self, record, *, current_user, reason):
            if invoice_sync is None:
                return None
            return await invoice_sync(record, current_user=current_user, reason=reason)

        async def _close_open_offers_for_request(self, *args, **kwargs):
            return 0

        async def _set_wave_status(self, wave, next_status, **kwargs):
            wave.wave_status = next_status
            return wave

        async def create_shift_replacement_wave(self, record, **kwargs):
            coverage_source_type = str(kwargs.get("original_coverage_source_type") or "").strip().lower()
            wave_status = (
                RequestWaveStatus.PENDING_REVIEW
                if coverage_source_type == ShiftCoverageSourceType.DIRECT_GUARD.value
                else RequestWaveStatus.ACTIVE
            )
            return SimpleNamespace(
                id=ObjectId(),
                request_id=str(record.id),
                wave_status=wave_status,
                wave_number=1,
            )

        @staticmethod
        def _serialize_wave(wave):
            return {"id": str(wave.id), "wave_status": getattr(getattr(wave, "wave_status", None), "value", getattr(wave, "wave_status", None))}

        @staticmethod
        def _assignment_slots(assignment):
            return int(getattr(assignment, "slots_committed", None) or 1)

        @staticmethod
        def _assignment_scope_value(assignment):
            return str(getattr(getattr(assignment, "assignment_scope", None), "value", getattr(assignment, "assignment_scope", "request")))

        @staticmethod
        def _role_value(current_user):
            return str(getattr(current_user, "role", "") or "").strip().lower()

        @staticmethod
        def _is_platform_write_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}

        @staticmethod
        def _is_platform_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}

        @staticmethod
        def _is_soft_deleted(record):
            return getattr(record, "deleted_at", None) is not None

        @classmethod
        def _assert_not_soft_deleted(cls, record):
            if cls._is_soft_deleted(record):
                raise HTTPException(status_code=404, detail="Request not found")

        async def _get_session_tenant(self, current_user):
            tenant = tenants.get(str(getattr(current_user, "tenant_uuid", "") or ""))
            if tenant:
                return tenant
            role_value = self._role_value(current_user)
            tenant_type = TenantType.SERVICE_PROVIDER
            if role_value == "client_admin":
                tenant_type = TenantType.CLIENT
            elif role_value == "guard_admin":
                tenant_type = TenantType.GUARD
            return SimpleNamespace(id=getattr(current_user, "tenant_uuid", ""), tenant_type=tenant_type, status=TenantStatus.ACTIVE)

    return FakeRequestManager()


def _stub_notifications(monkeypatch):
    class FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **kwargs):
            return None

        async def create_for_platform_admin_users(self, **kwargs):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeNotificationManager()))


@pytest.mark.anyio
async def test_upsert_request_schedule_generates_recurring_overnight_shifts(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request()
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record),
    )

    today = date.today() + timedelta(days=1)
    payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.RECURRING_WEEKLY,
        start_date=today,
        end_date=today + timedelta(days=9),
        start_time_local="22:00",
        end_time_local="06:00",
        recurrence_days=["mon", "wed", "fri"],
        generation_horizon_days=10,
    )

    response = await manager.upsert_request_schedule("req-1", payload, current_user=SimpleNamespace(username="tester"))

    generated = sorted(engine.shift_instances, key=lambda item: item.shift_start_at_utc)
    assert response["schedule"]["schedule_type"] == "recurring_weekly"
    assert response["schedule"]["is_overnight"] is True
    assert response["schedule"]["generated_shift_count"] == len(generated)
    assert len(generated) >= 1
    for shift in generated:
        assert shift.slots_required == 2
        assert shift.shift_end_at_utc > shift.shift_start_at_utc
        assert shift.roster_due_at == shift.shift_start_at_utc - timedelta(minutes=120)


@pytest.mark.anyio
async def test_upsert_request_schedule_syncs_long_term_finance_snapshot(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request(invoicing_snapshot={"contract_type": "short_term"})
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine

    captured = {}

    async def _schedule_finance_sync(record, schedule_record):
        captured["request_id"] = str(record.id)
        captured["schedule_type"] = getattr(schedule_record.schedule_type, "value", schedule_record.schedule_type)
        record.invoicing_snapshot = {"contract_type": "long_term"}
        return None

    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, schedule_finance_sync=_schedule_finance_sync),
    )

    today = date.today() + timedelta(days=1)
    payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.RECURRING_WEEKLY,
        start_date=today,
        end_date=today + timedelta(days=14),
        start_time_local="08:00",
        end_time_local="16:00",
        recurrence_days=["mon", "wed"],
        generation_horizon_days=14,
    )

    response = await manager.upsert_request_schedule("req-1", payload, current_user=SimpleNamespace(username="tester"))

    assert response["schedule"]["schedule_type"] == "recurring_weekly"
    assert captured["request_id"] == str(request_record.id)
    assert captured["schedule_type"] == "recurring_weekly"
    assert request_record.invoicing_snapshot["contract_type"] == "long_term"


@pytest.mark.anyio
async def test_upsert_request_schedule_syncs_invoice_for_live_request(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request(request_status=RequestStatus.SUBMITTED, invoicing_snapshot={"contract_type": "short_term"})
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine

    invoice_calls = []

    async def _invoice_sync(record, *, current_user, reason):
        invoice_calls.append((str(record.id), getattr(reason, "value", reason), getattr(current_user, "username", "")))
        return None

    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, invoice_sync=_invoice_sync),
    )

    today = date.today() + timedelta(days=1)
    payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.DATE_RANGE,
        start_date=today,
        end_date=today + timedelta(days=3),
        start_time_local="08:00",
        end_time_local="16:00",
        generation_horizon_days=10,
    )

    await manager.upsert_request_schedule("req-1", payload, current_user=SimpleNamespace(username="tester"))

    assert invoice_calls == [(str(request_record.id), RequestInvoiceTrigger.SCHEDULE_UPDATED.value, "tester")]


@pytest.mark.anyio
async def test_upsert_request_schedule_replaces_future_shift_instances(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request()
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record),
    )

    today = date.today() + timedelta(days=1)
    first_payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.DATE_RANGE,
        start_date=today,
        end_date=today + timedelta(days=2),
        start_time_local="08:00",
        end_time_local="16:00",
        generation_horizon_days=30,
    )
    second_payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.DATE_RANGE,
        start_date=today,
        end_date=today + timedelta(days=1),
        start_time_local="09:00",
        end_time_local="17:00",
        generation_horizon_days=30,
    )

    await manager.upsert_request_schedule("req-1", first_payload, current_user=SimpleNamespace(username="tester"))
    initial_count = len(engine.shift_instances)
    await manager.upsert_request_schedule("req-1", second_payload, current_user=SimpleNamespace(username="tester"))

    assert initial_count == 3
    assert len(engine.shift_instances) == 2
    assert all(shift.shift_start_at_utc.hour == 4 for shift in engine.shift_instances)


@pytest.mark.anyio
async def test_list_shifts_filters_by_request_and_date(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request()
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record),
    )

    template = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.DATE_RANGE,
        start_date_local="2026-01-01",
        end_date_local="2026-01-03",
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(template, "id", ObjectId())
    engine.schedule_record = template
    for day in ("2026-01-01", "2026-01-02", "2026-01-03"):
        shift = ShiftInstanceRecord(
            request_id=str(request_record.id),
            client_tenant_id=request_record.client_tenant_id,
            schedule_template_id=str(template.id),
            shift_date_local=day,
            shift_start_at_utc=datetime.fromisoformat(f"{day}T03:00:00"),
            shift_end_at_utc=datetime.fromisoformat(f"{day}T11:00:00"),
            timezone="Asia/Karachi",
        )
        object.__setattr__(shift, "id", ObjectId())
        engine.shift_instances.append(shift)

    response = await manager.list_shifts(
        current_user=SimpleNamespace(username="tester", role="client_admin", tenant_uuid=request_record.client_tenant_id),
        request_id=str(request_record.id),
        date_from=date.fromisoformat("2026-01-02"),
        date_to=date.fromisoformat("2026-01-03"),
    )

    assert response["pagination"]["total_items"] == 2
    assert [item["shift_date_local"] for item in response["items"]] == ["2026-01-02", "2026-01-03"]
    assert response["items"][0]["request_title"] == request_record.title
    assert response["items"][0]["site_name"] == request_record.site_snapshot["site_name"]


@pytest.mark.anyio
async def test_list_shifts_excludes_soft_deleted_requests(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request(
        request_status=RequestStatus.CLOSED,
        deleted_at=datetime.utcnow(),
    )
    engine.request_record = request_record
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, engine=engine),
    )

    template = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local="2026-01-01",
        end_date_local="2026-01-01",
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(template, "id", ObjectId())
    engine.schedule_record = template

    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(template.id),
        shift_date_local="2026-01-01",
        shift_start_at_utc=datetime.fromisoformat("2026-01-01T03:00:00"),
        shift_end_at_utc=datetime.fromisoformat("2026-01-01T11:00:00"),
        timezone="Asia/Karachi",
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)

    response = await manager.list_shifts(
        current_user=SimpleNamespace(username="tester", role="client_admin", tenant_uuid=request_record.client_tenant_id),
    )

    assert response["items"] == []


@pytest.mark.anyio
async def test_schedule_upsert_generates_direct_provider_and_open_slots(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request(guards_required=4, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    provider_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="provider-1",
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        slots_committed=2,
    )
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment, provider_assignment]),
    )

    today = date.today()
    payload = RequestScheduleUpsertPayload(
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date=today,
        start_time_local="20:00",
        end_time_local="04:00",
    )

    response = await manager.upsert_request_schedule("req-1", payload, current_user=SimpleNamespace(username="tester"))

    assert response["schedule"]["generated_shift_count"] == 1
    assert response["schedule"]["generated_slot_count"] == 4
    assert len(engine.shift_slots) == 4
    direct_slots = [slot for slot in engine.shift_slots if slot.coverage_source_type == ShiftCoverageSourceType.DIRECT_GUARD]
    provider_slots = [slot for slot in engine.shift_slots if slot.coverage_source_type == ShiftCoverageSourceType.SERVICE_PROVIDER]
    open_slots = [slot for slot in engine.shift_slots if slot.slot_status == ShiftSlotStatus.OPEN]
    assert len(direct_slots) == 1
    assert len(provider_slots) == 2
    assert len(open_slots) == 1
    assert direct_slots[0].assigned_guard_tenant_id == "guard-direct-1"
    assert all(slot.slot_status == ShiftSlotStatus.RESERVED for slot in provider_slots)


@pytest.mark.anyio
async def test_sync_shift_slots_for_request_creates_system_generated_shift_for_committed_non_scheduled_job(monkeypatch):
    engine = FakeEngine()
    start_at = datetime.utcnow() + timedelta(days=1, hours=2)
    end_at = start_at + timedelta(hours=2)
    request_record = _make_request(
        guards_required=1,
        request_status=RequestStatus.SUBMITTED,
        requested_start_at=start_at,
        requested_end_at=end_at,
    )
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    engine.request_assignments = [direct_assignment]

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[direct_assignment],
            engine=engine,
        ),
    )

    result = await manager.sync_shift_slots_for_request(request_record)

    assert result == {"shift_count": 1, "slot_count": 1}
    assert engine.schedule_record is not None
    assert engine.schedule_record.active is True
    assert engine.schedule_record.system_generated is True
    assert len(engine.shift_instances) == 1
    implicit_shift = engine.shift_instances[0]
    assert implicit_shift.shift_start_at_utc == start_at.replace(microsecond=(start_at.microsecond // 1000) * 1000)
    assert implicit_shift.shift_end_at_utc == end_at.replace(microsecond=(end_at.microsecond // 1000) * 1000)
    assert len(engine.shift_slots) == 1
    implicit_slot = engine.shift_slots[0]
    assert implicit_slot.slot_status == ShiftSlotStatus.RESERVED
    assert implicit_slot.assigned_guard_tenant_id == "guard-direct-1"
    assert str(direct_assignment.shift_instance_id or "") == str(implicit_shift.id)
    assert str(direct_assignment.shift_slot_id or "") == str(implicit_slot.id)


@pytest.mark.anyio
async def test_sync_shift_slots_for_request_allows_implicit_attendance_shift_after_request_expiry(monkeypatch):
    engine = FakeEngine()
    start_at = datetime.utcnow() + timedelta(days=1, hours=1)
    end_at = start_at + timedelta(hours=9)
    request_record = _make_request(
        guards_required=1,
        request_status=RequestStatus.SUBMITTED,
        expired_at=datetime.utcnow() - timedelta(hours=1),
        requested_start_at=start_at,
        requested_end_at=end_at,
    )
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    engine.request_assignments = [direct_assignment]

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[direct_assignment],
            engine=engine,
        ),
    )

    result = await manager.sync_shift_slots_for_request(request_record)

    assert result == {"shift_count": 1, "slot_count": 1}
    assert engine.schedule_record is not None
    assert engine.schedule_record.system_generated is True
    assert len(engine.shift_instances) == 1
    assert len(engine.shift_slots) == 1


@pytest.mark.anyio
async def test_check_in_shift_slot_uses_actor_timezone_for_system_generated_shift(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    start_at = datetime.utcnow() + timedelta(days=1, hours=2)
    end_at = start_at + timedelta(hours=1)
    request_record = _make_request(
        guards_required=1,
        request_status=RequestStatus.SUBMITTED,
        requested_start_at=start_at,
        requested_end_at=end_at,
    )
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    engine.request_assignments = [direct_assignment]

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[direct_assignment],
            engine=engine,
        ),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    shift = engine.shift_instances[0]
    assert engine.schedule_record.system_generated is True

    def fake_runtime_now(_cls, shift_record, schedule_record=None, *, actor_timezone=None):
        if actor_timezone == "Asia/Karachi":
            return shift_record.shift_start_at_utc - timedelta(minutes=10)
        return shift_record.shift_start_at_utc - timedelta(minutes=121)

    monkeypatch.setattr(RequestShiftManager, "_runtime_now_for_shift", classmethod(fake_runtime_now))

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(
            latitude=24.8608,
            longitude=67.0012,
            note="arrived",
            timezone="Asia/Karachi",
        ),
        SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1"),
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING
    assert slot.arrived_at is not None


@pytest.mark.anyio
async def test_start_shift_slot_uses_actor_timezone_for_system_generated_shift_and_persists_utc_now(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    start_at = datetime.utcnow() + timedelta(days=1, hours=2)
    end_at = start_at + timedelta(hours=1)
    request_record = _make_request(
        guards_required=1,
        request_status=RequestStatus.SUBMITTED,
        requested_start_at=start_at,
        requested_end_at=end_at,
    )
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    engine.request_assignments = [direct_assignment]

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[direct_assignment],
            engine=engine,
        ),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    shift = engine.shift_instances[0]
    assert engine.schedule_record.system_generated is True

    def fake_runtime_now(_cls, shift_record, schedule_record=None, *, actor_timezone=None):
        if actor_timezone == "Asia/Karachi":
            return shift_record.shift_start_at_utc + timedelta(minutes=10)
        return shift_record.shift_start_at_utc - timedelta(minutes=5)

    fixed_utc_now = datetime.utcnow().replace(microsecond=0)
    monkeypatch.setattr(RequestShiftManager, "_runtime_now_for_shift", classmethod(fake_runtime_now))
    monkeypatch.setattr(RequestShiftManager, "_utc_now", staticmethod(lambda: fixed_utc_now))

    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")
    client_user = SimpleNamespace(username="client", role="client_admin", tenant_uuid=request_record.client_tenant_id)

    slot.arrived_at = fixed_utc_now - timedelta(minutes=5)
    slot.slot_status = ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING
    await engine.save(slot)

    await manager.confirm_shift_slot_arrival(
        str(slot.id),
        ShiftSlotClientConfirmPayload(note="ok"),
        client_user,
    )

    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start", timezone="Asia/Karachi"),
        guard_user,
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.IN_PROGRESS
    assert slot.started_at == fixed_utc_now
    assert slot.actual_start_at == fixed_utc_now


@pytest.mark.anyio
async def test_roster_shift_assigns_provider_guard_to_provider_slot(monkeypatch):
    engine = FakeEngine()
    request_record = _make_request(guards_required=3, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    provider_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="provider-1",
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        slots_committed=2,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=4),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=12),
        timezone="Asia/Karachi",
        slots_required=3,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)

    provider_tenant = SimpleNamespace(id="provider-1", tenant_type=TenantType.SERVICE_PROVIDER, status=TenantStatus.ACTIVE)
    provider_guard = SimpleNamespace(
        id="guard-provider-1",
        tenant_type=TenantType.GUARD,
        status=TenantStatus.ACTIVE,
        service_provider_tenant_id="provider-1",
    )
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[provider_assignment],
            tenants={
                "provider-1": provider_tenant,
                "guard-provider-1": provider_guard,
            },
        ),
    )

    await manager.sync_shift_slots_for_request(request_record)
    provider_slot = next(slot for slot in engine.shift_slots if slot.coverage_source_type == ShiftCoverageSourceType.SERVICE_PROVIDER)
    payload = ProviderRosterPayload(assignments=[{"slot_id": str(provider_slot.id), "guard_tenant_id": "guard-provider-1"}])

    result = await manager.roster_shift(
        shift_id=str(shift.id),
        payload=payload,
        current_user=SimpleNamespace(username="tester", role="sp_admin", tenant_uuid="provider-1"),
    )

    updated_slot = next(slot for slot in engine.shift_slots if str(slot.id) == str(provider_slot.id))
    assert updated_slot.assigned_guard_tenant_id == "guard-provider-1"
    assert updated_slot.slot_status == ShiftSlotStatus.ROSTERED
    assert result["slot_summary"]["rostered_slots"] >= 1


@pytest.mark.anyio
async def test_shift_slot_attendance_flow_updates_slot_shift_and_events(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")
    client_user = SimpleNamespace(username="client", role="client_admin", tenant_uuid=request_record.client_tenant_id)

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )
    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING
    assert slot.arrived_at is not None
    assert shift.slots_checked_in == 1

    await manager.confirm_shift_slot_arrival(
        str(slot.id),
        ShiftSlotClientConfirmPayload(note="ok"),
        client_user,
    )
    slot = engine.shift_slots[0]
    assert slot.client_confirmed_at is not None
    assert slot.slot_status == ShiftSlotStatus.RESERVED
    assert shift.client_action_required is False

    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start"),
        guard_user,
    )
    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.IN_PROGRESS
    assert slot.started_at is not None
    assert direct_assignment.assignment_status == RequestAssignmentStatus.IN_PROGRESS
    assert request_record.request_status == RequestStatus.IN_PROGRESS
    assert shift.instance_status == "in_progress" or getattr(shift.instance_status, "value", shift.instance_status) == "in_progress"

    await manager.check_out_shift_slot(
        str(slot.id),
        ShiftSlotCheckOutPayload(note="done"),
        guard_user,
    )
    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.COMPLETED
    assert slot.completed_at is not None
    assert getattr(shift.instance_status, "value", shift.instance_status) == "completed"
    assert shift.slots_completed == 1
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.CHECKIN_ATTEMPTED,
        ShiftAttendanceEventType.ARRIVED,
        ShiftAttendanceEventType.CLIENT_CONFIRMED,
        ShiftAttendanceEventType.STARTED,
        ShiftAttendanceEventType.CHECKOUT,
        ShiftAttendanceEventType.COMPLETED,
    ]


@pytest.mark.anyio
async def test_shift_slot_attendance_flow_emits_notifications_after_confirmation(monkeypatch):
    tenant_notifications: list[dict] = []

    class FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **kwargs):
            tenant_notifications.append(kwargs)
            return None

        async def create_for_platform_admin_users(self, **kwargs):
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeNotificationManager()))

    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")
    client_user = SimpleNamespace(username="client", role="client_admin", tenant_uuid=request_record.client_tenant_id)

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )
    await manager.confirm_shift_slot_arrival(
        str(slot.id),
        ShiftSlotClientConfirmPayload(note="ok"),
        client_user,
    )
    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start"),
        guard_user,
    )
    await manager.check_out_shift_slot(
        str(slot.id),
        ShiftSlotCheckOutPayload(note="done"),
        guard_user,
    )

    titles = [str(item.get("title") or "") for item in tenant_notifications]
    assert "Guard arrived on site" in titles
    assert "Arrival confirmed" in titles
    assert "Shift started" in titles
    assert "Shift checked out" in titles


@pytest.mark.anyio
async def test_completed_shift_marks_parent_assignment_completed_only_after_schedule_window_elapses(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    yesterday = date.today() - timedelta(days=1)
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="UTC",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=yesterday.isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=yesterday.isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=2),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=1),
        timezone="UTC",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)

    sync_calls = []

    class FakeRequestManager:
        async def _get_request_or_404(self, _request_id):
            return request_record

        async def _sync_request_runtime_state(self, record):
            sync_calls.append(str(record.id))
            return record

        async def _get_assignments_for_request(self, _request_id):
            return [direct_assignment]

        async def _get_assignment_or_404(self, assignment_id):
            assert str(direct_assignment.id) == str(assignment_id)
            return direct_assignment

        async def _get_session_tenant(self, current_user):
            return SimpleNamespace(id=getattr(current_user, "tenant_uuid", ""), tenant_type=TenantType.GUARD, status=TenantStatus.ACTIVE)

        @staticmethod
        def _assignment_slots(assignment):
            return int(getattr(assignment, "slots_committed", None) or 1)

        @staticmethod
        def _assignment_scope_value(assignment):
            return str(getattr(getattr(assignment, "assignment_scope", None), "value", getattr(assignment, "assignment_scope", "request")))

        @staticmethod
        def _role_value(current_user):
            return str(getattr(current_user, "role", "") or "").strip().lower()

        @staticmethod
        def _is_platform_write_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}

        @staticmethod
        def _is_platform_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: FakeRequestManager(),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )
    slot = engine.shift_slots[0]

    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start"),
        SimpleNamespace(username="ops", role="admin", tenant_uuid=""),
    )
    assert direct_assignment.assignment_status == RequestAssignmentStatus.IN_PROGRESS

    await manager.check_out_shift_slot(
        str(slot.id),
        ShiftSlotCheckOutPayload(note="done"),
        guard_user,
    )

    assert direct_assignment.assignment_status == RequestAssignmentStatus.COMPLETED
    assert direct_assignment.completed_at is not None
    assert sync_calls


@pytest.mark.anyio
async def test_completed_one_time_shift_marks_parent_assignment_completed_before_shift_end(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    today = date.today()
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="UTC",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=today.isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=today.isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=2),
        timezone="UTC",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)

    sync_calls = []

    class FakeRequestManager:
        async def _get_request_or_404(self, _request_id):
            return request_record

        async def _sync_request_runtime_state(self, record):
            sync_calls.append(str(record.id))
            return record

        async def _get_assignments_for_request(self, _request_id):
            return [direct_assignment]

        async def _get_assignment_or_404(self, assignment_id):
            assert str(direct_assignment.id) == str(assignment_id)
            return direct_assignment

        async def _get_session_tenant(self, current_user):
            return SimpleNamespace(id=getattr(current_user, "tenant_uuid", ""), tenant_type=TenantType.GUARD, status=TenantStatus.ACTIVE)

        @staticmethod
        def _assignment_slots(assignment):
            return int(getattr(assignment, "slots_committed", None) or 1)

        @staticmethod
        def _assignment_scope_value(assignment):
            return str(getattr(getattr(assignment, "assignment_scope", None), "value", getattr(assignment, "assignment_scope", "request")))

        @staticmethod
        def _role_value(current_user):
            return str(getattr(current_user, "role", "") or "").strip().lower()

        @staticmethod
        def _is_platform_write_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}

        @staticmethod
        def _is_platform_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}

    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: FakeRequestManager(),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )
    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start"),
        SimpleNamespace(username="ops", role="admin", tenant_uuid=""),
    )
    await manager.check_out_shift_slot(
        str(slot.id),
        ShiftSlotCheckOutPayload(note="done"),
        guard_user,
    )

    assert direct_assignment.assignment_status == RequestAssignmentStatus.COMPLETED
    assert direct_assignment.completed_at is not None
    assert sync_calls


@pytest.mark.anyio
async def test_platform_start_override_without_client_confirmation_records_override(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")
    admin_user = SimpleNamespace(username="admin", role="admin", tenant_uuid="admin-tenant")
    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )

    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="override"),
        admin_user,
    )

    assert [event.event_type for event in engine.shift_events][-2:] == [
        ShiftAttendanceEventType.OPS_START_OVERRIDE,
        ShiftAttendanceEventType.STARTED,
    ]


@pytest.mark.anyio
async def test_start_shift_slot_rejects_before_scheduled_start(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=2),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=10),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")
    client_user = SimpleNamespace(username="client", role="client_admin", tenant_uuid=request_record.client_tenant_id)

    await manager.check_in_shift_slot(
        str(slot.id),
        ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="arrived"),
        guard_user,
    )
    await manager.confirm_shift_slot_arrival(
        str(slot.id),
        ShiftSlotClientConfirmPayload(note="ok"),
        client_user,
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager.start_shift_slot(
            str(slot.id),
            ShiftSlotStartPayload(note="too early"),
            guard_user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Cannot start the shift before its scheduled start time"


@pytest.mark.anyio
async def test_check_in_shift_slot_rejects_after_shift_end(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    yesterday = date.today() - timedelta(days=1)
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=yesterday.isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=yesterday.isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(hours=10),
        shift_end_at_utc=datetime.utcnow() - timedelta(hours=2),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    slot = ShiftSlotRecord(
        shift_instance_id=str(shift.id),
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        parent_assignment_id=str(direct_assignment.id),
        slot_number=1,
        coverage_slot_index=1,
        coverage_source_type=ShiftCoverageSourceType.DIRECT_GUARD,
        coverage_tenant_id="guard-direct-1",
        service_provider_tenant_id=None,
        assigned_guard_tenant_id="guard-direct-1",
        slot_status=ShiftSlotStatus.RESERVED,
        roster_due_at=None,
    )
    object.__setattr__(slot, "id", ObjectId())
    engine.shift_slots.append(slot)

    with pytest.raises(HTTPException) as exc_info:
        await manager.check_in_shift_slot(
            str(slot.id),
            ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="too late"),
            SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Cannot check in after the shift has ended"


@pytest.mark.anyio
async def test_check_in_shift_slot_rejects_before_pre_start_window(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
        checkin_geofence_meters=300,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=5),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=13),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    with pytest.raises(HTTPException) as exc_info:
        await manager.check_in_shift_slot(
            str(slot.id),
            ShiftSlotCheckInPayload(latitude=24.8608, longitude=67.0012, note="too early"),
            SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1"),
        )

    assert exc_info.value.status_code == 409
    assert "Check-in opens 120 minutes before shift start" in exc_info.value.detail
    assert "(Asia/Karachi)." in exc_info.value.detail


@pytest.mark.anyio
async def test_platform_report_shift_slot_unavailable_before_cutoff_marks_slot_unavailable(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=4),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=12),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    ops_user = SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant")

    await manager.report_shift_slot_unavailable(
        str(slot.id),
        ShiftSlotUnavailablePayload(note="family emergency"),
        ops_user,
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.UNAVAILABLE
    assert slot.guard_unavailable_reported_at is not None
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert getattr(shift.instance_status, "value", shift.instance_status) == "scheduled"
    assert engine.shift_events[-1].event_type == ShiftAttendanceEventType.UNAVAILABLE_REPORTED
    assert engine.shift_events[-1].metadata["platform_override"] is True


@pytest.mark.anyio
async def test_platform_report_shift_slot_unavailable_after_cutoff_marks_late_risk(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=50),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=8),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    ops_user = SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant")

    await manager.report_shift_slot_unavailable(
        str(slot.id),
        ShiftSlotUnavailablePayload(note="running late"),
        ops_user,
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.LATE_RISK
    assert slot.guard_unavailable_reported_at is not None
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert engine.shift_events[-1].event_type == ShiftAttendanceEventType.UNAVAILABLE_REPORTED
    assert engine.shift_events[-1].metadata["late_risk"] is True
    assert engine.shift_events[-1].metadata["platform_override"] is True


@pytest.mark.anyio
async def test_guard_cannot_use_platform_unavailable_override_path(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=4),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=12),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    with pytest.raises(HTTPException) as exc_info:
        await manager.report_shift_slot_unavailable(
            str(slot.id),
            ShiftSlotUnavailablePayload(note="family emergency"),
            SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1"),
        )

    assert exc_info.value.status_code == 403
    assert "leave flow" in str(exc_info.value.detail)


@pytest.mark.anyio
async def test_get_shift_slot_triggers_late_arrival_transition_and_escalation_notifications(monkeypatch):
    notifications = {"tenant": [], "platform": []}

    class FakeNotificationManager:
        async def create_for_tenant_admin_users(self, **kwargs):
            notifications["tenant"].append(kwargs)
            return None

        async def create_for_platform_admin_users(self, **kwargs):
            notifications["platform"].append(kwargs)
            return None

    monkeypatch.setattr(NotificationManager, "get_instance", staticmethod(lambda: FakeNotificationManager()))
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        late_grace_minutes=15,
        no_show_cutoff_minutes=30,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(minutes=20),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    result = await manager.get_shift_slot_by_id(
        str(slot.id),
        current_user=SimpleNamespace(username="admin", role="admin", tenant_uuid="admin-tenant"),
    )

    slot = engine.shift_slots[0]
    assert result["slot"]["slot_status"] == ShiftSlotStatus.LATE_RISK.value
    assert slot.slot_status == ShiftSlotStatus.LATE_RISK
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert [event.event_type for event in engine.shift_events] == [ShiftAttendanceEventType.LATE_ARRIVAL]
    tenant_targets = {item["tenant_id"] for item in notifications["tenant"]}
    assert tenant_targets == {request_record.client_tenant_id, "guard-direct-1"}
    assert len(notifications["platform"]) == 1
    assert notifications["tenant"][0]["source_module"] == "requests"


@pytest.mark.anyio
async def test_get_shift_slot_triggers_no_show_confirmed_transition(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        late_grace_minutes=15,
        no_show_cutoff_minutes=30,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(minutes=40),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]

    result = await manager.get_shift_slot_by_id(
        str(slot.id),
        current_user=SimpleNamespace(username="admin", role="admin", tenant_uuid="admin-tenant"),
    )
    repeat_result = await manager.get_shift_slot_by_id(
        str(slot.id),
        current_user=SimpleNamespace(username="admin", role="admin", tenant_uuid="admin-tenant"),
    )

    slot = next(saved_slot for saved_slot in engine.shift_slots if str(saved_slot.id) == str(slot.id))
    assert result["slot"]["slot_status"] == ShiftSlotStatus.NO_SHOW_CONFIRMED.value
    assert repeat_result["slot"]["slot_status"] == ShiftSlotStatus.NO_SHOW_CONFIRMED.value
    assert slot.slot_status == ShiftSlotStatus.NO_SHOW_CONFIRMED
    assert slot.no_show_confirmed_at is not None
    assert len(engine.shift_slots) == 1
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.LATE_ARRIVAL,
        ShiftAttendanceEventType.NO_SHOW_CONFIRMED,
    ]


@pytest.mark.anyio
async def test_list_shift_exceptions_returns_runtime_no_show_slots(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        late_grace_minutes=15,
        no_show_cutoff_minutes=30,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() - timedelta(minutes=40),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=7),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    response = await manager.list_shift_exceptions(
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
        exception_status=ShiftSlotStatus.NO_SHOW_CONFIRMED.value,
    )

    assert response["pagination"]["total_items"] == 1
    assert response["items"][0]["slot"]["slot_status"] == ShiftSlotStatus.NO_SHOW_CONFIRMED.value
    assert response["items"][0]["request"]["title"] == request_record.title


@pytest.mark.anyio
async def test_reopen_shift_slot_creates_replacement_slot_and_wave(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id="guard-direct-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=4),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=12),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    original_slot = engine.shift_slots[0]
    await manager.report_shift_slot_unavailable(
        str(original_slot.id),
        ShiftSlotUnavailablePayload(note="need emergency refill"),
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
    )

    result = await manager.reopen_shift_slot(
        str(original_slot.id),
        ShiftSlotReopenPayload(note="need emergency refill", max_match_results=40),
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
    )

    assert result["message"] == "Shift slot reopened for replacement"
    assert len(engine.shift_slots) == 2
    original_slot = next(slot for slot in engine.shift_slots if str(slot.id) == str(original_slot.id))
    replacement_slot = next(slot for slot in engine.shift_slots if str(slot.id) != str(original_slot.id))
    assert original_slot.slot_status == ShiftSlotStatus.REPLACEMENT_REQUIRED
    assert replacement_slot.slot_status == ShiftSlotStatus.OPEN
    assert replacement_slot.replacement_of_slot_id == str(original_slot.id)
    assert result["wave"]["wave_status"] == RequestWaveStatus.PENDING_REVIEW.value
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.UNAVAILABLE_REPORTED,
        ShiftAttendanceEventType.REPLACEMENT_REQUESTED,
    ]


@pytest.mark.anyio
async def test_report_guard_leave_direct_guard_marks_selected_shift_unavailable(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    guard_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439011"),
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.PLATFORM,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.append(guard_tenant)

    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id=str(guard_tenant.id),
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
        unavailable_cutoff_minutes=120,
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=90),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9, minutes=30),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    response = await manager.report_guard_leave(
        ShiftGuardLeaveCreatePayload(
            start_at_utc=datetime.utcnow() + timedelta(minutes=30),
            end_at_utc=datetime.utcnow() + timedelta(hours=12),
            reason="medical leave",
        ),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    assert response["message"] == "Guard leave recorded"
    assert response["summary"]["affected_slot_count"] == 1
    assert response["summary"]["replacement_slot_count"] == 0
    assert len(engine.shift_guard_leaves) == 1
    leave_record = engine.shift_guard_leaves[0]
    assert leave_record.leave_status == ShiftGuardLeaveStatus.ACTIVE
    assert len(leave_record.affected_slot_ids) == 1
    assert len(leave_record.replacement_slot_ids) == 0
    assert leave_record.start_at_utc == shift.shift_start_at_utc
    assert leave_record.end_at_utc == shift.shift_end_at_utc

    original_slot = engine.shift_slots[0]
    assert original_slot.slot_status == ShiftSlotStatus.UNAVAILABLE
    assert [event.event_type for event in engine.shift_events] == [ShiftAttendanceEventType.LEAVE_REPORTED]


@pytest.mark.anyio
async def test_report_guard_leave_provider_backed_marks_slot_unavailable_without_replacement(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    provider_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439012"),
        tenant_type=TenantType.SERVICE_PROVIDER,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    guard_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439013"),
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id=str(provider_tenant.id),
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.extend([provider_tenant, guard_tenant])

    provider_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id=str(provider_tenant.id),
        assignee_tenant_type=RequestTargetType.SERVICE_PROVIDER,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=90),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9, minutes=30),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(
            request_record,
            assignments=[provider_assignment],
            tenants={
                str(provider_tenant.id): provider_tenant,
                str(guard_tenant.id): guard_tenant,
            },
        ),
    )

    await manager.sync_shift_slots_for_request(request_record)
    slot = engine.shift_slots[0]
    slot.assigned_guard_tenant_id = str(guard_tenant.id)
    slot.slot_status = ShiftSlotStatus.ROSTERED
    await engine.save(slot)

    response = await manager.report_guard_leave(
        ShiftGuardLeaveCreatePayload(
            start_at_utc=datetime.utcnow() + timedelta(minutes=30),
            end_at_utc=datetime.utcnow() + timedelta(hours=12),
            reason="family emergency",
        ),
        current_user=SimpleNamespace(id="guard-user-2", username="provider-guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    assert response["summary"]["affected_slot_count"] == 1
    assert response["summary"]["replacement_slot_count"] == 0
    assert len(engine.shift_slots) == 1
    assert engine.shift_slots[0].slot_status == ShiftSlotStatus.UNAVAILABLE
    assert engine.shift_events[0].event_type == ShiftAttendanceEventType.LEAVE_REPORTED


@pytest.mark.anyio
async def test_report_guard_leave_rejects_service_provider_admin_actor(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    provider_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439112"),
        tenant_type=TenantType.SERVICE_PROVIDER,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.append(provider_tenant)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, tenants={str(provider_tenant.id): provider_tenant}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await manager.report_guard_leave(
            ShiftGuardLeaveCreatePayload(
                guard_tenant_id="guard-provider-1",
                start_at_utc=datetime.utcnow() + timedelta(minutes=30),
                end_at_utc=datetime.utcnow() + timedelta(hours=3),
                reason="not allowed from provider admin",
            ),
            current_user=SimpleNamespace(id="sp-user-1", username="provider", role="sp_admin", tenant_uuid=str(provider_tenant.id)),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only the assigned guard can report leave for their own upcoming shift"


@pytest.mark.anyio
async def test_return_guard_leave_early_restores_future_slot_and_cancels_open_replacement(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    guard_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439014"),
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.PLATFORM,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.append(guard_tenant)
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id=str(guard_tenant.id),
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=90),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9, minutes=30),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=[direct_assignment]),
    )

    await manager.sync_shift_slots_for_request(request_record)
    create_response = await manager.report_guard_leave(
        ShiftGuardLeaveCreatePayload(
            start_at_utc=datetime.utcnow() + timedelta(minutes=30),
            end_at_utc=datetime.utcnow() + timedelta(hours=12),
            reason="planned leave",
        ),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    leave_id = create_response["item"]["id"]
    original_slot = engine.shift_slots[0]
    assert original_slot.slot_status == ShiftSlotStatus.UNAVAILABLE

    await manager.reopen_shift_slot(
        str(original_slot.id),
        ShiftSlotReopenPayload(note="client requested replacement", max_match_results=25),
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
    )

    original_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id is None)
    replacement_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id == str(original_slot.id))
    assert original_slot.slot_status == ShiftSlotStatus.REPLACEMENT_REQUIRED
    assert replacement_slot.slot_status == ShiftSlotStatus.OPEN

    return_response = await manager.return_guard_leave_early(
        leave_id,
        ShiftGuardLeaveReturnPayload(note="back earlier than planned"),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    assert return_response["message"] == "Guard leave ended early"
    assert return_response["summary"]["restored_slot_count"] == 1
    assert return_response["summary"]["cancelled_replacement_slot_count"] == 1
    leave_record = engine.shift_guard_leaves[0]
    assert leave_record.leave_status == ShiftGuardLeaveStatus.RETURNED_EARLY

    original_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id is None)
    replacement_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id == str(original_slot.id))
    assert original_slot.slot_status == ShiftSlotStatus.RESERVED
    assert replacement_slot.slot_status == ShiftSlotStatus.CANCELLED
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.LEAVE_REPORTED,
        ShiftAttendanceEventType.REPLACEMENT_REQUESTED,
        ShiftAttendanceEventType.LEAVE_RETURNED,
    ]


@pytest.mark.anyio
async def test_get_guard_leave_return_review_flags_reserved_replacement_for_manual_review(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    guard_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439015"),
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.PLATFORM,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.append(guard_tenant)
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id=str(guard_tenant.id),
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    assignments = [direct_assignment]
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=90),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9, minutes=30),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=assignments, engine=engine),
    )

    await manager.sync_shift_slots_for_request(request_record)
    create_response = await manager.report_guard_leave(
        ShiftGuardLeaveCreatePayload(
            start_at_utc=datetime.utcnow() + timedelta(minutes=30),
            end_at_utc=datetime.utcnow() + timedelta(hours=12),
            reason="planned leave",
        ),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    leave_id = create_response["item"]["id"]
    original_slot = engine.shift_slots[0]
    await manager.reopen_shift_slot(
        str(original_slot.id),
        ShiftSlotReopenPayload(note="client requested replacement", max_match_results=25),
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
    )
    original_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id is None)
    replacement_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id == str(original_slot.id))
    replacement_assignment = _make_assignment(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        assignee_tenant_id="guard-replacement-1",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_scope=RequestAssignmentScope.SHIFT_REPLACEMENT,
        shift_slot_id=str(replacement_slot.id),
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        slots_committed=1,
    )
    assignments.append(replacement_assignment)
    replacement_slot.parent_assignment_id = str(replacement_assignment.id)
    replacement_slot.coverage_source_type = ShiftCoverageSourceType.DIRECT_GUARD
    replacement_slot.coverage_tenant_id = replacement_assignment.assignee_tenant_id
    replacement_slot.assigned_guard_tenant_id = replacement_assignment.assignee_tenant_id
    replacement_slot.slot_status = ShiftSlotStatus.RESERVED
    await engine.save(replacement_slot)

    review = await manager.get_guard_leave_return_review(
        leave_id,
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    assert review["summary"]["decision_required_count"] == 1
    assert review["summary"]["auto_restore_count"] == 0
    assert len(review["items"]) == 1
    item = review["items"][0]
    assert item["review_mode"] == "manual_review"
    assert item["can_restore_original"] is True
    assert item["can_keep_replacement"] is True
    assert item["replacement_assignment_status"] == RequestAssignmentStatus.ACCEPTED.value
    assert item["replacement_slot_status"] == ShiftSlotStatus.RESERVED.value


@pytest.mark.anyio
async def test_reconcile_guard_leave_return_restores_reserved_replacement_to_original_guard(monkeypatch):
    _stub_notifications(monkeypatch)
    engine = FakeEngine()
    request_record = _make_request(guards_required=1, request_status=RequestStatus.SUBMITTED)
    engine.request_record = request_record
    guard_tenant = db_tenant_model(
        id=ObjectId("507f1f77bcf86cd799439016"),
        tenant_type=TenantType.GUARD,
        ownership_type=GuardOwnershipType.PLATFORM,
        status=TenantStatus.ACTIVE,
        profile={},
    )
    engine.tenants.append(guard_tenant)
    direct_assignment = _make_assignment(
        request_id=str(request_record.id),
        assignee_tenant_id=str(guard_tenant.id),
        assignee_tenant_type=RequestTargetType.GUARD,
        slots_committed=1,
    )
    assignments = [direct_assignment]
    schedule = RequestScheduleTemplateRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        timezone="Asia/Karachi",
        schedule_type=RequestScheduleType.ONE_TIME,
        start_date_local=date.today().isoformat(),
        end_date_local=None,
        start_time_local="08:00",
        end_time_local="16:00",
    )
    object.__setattr__(schedule, "id", ObjectId())
    engine.schedule_record = schedule
    shift = ShiftInstanceRecord(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        schedule_template_id=str(schedule.id),
        shift_date_local=date.today().isoformat(),
        shift_start_at_utc=datetime.utcnow() + timedelta(minutes=90),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9, minutes=30),
        timezone="Asia/Karachi",
        slots_required=1,
    )
    object.__setattr__(shift, "id", ObjectId())
    engine.shift_instances.append(shift)
    manager = object.__new__(RequestShiftManager)
    manager._engine = engine
    monkeypatch.setattr(
        "orion.api.interactive.request_shift_manager.request_shift_manager.RequestManager.get_instance",
        lambda: _fake_request_manager(request_record, assignments=assignments, engine=engine),
    )

    await manager.sync_shift_slots_for_request(request_record)
    create_response = await manager.report_guard_leave(
        ShiftGuardLeaveCreatePayload(
            start_at_utc=datetime.utcnow() + timedelta(minutes=30),
            end_at_utc=datetime.utcnow() + timedelta(hours=12),
            reason="planned leave",
        ),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    leave_id = create_response["item"]["id"]
    original_slot = engine.shift_slots[0]
    await manager.reopen_shift_slot(
        str(original_slot.id),
        ShiftSlotReopenPayload(note="client requested replacement", max_match_results=25),
        current_user=SimpleNamespace(username="ops", role="ops_admin", tenant_uuid="ops-tenant"),
    )
    original_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id is None)
    replacement_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id == str(original_slot.id))
    replacement_assignment = _make_assignment(
        request_id=str(request_record.id),
        client_tenant_id=request_record.client_tenant_id,
        assignee_tenant_id="guard-replacement-2",
        assignee_tenant_type=RequestTargetType.GUARD,
        assignment_scope=RequestAssignmentScope.SHIFT_REPLACEMENT,
        shift_slot_id=str(replacement_slot.id),
        assignment_status=RequestAssignmentStatus.ACCEPTED,
        slots_committed=1,
    )
    assignments.append(replacement_assignment)
    replacement_slot.parent_assignment_id = str(replacement_assignment.id)
    replacement_slot.coverage_source_type = ShiftCoverageSourceType.DIRECT_GUARD
    replacement_slot.coverage_tenant_id = replacement_assignment.assignee_tenant_id
    replacement_slot.assigned_guard_tenant_id = replacement_assignment.assignee_tenant_id
    replacement_slot.slot_status = ShiftSlotStatus.RESERVED
    await engine.save(replacement_slot)

    response = await manager.reconcile_guard_leave_return(
        leave_id,
        ShiftGuardLeaveReconcilePayload(
            note="original guard returned early",
            decisions=[
                {
                    "original_slot_id": str(original_slot.id),
                    "action": ShiftGuardLeaveReturnDecisionAction.RESTORE_ORIGINAL,
                }
            ],
        ),
        current_user=SimpleNamespace(id="guard-user-1", username="guard", role="guard_admin", tenant_uuid=str(guard_tenant.id)),
    )

    assert response["message"] == "Guard leave return reconciled"
    assert response["summary"]["restored_slot_count"] == 1
    assert response["summary"]["cancelled_replacement_slot_count"] == 1
    assert response["summary"]["cancelled_assignment_count"] == 1
    assert response["summary"]["kept_replacement_count"] == 0
    leave_record = engine.shift_guard_leaves[0]
    assert leave_record.leave_status == ShiftGuardLeaveStatus.RETURNED_EARLY

    original_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id is None)
    replacement_slot = next(slot for slot in engine.shift_slots if slot.replacement_of_slot_id == str(original_slot.id))
    assert original_slot.slot_status == ShiftSlotStatus.RESERVED
    assert replacement_slot.slot_status == ShiftSlotStatus.CANCELLED
    assert replacement_assignment.assignment_status == RequestAssignmentStatus.CANCELLED
    assert engine.shift_events[-1].event_type == ShiftAttendanceEventType.LEAVE_RETURNED
