import threading
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord,
    ProviderRosterPayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestScheduleTemplateRecord,
    RequestScheduleType,
    RequestScheduleUpsertPayload,
    RequestStatus,
    ShiftAttendanceEventRecord,
    ShiftAttendanceEventType,
    ShiftCoverageSourceType,
    ShiftInstanceRecord,
    ShiftInstanceStatus,
    ShiftSlotCheckInPayload,
    ShiftSlotCheckOutPayload,
    ShiftSlotClientConfirmPayload,
    ShiftSlotReopenPayload,
    ShiftSlotRecord,
    ShiftSlotStartPayload,
    ShiftSlotUnavailablePayload,
    ShiftSlotStatus,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType, db_tenant_model


_WEEKDAY_TOKEN_TO_INDEX = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

_COMMITTED_ASSIGNMENT_STATUSES = {
    RequestAssignmentStatus.ACCEPTED,
    RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
    RequestAssignmentStatus.IN_PROGRESS,
    RequestAssignmentStatus.COMPLETED,
}

_SLOT_PRE_START_STATUSES = {
    ShiftSlotStatus.RESERVED,
    ShiftSlotStatus.ROSTERED,
    ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING,
}

_SLOT_STAFFED_STATUSES = {
    ShiftSlotStatus.RESERVED,
    ShiftSlotStatus.ROSTERED,
    ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING,
    ShiftSlotStatus.IN_PROGRESS,
    ShiftSlotStatus.COMPLETED,
}

_SLOT_CLIENT_ACTION_STATUSES = {
    ShiftSlotStatus.UNAVAILABLE,
    ShiftSlotStatus.LATE_RISK,
    ShiftSlotStatus.NO_SHOW_SUSPECTED,
    ShiftSlotStatus.NO_SHOW_CONFIRMED,
    ShiftSlotStatus.REPLACEMENT_REQUIRED,
}

_SHIFT_EXCEPTION_STATUSES = {
    ShiftSlotStatus.UNAVAILABLE,
    ShiftSlotStatus.LATE_RISK,
    ShiftSlotStatus.NO_SHOW_SUSPECTED,
    ShiftSlotStatus.NO_SHOW_CONFIRMED,
    ShiftSlotStatus.REPLACEMENT_REQUIRED,
}


class RequestShiftManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance() -> "RequestShiftManager":
        if RequestShiftManager.__instance is None:
            with RequestShiftManager.__lock:
                if RequestShiftManager.__instance is None:
                    RequestShiftManager.__instance = RequestShiftManager()
        return RequestShiftManager.__instance

    def __init__(self):
        if RequestShiftManager.__instance is not None:
            raise Exception("RequestShiftManager is a singleton")
        controller = mongo_controller.get_instance()
        if controller is None:
            raise RuntimeError("Mongo controller is not initialized")
        self._engine = controller.get_engine()

    @staticmethod
    def _serialize_schedule(record: RequestScheduleTemplateRecord, generated_shift_count: Optional[int] = None) -> Dict[str, Any]:
        payload = {
            "id": str(record.id),
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "timezone": record.timezone,
            "schedule_type": record.schedule_type.value,
            "start_date": record.start_date_local,
            "end_date": record.end_date_local,
            "start_time_local": record.start_time_local,
            "end_time_local": record.end_time_local,
            "is_overnight": bool(record.is_overnight),
            "recurrence_days": list(record.recurrence_days or []),
            "generation_horizon_days": int(record.generation_horizon_days or 0),
            "roster_due_offset_minutes": int(record.roster_due_offset_minutes or 0),
            "unavailable_cutoff_minutes": int(record.unavailable_cutoff_minutes or 0),
            "late_grace_minutes": int(record.late_grace_minutes or 0),
            "no_show_cutoff_minutes": int(record.no_show_cutoff_minutes or 0),
            "checkin_geofence_meters": int(record.checkin_geofence_meters or 0),
            "active": bool(record.active),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        if generated_shift_count is not None:
            payload["generated_shift_count"] = int(generated_shift_count)
        return payload

    @staticmethod
    def _serialize_shift(record: ShiftInstanceRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "request_id": record.get("request_id"),
                "client_tenant_id": record.get("client_tenant_id"),
                "schedule_template_id": record.get("schedule_template_id"),
                "shift_date_local": record.get("shift_date_local"),
                "shift_start_at_utc": record.get("shift_start_at_utc"),
                "shift_end_at_utc": record.get("shift_end_at_utc"),
                "timezone": record.get("timezone"),
                "instance_status": getattr(record.get("instance_status"), "value", record.get("instance_status")),
                "slots_required": int(record.get("slots_required") or 0),
                "slots_staffed": int(record.get("slots_staffed") or 0),
                "slots_checked_in": int(record.get("slots_checked_in") or 0),
                "slots_completed": int(record.get("slots_completed") or 0),
                "client_action_required": bool(record.get("client_action_required")),
                "roster_due_at": record.get("roster_due_at"),
                "created_from_revision": int(record.get("created_from_revision") or 0),
                "cancel_reason": record.get("cancel_reason"),
                "reduction_reason": record.get("reduction_reason"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }
        return {
            "id": str(record.id),
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "schedule_template_id": record.schedule_template_id,
            "shift_date_local": record.shift_date_local,
            "shift_start_at_utc": record.shift_start_at_utc,
            "shift_end_at_utc": record.shift_end_at_utc,
            "timezone": record.timezone,
            "instance_status": record.instance_status.value,
            "slots_required": int(record.slots_required or 0),
            "slots_staffed": int(record.slots_staffed or 0),
            "slots_checked_in": int(record.slots_checked_in or 0),
            "slots_completed": int(record.slots_completed or 0),
            "client_action_required": bool(record.client_action_required),
            "roster_due_at": record.roster_due_at,
            "created_from_revision": int(record.created_from_revision or 0),
            "cancel_reason": record.cancel_reason,
            "reduction_reason": record.reduction_reason,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _serialize_slot(record: ShiftSlotRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "shift_instance_id": record.get("shift_instance_id"),
                "request_id": record.get("request_id"),
                "client_tenant_id": record.get("client_tenant_id"),
                "parent_assignment_id": record.get("parent_assignment_id"),
                "slot_number": int(record.get("slot_number") or 0),
                "coverage_slot_index": int(record.get("coverage_slot_index") or 0),
                "coverage_source_type": getattr(record.get("coverage_source_type"), "value", record.get("coverage_source_type")),
                "coverage_tenant_id": record.get("coverage_tenant_id"),
                "service_provider_tenant_id": record.get("service_provider_tenant_id"),
                "assigned_guard_tenant_id": record.get("assigned_guard_tenant_id"),
                "slot_status": getattr(record.get("slot_status"), "value", record.get("slot_status")),
                "replacement_of_slot_id": record.get("replacement_of_slot_id"),
                "rostered_at": record.get("rostered_at"),
                "roster_due_at": record.get("roster_due_at"),
                "guard_unavailable_reported_at": record.get("guard_unavailable_reported_at"),
                "arrived_at": record.get("arrived_at"),
                "client_confirmed_at": record.get("client_confirmed_at"),
                "started_at": record.get("started_at"),
                "checked_out_at": record.get("checked_out_at"),
                "completed_at": record.get("completed_at"),
                "no_show_confirmed_at": record.get("no_show_confirmed_at"),
                "geo_check_passed": record.get("geo_check_passed"),
                "actual_start_at": record.get("actual_start_at"),
                "actual_end_at": record.get("actual_end_at"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }
        return {
            "id": str(record.id),
            "shift_instance_id": record.shift_instance_id,
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "parent_assignment_id": record.parent_assignment_id,
            "slot_number": int(record.slot_number or 0),
            "coverage_slot_index": int(record.coverage_slot_index or 0),
            "coverage_source_type": record.coverage_source_type.value if record.coverage_source_type else None,
            "coverage_tenant_id": record.coverage_tenant_id,
            "service_provider_tenant_id": record.service_provider_tenant_id,
            "assigned_guard_tenant_id": record.assigned_guard_tenant_id,
            "slot_status": record.slot_status.value,
            "replacement_of_slot_id": record.replacement_of_slot_id,
            "rostered_at": record.rostered_at,
            "roster_due_at": record.roster_due_at,
            "guard_unavailable_reported_at": record.guard_unavailable_reported_at,
            "arrived_at": record.arrived_at,
            "client_confirmed_at": record.client_confirmed_at,
            "started_at": record.started_at,
            "checked_out_at": record.checked_out_at,
            "completed_at": record.completed_at,
            "no_show_confirmed_at": record.no_show_confirmed_at,
            "geo_check_passed": record.geo_check_passed,
            "actual_start_at": record.actual_start_at,
            "actual_end_at": record.actual_end_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _serialize_event(record: ShiftAttendanceEventRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "shift_slot_id": record.get("shift_slot_id"),
                "shift_instance_id": record.get("shift_instance_id"),
                "request_id": record.get("request_id"),
                "event_type": getattr(record.get("event_type"), "value", record.get("event_type")),
                "actor_user_id": record.get("actor_user_id"),
                "actor_role": record.get("actor_role"),
                "guard_tenant_id": record.get("guard_tenant_id"),
                "service_provider_tenant_id": record.get("service_provider_tenant_id"),
                "client_tenant_id": record.get("client_tenant_id"),
                "timestamp": record.get("timestamp"),
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
                "distance_meters": record.get("distance_meters"),
                "note": record.get("note"),
                "metadata": record.get("metadata") or {},
            }
        return {
            "id": str(record.id),
            "shift_slot_id": record.shift_slot_id,
            "shift_instance_id": record.shift_instance_id,
            "request_id": record.request_id,
            "event_type": record.event_type.value,
            "actor_user_id": record.actor_user_id,
            "actor_role": record.actor_role,
            "guard_tenant_id": record.guard_tenant_id,
            "service_provider_tenant_id": record.service_provider_tenant_id,
            "client_tenant_id": record.client_tenant_id,
            "timestamp": record.timestamp,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "distance_meters": record.distance_meters,
            "note": record.note,
            "metadata": dict(record.metadata or {}),
        }

    @staticmethod
    def _parse_local_time(label: str, value: str) -> time:
        raw = str(value or "").strip()
        try:
            parsed = time.fromisoformat(raw)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid {label}. Use HH:MM 24-hour format")
        if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
            raise HTTPException(status_code=400, detail=f"Invalid {label}. Use HH:MM 24-hour format")
        return parsed

    @staticmethod
    def _resolve_timezone(value: str) -> ZoneInfo:
        raw = str(value or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="Timezone is required")
        try:
            return ZoneInfo(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid timezone")

    @staticmethod
    def _normalize_recurrence_days(values: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for value in values or []:
            token = str(value or "").strip().lower()
            if not token:
                continue
            if token not in _WEEKDAY_TOKEN_TO_INDEX:
                raise HTTPException(status_code=400, detail="Invalid recurrence day. Use weekday names like mon or monday")
            short = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][_WEEKDAY_TOKEN_TO_INDEX[token]]
            if short in seen:
                continue
            seen.add(short)
            normalized.append(short)
        return normalized

    @staticmethod
    def _validate_request_can_have_schedule(record: ClientRequestRecord) -> None:
        if record.request_status in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            raise HTTPException(status_code=409, detail="Cannot manage schedule for a cancelled or closed request")
        if getattr(record, "expired_at", None) is not None:
            raise HTTPException(status_code=409, detail="Cannot manage schedule for an expired request")

    @staticmethod
    def _slot_key(parent_assignment_id: Optional[str], coverage_slot_index: int) -> Tuple[str, int]:
        return (str(parent_assignment_id or "open"), int(coverage_slot_index or 0))

    @staticmethod
    def _slot_status_value(slot: ShiftSlotRecord | Dict[str, Any]) -> str:
        raw = slot.slot_status if isinstance(slot, ShiftSlotRecord) else slot.get("slot_status")
        return getattr(raw, "value", raw or "")

    @staticmethod
    def _coverage_source_value(slot: ShiftSlotRecord | Dict[str, Any]) -> str:
        raw = slot.coverage_source_type if isinstance(slot, ShiftSlotRecord) else slot.get("coverage_source_type")
        return getattr(raw, "value", raw or "")

    @staticmethod
    def _parse_optional_note(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @classmethod
    def _is_staffed_slot_status(cls, value: ShiftSlotStatus | str | None) -> bool:
        normalized = getattr(value, "value", value or "")
        return normalized in {status.value for status in _SLOT_STAFFED_STATUSES}

    @classmethod
    def _slot_requires_client_action(cls, value: ShiftSlotStatus | str | None) -> bool:
        normalized = getattr(value, "value", value or "")
        return normalized in {status.value for status in _SLOT_CLIENT_ACTION_STATUSES}

    @classmethod
    def _is_exception_slot_status(cls, value: ShiftSlotStatus | str | None) -> bool:
        normalized = getattr(value, "value", value or "")
        return normalized in {status.value for status in _SHIFT_EXCEPTION_STATUSES}

    @staticmethod
    def _system_actor():
        return SimpleNamespace(id="", role="system", username="system")

    @staticmethod
    def _request_display_title(request_record: ClientRequestRecord) -> str:
        return str(getattr(request_record, "title", "") or "Client request")

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value)
        except Exception:
            return None
        return parsed if parsed == parsed else None

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import atan2, cos, radians, sin, sqrt

        earth_radius_m = 6371000.0
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)
        a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return earth_radius_m * c

    @classmethod
    def _site_coordinates(cls, request_record: ClientRequestRecord) -> Tuple[float, float]:
        site_snapshot = getattr(request_record, "site_snapshot", {}) or {}
        site_address = site_snapshot.get("site_address") if isinstance(site_snapshot, dict) else {}
        latitude = cls._as_float(site_address.get("latitude") if isinstance(site_address, dict) else None)
        longitude = cls._as_float(site_address.get("longitude") if isinstance(site_address, dict) else None)
        if latitude is None or longitude is None:
            raise HTTPException(status_code=409, detail="Site coordinates are required before attendance check-in can be used")
        return latitude, longitude

    @classmethod
    def _validate_schedule_payload(
        cls,
        payload: RequestScheduleUpsertPayload,
    ) -> Tuple[ZoneInfo, time, time, List[str], bool]:
        tzinfo = cls._resolve_timezone(payload.timezone)
        start_clock = cls._parse_local_time("start_time_local", payload.start_time_local)
        end_clock = cls._parse_local_time("end_time_local", payload.end_time_local)
        is_overnight = end_clock <= start_clock
        recurrence_days = cls._normalize_recurrence_days(payload.recurrence_days)

        if payload.schedule_type == RequestScheduleType.ONE_TIME:
            if payload.end_date and payload.end_date != payload.start_date:
                raise HTTPException(status_code=400, detail="One-time schedules cannot have a different end date")
            if recurrence_days:
                raise HTTPException(status_code=400, detail="One-time schedules do not support recurrence_days")
        elif payload.schedule_type == RequestScheduleType.DATE_RANGE:
            if payload.end_date is None:
                raise HTTPException(status_code=400, detail="Date-range schedules require end_date")
            if payload.end_date < payload.start_date:
                raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
            if recurrence_days:
                raise HTTPException(status_code=400, detail="Date-range schedules do not support recurrence_days")
        elif payload.schedule_type == RequestScheduleType.RECURRING_WEEKLY:
            if payload.end_date is None:
                raise HTTPException(status_code=400, detail="Recurring schedules require end_date")
            if payload.end_date < payload.start_date:
                raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
            if not recurrence_days:
                raise HTTPException(status_code=400, detail="Recurring schedules require at least one recurrence day")

        return tzinfo, start_clock, end_clock, recurrence_days, is_overnight

    @classmethod
    def _iter_occurrence_dates(
        cls,
        payload: RequestScheduleUpsertPayload,
        tzinfo: ZoneInfo,
        recurrence_days: List[str],
    ) -> List[date]:
        today_local = datetime.now(tzinfo).date()
        generation_start = max(payload.start_date, today_local)
        effective_end = payload.end_date or payload.start_date
        generation_end = min(effective_end, generation_start + timedelta(days=max(int(payload.generation_horizon_days or 1) - 1, 0)))
        if generation_end < generation_start:
            return []

        if payload.schedule_type == RequestScheduleType.ONE_TIME:
            return [payload.start_date] if generation_start <= payload.start_date <= generation_end else []

        allowed_weekdays = {_WEEKDAY_TOKEN_TO_INDEX[token] for token in recurrence_days}
        current = generation_start
        results: List[date] = []
        while current <= generation_end:
            if payload.schedule_type == RequestScheduleType.DATE_RANGE or current.weekday() in allowed_weekdays:
                results.append(current)
            current += timedelta(days=1)
        return results

    @staticmethod
    def _build_shift_window(
        occurrence_date: date,
        tzinfo: ZoneInfo,
        start_clock: time,
        end_clock: time,
        is_overnight: bool,
    ) -> Tuple[datetime, datetime]:
        local_start = datetime.combine(occurrence_date, start_clock, tzinfo=tzinfo)
        end_date_value = occurrence_date + timedelta(days=1) if is_overnight else occurrence_date
        local_end = datetime.combine(end_date_value, end_clock, tzinfo=tzinfo)
        if local_end <= local_start:
            raise HTTPException(status_code=400, detail="Schedule end time must be after start time")
        return (
            local_start.astimezone(timezone.utc).replace(tzinfo=None),
            local_end.astimezone(timezone.utc).replace(tzinfo=None),
        )

    def _build_shift_instances(
        self,
        request_record: ClientRequestRecord,
        template_record: RequestScheduleTemplateRecord,
        payload: RequestScheduleUpsertPayload,
        tzinfo: ZoneInfo,
        start_clock: time,
        end_clock: time,
        recurrence_days: List[str],
        is_overnight: bool,
    ) -> List[ShiftInstanceRecord]:
        occurrence_dates = self._iter_occurrence_dates(payload, tzinfo, recurrence_days)
        if not occurrence_dates and bool(payload.active):
            raise HTTPException(status_code=400, detail="Schedule must generate at least one upcoming shift in the configured horizon")

        slots_required = max(int(getattr(request_record, "guards_required", 1) or 1), 1)
        instances: List[ShiftInstanceRecord] = []
        for occurrence_date in occurrence_dates:
            shift_start_at_utc, shift_end_at_utc = self._build_shift_window(
                occurrence_date=occurrence_date,
                tzinfo=tzinfo,
                start_clock=start_clock,
                end_clock=end_clock,
                is_overnight=is_overnight,
            )
            roster_due_at = shift_start_at_utc - timedelta(minutes=int(template_record.roster_due_offset_minutes or 0))
            instances.append(
                ShiftInstanceRecord(
                    request_id=str(request_record.id),
                    client_tenant_id=request_record.client_tenant_id,
                    schedule_template_id=str(template_record.id),
                    shift_date_local=occurrence_date.isoformat(),
                    shift_start_at_utc=shift_start_at_utc,
                    shift_end_at_utc=shift_end_at_utc,
                    timezone=template_record.timezone,
                    instance_status=ShiftInstanceStatus.SCHEDULED,
                    slots_required=slots_required,
                    slots_staffed=0,
                    slots_checked_in=0,
                    slots_completed=0,
                    client_action_required=False,
                    roster_due_at=roster_due_at,
                    created_from_revision=int(getattr(request_record, "request_revision", 0) or 0),
                )
            )
        return instances

    @staticmethod
    def _desired_slot_specs(
        request_manager: RequestManager,
        request_record: ClientRequestRecord,
        shift_record: ShiftInstanceRecord,
        assignments: List[RequestAssignmentRecord],
    ) -> List[Dict[str, Any]]:
        desired: List[Dict[str, Any]] = []
        global_slot_number = 1
        covered_slots = 0
        ordered_assignments = sorted(
            assignments,
            key=lambda item: (
                str(getattr(item, "accepted_at", None) or ""),
                str(getattr(item, "created_at", None) or ""),
                str(getattr(item, "id", "")),
            ),
        )
        for assignment in ordered_assignments:
            slot_count = max(int(request_manager._assignment_slots(assignment) or 0), 0)
            if slot_count <= 0:
                continue

            is_provider = str(getattr(getattr(assignment, "assignee_tenant_type", None), "value", getattr(assignment, "assignee_tenant_type", ""))) == "service_provider"
            for coverage_index in range(1, slot_count + 1):
                desired.append(
                    {
                        "slot_number": global_slot_number,
                        "coverage_slot_index": coverage_index,
                        "parent_assignment_id": str(assignment.id),
                        "coverage_source_type": ShiftCoverageSourceType.SERVICE_PROVIDER if is_provider else ShiftCoverageSourceType.DIRECT_GUARD,
                        "coverage_tenant_id": assignment.assignee_tenant_id,
                        "service_provider_tenant_id": assignment.assignee_tenant_id if is_provider else None,
                        "assigned_guard_tenant_id": None if is_provider else assignment.assignee_tenant_id,
                        "slot_status": ShiftSlotStatus.RESERVED,
                        "roster_due_at": shift_record.roster_due_at,
                    }
                )
                global_slot_number += 1
                covered_slots += 1

        open_slots = max(int(shift_record.slots_required or 0) - covered_slots, 0)
        for open_index in range(1, open_slots + 1):
            desired.append(
                {
                    "slot_number": global_slot_number,
                    "coverage_slot_index": open_index,
                    "parent_assignment_id": None,
                    "coverage_source_type": None,
                    "coverage_tenant_id": None,
                    "service_provider_tenant_id": None,
                    "assigned_guard_tenant_id": None,
                    "slot_status": ShiftSlotStatus.OPEN,
                    "roster_due_at": shift_record.roster_due_at,
                }
            )
            global_slot_number += 1

        return desired

    async def _sync_shift_slots_for_shift(
        self,
        request_record: ClientRequestRecord,
        shift_record: ShiftInstanceRecord,
        assignments: List[RequestAssignmentRecord],
    ) -> Dict[str, int]:
        request_manager = RequestManager.get_instance()
        shift_record.slots_required = max(int(getattr(request_record, "guards_required", 1) or 1), 1)
        desired_specs = self._desired_slot_specs(request_manager, request_record, shift_record, assignments)

        existing_slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
        existing_by_key = {
            self._slot_key(getattr(slot, "parent_assignment_id", None), getattr(slot, "coverage_slot_index", 0)): slot
            for slot in existing_slots
        }
        desired_keys = set()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for spec in desired_specs:
            slot_key = self._slot_key(spec["parent_assignment_id"], spec["coverage_slot_index"])
            desired_keys.add(slot_key)
            existing = existing_by_key.get(slot_key)
            preserved_status = spec["slot_status"]
            preserved_assigned_guard = spec["assigned_guard_tenant_id"]
            preserved_rostered_at = None
            preserved_guard_unavailable_reported_at = None
            preserved_arrived_at = None
            preserved_client_confirmed_at = None
            preserved_started_at = None
            preserved_checked_out_at = None
            preserved_completed_at = None
            preserved_no_show_confirmed_at = None
            preserved_geo_check_passed = None
            preserved_actual_start_at = None
            preserved_actual_end_at = None

            if existing:
                preserved_status = existing.slot_status
                preserved_assigned_guard = existing.assigned_guard_tenant_id or spec["assigned_guard_tenant_id"]
                preserved_rostered_at = existing.rostered_at
                preserved_guard_unavailable_reported_at = existing.guard_unavailable_reported_at
                preserved_arrived_at = existing.arrived_at
                preserved_client_confirmed_at = existing.client_confirmed_at
                preserved_started_at = existing.started_at
                preserved_checked_out_at = existing.checked_out_at
                preserved_completed_at = existing.completed_at
                preserved_no_show_confirmed_at = existing.no_show_confirmed_at
                preserved_geo_check_passed = existing.geo_check_passed
                preserved_actual_start_at = existing.actual_start_at
                preserved_actual_end_at = existing.actual_end_at

            slot_record = ShiftSlotRecord(
                id=getattr(existing, "id", ObjectId()),
                shift_instance_id=str(shift_record.id),
                request_id=str(request_record.id),
                client_tenant_id=request_record.client_tenant_id,
                parent_assignment_id=spec["parent_assignment_id"],
                slot_number=int(spec["slot_number"]),
                coverage_slot_index=int(spec["coverage_slot_index"]),
                coverage_source_type=spec["coverage_source_type"],
                coverage_tenant_id=spec["coverage_tenant_id"],
                service_provider_tenant_id=spec["service_provider_tenant_id"],
                assigned_guard_tenant_id=preserved_assigned_guard,
                slot_status=preserved_status,
                rostered_at=preserved_rostered_at,
                roster_due_at=spec["roster_due_at"],
                guard_unavailable_reported_at=preserved_guard_unavailable_reported_at,
                arrived_at=preserved_arrived_at,
                client_confirmed_at=preserved_client_confirmed_at,
                started_at=preserved_started_at,
                checked_out_at=preserved_checked_out_at,
                completed_at=preserved_completed_at,
                no_show_confirmed_at=preserved_no_show_confirmed_at,
                geo_check_passed=preserved_geo_check_passed,
                actual_start_at=preserved_actual_start_at,
                actual_end_at=preserved_actual_end_at,
                created_at=getattr(existing, "created_at", now),
                updated_at=now,
            )
            await self._engine.save(slot_record)

        for slot in existing_slots:
            slot_key = self._slot_key(getattr(slot, "parent_assignment_id", None), getattr(slot, "coverage_slot_index", 0))
            if getattr(slot, "replacement_of_slot_id", None):
                continue
            if slot_key in desired_keys:
                continue
            await self._engine.delete(slot)

        saved_slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
        staffed_slots = len([slot for slot in saved_slots if self._is_staffed_slot_status(getattr(slot, "slot_status", None))])
        shift_record.slots_staffed = staffed_slots
        shift_record.updated_at = now
        if shift_record.instance_status in {
            ShiftInstanceStatus.SCHEDULED,
            ShiftInstanceStatus.PARTIALLY_STAFFED,
            ShiftInstanceStatus.STAFFED,
        }:
            if staffed_slots <= 0:
                shift_record.instance_status = ShiftInstanceStatus.SCHEDULED
            elif staffed_slots >= int(shift_record.slots_required or 0):
                shift_record.instance_status = ShiftInstanceStatus.STAFFED
            else:
                shift_record.instance_status = ShiftInstanceStatus.PARTIALLY_STAFFED
        await self._engine.save(shift_record)
        return {"slot_count": len(saved_slots), "staffed_slots": staffed_slots}

    async def _delete_future_shift_instances(self, request_id: str, template_id: str, from_utc: datetime) -> None:
        collection = self._engine.get_collection(ShiftInstanceRecord)
        await collection.delete_many(
            {
                "request_id": request_id,
                "schedule_template_id": template_id,
                "shift_end_at_utc": {"$gte": from_utc},
            }
        )

    async def sync_shift_slots_for_request(self, request_record: ClientRequestRecord | str) -> Dict[str, int]:
        request_manager = RequestManager.get_instance()
        if isinstance(request_record, str):
            request_record = await request_manager._get_request_or_404(request_record)

        schedule_record = await self._engine.find_one(
            RequestScheduleTemplateRecord,
            RequestScheduleTemplateRecord.request_id == str(request_record.id),
        )
        if not schedule_record or not bool(schedule_record.active):
            return {"shift_count": 0, "slot_count": 0}

        shifts = await self._engine.find(ShiftInstanceRecord, ShiftInstanceRecord.request_id == str(request_record.id))
        assignments = await request_manager._get_assignments_for_request(str(request_record.id))
        committed_assignments = [
            assignment for assignment in assignments if getattr(assignment, "assignment_status", None) in _COMMITTED_ASSIGNMENT_STATUSES
        ]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        shift_count = 0
        slot_count = 0
        for shift in shifts:
            if getattr(shift, "shift_end_at_utc", None) and shift.shift_end_at_utc < now:
                continue
            counts = await self._sync_shift_slots_for_shift(request_record, shift, committed_assignments)
            shift_count += 1
            slot_count += int(counts.get("slot_count") or 0)
        return {"shift_count": shift_count, "slot_count": slot_count}

    async def _count_shift_instances_for_schedule(self, template_id: str) -> int:
        collection = self._engine.get_collection(ShiftInstanceRecord)
        return int(await collection.count_documents({"schedule_template_id": template_id}))

    async def _get_shift_slot_docs(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        collection = self._engine.get_collection(ShiftSlotRecord)
        return await collection.find(query).sort("slot_number", 1).to_list(length=None)

    async def _get_shift_event_docs(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        collection = self._engine.get_collection(ShiftAttendanceEventRecord)
        return await collection.find(query).sort("timestamp", 1).to_list(length=None)

    async def _record_slot_event(
        self,
        slot_record: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
        current_user,
        event_type: ShiftAttendanceEventType,
        *,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        distance_meters: Optional[float] = None,
        note: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ShiftAttendanceEventRecord:
        role_value = RequestManager.get_instance()._role_value(current_user)
        service_provider_tenant_id = (
            slot_record.service_provider_tenant_id
            or (slot_record.coverage_tenant_id if slot_record.coverage_source_type == ShiftCoverageSourceType.SERVICE_PROVIDER else None)
        )
        event = ShiftAttendanceEventRecord(
            shift_slot_id=str(slot_record.id),
            shift_instance_id=str(shift_record.id),
            request_id=str(request_record.id),
            event_type=event_type,
            actor_user_id=str(getattr(current_user, "id", "") or ""),
            actor_role=role_value,
            guard_tenant_id=slot_record.assigned_guard_tenant_id,
            service_provider_tenant_id=service_provider_tenant_id,
            client_tenant_id=request_record.client_tenant_id,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            latitude=latitude,
            longitude=longitude,
            distance_meters=distance_meters,
            note=self._parse_optional_note(note),
            metadata=metadata or {},
        )
        return await self._engine.save(event)

    async def _refresh_shift_progress(self, shift_record: ShiftInstanceRecord) -> ShiftInstanceRecord:
        slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
        staffed_slots = [slot for slot in slots if self._is_staffed_slot_status(getattr(slot, "slot_status", None))]
        checked_in_slots = [slot for slot in slots if getattr(slot, "arrived_at", None) is not None]
        completed_slots = [slot for slot in slots if getattr(slot, "completed_at", None) is not None]
        in_progress_slots = [slot for slot in slots if self._slot_status_value(slot) == ShiftSlotStatus.IN_PROGRESS.value]
        client_action_slots = [slot for slot in slots if self._slot_requires_client_action(getattr(slot, "slot_status", None))]

        shift_record.slots_staffed = len(staffed_slots)
        shift_record.slots_checked_in = len(checked_in_slots)
        shift_record.slots_completed = len(completed_slots)
        shift_record.client_action_required = bool(client_action_slots)
        if in_progress_slots:
            shift_record.instance_status = ShiftInstanceStatus.IN_PROGRESS
        elif completed_slots and len(completed_slots) >= len(staffed_slots) and staffed_slots:
            shift_record.instance_status = ShiftInstanceStatus.COMPLETED
        elif staffed_slots and len(staffed_slots) >= int(shift_record.slots_required or 0):
            shift_record.instance_status = ShiftInstanceStatus.STAFFED
        elif staffed_slots:
            shift_record.instance_status = ShiftInstanceStatus.PARTIALLY_STAFFED
        else:
            shift_record.instance_status = ShiftInstanceStatus.SCHEDULED

        shift_record.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self._engine.save(shift_record)

    async def _notify_slot_exception(
        self,
        *,
        slot_record: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "request_id": str(request_record.id),
            "shift_id": str(shift_record.id),
            "slot_id": str(slot_record.id),
            **(metadata or {}),
        }
        action_url = f"/dashboard/requests?shift={shift_record.id}"
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title=title,
            message=message,
            category="warning",
            source_module="requests",
            action_url=action_url,
            action_label="Review shift",
            metadata=payload,
        )
        if slot_record.service_provider_tenant_id and slot_record.service_provider_tenant_id != request_record.client_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.service_provider_tenant_id,
                title=title,
                message=message,
                category="warning",
                source_module="requests",
                action_url=action_url,
                action_label="Open shift",
                metadata=payload,
            )

    async def _sync_shift_runtime_exception_states(self, shift_record: ShiftInstanceRecord) -> ShiftInstanceRecord:
        schedule_record = await self._get_schedule_template_or_404(shift_record.schedule_template_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(shift_record.request_id)
        slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        suspected_threshold = shift_record.shift_start_at_utc + timedelta(minutes=int(getattr(schedule_record, "late_grace_minutes", 15) or 0))
        confirmed_threshold = shift_record.shift_start_at_utc + timedelta(minutes=int(getattr(schedule_record, "no_show_cutoff_minutes", 30) or 0))
        changed = False
        request_title = self._request_display_title(request_record)
        system_actor = self._system_actor()

        for slot_record in slots:
            if not slot_record.assigned_guard_tenant_id:
                continue
            if slot_record.arrived_at is not None or slot_record.started_at is not None or slot_record.completed_at is not None:
                continue
            if slot_record.slot_status in {
                ShiftSlotStatus.UNAVAILABLE,
                ShiftSlotStatus.LATE_RISK,
                ShiftSlotStatus.NO_SHOW_CONFIRMED,
                ShiftSlotStatus.REPLACEMENT_REQUIRED,
                ShiftSlotStatus.CANCELLED,
                ShiftSlotStatus.COMPLETED,
                ShiftSlotStatus.IN_PROGRESS,
            }:
                continue

            if now >= confirmed_threshold:
                if slot_record.slot_status != ShiftSlotStatus.NO_SHOW_SUSPECTED:
                    slot_record.slot_status = ShiftSlotStatus.NO_SHOW_SUSPECTED
                    slot_record.updated_at = now
                    await self._engine.save(slot_record)
                    await self._record_slot_event(
                        slot_record,
                        shift_record,
                        request_record,
                        system_actor,
                        ShiftAttendanceEventType.NO_SHOW_SUSPECTED,
                        metadata={"threshold_minutes": int(getattr(schedule_record, "late_grace_minutes", 15) or 0)},
                    )
                slot_record.slot_status = ShiftSlotStatus.NO_SHOW_CONFIRMED
                slot_record.no_show_confirmed_at = slot_record.no_show_confirmed_at or now
                slot_record.updated_at = now
                await self._engine.save(slot_record)
                await self._record_slot_event(
                    slot_record,
                    shift_record,
                    request_record,
                    system_actor,
                    ShiftAttendanceEventType.NO_SHOW_CONFIRMED,
                    metadata={"threshold_minutes": int(getattr(schedule_record, "no_show_cutoff_minutes", 30) or 0)},
                )
                await self._notify_slot_exception(
                    slot_record=slot_record,
                    shift_record=shift_record,
                    request_record=request_record,
                    title="Guard no-show confirmed",
                    message=f"{request_title}: a guard did not check in and is now marked as a confirmed no-show.",
                    metadata={"exception_status": ShiftSlotStatus.NO_SHOW_CONFIRMED.value},
                )
                changed = True
                continue

            if now >= suspected_threshold and slot_record.slot_status in {ShiftSlotStatus.RESERVED, ShiftSlotStatus.ROSTERED}:
                slot_record.slot_status = ShiftSlotStatus.NO_SHOW_SUSPECTED
                slot_record.updated_at = now
                await self._engine.save(slot_record)
                await self._record_slot_event(
                    slot_record,
                    shift_record,
                    request_record,
                    system_actor,
                    ShiftAttendanceEventType.NO_SHOW_SUSPECTED,
                    metadata={"threshold_minutes": int(getattr(schedule_record, "late_grace_minutes", 15) or 0)},
                )
                await self._notify_slot_exception(
                    slot_record=slot_record,
                    shift_record=shift_record,
                    request_record=request_record,
                    title="Guard no-show suspected",
                    message=f"{request_title}: a guard has not checked in and this shift slot is now marked as no-show suspected.",
                    metadata={"exception_status": ShiftSlotStatus.NO_SHOW_SUSPECTED.value},
                )
                changed = True

        if changed:
            return await self._refresh_shift_progress(shift_record)
        return shift_record

    async def _visible_shift_ids_for_user(self, current_user) -> Optional[set[str]]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        if request_manager._is_platform_role(role_value):
            return None

        session_tenant = await request_manager._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)
        shift_collection = self._engine.get_collection(ShiftInstanceRecord)
        slot_collection = self._engine.get_collection(ShiftSlotRecord)

        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            docs = await shift_collection.find({"client_tenant_id": tenant_id}).to_list(length=None)
            return {str(doc.get("_id")) for doc in docs if doc.get("_id")}

        if role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
            docs = await slot_collection.find({"coverage_tenant_id": tenant_id}).to_list(length=None)
            return {str(doc.get("shift_instance_id")) for doc in docs if doc.get("shift_instance_id")}

        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            docs = await slot_collection.find(
                {"$or": [{"assigned_guard_tenant_id": tenant_id}, {"coverage_tenant_id": tenant_id}]}
            ).to_list(length=None)
            return {str(doc.get("shift_instance_id")) for doc in docs if doc.get("shift_instance_id")}

        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _get_visible_shift_slot_docs(
        self,
        shift_id: str,
        current_user,
    ) -> List[Dict[str, Any]]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        if request_manager._is_platform_role(role_value):
            return await self._get_shift_slot_docs({"shift_instance_id": shift_id})

        session_tenant = await request_manager._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)
        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            return await self._get_shift_slot_docs({"shift_instance_id": shift_id})
        if role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
            return await self._get_shift_slot_docs({"shift_instance_id": shift_id, "coverage_tenant_id": tenant_id})
        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            return await self._get_shift_slot_docs(
                {
                    "shift_instance_id": shift_id,
                    "$or": [{"assigned_guard_tenant_id": tenant_id}, {"coverage_tenant_id": tenant_id}],
                }
            )
        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _get_shift_or_404(self, shift_id: str) -> ShiftInstanceRecord:
        try:
            object_id = ObjectId(shift_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid shift id")
        record = await self._engine.find_one(ShiftInstanceRecord, ShiftInstanceRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Shift not found")
        return record

    async def _get_shift_slot_or_404(self, slot_id: str) -> ShiftSlotRecord:
        try:
            object_id = ObjectId(slot_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid shift slot id")
        record = await self._engine.find_one(ShiftSlotRecord, ShiftSlotRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Shift slot not found")
        return record

    async def _get_schedule_template_or_404(self, template_id: str) -> RequestScheduleTemplateRecord:
        try:
            object_id = ObjectId(template_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid schedule template id")
        record = await self._engine.find_one(RequestScheduleTemplateRecord, RequestScheduleTemplateRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request schedule not found")
        return record

    async def _assert_guard_slot_action_access(self, slot_record: ShiftSlotRecord, current_user) -> tuple[bool, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        is_platform = request_manager._is_platform_write_role(role_value)
        if is_platform:
            return True, None
        session_tenant = await request_manager._get_session_tenant(current_user)
        if role_value != "guard_admin" or session_tenant.tenant_type != TenantType.GUARD:
            raise HTTPException(status_code=403, detail="Only assigned guard users or platform admins can update attendance")
        if str(session_tenant.id) != str(slot_record.assigned_guard_tenant_id or ""):
            raise HTTPException(status_code=403, detail="This shift slot is not assigned to your guard tenant")
        return False, session_tenant

    async def _assert_client_slot_action_access(self, request_record: ClientRequestRecord, current_user) -> tuple[bool, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        is_platform = request_manager._is_platform_write_role(role_value)
        if is_platform:
            return True, None
        session_tenant = await request_manager._get_session_tenant(current_user)
        if role_value != "client_admin" or session_tenant.tenant_type != TenantType.CLIENT:
            raise HTTPException(status_code=403, detail="Only owning client admins or platform admins can confirm arrivals")
        if str(session_tenant.id) != str(request_record.client_tenant_id or ""):
            raise HTTPException(status_code=403, detail="This shift does not belong to your client tenant")
        return False, session_tenant

    async def upsert_request_schedule(self, request_id: str, payload: RequestScheduleUpsertPayload, current_user) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(request_id)
        await request_manager._sync_request_runtime_state(request_record)
        await request_manager._assert_request_write_access(request_record, current_user)
        self._validate_request_can_have_schedule(request_record)

        tzinfo, start_clock, end_clock, recurrence_days, is_overnight = self._validate_schedule_payload(payload)
        existing = await self._engine.find_one(
            RequestScheduleTemplateRecord,
            RequestScheduleTemplateRecord.request_id == str(request_record.id),
        )
        now = datetime.utcnow()
        if existing:
            template_record = existing
            template_record.updated_at = now
        else:
            template_record = RequestScheduleTemplateRecord(
                request_id=str(request_record.id),
                client_tenant_id=request_record.client_tenant_id,
                timezone=payload.timezone.strip(),
                schedule_type=payload.schedule_type,
                start_date_local=payload.start_date.isoformat(),
                end_date_local=payload.end_date.isoformat() if payload.end_date else None,
                start_time_local=payload.start_time_local,
                end_time_local=payload.end_time_local,
                is_overnight=is_overnight,
                recurrence_days=[],
                generation_horizon_days=payload.generation_horizon_days,
                roster_due_offset_minutes=payload.roster_due_offset_minutes,
                unavailable_cutoff_minutes=payload.unavailable_cutoff_minutes,
                late_grace_minutes=payload.late_grace_minutes,
                no_show_cutoff_minutes=payload.no_show_cutoff_minutes,
                checkin_geofence_meters=payload.checkin_geofence_meters,
                active=payload.active,
            )

        template_record.timezone = payload.timezone.strip()
        template_record.schedule_type = payload.schedule_type
        template_record.start_date_local = payload.start_date.isoformat()
        template_record.end_date_local = payload.end_date.isoformat() if payload.end_date else None
        template_record.start_time_local = payload.start_time_local
        template_record.end_time_local = payload.end_time_local
        template_record.is_overnight = is_overnight
        template_record.recurrence_days = recurrence_days
        template_record.generation_horizon_days = int(payload.generation_horizon_days or 30)
        template_record.roster_due_offset_minutes = int(payload.roster_due_offset_minutes or 0)
        template_record.unavailable_cutoff_minutes = int(payload.unavailable_cutoff_minutes or 0)
        template_record.late_grace_minutes = int(payload.late_grace_minutes or 0)
        template_record.no_show_cutoff_minutes = int(payload.no_show_cutoff_minutes or 0)
        template_record.checkin_geofence_meters = int(payload.checkin_geofence_meters or 0)
        template_record.active = bool(payload.active)
        saved_template = await self._engine.save(template_record)

        await self._delete_future_shift_instances(str(request_record.id), str(saved_template.id), now)
        generated_instances: List[ShiftInstanceRecord] = []
        if saved_template.active:
            generated_instances = self._build_shift_instances(
                request_record=request_record,
                template_record=saved_template,
                payload=payload,
                tzinfo=tzinfo,
                start_clock=start_clock,
                end_clock=end_clock,
                recurrence_days=recurrence_days,
                is_overnight=is_overnight,
            )
            for instance in generated_instances:
                await self._engine.save(instance)
        slot_counts = await self.sync_shift_slots_for_request(request_record)

        await request_manager._write_activity(
            action="request_schedule_upserted",
            entity_type="request_schedule",
            entity_id=str(saved_template.id),
            current_user=current_user,
            metadata={
                "request_id": str(request_record.id),
                "schedule_type": saved_template.schedule_type.value,
                "timezone": saved_template.timezone,
                "generated_shift_count": len(generated_instances),
                "generated_slot_count": int(slot_counts.get("slot_count") or 0),
            },
        )

        return {
            "schedule": {
                **self._serialize_schedule(saved_template, generated_shift_count=len(generated_instances)),
                "generated_slot_count": int(slot_counts.get("slot_count") or 0),
            },
        }

    async def get_request_schedule(self, request_id: str, current_user) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(request_id)
        if not await request_manager._can_view_request(request_record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")

        template_record = await self._engine.find_one(
            RequestScheduleTemplateRecord,
            RequestScheduleTemplateRecord.request_id == str(request_record.id),
        )
        if not template_record:
            raise HTTPException(status_code=404, detail="Request schedule not found")

        generated_count = await self._count_shift_instances_for_schedule(str(template_record.id))
        return {
            "schedule": self._serialize_schedule(template_record, generated_shift_count=generated_count),
        }

    async def list_shifts(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
        request_id: str = "",
        instance_status: str = "",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        visible_shift_ids = await self._visible_shift_ids_for_user(current_user)
        if visible_shift_ids is not None and not visible_shift_ids:
            return {
                "items": [],
                "pagination": {"page": max(page, 1), "rows": max(rows, 1), "total_items": 0, "total_pages": 0},
            }

        if request_id:
            record = await request_manager._get_request_or_404(request_id)
            if not await request_manager._can_view_request(record, current_user):
                raise HTTPException(status_code=403, detail="Access forbidden")

        query: Dict[str, Any] = {}
        if visible_shift_ids is not None:
            query["_id"] = {"$in": [ObjectId(shift_id) for shift_id in visible_shift_ids]}
        if request_id:
            query["request_id"] = str(record.id)
        if instance_status:
            normalized_status = str(instance_status or "").strip().lower()
            allowed_statuses = {member.value for member in ShiftInstanceStatus}
            if normalized_status not in allowed_statuses:
                raise HTTPException(status_code=400, detail="Invalid shift instance status filter")
            query["instance_status"] = normalized_status
        if date_from or date_to:
            date_filter: Dict[str, Any] = {}
            if date_from:
                date_filter["$gte"] = date_from.isoformat()
            if date_to:
                date_filter["$lte"] = date_to.isoformat()
            query["shift_date_local"] = date_filter

        collection = self._engine.get_collection(ShiftInstanceRecord)
        total_items = int(await collection.count_documents(query))
        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        skip = (safe_page - 1) * safe_rows
        docs = await collection.find(query).sort("shift_start_at_utc", 1).skip(skip).limit(safe_rows).to_list(length=safe_rows)
        items = []
        for doc in docs:
            shift_record = await self._get_shift_or_404(str(doc.get("_id")))
            shift_record = await self._sync_shift_runtime_exception_states(shift_record)
            items.append(self._serialize_shift(shift_record))
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        return {
            "items": items,
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def get_shift_by_id(self, shift_id: str, current_user) -> Dict[str, Any]:
        record = await self._get_shift_or_404(shift_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(record.request_id)
        await self.sync_shift_slots_for_request(request_record)
        record = await self._get_shift_or_404(shift_id)
        record = await self._sync_shift_runtime_exception_states(record)
        visible_shift_ids = await self._visible_shift_ids_for_user(current_user)
        if visible_shift_ids is not None and str(record.id) not in visible_shift_ids:
            raise HTTPException(status_code=403, detail="Access forbidden")
        slot_docs = await self._get_visible_shift_slot_docs(str(record.id), current_user)
        role_value = request_manager._role_value(current_user)
        if not request_manager._is_platform_role(role_value):
            session_tenant = await request_manager._get_session_tenant(current_user)
            if not (
                role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT
            ) and not slot_docs:
                raise HTTPException(status_code=403, detail="Access forbidden")

        serialized_slots = [self._serialize_slot(doc) for doc in slot_docs]
        return {
            "shift": self._serialize_shift(record),
            "slots": serialized_slots,
            "slot_summary": {
                "total_visible_slots": len(serialized_slots),
                "open_slots": len([slot for slot in serialized_slots if slot["slot_status"] == ShiftSlotStatus.OPEN.value]),
                "reserved_slots": len([slot for slot in serialized_slots if slot["slot_status"] == ShiftSlotStatus.RESERVED.value]),
                "rostered_slots": len([slot for slot in serialized_slots if slot["slot_status"] == ShiftSlotStatus.ROSTERED.value]),
            },
        }

    async def get_shift_slot_by_id(self, slot_id: str, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        await self._sync_shift_runtime_exception_states(shift_record)
        slot_record = await self._get_shift_slot_or_404(slot_id)
        visible_shift_ids = await self._visible_shift_ids_for_user(current_user)
        if visible_shift_ids is not None and slot_record.shift_instance_id not in visible_shift_ids:
            raise HTTPException(status_code=403, detail="Access forbidden")
        visible_slots = await self._get_visible_shift_slot_docs(slot_record.shift_instance_id, current_user)
        if not any(str(slot.get("_id") or slot.get("id") or "") == str(slot_record.id) for slot in visible_slots):
            raise HTTPException(status_code=403, detail="Access forbidden")
        event_docs = await self._get_shift_event_docs({"shift_slot_id": str(slot_record.id)})
        return {
            "slot": self._serialize_slot(slot_record),
            "events": [self._serialize_event(doc) for doc in event_docs],
        }

    async def list_shift_exceptions(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
        exception_status: str = "",
        request_id: str = "",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        if not request_manager._is_platform_role(role_value):
            raise HTTPException(status_code=403, detail="Only platform users can access shift exceptions")

        request_filter_id = ""
        if request_id:
            request_record = await request_manager._get_request_or_404(request_id)
            request_filter_id = str(request_record.id)

        shift_query: Dict[str, Any] = {}
        if request_filter_id:
            shift_query["request_id"] = request_filter_id
        if date_from or date_to:
            date_filter: Dict[str, Any] = {}
            if date_from:
                date_filter["$gte"] = date_from.isoformat()
            if date_to:
                date_filter["$lte"] = date_to.isoformat()
            shift_query["shift_date_local"] = date_filter

        shift_collection = self._engine.get_collection(ShiftInstanceRecord)
        shift_docs = await shift_collection.find(shift_query).sort("shift_start_at_utc", 1).to_list(length=None)
        shift_records: Dict[str, ShiftInstanceRecord] = {}
        request_cache: Dict[str, ClientRequestRecord] = {}
        for shift_doc in shift_docs:
            shift_record = await self._get_shift_or_404(str(shift_doc.get("_id")))
            shift_record = await self._sync_shift_runtime_exception_states(shift_record)
            shift_records[str(shift_record.id)] = shift_record
            if shift_record.request_id not in request_cache:
                request_cache[shift_record.request_id] = await request_manager._get_request_or_404(shift_record.request_id)

        normalized_status = str(exception_status or "").strip().lower()
        allowed_statuses = {status.value for status in _SHIFT_EXCEPTION_STATUSES}
        if normalized_status and normalized_status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Invalid shift exception status filter")

        slot_query: Dict[str, Any] = {"slot_status": {"$in": sorted(allowed_statuses)}}
        if shift_records:
            slot_query["shift_instance_id"] = {"$in": list(shift_records.keys())}
        elif request_filter_id or date_from or date_to:
            return {
                "items": [],
                "pagination": {"page": max(page, 1), "rows": max(rows, 1), "total_items": 0, "total_pages": 0},
            }
        slot_docs = await self._get_shift_slot_docs(slot_query)
        items = []
        for slot_doc in slot_docs:
            status_value = str(slot_doc.get("slot_status") or "")
            if normalized_status and status_value != normalized_status:
                continue
            shift_record = shift_records.get(str(slot_doc.get("shift_instance_id") or ""))
            if not shift_record:
                continue
            request_record = request_cache.get(shift_record.request_id)
            items.append(
                {
                    "slot": self._serialize_slot(slot_doc),
                    "shift": self._serialize_shift(shift_record),
                    "request": {
                        "id": str(request_record.id) if request_record else shift_record.request_id,
                        "title": self._request_display_title(request_record) if request_record else "Client request",
                        "client_tenant_id": request_record.client_tenant_id if request_record else shift_record.client_tenant_id,
                    },
                }
            )

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(items)
        start = (safe_page - 1) * safe_rows
        page_items = items[start:start + safe_rows]
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        return {
            "items": page_items,
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def roster_shift(self, shift_id: str, payload: ProviderRosterPayload, current_user) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        is_platform = request_manager._is_platform_write_role(role_value)
        if not is_platform and role_value != "sp_admin":
            raise HTTPException(status_code=403, detail="Only platform admins or service provider admins can roster provider shifts")

        shift_record = await self._get_shift_or_404(shift_id)
        request_record = await request_manager._get_request_or_404(shift_record.request_id)
        await self.sync_shift_slots_for_request(request_record)

        session_tenant = None if is_platform else await request_manager._get_session_tenant(current_user)
        provider_tenant_id = None if is_platform else str(session_tenant.id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        shift_slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
        slot_map = {str(slot.id): slot for slot in shift_slots}
        touched_provider_ids = set()

        for selection in payload.assignments:
            slot_record = slot_map.get(selection.slot_id)
            if not slot_record:
                raise HTTPException(status_code=404, detail="Shift slot not found in this shift")
            if slot_record.coverage_source_type != ShiftCoverageSourceType.SERVICE_PROVIDER:
                raise HTTPException(status_code=400, detail="Only provider-backed slots can be rostered")

            slot_provider_tenant_id = str(slot_record.coverage_tenant_id or slot_record.service_provider_tenant_id or "").strip()
            if not slot_provider_tenant_id:
                raise HTTPException(status_code=400, detail="Provider slot is missing provider ownership")
            if provider_tenant_id and slot_provider_tenant_id != provider_tenant_id:
                raise HTTPException(status_code=403, detail="Cannot roster a slot owned by another service provider")

            guard = await request_manager._get_tenant(selection.guard_tenant_id)
            if not guard or guard.tenant_type != TenantType.GUARD:
                raise HTTPException(status_code=404, detail="Guard not found")
            if guard.status != TenantStatus.ACTIVE:
                raise HTTPException(status_code=400, detail="Only active guards can be rostered")
            if str(getattr(guard, "service_provider_tenant_id", "") or "").strip() != slot_provider_tenant_id:
                raise HTTPException(status_code=400, detail="Guard does not belong to the service provider that owns this slot")

            slot_record.assigned_guard_tenant_id = str(guard.id)
            slot_record.slot_status = ShiftSlotStatus.ROSTERED
            slot_record.rostered_at = now
            slot_record.roster_due_at = shift_record.roster_due_at
            slot_record.updated_at = now
            await self._engine.save(slot_record)
            touched_provider_ids.add(slot_provider_tenant_id)

        await self._sync_shift_slots_for_shift(
            request_record=request_record,
            shift_record=shift_record,
            assignments=[
                assignment
                for assignment in await request_manager._get_assignments_for_request(str(request_record.id))
                if getattr(assignment, "assignment_status", None) in _COMMITTED_ASSIGNMENT_STATUSES
            ],
        )

        await request_manager._write_activity(
            action="shift_provider_rostered",
            entity_type="shift",
            entity_id=str(shift_record.id),
            current_user=current_user,
            metadata={
                "request_id": str(request_record.id),
                "assignment_count": len(payload.assignments),
                "provider_tenant_ids": sorted(touched_provider_ids),
            },
        )
        return await self.get_shift_by_id(shift_id=str(shift_record.id), current_user=current_user)

    async def report_shift_slot_unavailable(
        self,
        slot_id: str,
        payload: ShiftSlotUnavailablePayload,
        current_user,
    ) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        is_platform, _session_tenant = await self._assert_guard_slot_action_access(slot_record, current_user)
        if not slot_record.assigned_guard_tenant_id:
            raise HTTPException(status_code=409, detail="This shift slot has not been assigned to a named guard yet")
        if slot_record.slot_status not in {ShiftSlotStatus.RESERVED, ShiftSlotStatus.ROSTERED}:
            raise HTTPException(status_code=409, detail="This shift slot cannot be marked unavailable from its current state")

        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        schedule_record = await self._get_schedule_template_or_404(shift_record.schedule_template_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if shift_record.shift_start_at_utc <= now:
            raise HTTPException(status_code=409, detail="Unavailable reporting is only allowed before shift start")

        cutoff_minutes = int(getattr(schedule_record, "unavailable_cutoff_minutes", 120) or 0)
        unavailable_deadline = shift_record.shift_start_at_utc - timedelta(minutes=cutoff_minutes)
        is_late_risk = now > unavailable_deadline

        slot_record.guard_unavailable_reported_at = now
        slot_record.slot_status = ShiftSlotStatus.LATE_RISK if is_late_risk else ShiftSlotStatus.UNAVAILABLE
        slot_record.updated_at = now
        await self._engine.save(slot_record)
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.UNAVAILABLE_REPORTED,
            note=payload.note,
            metadata={
                "platform_override": is_platform,
                "late_risk": is_late_risk,
                "unavailable_cutoff_minutes": cutoff_minutes,
            },
        )
        await self._refresh_shift_progress(shift_record)

        request_title = str(getattr(request_record, "title", "") or "Client request")
        status_label = "late risk" if is_late_risk else "unavailable"
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Shift coverage exception reported",
            message=f"{request_title}: a guard reported this shift slot as {status_label}.",
            category="warning",
            source_module="requests",
            action_url=f"/dashboard/requests?shift={shift_record.id}",
            action_label="Review shift",
            metadata={
                "request_id": str(request_record.id),
                "shift_id": str(shift_record.id),
                "slot_id": str(slot_record.id),
                "exception_status": slot_record.slot_status.value,
            },
        )
        if slot_record.service_provider_tenant_id and slot_record.service_provider_tenant_id != request_record.client_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.service_provider_tenant_id,
                title="Provider guard reported unavailable",
                message=f"{request_title}: one of your rostered guards reported this shift slot as {status_label}.",
                category="warning",
                source_module="requests",
                action_url=f"/dashboard/requests?shift={shift_record.id}",
                action_label="Open shift",
                metadata={
                    "request_id": str(request_record.id),
                    "shift_id": str(shift_record.id),
                    "slot_id": str(slot_record.id),
                    "exception_status": slot_record.slot_status.value,
                },
            )

        await request_manager._write_activity(
            action="shift_slot_unavailable_reported",
            entity_type="shift_slot",
            entity_id=str(slot_record.id),
            current_user=current_user,
            metadata={
                "request_id": str(request_record.id),
                "shift_id": str(shift_record.id),
                "status": slot_record.slot_status.value,
            },
        )
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)

    async def reopen_shift_slot(
        self,
        slot_id: str,
        payload: ShiftSlotReopenPayload,
        current_user,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        if not request_manager._is_platform_write_role(role_value):
            raise HTTPException(status_code=403, detail="Only platform admins can reopen shift slots for replacement")

        original_slot = await self._get_shift_slot_or_404(slot_id)
        shift_record = await self._get_shift_or_404(original_slot.shift_instance_id)
        shift_record = await self._sync_shift_runtime_exception_states(shift_record)
        original_slot = await self._get_shift_slot_or_404(slot_id)
        request_record = await request_manager._get_request_or_404(original_slot.request_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if shift_record.shift_end_at_utc <= now:
            raise HTTPException(status_code=409, detail="Cannot reopen a shift slot after the shift has ended")
        if original_slot.slot_status not in _SHIFT_EXCEPTION_STATUSES:
            raise HTTPException(status_code=409, detail="Only exception shift slots can be reopened for replacement")

        existing_replacements = [
            slot for slot in await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
            if str(getattr(slot, "replacement_of_slot_id", "") or "") == str(original_slot.id)
            and getattr(slot, "slot_status", None) not in {ShiftSlotStatus.CANCELLED, ShiftSlotStatus.COMPLETED}
        ]
        if existing_replacements:
            raise HTTPException(status_code=409, detail="A replacement slot is already open for this shift slot")

        original_slot.slot_status = ShiftSlotStatus.REPLACEMENT_REQUIRED
        original_slot.updated_at = now
        await self._engine.save(original_slot)
        await self._record_slot_event(
            original_slot,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.REPLACEMENT_REQUESTED,
            note=payload.note,
            metadata={"original_status": self._slot_status_value(original_slot)},
        )

        replacement_slot = ShiftSlotRecord(
            id=ObjectId(),
            shift_instance_id=str(shift_record.id),
            request_id=str(request_record.id),
            client_tenant_id=request_record.client_tenant_id,
            parent_assignment_id=None,
            slot_number=int(original_slot.slot_number or 0),
            coverage_slot_index=0,
            coverage_source_type=None,
            coverage_tenant_id=None,
            service_provider_tenant_id=None,
            assigned_guard_tenant_id=None,
            slot_status=ShiftSlotStatus.OPEN,
            replacement_of_slot_id=str(original_slot.id),
            roster_due_at=shift_record.roster_due_at,
            created_at=now,
            updated_at=now,
        )
        await self._engine.save(replacement_slot)
        await self._refresh_shift_progress(shift_record)

        wave = await request_manager.create_shift_replacement_wave(
            request_record,
            shift_instance_id=str(shift_record.id),
            original_slot_id=str(original_slot.id),
            replacement_slot_id=str(replacement_slot.id),
            current_user=current_user,
            max_match_results=payload.max_match_results,
        )

        await self._notify_slot_exception(
            slot_record=original_slot,
            shift_record=shift_record,
            request_record=request_record,
            title="Shift replacement requested",
            message=f"{self._request_display_title(request_record)}: platform reopened this shift slot for replacement coverage.",
            metadata={
                "exception_status": ShiftSlotStatus.REPLACEMENT_REQUIRED.value,
                "replacement_slot_id": str(replacement_slot.id),
                "wave_id": str(wave.id) if wave else None,
            },
        )
        await request_manager._write_activity(
            action="shift_slot_reopened",
            entity_type="shift_slot",
            entity_id=str(original_slot.id),
            current_user=current_user,
            metadata={
                "request_id": str(request_record.id),
                "shift_id": str(shift_record.id),
                "replacement_slot_id": str(replacement_slot.id),
                "wave_id": str(wave.id) if wave else None,
            },
        )
        return {
            "message": "Shift slot reopened for replacement",
            "original_slot": self._serialize_slot(original_slot),
            "replacement_slot": self._serialize_slot(replacement_slot),
            "wave": request_manager._serialize_wave(wave) if wave else None,
        }

    async def check_in_shift_slot(self, slot_id: str, payload: ShiftSlotCheckInPayload, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        is_platform, _session_tenant = await self._assert_guard_slot_action_access(slot_record, current_user)
        if not slot_record.assigned_guard_tenant_id:
            raise HTTPException(status_code=409, detail="This shift slot has not been assigned to a named guard yet")
        if slot_record.slot_status not in _SLOT_PRE_START_STATUSES:
            raise HTTPException(status_code=409, detail="This shift slot cannot be checked in from its current state")

        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        schedule_record = await self._get_schedule_template_or_404(shift_record.schedule_template_id)
        site_lat, site_lon = self._site_coordinates(request_record)
        guard_lat = float(payload.latitude)
        guard_lon = float(payload.longitude)
        distance_meters = self._haversine_meters(site_lat, site_lon, guard_lat, guard_lon)
        geofence_meters = float(getattr(schedule_record, "checkin_geofence_meters", 200) or 200)
        if distance_meters > geofence_meters:
            await self._record_slot_event(
                slot_record,
                shift_record,
                request_record,
                current_user,
                ShiftAttendanceEventType.GEO_FAILED,
                latitude=guard_lat,
                longitude=guard_lon,
                distance_meters=distance_meters,
                note=payload.note,
                metadata={"geofence_meters": geofence_meters},
            )
            raise HTTPException(status_code=409, detail="Check-in location is outside the allowed site geofence")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_record.geo_check_passed = True
        slot_record.arrived_at = slot_record.arrived_at or now
        slot_record.slot_status = ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING
        slot_record.updated_at = now
        await self._engine.save(slot_record)
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.CHECKIN_ATTEMPTED,
            latitude=guard_lat,
            longitude=guard_lon,
            distance_meters=distance_meters,
            note=payload.note,
            metadata={"platform_override": is_platform, "geofence_meters": geofence_meters},
        )
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.ARRIVED,
            latitude=guard_lat,
            longitude=guard_lon,
            distance_meters=distance_meters,
            note=payload.note,
            metadata={"platform_override": is_platform},
        )
        await self._refresh_shift_progress(shift_record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Guard arrived on site",
            message=f"{request_record.title}: a guard has checked in and is waiting for arrival confirmation.",
            category="info",
            source_module="requests",
            action_url=f"/dashboard/requests?shift={shift_record.id}",
            action_label="Review shift",
            metadata={"request_id": str(request_record.id), "shift_id": str(shift_record.id), "slot_id": str(slot_record.id)},
        )
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)

    async def confirm_shift_slot_arrival(self, slot_id: str, payload: ShiftSlotClientConfirmPayload, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        await self._assert_client_slot_action_access(request_record, current_user)
        if slot_record.arrived_at is None:
            raise HTTPException(status_code=409, detail="Guard must check in before client confirmation")
        if slot_record.started_at is not None:
            raise HTTPException(status_code=409, detail="This shift slot has already started")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_record.client_confirmed_at = slot_record.client_confirmed_at or now
        slot_record.slot_status = ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING
        slot_record.updated_at = now
        await self._engine.save(slot_record)
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.CLIENT_CONFIRMED,
            note=payload.note,
        )
        await self._refresh_shift_progress(shift_record)

        if slot_record.assigned_guard_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.assigned_guard_tenant_id,
                title="Arrival confirmed",
                message=f"{request_record.title}: your arrival has been confirmed by the client.",
                category="success",
                source_module="requests",
                action_url=f"/dashboard/requests?slot={slot_record.id}",
                action_label="Open slot",
                metadata={"request_id": str(request_record.id), "shift_id": str(shift_record.id), "slot_id": str(slot_record.id)},
            )
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)

    async def start_shift_slot(self, slot_id: str, payload: ShiftSlotStartPayload, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        is_platform, _session_tenant = await self._assert_guard_slot_action_access(slot_record, current_user)
        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        if slot_record.arrived_at is None:
            raise HTTPException(status_code=409, detail="Guard must check in before starting the shift")
        if slot_record.started_at is not None:
            raise HTTPException(status_code=409, detail="This shift slot has already started")
        if slot_record.client_confirmed_at is None and not is_platform:
            raise HTTPException(status_code=409, detail="Client confirmation is required before starting the shift")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_record.started_at = slot_record.started_at or now
        slot_record.actual_start_at = slot_record.actual_start_at or now
        slot_record.slot_status = ShiftSlotStatus.IN_PROGRESS
        slot_record.updated_at = now
        await self._engine.save(slot_record)
        if slot_record.client_confirmed_at is None and is_platform:
            await self._record_slot_event(
                slot_record,
                shift_record,
                request_record,
                current_user,
                ShiftAttendanceEventType.OPS_START_OVERRIDE,
                note=payload.note,
                metadata={"client_confirmed": False},
            )
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.STARTED,
            note=payload.note,
            metadata={"platform_override": is_platform and slot_record.client_confirmed_at is None},
        )
        await self._refresh_shift_progress(shift_record)
        if request_record.request_status in {RequestStatus.SUBMITTED, RequestStatus.ASSIGNED}:
            request_record.request_status = RequestStatus.IN_PROGRESS
            request_record.updated_at = now
            await self._engine.save(request_record)
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)

    async def check_out_shift_slot(self, slot_id: str, payload: ShiftSlotCheckOutPayload, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        _is_platform, _session_tenant = await self._assert_guard_slot_action_access(slot_record, current_user)
        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        if slot_record.slot_status != ShiftSlotStatus.IN_PROGRESS or slot_record.started_at is None:
            raise HTTPException(status_code=409, detail="Only in-progress shift slots can be checked out")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_record.checked_out_at = now
        slot_record.actual_end_at = now
        slot_record.completed_at = now
        slot_record.slot_status = ShiftSlotStatus.COMPLETED
        slot_record.updated_at = now
        await self._engine.save(slot_record)
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.CHECKOUT,
            note=payload.note,
        )
        await self._record_slot_event(
            slot_record,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.COMPLETED,
            note=payload.note,
        )
        await self._refresh_shift_progress(shift_record)
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)
