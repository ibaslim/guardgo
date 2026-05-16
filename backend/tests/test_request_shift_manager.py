from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId

from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ProviderRosterPayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestWaveStatus,
    RequestScheduleTemplateRecord,
    RequestScheduleType,
    RequestScheduleUpsertPayload,
    RequestStatus,
    RequestTargetType,
    ShiftAttendanceEventRecord,
    ShiftAttendanceEventType,
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
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType


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


class FakeEngine:
    def __init__(self):
        self.request_record = None
        self.schedule_record = None
        self.shift_instances = []
        self.shift_slots = []
        self.shift_events = []

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
        return None

    async def find(self, model, _condition):
        if model is ShiftInstanceRecord:
            return list(self.shift_instances)
        if model is ShiftSlotRecord:
            return list(self.shift_slots)
        if model is ShiftAttendanceEventRecord:
            return list(self.shift_events)
        return []

    async def delete(self, model):
        if isinstance(model, ShiftSlotRecord):
            self.shift_slots = [item for item in self.shift_slots if str(item.id) != str(model.id)]
        if isinstance(model, ShiftInstanceRecord):
            self.shift_instances = [item for item in self.shift_instances if str(item.id) != str(model.id)]

    def get_collection(self, model):
        if model is ShiftInstanceRecord:
            return FakeShiftCollection(self)
        if model is ShiftSlotRecord:
            return FakeSlotCollection(self)
        if model is ShiftAttendanceEventRecord:
            return FakeEventCollection(self)
        raise AssertionError(f"Unexpected collection request: {model}")


def _make_request(**overrides):
    base = {
        "id": ObjectId(),
        "client_tenant_id": "tenant-client-1",
        "title": "Mall day shift",
        "request_status": RequestStatus.DRAFT,
        "expired_at": None,
        "guards_required": 2,
        "request_revision": 1,
        "site_snapshot": {
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


def _fake_request_manager(request_record, assignments=None, tenants=None):
    assignments = list(assignments or [])
    tenants = dict(tenants or {})

    class FakeRequestManager:
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

        async def _get_tenant(self, tenant_id):
            return tenants.get(str(tenant_id))

        async def _write_activity(self, **kwargs):
            return None

        async def create_shift_replacement_wave(self, record, **kwargs):
            return SimpleNamespace(
                id=ObjectId(),
                request_id=str(record.id),
                wave_status=RequestWaveStatus.ACTIVE,
                wave_number=1,
            )

        @staticmethod
        def _serialize_wave(wave):
            return {"id": str(wave.id), "wave_status": getattr(getattr(wave, "wave_status", None), "value", getattr(wave, "wave_status", None))}

        @staticmethod
        def _assignment_slots(assignment):
            return int(getattr(assignment, "slots_committed", None) or 1)

        @staticmethod
        def _role_value(current_user):
            return str(getattr(current_user, "role", "") or "").strip().lower()

        @staticmethod
        def _is_platform_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin", "read_only_admin"}

        @staticmethod
        def _is_platform_write_role(role_value):
            return role_value in {"admin", "ops_admin", "support_admin", "compliance_admin"}

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

    today = date.today()
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

    today = date.today()
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
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9),
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

    await manager.start_shift_slot(
        str(slot.id),
        ShiftSlotStartPayload(note="start"),
        guard_user,
    )
    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.IN_PROGRESS
    assert slot.started_at is not None
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
        shift_start_at_utc=datetime.utcnow() + timedelta(hours=1),
        shift_end_at_utc=datetime.utcnow() + timedelta(hours=9),
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
async def test_report_shift_slot_unavailable_before_cutoff_marks_slot_unavailable(monkeypatch):
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
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")

    await manager.report_shift_slot_unavailable(
        str(slot.id),
        ShiftSlotUnavailablePayload(note="family emergency"),
        guard_user,
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.UNAVAILABLE
    assert slot.guard_unavailable_reported_at is not None
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert getattr(shift.instance_status, "value", shift.instance_status) == "scheduled"
    assert engine.shift_events[-1].event_type == ShiftAttendanceEventType.UNAVAILABLE_REPORTED


@pytest.mark.anyio
async def test_report_shift_slot_unavailable_after_cutoff_marks_late_risk(monkeypatch):
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
    guard_user = SimpleNamespace(username="guard", role="guard_admin", tenant_uuid="guard-direct-1")

    await manager.report_shift_slot_unavailable(
        str(slot.id),
        ShiftSlotUnavailablePayload(note="running late"),
        guard_user,
    )

    slot = engine.shift_slots[0]
    assert slot.slot_status == ShiftSlotStatus.LATE_RISK
    assert slot.guard_unavailable_reported_at is not None
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert engine.shift_events[-1].event_type == ShiftAttendanceEventType.UNAVAILABLE_REPORTED
    assert engine.shift_events[-1].metadata["late_risk"] is True


@pytest.mark.anyio
async def test_get_shift_slot_triggers_no_show_suspected_transition(monkeypatch):
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
    assert result["slot"]["slot_status"] == ShiftSlotStatus.NO_SHOW_SUSPECTED.value
    assert slot.slot_status == ShiftSlotStatus.NO_SHOW_SUSPECTED
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert [event.event_type for event in engine.shift_events] == [ShiftAttendanceEventType.NO_SHOW_SUSPECTED]


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

    slot = engine.shift_slots[0]
    assert result["slot"]["slot_status"] == ShiftSlotStatus.NO_SHOW_CONFIRMED.value
    assert slot.slot_status == ShiftSlotStatus.NO_SHOW_CONFIRMED
    assert slot.no_show_confirmed_at is not None
    assert shift.client_action_required is True
    assert shift.slots_staffed == 0
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.NO_SHOW_SUSPECTED,
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
    original_slot = engine.shift_slots[0]

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
    assert result["wave"]["wave_status"] == RequestWaveStatus.ACTIVE.value
    assert [event.event_type for event in engine.shift_events] == [
        ShiftAttendanceEventType.NO_SHOW_SUSPECTED,
        ShiftAttendanceEventType.NO_SHOW_CONFIRMED,
        ShiftAttendanceEventType.REPLACEMENT_REQUESTED,
    ]
