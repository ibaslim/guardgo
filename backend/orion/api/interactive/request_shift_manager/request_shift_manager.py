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
    AssignmentLockReason,
    ClientRequestRecord,
    ProviderRosterPayload,
    RequestAssignmentRecord,
    RequestAssignmentScope,
    RequestAssignmentStatus,
    RequestScheduleTemplateRecord,
    RequestScheduleType,
    RequestScheduleUpsertPayload,
    RequestStatus,
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
    ShiftInstanceStatus,
    ShiftSlotCheckInPayload,
    ShiftSlotCheckOutPayload,
    ShiftSlotClientConfirmPayload,
    ShiftSlotReopenPayload,
    ShiftSlotRecord,
    ShiftSlotStartPayload,
    ShiftSlotUnavailablePayload,
    ShiftSlotStatus,
    RequestBroadcastWaveRecord,
    RequestWaveStatus,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    TenantStatus,
    TenantType,
    db_tenant_model,
)


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

_IMPLICIT_SCHEDULE_TIMEZONE = "UTC"
_DEFAULT_GENERATION_HORIZON_DAYS = 1
_DEFAULT_ROSTER_DUE_OFFSET_MINUTES = 120
_DEFAULT_UNAVAILABLE_CUTOFF_MINUTES = 120
_DEFAULT_LATE_GRACE_MINUTES = 15
_DEFAULT_NO_SHOW_CUTOFF_MINUTES = 30
_DEFAULT_CHECKIN_GEOFENCE_METERS = 200


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

    async def _non_deleted_request_ids(self, request_ids: List[str]) -> set[str]:
        normalized_ids = [str(request_id or "").strip() for request_id in request_ids if str(request_id or "").strip()]
        if not normalized_ids:
            return set()
        object_ids: List[ObjectId] = []
        for request_id in normalized_ids:
            try:
                object_ids.append(ObjectId(request_id))
            except Exception:
                continue
        if not object_ids:
            return set()
        request_collection = self._engine.get_collection(ClientRequestRecord)
        docs = await request_collection.find({"_id": {"$in": object_ids}, "deleted_at": None}).to_list(length=None)
        return {
            str(doc.get("_id") or "").strip()
            for doc in docs
            if str(doc.get("_id") or "").strip()
        }

    @staticmethod
    def _request_is_soft_deleted(request_manager, request_record: Any) -> bool:
        checker = getattr(request_manager, "_is_soft_deleted", None)
        if callable(checker):
            return bool(checker(request_record))
        return getattr(request_record, "deleted_at", None) is not None

    def _assert_request_not_soft_deleted(self, request_manager, request_record: Any, *, detail: str) -> None:
        checker = getattr(request_manager, "_assert_not_soft_deleted", None)
        if callable(checker):
            checker(request_record)
            return
        if self._request_is_soft_deleted(request_manager, request_record):
            raise HTTPException(status_code=404, detail=detail)

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
            "system_generated": bool(getattr(record, "system_generated", False)),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
        if generated_shift_count is not None:
            payload["generated_shift_count"] = int(generated_shift_count)
        return payload

    @staticmethod
    def _serialize_shift(
        record: ShiftInstanceRecord | Dict[str, Any],
        request_record: Optional[ClientRequestRecord | Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        request_title: Optional[str] = None
        site_name: Optional[str] = None
        if request_record is not None:
            if isinstance(request_record, dict):
                request_title = str(request_record.get("title") or "Client request")
                site_snapshot = request_record.get("site_snapshot") or {}
                site_name = str(site_snapshot.get("site_name") or "Unknown site")
            else:
                request_title = str(getattr(request_record, "title", "") or "Client request")
                site_snapshot = getattr(request_record, "site_snapshot", None) or {}
                site_name = str(site_snapshot.get("site_name") or "Unknown site")
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
                "request_title": request_title,
                "site_name": site_name,
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
            "request_title": request_title,
            "site_name": site_name,
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
    def _serialize_leave(record: ShiftGuardLeaveRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "guard_tenant_id": record.get("guard_tenant_id"),
                "service_provider_tenant_id": record.get("service_provider_tenant_id"),
                "leave_status": getattr(record.get("leave_status"), "value", record.get("leave_status")),
                "start_at_utc": record.get("start_at_utc"),
                "end_at_utc": record.get("end_at_utc"),
                "effective_end_at_utc": record.get("effective_end_at_utc"),
                "reason": record.get("reason"),
                "affected_slot_ids": list(record.get("affected_slot_ids") or []),
                "replacement_slot_ids": list(record.get("replacement_slot_ids") or []),
                "requested_by_user_id": record.get("requested_by_user_id"),
                "requested_by_username": record.get("requested_by_username"),
                "requested_by_role": record.get("requested_by_role"),
                "returned_early_at": record.get("returned_early_at"),
                "returned_early_by_user_id": record.get("returned_early_by_user_id"),
                "returned_early_by_username": record.get("returned_early_by_username"),
                "return_note": record.get("return_note"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }
        return {
            "id": str(record.id),
            "guard_tenant_id": record.guard_tenant_id,
            "service_provider_tenant_id": record.service_provider_tenant_id,
            "leave_status": record.leave_status.value,
            "start_at_utc": record.start_at_utc,
            "end_at_utc": record.end_at_utc,
            "effective_end_at_utc": record.effective_end_at_utc,
            "reason": record.reason,
            "affected_slot_ids": list(record.affected_slot_ids or []),
            "replacement_slot_ids": list(record.replacement_slot_ids or []),
            "requested_by_user_id": record.requested_by_user_id,
            "requested_by_username": record.requested_by_username,
            "requested_by_role": record.requested_by_role,
            "returned_early_at": record.returned_early_at,
            "returned_early_by_user_id": record.returned_early_by_user_id,
            "returned_early_by_username": record.returned_early_by_username,
            "return_note": record.return_note,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
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

    @staticmethod
    def _leave_status_value(record: ShiftGuardLeaveRecord | Dict[str, Any]) -> str:
        raw = record.leave_status if isinstance(record, ShiftGuardLeaveRecord) else record.get("leave_status")
        return getattr(raw, "value", raw or "")

    @staticmethod
    def _effective_leave_end(record: ShiftGuardLeaveRecord | Dict[str, Any]) -> Optional[datetime]:
        if isinstance(record, ShiftGuardLeaveRecord):
            return record.effective_end_at_utc or record.end_at_utc
        return record.get("effective_end_at_utc") or record.get("end_at_utc")

    @classmethod
    def _shift_overlaps_leave_window(
        cls,
        shift_record: ShiftInstanceRecord,
        *,
        leave_start_at_utc: datetime,
        leave_end_at_utc: datetime,
    ) -> bool:
        shift_start = getattr(shift_record, "shift_start_at_utc", None)
        shift_end = getattr(shift_record, "shift_end_at_utc", None)
        if shift_start is None or shift_end is None:
            return False
        return shift_end > leave_start_at_utc and shift_start < leave_end_at_utc

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
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @classmethod
    def _runtime_now_for_shift(
        cls,
        shift_record: ShiftInstanceRecord,
        schedule_record: Optional[RequestScheduleTemplateRecord] = None,
        *,
        actor_timezone: Optional[str] = None,
    ) -> datetime:
        if schedule_record and cls._is_system_generated_schedule(schedule_record):
            timezone_name = (
                str(actor_timezone or "").strip()
                or str(getattr(schedule_record, "timezone", "") or "").strip()
                or str(getattr(shift_record, "timezone", "") or "").strip()
                or "UTC"
            )
            try:
                tzinfo = cls._resolve_timezone(timezone_name)
                return datetime.now(tzinfo).replace(tzinfo=None)
            except HTTPException:
                pass
        return cls._utc_now()

    @classmethod
    def _assert_shift_has_not_ended(
        cls,
        shift_record: ShiftInstanceRecord,
        *,
        action: str,
        schedule_record: Optional[RequestScheduleTemplateRecord] = None,
        actor_timezone: Optional[str] = None,
    ) -> datetime:
        now = cls._runtime_now_for_shift(shift_record, schedule_record, actor_timezone=actor_timezone)
        if getattr(shift_record, "shift_end_at_utc", None) and shift_record.shift_end_at_utc <= now:
            raise HTTPException(status_code=409, detail=f"Cannot {action} after the shift has ended")
        return now

    @classmethod
    def _assert_shift_start_window_is_open(
        cls,
        shift_record: ShiftInstanceRecord,
        schedule_record: Optional[RequestScheduleTemplateRecord] = None,
        *,
        actor_timezone: Optional[str] = None,
    ) -> datetime:
        now = cls._assert_shift_has_not_ended(
            shift_record,
            action="start this shift",
            schedule_record=schedule_record,
            actor_timezone=actor_timezone,
        )
        if getattr(shift_record, "shift_start_at_utc", None) and shift_record.shift_start_at_utc > now:
            raise HTTPException(status_code=409, detail="Cannot start the shift before its scheduled start time")
        return now

    @classmethod
    def _assert_shift_checkin_window_is_open(
        cls,
        shift_record: ShiftInstanceRecord,
        schedule_record: RequestScheduleTemplateRecord,
        *,
        actor_timezone: Optional[str] = None,
    ) -> datetime:
        now = cls._assert_shift_has_not_ended(
            shift_record,
            action="check in",
            schedule_record=schedule_record,
            actor_timezone=actor_timezone,
        )
        shift_start = getattr(shift_record, "shift_start_at_utc", None)
        if shift_start is None:
            return now
        open_minutes = max(int(getattr(schedule_record, "unavailable_cutoff_minutes", 120) or 0), 0)
        if open_minutes <= 0:
            return now
        checkin_opens_at = shift_start - timedelta(minutes=open_minutes)
        if now < checkin_opens_at:
            try:
                shift_tz = cls._resolve_timezone(
                    str(actor_timezone or "").strip()
                    or str(getattr(schedule_record, "timezone", "") or "").strip()
                    or str(getattr(shift_record, "timezone", "") or "UTC")
                )
            except HTTPException:
                shift_tz = ZoneInfo("UTC")
            opens_at_local = datetime.combine(checkin_opens_at.date(), checkin_opens_at.time(), tzinfo=shift_tz)
            opens_at_label = opens_at_local.strftime("%b %d, %Y %I:%M %p")
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Check-in opens {open_minutes} minutes before shift start, "
                    f"at {opens_at_label} ({getattr(shift_tz, 'key', str(shift_tz))})."
                ),
            )
        return now

    @staticmethod
    def _request_display_title(request_record: ClientRequestRecord) -> str:
        return str(getattr(request_record, "title", "") or "Client request")

    async def _guard_display_name(self, guard_tenant_id: str) -> str:
        normalized_guard_id = str(guard_tenant_id or "").strip()
        if not normalized_guard_id:
            return "Assigned guard"
        try:
            guard_tenant = await self._get_guard_tenant_or_404(normalized_guard_id)
        except HTTPException:
            return normalized_guard_id
        profile = getattr(guard_tenant, "profile", None) or {}
        if isinstance(profile, dict):
            full_name = str(profile.get("full_name") or profile.get("name") or "").strip()
        else:
            full_name = str(getattr(profile, "full_name", "") or getattr(profile, "name", "") or "").strip()
        return full_name or normalized_guard_id

    async def _notify_platform_shift_exception(
        self,
        *,
        shift_record: ShiftInstanceRecord,
        slot_record: ShiftSlotRecord,
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
        await NotificationManager.get_instance().create_for_platform_admin_users(
            title=title,
            message=message,
            category="warning",
            source_module="requests",
            action_url=f"/dashboard/requests?tab=shifts&slot={slot_record.id}",
            action_label="Open shift slot",
            metadata=payload,
        )

    async def _notify_guard_leave_submission(
        self,
        *,
        leave_record: ShiftGuardLeaveRecord,
        slot_record: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
    ) -> None:
        request_title = self._request_display_title(request_record)
        guard_name = await self._guard_display_name(leave_record.guard_tenant_id)
        payload = {
            "request_id": str(request_record.id),
            "shift_id": str(shift_record.id),
            "slot_id": str(slot_record.id),
            "leave_id": str(leave_record.id),
            "exception_status": ShiftSlotStatus.UNAVAILABLE.value,
        }
        action_url = f"/dashboard/requests?tab=shifts&slot={slot_record.id}"
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Guard leave reported",
            message=(
                f"{request_title}: {guard_name} reported leave within the allowed pre-start window. "
                "Review the shift and republish replacement coverage if needed."
            ),
            category="warning",
            source_module="requests",
            action_url=action_url,
            action_label="Review shift",
            metadata=payload,
        )
        await self._notify_platform_shift_exception(
            shift_record=shift_record,
            slot_record=slot_record,
            request_record=request_record,
            title="Guard leave reported",
            message=(
                f"{guard_name} reported leave for {request_title} within the allowed 2-hour pre-start window."
            ),
            metadata={
                **payload,
                "guard_tenant_id": leave_record.guard_tenant_id,
            },
        )
        if slot_record.service_provider_tenant_id and slot_record.service_provider_tenant_id != request_record.client_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.service_provider_tenant_id,
                title="Linked guard leave reported",
                message=f"{request_title}: one of your rostered guards reported leave for this shift.",
                category="warning",
                source_module="requests",
                action_url=action_url,
                action_label="Open shift",
                metadata=payload,
            )

    async def _notify_late_arrival_ineligible(
        self,
        *,
        slot_record: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
        grace_minutes: int,
    ) -> None:
        request_title = self._request_display_title(request_record)
        guard_name = await self._guard_display_name(slot_record.assigned_guard_tenant_id or "")
        payload = {
            "request_id": str(request_record.id),
            "shift_id": str(shift_record.id),
            "slot_id": str(slot_record.id),
            "exception_status": ShiftSlotStatus.LATE_RISK.value,
            "late_grace_minutes": grace_minutes,
            "guard_tenant_id": str(slot_record.assigned_guard_tenant_id or ""),
        }
        action_url = f"/dashboard/requests?tab=shifts&slot={slot_record.id}"
        if slot_record.assigned_guard_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.assigned_guard_tenant_id,
                title="Shift check-in missed",
                message=(
                    f"{request_title}: you did not arrive within the {grace_minutes}-minute grace period "
                    "and are no longer eligible for this shift."
                ),
                category="warning",
                source_module="requests",
                action_url=action_url,
                action_label="Open shift slot",
                metadata=payload,
            )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Guard did not arrive in time",
            message=(
                f"{request_title}: {guard_name} did not arrive within the {grace_minutes}-minute grace period "
                "and did not report leave in the allowed pre-start window. Republish replacement coverage for this shift."
            ),
            category="warning",
            source_module="requests",
            action_url=action_url,
            action_label="Review shift",
            metadata=payload,
        )
        await self._notify_platform_shift_exception(
            shift_record=shift_record,
            slot_record=slot_record,
            request_record=request_record,
            title="Guard failed to arrive on time",
            message=(
                f"{guard_name} did not arrive for {request_title} within the {grace_minutes}-minute grace period "
                "and did not report leave in the allowed 2-hour pre-start window."
            ),
            metadata=payload,
        )
        if slot_record.service_provider_tenant_id and slot_record.service_provider_tenant_id != request_record.client_tenant_id:
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=slot_record.service_provider_tenant_id,
                title="Provider guard missed check-in",
                message=(
                    f"{request_title}: one of your rostered guards did not arrive within the {grace_minutes}-minute grace period."
                ),
                category="warning",
                source_module="requests",
                action_url=action_url,
                action_label="Open shift",
                metadata=payload,
            )

    async def _resolve_single_shift_slot_for_leave(
        self,
        *,
        guard_tenant_id: str,
        leave_start_at_utc: datetime,
        leave_end_at_utc: datetime,
        now: datetime,
    ) -> Tuple[ShiftSlotRecord, ShiftInstanceRecord, ClientRequestRecord]:
        candidate_slots = await self._engine.find(
            ShiftSlotRecord,
            ShiftSlotRecord.assigned_guard_tenant_id == str(guard_tenant_id),
        )
        matches: List[Tuple[ShiftSlotRecord, ShiftInstanceRecord, ClientRequestRecord]] = []
        for slot_record in candidate_slots:
            if slot_record.slot_status not in {ShiftSlotStatus.RESERVED, ShiftSlotStatus.ROSTERED}:
                continue
            try:
                shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
            except HTTPException:
                continue
            if shift_record.shift_start_at_utc <= now:
                continue
            if not self._shift_overlaps_leave_window(
                shift_record,
                leave_start_at_utc=leave_start_at_utc,
                leave_end_at_utc=leave_end_at_utc,
            ):
                continue
            request_record = await RequestManager.get_instance()._get_request_or_404(slot_record.request_id)
            matches.append((slot_record, shift_record, request_record))

        if not matches:
            raise HTTPException(
                status_code=409,
                detail="Leave can only be reported for an assigned upcoming shift within the final 2 hours before its start time",
            )
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail="Leave reporting is now shift-specific. Select only one assigned upcoming shift at a time.",
            )

        slot_record, shift_record, request_record = matches[0]
        leave_window_opens_at = shift_record.shift_start_at_utc - timedelta(minutes=120)
        if now < leave_window_opens_at:
            raise HTTPException(
                status_code=409,
                detail="Leave can only be reported within 2 hours before the job start time",
            )
        return slot_record, shift_record, request_record

    @staticmethod
    def _replacement_wave_match_limit(request_record: ClientRequestRecord) -> int:
        summary = getattr(request_record, "match_summary", None) or {}
        try:
            returned_count = int(summary.get("returned_count") or 25)
        except Exception:
            returned_count = 25
        return max(returned_count, 25)

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

    @classmethod
    def _schedule_final_end_at_utc(cls, schedule_record: RequestScheduleTemplateRecord) -> Optional[datetime]:
        try:
            tzinfo = ZoneInfo(str(schedule_record.timezone or "").strip())
            start_clock = cls._parse_local_time("start_time_local", schedule_record.start_time_local)
            end_clock = cls._parse_local_time("end_time_local", schedule_record.end_time_local)
            final_occurrence = date.fromisoformat(
                str(schedule_record.end_date_local or schedule_record.start_date_local or "").strip()
            )
        except Exception:
            return None
        _start_at_utc, end_at_utc = cls._build_shift_window(
            occurrence_date=final_occurrence,
            tzinfo=tzinfo,
            start_clock=start_clock,
            end_clock=end_clock,
            is_overnight=bool(getattr(schedule_record, "is_overnight", False)),
        )
        return end_at_utc

    @staticmethod
    def _implicit_request_window(request_record: ClientRequestRecord) -> Optional[Tuple[datetime, datetime]]:
        start_at = getattr(request_record, "requested_start_at", None)
        end_at = getattr(request_record, "requested_end_at", None)
        if start_at is None or end_at is None or end_at <= start_at:
            return None
        return start_at, end_at

    @staticmethod
    def _is_system_generated_schedule(schedule_record: Optional[RequestScheduleTemplateRecord]) -> bool:
        return bool(schedule_record and getattr(schedule_record, "system_generated", False))

    async def _ensure_implicit_request_schedule(
        self,
        request_record: ClientRequestRecord,
    ) -> Optional[RequestScheduleTemplateRecord]:
        request_window = self._implicit_request_window(request_record)
        if request_window is None:
            return None
        if request_record.request_status in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            return None

        existing = await self._engine.find_one(
            RequestScheduleTemplateRecord,
            RequestScheduleTemplateRecord.request_id == str(request_record.id),
        )
        if existing and bool(getattr(existing, "active", False)) and not self._is_system_generated_schedule(existing):
            return existing

        start_at, end_at = request_window
        now = datetime.utcnow()
        implicit_timezone = str(getattr(request_record, "timezone", "") or "").strip() or _IMPLICIT_SCHEDULE_TIMEZONE
        schedule_record = existing or RequestScheduleTemplateRecord(
            request_id=str(request_record.id),
            client_tenant_id=request_record.client_tenant_id,
            timezone=implicit_timezone,
            schedule_type=RequestScheduleType.ONE_TIME,
            start_date_local=start_at.date().isoformat(),
            end_date_local=end_at.date().isoformat(),
            start_time_local=start_at.strftime("%H:%M"),
            end_time_local=end_at.strftime("%H:%M"),
            is_overnight=end_at.date() != start_at.date() or end_at.time() <= start_at.time(),
            recurrence_days=[],
            generation_horizon_days=_DEFAULT_GENERATION_HORIZON_DAYS,
            roster_due_offset_minutes=_DEFAULT_ROSTER_DUE_OFFSET_MINUTES,
            unavailable_cutoff_minutes=_DEFAULT_UNAVAILABLE_CUTOFF_MINUTES,
            late_grace_minutes=_DEFAULT_LATE_GRACE_MINUTES,
            no_show_cutoff_minutes=_DEFAULT_NO_SHOW_CUTOFF_MINUTES,
            checkin_geofence_meters=_DEFAULT_CHECKIN_GEOFENCE_METERS,
            active=True,
            system_generated=True,
        )
        schedule_record.timezone = implicit_timezone
        schedule_record.schedule_type = RequestScheduleType.ONE_TIME
        schedule_record.start_date_local = start_at.date().isoformat()
        schedule_record.end_date_local = end_at.date().isoformat()
        schedule_record.start_time_local = start_at.strftime("%H:%M")
        schedule_record.end_time_local = end_at.strftime("%H:%M")
        schedule_record.is_overnight = end_at.date() != start_at.date() or end_at.time() <= start_at.time()
        schedule_record.recurrence_days = []
        schedule_record.generation_horizon_days = _DEFAULT_GENERATION_HORIZON_DAYS
        schedule_record.roster_due_offset_minutes = int(
            getattr(schedule_record, "roster_due_offset_minutes", None) or _DEFAULT_ROSTER_DUE_OFFSET_MINUTES
        )
        schedule_record.unavailable_cutoff_minutes = int(
            getattr(schedule_record, "unavailable_cutoff_minutes", None) or _DEFAULT_UNAVAILABLE_CUTOFF_MINUTES
        )
        schedule_record.late_grace_minutes = int(
            getattr(schedule_record, "late_grace_minutes", None) or _DEFAULT_LATE_GRACE_MINUTES
        )
        schedule_record.no_show_cutoff_minutes = int(
            getattr(schedule_record, "no_show_cutoff_minutes", None) or _DEFAULT_NO_SHOW_CUTOFF_MINUTES
        )
        schedule_record.checkin_geofence_meters = int(
            getattr(schedule_record, "checkin_geofence_meters", None) or _DEFAULT_CHECKIN_GEOFENCE_METERS
        )
        schedule_record.active = True
        schedule_record.system_generated = True
        schedule_record.updated_at = now
        return await self._engine.save(schedule_record)

    async def _sync_implicit_shift_instance_for_request(
        self,
        request_record: ClientRequestRecord,
        schedule_record: RequestScheduleTemplateRecord,
    ) -> Optional[ShiftInstanceRecord]:
        request_window = self._implicit_request_window(request_record)
        if request_window is None:
            return None

        start_at, end_at = request_window
        existing_shifts = [
            item
            for item in await self._engine.find(ShiftInstanceRecord, ShiftInstanceRecord.request_id == str(request_record.id))
            if str(getattr(item, "schedule_template_id", "") or "") == str(schedule_record.id)
        ]
        shift_record = existing_shifts[0] if existing_shifts else ShiftInstanceRecord(
            request_id=str(request_record.id),
            client_tenant_id=request_record.client_tenant_id,
            schedule_template_id=str(schedule_record.id),
            shift_date_local=start_at.date().isoformat(),
            shift_start_at_utc=start_at,
            shift_end_at_utc=end_at,
            timezone=schedule_record.timezone,
            instance_status=ShiftInstanceStatus.SCHEDULED,
            slots_required=max(int(getattr(request_record, "guards_required", 1) or 1), 1),
            slots_staffed=0,
            slots_checked_in=0,
            slots_completed=0,
            client_action_required=False,
            roster_due_at=start_at - timedelta(minutes=int(getattr(schedule_record, "roster_due_offset_minutes", 0) or 0)),
            created_from_revision=int(getattr(request_record, "request_revision", 0) or 0),
        )

        if getattr(shift_record, "instance_status", None) not in {ShiftInstanceStatus.IN_PROGRESS, ShiftInstanceStatus.COMPLETED}:
            shift_record.shift_date_local = start_at.date().isoformat()
            shift_record.shift_start_at_utc = start_at
            shift_record.shift_end_at_utc = end_at
            shift_record.timezone = schedule_record.timezone
            shift_record.slots_required = max(int(getattr(request_record, "guards_required", 1) or 1), 1)
            shift_record.roster_due_at = start_at - timedelta(
                minutes=int(getattr(schedule_record, "roster_due_offset_minutes", 0) or 0)
            )
            shift_record.created_from_revision = int(getattr(request_record, "request_revision", 0) or 0)

        shift_record.updated_at = datetime.utcnow()
        return await self._engine.save(shift_record)

    async def _sync_system_generated_assignment_shift_context(
        self,
        request_record: ClientRequestRecord,
        shift_record: ShiftInstanceRecord,
        saved_slots: List[ShiftSlotRecord],
        committed_assignments: List[RequestAssignmentRecord],
    ) -> None:
        request_manager = RequestManager.get_instance()
        if not saved_slots:
            return

        slots_by_assignment: Dict[str, List[ShiftSlotRecord]] = {}
        for slot in saved_slots:
            assignment_id = str(getattr(slot, "parent_assignment_id", "") or "").strip()
            if not assignment_id:
                continue
            slots_by_assignment.setdefault(assignment_id, []).append(slot)

        for assignment in committed_assignments:
            if request_manager._assignment_scope_value(assignment) != RequestAssignmentScope.REQUEST.value:
                continue

            assignment_id = str(getattr(assignment, "id", "") or "").strip()
            matching_slots = slots_by_assignment.get(assignment_id, [])
            desired_shift_id = str(shift_record.id)
            desired_slot_id = str(matching_slots[0].id) if len(matching_slots) == 1 else None

            if (
                str(getattr(assignment, "shift_instance_id", "") or "").strip() == desired_shift_id
                and str(getattr(assignment, "shift_slot_id", "") or "").strip() == str(desired_slot_id or "")
            ):
                continue

            assignment.shift_instance_id = desired_shift_id
            assignment.shift_slot_id = desired_slot_id
            assignment.updated_at = datetime.utcnow()
            await request_manager._engine.save(assignment)

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

        assignments = await request_manager._get_assignments_for_request(str(request_record.id))
        committed_assignments = [
            assignment for assignment in assignments if getattr(assignment, "assignment_status", None) in _COMMITTED_ASSIGNMENT_STATUSES
        ]
        committed_request_assignments = [
            assignment
            for assignment in committed_assignments
            if request_manager._assignment_scope_value(assignment) == RequestAssignmentScope.REQUEST.value
        ]

        schedule_record = await self._engine.find_one(
            RequestScheduleTemplateRecord,
            RequestScheduleTemplateRecord.request_id == str(request_record.id),
        )
        if not schedule_record or not bool(schedule_record.active):
            if committed_request_assignments:
                schedule_record = await self._ensure_implicit_request_schedule(request_record)
            if not schedule_record or not bool(schedule_record.active):
                return {"shift_count": 0, "slot_count": 0}

        if self._is_system_generated_schedule(schedule_record):
            implicit_shift = await self._sync_implicit_shift_instance_for_request(request_record, schedule_record)
            shifts = [implicit_shift] if implicit_shift else []
        else:
            shifts = await self._engine.find(ShiftInstanceRecord, ShiftInstanceRecord.request_id == str(request_record.id))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        shift_count = 0
        slot_count = 0
        for shift in shifts:
            if getattr(shift, "shift_end_at_utc", None) and shift.shift_end_at_utc < now:
                continue
            counts = await self._sync_shift_slots_for_shift(request_record, shift, committed_assignments)
            if self._is_system_generated_schedule(schedule_record):
                saved_slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift.id))
                await self._sync_system_generated_assignment_shift_context(
                    request_record,
                    shift,
                    saved_slots,
                    committed_request_assignments,
                )
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

    async def _sync_parent_request_assignment_lifecycle(
        self,
        *,
        slot_record: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
    ) -> None:
        parent_assignment_id = str(getattr(slot_record, "parent_assignment_id", "") or "").strip()
        if not parent_assignment_id:
            return

        request_manager = RequestManager.get_instance()
        parent_assignment = await request_manager._get_assignment_or_404(parent_assignment_id)
        if request_manager._assignment_scope_value(parent_assignment) != RequestAssignmentScope.REQUEST.value:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        changed = False
        current_status = getattr(parent_assignment, "assignment_status", None)
        if slot_record.started_at and current_status in {
            RequestAssignmentStatus.ACCEPTED,
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
        }:
            parent_assignment.assignment_status = RequestAssignmentStatus.IN_PROGRESS
            parent_assignment.started_at = getattr(parent_assignment, "started_at", None) or slot_record.started_at or now
            changed = True

        if slot_record.completed_at and current_status != RequestAssignmentStatus.COMPLETED:
            schedule_record = await self._get_schedule_template_or_404(shift_record.schedule_template_id)
            schedule_final_end_at_utc = self._schedule_final_end_at_utc(schedule_record)
            assignment_slots = [
                slot
                for slot in await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.request_id == str(request_record.id))
                if str(getattr(slot, "parent_assignment_id", "") or "").strip() == parent_assignment_id
                and not getattr(slot, "replacement_of_slot_id", None)
            ]
            all_assignment_slots_completed = bool(assignment_slots) and all(
                getattr(slot, "completed_at", None) is not None for slot in assignment_slots
            )
            schedule_type_value = str(getattr(getattr(schedule_record, "schedule_type", None), "value", getattr(schedule_record, "schedule_type", "")) or "").strip()
            completes_with_slot_checkout = schedule_type_value == RequestScheduleType.ONE_TIME.value
            if all_assignment_slots_completed and (
                completes_with_slot_checkout
                or (schedule_final_end_at_utc and schedule_final_end_at_utc <= now)
            ):
                parent_assignment.assignment_status = RequestAssignmentStatus.COMPLETED
                parent_assignment.started_at = (
                    getattr(parent_assignment, "started_at", None)
                    or getattr(slot_record, "started_at", None)
                    or getattr(slot_record, "actual_start_at", None)
                    or now
                )
                parent_assignment.completed_at = getattr(parent_assignment, "completed_at", None) or slot_record.completed_at or now
                changed = True

        if not changed:
            return

        parent_assignment.updated_at = now
        await self._engine.save(parent_assignment)
        await request_manager._sync_request_runtime_state(request_record)

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
        system_actor = self._system_actor()
        grace_minutes = int(getattr(schedule_record, "late_grace_minutes", 15) or 0)
        cutoff_minutes = int(getattr(schedule_record, "no_show_cutoff_minutes", 30) or 0)

        for slot_record in slots:
            if not slot_record.assigned_guard_tenant_id:
                continue
            if slot_record.arrived_at is not None or slot_record.started_at is not None or slot_record.completed_at is not None:
                continue
            if slot_record.slot_status in {
                ShiftSlotStatus.UNAVAILABLE,
                ShiftSlotStatus.REPLACEMENT_REQUIRED,
                ShiftSlotStatus.CANCELLED,
                ShiftSlotStatus.COMPLETED,
                ShiftSlotStatus.IN_PROGRESS,
            }:
                continue

            if slot_record.slot_status == ShiftSlotStatus.NO_SHOW_CONFIRMED:
                continue

            if now >= confirmed_threshold:
                if slot_record.slot_status not in {ShiftSlotStatus.LATE_RISK, ShiftSlotStatus.NO_SHOW_SUSPECTED}:
                    slot_record.slot_status = ShiftSlotStatus.LATE_RISK
                    slot_record.updated_at = now
                    await self._engine.save(slot_record)
                    await self._record_slot_event(
                        slot_record,
                        shift_record,
                        request_record,
                        system_actor,
                        ShiftAttendanceEventType.LATE_ARRIVAL,
                        metadata={"threshold_minutes": grace_minutes, "ineligible_for_shift": True},
                    )
                    await self._notify_late_arrival_ineligible(
                        slot_record=slot_record,
                        shift_record=shift_record,
                        request_record=request_record,
                        grace_minutes=grace_minutes,
                    )
                if slot_record.slot_status != ShiftSlotStatus.NO_SHOW_CONFIRMED:
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
                        metadata={"threshold_minutes": cutoff_minutes},
                    )
                changed = True
                continue

            if now >= suspected_threshold and slot_record.slot_status in {ShiftSlotStatus.RESERVED, ShiftSlotStatus.ROSTERED}:
                slot_record.slot_status = ShiftSlotStatus.LATE_RISK
                slot_record.updated_at = now
                await self._engine.save(slot_record)
                await self._record_slot_event(
                    slot_record,
                    shift_record,
                    request_record,
                    system_actor,
                    ShiftAttendanceEventType.LATE_ARRIVAL,
                    metadata={"threshold_minutes": grace_minutes, "ineligible_for_shift": True},
                )
                await self._notify_late_arrival_ineligible(
                    slot_record=slot_record,
                    shift_record=shift_record,
                    request_record=request_record,
                    grace_minutes=grace_minutes,
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
            visible_request_ids = await self._non_deleted_request_ids([
                str(doc.get("request_id") or "").strip()
                for doc in docs
            ])
            return {
                str(doc.get("_id"))
                for doc in docs
                if doc.get("_id") and str(doc.get("request_id") or "").strip() in visible_request_ids
            }

        if role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
            docs = await slot_collection.find({"coverage_tenant_id": tenant_id}).to_list(length=None)
            visible_request_ids = await self._non_deleted_request_ids([
                str(doc.get("request_id") or "").strip()
                for doc in docs
            ])
            return {
                str(doc.get("shift_instance_id"))
                for doc in docs
                if doc.get("shift_instance_id") and str(doc.get("request_id") or "").strip() in visible_request_ids
            }

        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            docs = await slot_collection.find(
                {"$or": [{"assigned_guard_tenant_id": tenant_id}, {"coverage_tenant_id": tenant_id}]}
            ).to_list(length=None)
            visible_request_ids = await self._non_deleted_request_ids([
                str(doc.get("request_id") or "").strip()
                for doc in docs
            ])
            return {
                str(doc.get("shift_instance_id"))
                for doc in docs
                if doc.get("shift_instance_id") and str(doc.get("request_id") or "").strip() in visible_request_ids
            }

        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _ensure_implicit_shift_slots_for_current_view(
        self,
        current_user,
        *,
        request_id: str = "",
        limit: int = 200,
    ) -> None:
        request_manager = RequestManager.get_instance()
        normalized_request_id = str(request_id or "").strip()
        if normalized_request_id:
            try:
                request_record = await request_manager._get_request_or_404(normalized_request_id)
            except HTTPException:
                return
            if self._request_is_soft_deleted(request_manager, request_record):
                return
            await self.sync_shift_slots_for_request(request_record)
            return

        role_value = request_manager._role_value(current_user)
        if request_manager._is_platform_role(role_value):
            return

        session_tenant = await request_manager._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)
        assignment_query: Dict[str, Any] = {
            "assignment_scope": RequestAssignmentScope.REQUEST.value,
            "assignment_status": {"$in": [status.value for status in _COMMITTED_ASSIGNMENT_STATUSES]},
        }
        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            assignment_query["client_tenant_id"] = tenant_id
        elif role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            assignment_query["assignee_tenant_id"] = tenant_id
        else:
            return

        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        assignment_docs = await assignment_collection.find(assignment_query).to_list(length=max(int(limit or 0), 0) or 200)
        seen_request_ids: set[str] = set()
        for assignment_doc in assignment_docs:
            current_request_id = str(assignment_doc.get("request_id") or "").strip()
            if not current_request_id or current_request_id in seen_request_ids:
                continue
            seen_request_ids.add(current_request_id)
            try:
                request_record = await request_manager._get_request_or_404(current_request_id)
            except HTTPException:
                continue
            if self._request_is_soft_deleted(request_manager, request_record):
                continue
            await self.sync_shift_slots_for_request(request_record)

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

    async def _get_shift_guard_leave_or_404(self, leave_id: str) -> ShiftGuardLeaveRecord:
        try:
            object_id = ObjectId(leave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid shift guard leave id")
        record = await self._engine.find_one(ShiftGuardLeaveRecord, ShiftGuardLeaveRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Shift guard leave not found")
        return record

    async def _get_guard_tenant_or_404(self, guard_tenant_id: str) -> db_tenant_model:
        if not ObjectId.is_valid(str(guard_tenant_id or "")):
            raise HTTPException(status_code=400, detail="Invalid guard tenant id")
        guard = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(str(guard_tenant_id)))
        if not guard or guard.tenant_type != TenantType.GUARD:
            raise HTTPException(status_code=404, detail="Guard tenant not found")
        return guard

    async def _resolve_leave_target_guard(self, payload: ShiftGuardLeaveCreatePayload, current_user) -> db_tenant_model:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        requested_guard_id = str(payload.guard_tenant_id or "").strip() or None

        session_tenant = await request_manager._get_session_tenant(current_user)
        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            if requested_guard_id and requested_guard_id != str(session_tenant.id):
                raise HTTPException(status_code=403, detail="Guard admins can only report leave for their own guard tenant")
            return await self._get_guard_tenant_or_404(str(session_tenant.id))

        raise HTTPException(status_code=403, detail="Only the assigned guard can report leave for their own upcoming shift")

    async def _assert_guard_leave_access(self, leave_record: ShiftGuardLeaveRecord, current_user) -> None:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        if request_manager._is_platform_role(role_value):
            return
        session_tenant = await request_manager._get_session_tenant(current_user)
        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            if str(session_tenant.id) != str(leave_record.guard_tenant_id or ""):
                raise HTTPException(status_code=403, detail="This leave record does not belong to your guard tenant")
            return
        if role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
            if str(session_tenant.id) != str(leave_record.service_provider_tenant_id or ""):
                raise HTTPException(status_code=403, detail="This leave record does not belong to your service provider")
            return
        raise HTTPException(status_code=403, detail="Access forbidden")

    @classmethod
    def _restored_slot_status(cls, slot_record: ShiftSlotRecord) -> ShiftSlotStatus:
        return (
            ShiftSlotStatus.ROSTERED
            if cls._coverage_source_value(slot_record) == ShiftCoverageSourceType.SERVICE_PROVIDER.value
            else ShiftSlotStatus.RESERVED
        )

    async def _cancel_replacement_wave_for_slot(
        self,
        *,
        request_record: ClientRequestRecord,
        replacement_slot: ShiftSlotRecord,
        current_user,
        note: str,
    ) -> int:
        request_manager = RequestManager.get_instance()
        cancelled = 0
        waves = await self._engine.find(RequestBroadcastWaveRecord, RequestBroadcastWaveRecord.request_id == str(request_record.id))
        for wave in waves:
            snapshot = getattr(wave, "request_snapshot", None) or {}
            replacement_context = snapshot.get("shift_replacement") or {}
            if str(replacement_context.get("replacement_slot_id") or "") != str(replacement_slot.id):
                continue
            if wave.wave_status not in {RequestWaveStatus.ACTIVE, RequestWaveStatus.PENDING_REVIEW}:
                continue
            if wave.wave_status == RequestWaveStatus.ACTIVE:
                await request_manager._close_open_offers_for_request(
                    request_record,
                    to_status=RequestAssignmentStatus.CANCELLED,
                    lock_reason=AssignmentLockReason.REQUEST_CANCELLED,
                    wave_id=str(wave.id),
                )
            await request_manager._set_wave_status(wave, RequestWaveStatus.CANCELLED, current_user=current_user, note=note)
            cancelled += 1
        return cancelled

    async def _reconcile_leave_return_for_future_slots(
        self,
        leave_record: ShiftGuardLeaveRecord,
        *,
        current_user,
    ) -> Dict[str, int]:
        request_manager = RequestManager.get_instance()
        now = self._utc_now()
        restored_count = 0
        cancelled_replacements = 0
        cancelled_waves = 0

        for slot_id in list(leave_record.affected_slot_ids or []):
            try:
                original_slot = await self._get_shift_slot_or_404(slot_id)
                shift_record = await self._get_shift_or_404(original_slot.shift_instance_id)
            except HTTPException:
                continue
            if shift_record.shift_start_at_utc <= now:
                continue
            if original_slot.assigned_guard_tenant_id != leave_record.guard_tenant_id:
                continue

            active_replacements = await self._active_replacement_slots_for_original_slot(
                shift_record=shift_record,
                original_slot=original_slot,
            )
            request_record = await request_manager._get_request_or_404(original_slot.request_id)
            for replacement_slot in active_replacements:
                if replacement_slot.slot_status != ShiftSlotStatus.OPEN or replacement_slot.parent_assignment_id:
                    continue
                replacement_slot.slot_status = ShiftSlotStatus.CANCELLED
                replacement_slot.updated_at = now
                await self._engine.save(replacement_slot)
                cancelled_replacements += 1
                cancelled_waves += await self._cancel_replacement_wave_for_slot(
                    request_record=request_record,
                    replacement_slot=replacement_slot,
                    current_user=current_user,
                    note="Replacement cancelled because the original guard returned from leave",
                )

            remaining_replacements = await self._active_replacement_slots_for_original_slot(
                shift_record=shift_record,
                original_slot=original_slot,
            )
            if remaining_replacements:
                continue
            if original_slot.slot_status not in {
                ShiftSlotStatus.UNAVAILABLE,
                ShiftSlotStatus.LATE_RISK,
                ShiftSlotStatus.REPLACEMENT_REQUIRED,
            }:
                continue

            original_slot.slot_status = self._restored_slot_status(original_slot)
            original_slot.guard_unavailable_reported_at = None
            original_slot.updated_at = now
            await self._engine.save(original_slot)
            await self._record_slot_event(
                original_slot,
                shift_record,
                request_record,
                current_user,
                ShiftAttendanceEventType.LEAVE_RETURNED,
                note=leave_record.return_note,
                metadata={"leave_id": str(leave_record.id)},
            )
            restored_count += 1

        return {
            "restored_slot_count": restored_count,
            "cancelled_replacement_slot_count": cancelled_replacements,
            "cancelled_wave_count": cancelled_waves,
        }

    async def _get_assignment_if_present(self, assignment_id: Optional[str]) -> Optional[RequestAssignmentRecord]:
        normalized = str(assignment_id or "").strip()
        if not normalized:
            return None
        try:
            return await RequestManager.get_instance()._get_assignment_or_404(normalized)
        except HTTPException:
            return None

    async def _build_guard_leave_return_review(
        self,
        leave_record: ShiftGuardLeaveRecord,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        now = self._utc_now()
        items: List[Dict[str, Any]] = []
        summary = {
            "total_items": 0,
            "auto_restore_count": 0,
            "decision_required_count": 0,
            "locked_history_count": 0,
        }

        for slot_id in list(leave_record.affected_slot_ids or []):
            try:
                original_slot = await self._get_shift_slot_or_404(slot_id)
                shift_record = await self._get_shift_or_404(original_slot.shift_instance_id)
                request_record = await request_manager._get_request_or_404(original_slot.request_id)
            except HTTPException:
                continue

            if shift_record.shift_start_at_utc <= now:
                continue
            if original_slot.assigned_guard_tenant_id != leave_record.guard_tenant_id:
                continue

            active_replacements = await self._active_replacement_slots_for_original_slot(
                shift_record=shift_record,
                original_slot=original_slot,
            )
            replacement_slot = sorted(
                active_replacements,
                key=lambda item: (getattr(item, "created_at", now), str(getattr(item, "id", ""))),
            )[0] if active_replacements else None
            replacement_assignment = await self._get_assignment_if_present(
                getattr(replacement_slot, "parent_assignment_id", None) if replacement_slot else None,
            )

            replacement_slot_status = self._slot_status_value(replacement_slot) if replacement_slot else ""
            replacement_assignment_status = getattr(
                getattr(replacement_assignment, "assignment_status", None),
                "value",
                getattr(replacement_assignment, "assignment_status", None),
            ) if replacement_assignment else None

            review_mode = "auto_restore"
            recommended_action = ShiftGuardLeaveReturnDecisionAction.RESTORE_ORIGINAL.value
            can_restore_original = True
            can_keep_replacement = False

            if replacement_slot:
                if replacement_slot.slot_status == ShiftSlotStatus.OPEN and not replacement_slot.parent_assignment_id:
                    review_mode = "auto_restore"
                elif replacement_slot.slot_status in {ShiftSlotStatus.RESERVED, ShiftSlotStatus.ROSTERED} and not replacement_slot.started_at:
                    review_mode = "manual_review"
                    recommended_action = ShiftGuardLeaveReturnDecisionAction.KEEP_REPLACEMENT.value
                    can_keep_replacement = True
                else:
                    review_mode = "keep_history"
                    recommended_action = ShiftGuardLeaveReturnDecisionAction.KEEP_REPLACEMENT.value
                    can_restore_original = False
                    can_keep_replacement = True

            items.append({
                "original_slot_id": str(original_slot.id),
                "original_slot_status": self._slot_status_value(original_slot),
                "shift_id": str(shift_record.id),
                "request_id": str(request_record.id),
                "request_title": self._request_display_title(request_record),
                "shift_date_local": shift_record.shift_date_local,
                "shift_start_at_utc": shift_record.shift_start_at_utc,
                "shift_end_at_utc": shift_record.shift_end_at_utc,
                "replacement_slot_id": str(replacement_slot.id) if replacement_slot else None,
                "replacement_slot_status": replacement_slot_status or None,
                "replacement_assignment_id": str(replacement_assignment.id) if replacement_assignment else None,
                "replacement_assignment_status": replacement_assignment_status,
                "replacement_assignee_tenant_id": getattr(replacement_assignment, "assignee_tenant_id", None),
                "replacement_assignee_tenant_type": getattr(
                    getattr(replacement_assignment, "assignee_tenant_type", None),
                    "value",
                    getattr(replacement_assignment, "assignee_tenant_type", None),
                ) if replacement_assignment else None,
                "replacement_assigned_guard_tenant_id": getattr(replacement_slot, "assigned_guard_tenant_id", None) if replacement_slot else None,
                "review_mode": review_mode,
                "recommended_action": recommended_action,
                "can_restore_original": can_restore_original,
                "can_keep_replacement": can_keep_replacement,
            })

            summary["total_items"] += 1
            if review_mode == "manual_review":
                summary["decision_required_count"] += 1
            elif review_mode == "keep_history":
                summary["locked_history_count"] += 1
            else:
                summary["auto_restore_count"] += 1

        return {
            "leave": self._serialize_leave(leave_record),
            "items": items,
            "summary": summary,
        }

    async def _cancel_replacement_assignment_for_leave_return(
        self,
        *,
        assignment: RequestAssignmentRecord,
        request_record: ClientRequestRecord,
        current_user,
        note: Optional[str],
    ) -> int:
        if assignment.assignment_status in {
            RequestAssignmentStatus.IN_PROGRESS,
            RequestAssignmentStatus.COMPLETED,
            RequestAssignmentStatus.CANCELLED,
            RequestAssignmentStatus.DECLINED,
            RequestAssignmentStatus.EXPIRED,
            RequestAssignmentStatus.CLOSED_FILLED,
            RequestAssignmentStatus.SUPERSEDED,
        }:
            return 0

        request_manager = RequestManager.get_instance()
        now = self._utc_now()
        assignment.assignment_status = RequestAssignmentStatus.CANCELLED
        assignment.cancelled_at = now
        assignment.updated_at = now
        if note:
            assignment.note = note
        await request_manager._engine.save(assignment)
        await request_manager._sync_request_runtime_state(request_record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=assignment.assignee_tenant_id,
            title="Replacement job cancelled",
            message=(
                f"{self._request_display_title(request_record)}: a future replacement shift was returned "
                "to the original guard after leave reconciliation."
            ),
            category="info",
            source_module="requests",
            action_url=f"/dashboard/requests?tab=jobs&job={assignment.id}",
            action_label="Open jobs",
            metadata={
                "assignment_id": str(assignment.id),
                "request_id": str(request_record.id),
                "assignment_status": RequestAssignmentStatus.CANCELLED.value,
            },
        )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=assignment.client_tenant_id,
            title="Replacement job cancelled",
            message=(
                f"{self._request_display_title(request_record)}: a future replacement shift was handed back "
                "to the original guard."
            ),
            category="info",
            source_module="requests",
            action_url=f"/dashboard/requests?tab=shifts&request={request_record.id}",
            action_label="Open shifts",
            metadata={
                "assignment_id": str(assignment.id),
                "request_id": str(request_record.id),
                "assignment_status": RequestAssignmentStatus.CANCELLED.value,
            },
        )
        await request_manager._write_activity(
            action="shift_replacement_assignment_cancelled_for_leave_return",
            entity_type="assignment",
            entity_id=str(assignment.id),
            current_user=current_user,
            reason=note,
            metadata={"request_id": str(request_record.id)},
            severity="warning",
        )
        return 1

    async def _restore_original_slot_from_leave_return(
        self,
        *,
        leave_record: ShiftGuardLeaveRecord,
        original_slot: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
        replacement_slot: Optional[ShiftSlotRecord],
        replacement_assignment: Optional[RequestAssignmentRecord],
        current_user,
        note: Optional[str],
    ) -> Dict[str, int]:
        now = self._utc_now()
        cancelled_replacement_slots = 0
        cancelled_waves = 0
        cancelled_assignments = 0
        restored_slots = 0

        if replacement_assignment:
            cancelled_assignments += await self._cancel_replacement_assignment_for_leave_return(
                assignment=replacement_assignment,
                request_record=request_record,
                current_user=current_user,
                note=note,
            )

        if replacement_slot and replacement_slot.slot_status != ShiftSlotStatus.CANCELLED:
            replacement_slot.slot_status = ShiftSlotStatus.CANCELLED
            replacement_slot.updated_at = now
            await self._engine.save(replacement_slot)
            cancelled_replacement_slots += 1
            cancelled_waves += await self._cancel_replacement_wave_for_slot(
                request_record=request_record,
                replacement_slot=replacement_slot,
                current_user=current_user,
                note=note or "Replacement cancelled because the original guard returned from leave",
            )

        remaining_replacements = await self._active_replacement_slots_for_original_slot(
            shift_record=shift_record,
            original_slot=original_slot,
        )
        if not remaining_replacements and original_slot.slot_status in {
            ShiftSlotStatus.UNAVAILABLE,
            ShiftSlotStatus.LATE_RISK,
            ShiftSlotStatus.REPLACEMENT_REQUIRED,
        }:
            original_slot.slot_status = self._restored_slot_status(original_slot)
            original_slot.guard_unavailable_reported_at = None
            original_slot.updated_at = now
            await self._engine.save(original_slot)
            await self._record_slot_event(
                original_slot,
                shift_record,
                request_record,
                current_user,
                ShiftAttendanceEventType.LEAVE_RETURNED,
                note=note or leave_record.return_note,
                metadata={
                    "leave_id": str(leave_record.id),
                    "replacement_slot_id": str(replacement_slot.id) if replacement_slot else None,
                },
            )
            restored_slots += 1

        return {
            "restored_slot_count": restored_slots,
            "cancelled_replacement_slot_count": cancelled_replacement_slots,
            "cancelled_wave_count": cancelled_waves,
            "cancelled_assignment_count": cancelled_assignments,
        }

    async def _apply_guard_leave_record(
        self,
        leave_record: ShiftGuardLeaveRecord,
        *,
        current_user,
    ) -> Dict[str, int]:
        request_manager = RequestManager.get_instance()
        leave_end_at_utc = self._effective_leave_end(leave_record)
        if leave_end_at_utc is None:
            return {"affected_slot_count": 0, "replacement_slot_count": 0}

        now = self._utc_now()
        affected_slot_count = 0
        replacement_slot_count = 0
        slots = await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.assigned_guard_tenant_id == str(leave_record.guard_tenant_id))
        for slot_record in slots:
            if str(slot_record.id) in set(leave_record.affected_slot_ids or []):
                continue
            if slot_record.slot_status in {ShiftSlotStatus.CANCELLED, ShiftSlotStatus.COMPLETED, ShiftSlotStatus.IN_PROGRESS}:
                continue
            try:
                shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
            except HTTPException:
                continue
            if shift_record.shift_start_at_utc <= now:
                continue
            if not self._shift_overlaps_leave_window(
                shift_record,
                leave_start_at_utc=leave_record.start_at_utc,
                leave_end_at_utc=leave_end_at_utc,
            ):
                continue

            request_record = await request_manager._get_request_or_404(slot_record.request_id)
            slot_record.guard_unavailable_reported_at = now
            slot_record.slot_status = ShiftSlotStatus.UNAVAILABLE
            slot_record.updated_at = now
            await self._engine.save(slot_record)
            await self._record_slot_event(
                slot_record,
                shift_record,
                request_record,
                current_user,
                ShiftAttendanceEventType.LEAVE_REPORTED,
                note=leave_record.reason,
                metadata={
                    "leave_id": str(leave_record.id),
                    "leave_start_at_utc": leave_record.start_at_utc.isoformat(),
                    "leave_end_at_utc": leave_end_at_utc.isoformat(),
                },
            )
            leave_record.affected_slot_ids = list(dict.fromkeys([*list(leave_record.affected_slot_ids or []), str(slot_record.id)]))
            affected_slot_count += 1

            await self._notify_guard_leave_submission(
                leave_record=leave_record,
                slot_record=slot_record,
                shift_record=shift_record,
                request_record=request_record,
            )

        leave_record.updated_at = now
        await self._engine.save(leave_record)
        return {
            "affected_slot_count": affected_slot_count,
            "replacement_slot_count": replacement_slot_count,
        }

    async def sync_active_guard_leaves(self, *, limit: int = 200) -> int:
        now = self._utc_now()
        leave_records = await self._engine.find(ShiftGuardLeaveRecord, ShiftGuardLeaveRecord.leave_status == ShiftGuardLeaveStatus.ACTIVE)
        touched = 0
        for leave_record in sorted(
            list(leave_records)[: max(int(limit or 0), 0) or len(leave_records)],
            key=lambda item: (item.start_at_utc, item.created_at, str(item.id)),
        ):
            if self._effective_leave_end(leave_record) and self._effective_leave_end(leave_record) <= now:
                leave_record.leave_status = ShiftGuardLeaveStatus.COMPLETED
                leave_record.updated_at = now
                await self._engine.save(leave_record)
                touched += 1
                continue
            summary = await self._apply_guard_leave_record(leave_record, current_user=self._system_actor())
            if summary["affected_slot_count"] or summary["replacement_slot_count"]:
                touched += 1
        return touched

    async def list_guard_leaves(
        self,
        *,
        current_user,
        page: int = 1,
        rows: int = 20,
        guard_tenant_id: str = "",
        leave_status: str = "",
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        role_value = request_manager._role_value(current_user)
        normalized_guard_id = str(guard_tenant_id or "").strip()
        normalized_status = str(leave_status or "").strip().lower()
        if normalized_status and normalized_status not in {status.value for status in ShiftGuardLeaveStatus}:
            raise HTTPException(status_code=400, detail="Invalid shift guard leave status filter")

        records = await self._engine.find(ShiftGuardLeaveRecord, {})
        visible: List[ShiftGuardLeaveRecord] = []
        session_tenant = None if request_manager._is_platform_role(role_value) else await request_manager._get_session_tenant(current_user)
        for record in records:
            if request_manager._is_platform_role(role_value):
                pass
            elif role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
                if str(record.guard_tenant_id or "") != str(session_tenant.id):
                    continue
            elif role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
                if str(record.service_provider_tenant_id or "") != str(session_tenant.id):
                    continue
            else:
                raise HTTPException(status_code=403, detail="Access forbidden")
            if normalized_guard_id and str(record.guard_tenant_id or "") != normalized_guard_id:
                continue
            if normalized_status and self._leave_status_value(record) != normalized_status:
                continue
            visible.append(record)

        ordered = sorted(visible, key=lambda item: (item.created_at, str(item.id)), reverse=True)
        page_number = max(int(page or 1), 1)
        page_size = max(int(rows or 20), 1)
        start_index = (page_number - 1) * page_size
        items = ordered[start_index:start_index + page_size]
        total_items = len(ordered)
        total_pages = (total_items + page_size - 1) // page_size if total_items else 0
        return {
            "items": [self._serialize_leave(item) for item in items],
            "pagination": {
                "page": page_number,
                "rows": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "guard_tenant_id": normalized_guard_id,
                "leave_status": normalized_status,
            },
        }

    async def report_guard_leave(
        self,
        payload: ShiftGuardLeaveCreatePayload,
        current_user,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        guard_tenant = await self._resolve_leave_target_guard(payload, current_user)
        now = self._utc_now()
        if payload.end_at_utc <= payload.start_at_utc:
            raise HTTPException(status_code=400, detail="Leave end time must be after leave start time")
        slot_record, shift_record, _request_record = await self._resolve_single_shift_slot_for_leave(
            guard_tenant_id=str(guard_tenant.id),
            leave_start_at_utc=payload.start_at_utc,
            leave_end_at_utc=payload.end_at_utc,
            now=now,
        )

        existing_records = await self._engine.find(ShiftGuardLeaveRecord, ShiftGuardLeaveRecord.guard_tenant_id == str(guard_tenant.id))
        for existing in existing_records:
            if existing.leave_status != ShiftGuardLeaveStatus.ACTIVE:
                continue
            existing_end = self._effective_leave_end(existing)
            if existing_end and existing_end > shift_record.shift_start_at_utc and existing.start_at_utc < shift_record.shift_end_at_utc:
                raise HTTPException(status_code=409, detail="An overlapping active leave record already exists for this guard")

        leave_record = ShiftGuardLeaveRecord(
            id=ObjectId(),
            guard_tenant_id=str(guard_tenant.id),
            service_provider_tenant_id=str(getattr(guard_tenant, "service_provider_tenant_id", "") or "").strip() or None,
            leave_status=ShiftGuardLeaveStatus.ACTIVE,
            start_at_utc=shift_record.shift_start_at_utc,
            end_at_utc=shift_record.shift_end_at_utc,
            effective_end_at_utc=shift_record.shift_end_at_utc,
            reason=self._parse_optional_note(payload.reason),
            requested_by_user_id=str(getattr(current_user, "id", "") or ""),
            requested_by_username=str(getattr(current_user, "username", "") or ""),
            requested_by_role=request_manager._role_value(current_user),
            created_at=now,
            updated_at=now,
        )
        await self._engine.save(leave_record)
        summary = await self._apply_guard_leave_record(leave_record, current_user=current_user)

        await request_manager._write_activity(
            action="shift_guard_leave_reported",
            entity_type="shift_guard_leave",
            entity_id=str(leave_record.id),
            current_user=current_user,
            metadata={
                "guard_tenant_id": str(guard_tenant.id),
                "affected_slot_count": summary["affected_slot_count"],
                "replacement_slot_count": summary["replacement_slot_count"],
            },
        )
        return {
            "message": "Guard leave recorded",
            "item": self._serialize_leave(leave_record),
            "summary": summary,
        }

    async def return_guard_leave_early(
        self,
        leave_id: str,
        payload: ShiftGuardLeaveReturnPayload,
        current_user,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        leave_record = await self._get_shift_guard_leave_or_404(leave_id)
        await self._assert_guard_leave_access(leave_record, current_user)
        if leave_record.leave_status != ShiftGuardLeaveStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Only active leave records can be returned early")

        now = self._utc_now()
        leave_record.leave_status = ShiftGuardLeaveStatus.RETURNED_EARLY
        leave_record.effective_end_at_utc = now
        leave_record.returned_early_at = now
        leave_record.returned_early_by_user_id = str(getattr(current_user, "id", "") or "")
        leave_record.returned_early_by_username = str(getattr(current_user, "username", "") or "")
        leave_record.return_note = self._parse_optional_note(payload.note)
        leave_record.updated_at = now
        await self._engine.save(leave_record)
        summary = await self._reconcile_leave_return_for_future_slots(leave_record, current_user=current_user)

        await request_manager._write_activity(
            action="shift_guard_leave_returned_early",
            entity_type="shift_guard_leave",
            entity_id=str(leave_record.id),
            current_user=current_user,
            metadata={
                "guard_tenant_id": leave_record.guard_tenant_id,
                "restored_slot_count": summary["restored_slot_count"],
                "cancelled_replacement_slot_count": summary["cancelled_replacement_slot_count"],
                "cancelled_wave_count": summary["cancelled_wave_count"],
            },
        )
        return {
            "message": "Guard leave ended early",
            "item": self._serialize_leave(leave_record),
            "summary": summary,
        }

    async def get_guard_leave_return_review(
        self,
        leave_id: str,
        current_user,
    ) -> Dict[str, Any]:
        leave_record = await self._get_shift_guard_leave_or_404(leave_id)
        await self._assert_guard_leave_access(leave_record, current_user)
        return await self._build_guard_leave_return_review(leave_record)

    async def reconcile_guard_leave_return(
        self,
        leave_id: str,
        payload: ShiftGuardLeaveReconcilePayload,
        current_user,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        leave_record = await self._get_shift_guard_leave_or_404(leave_id)
        await self._assert_guard_leave_access(leave_record, current_user)
        if leave_record.leave_status != ShiftGuardLeaveStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Only active leave records can be reconciled for return")

        review = await self._build_guard_leave_return_review(leave_record)
        review_items = review.get("items") or []
        decision_map: Dict[str, str] = {}
        for decision in list(getattr(payload, "decisions", []) or []):
            original_slot_id = str(getattr(decision, "original_slot_id", "") or "").strip()
            action_value = getattr(getattr(decision, "action", None), "value", getattr(decision, "action", None))
            if not original_slot_id or not action_value:
                continue
            if original_slot_id in decision_map:
                raise HTTPException(status_code=400, detail="Duplicate leave return decision for the same original slot")
            decision_map[original_slot_id] = str(action_value)

        known_original_slot_ids = {str(item.get("original_slot_id") or "") for item in review_items}
        unknown_decisions = sorted(slot_id for slot_id in decision_map if slot_id not in known_original_slot_ids)
        if unknown_decisions:
            raise HTTPException(status_code=400, detail="One or more leave return decisions reference unknown future slots")

        now = self._utc_now()
        restored_slots = 0
        cancelled_replacement_slots = 0
        cancelled_waves = 0
        cancelled_assignments = 0
        kept_replacements = 0

        for item in review_items:
            original_slot_id = str(item.get("original_slot_id") or "")
            review_mode = str(item.get("review_mode") or "")
            recommended_action = str(item.get("recommended_action") or ShiftGuardLeaveReturnDecisionAction.RESTORE_ORIGINAL.value)
            action_value = decision_map.get(original_slot_id, recommended_action)

            if review_mode == "manual_review" and original_slot_id not in decision_map:
                raise HTTPException(
                    status_code=400,
                    detail="Explicit decisions are required for future replacement shifts that are already committed",
                )
            if action_value == ShiftGuardLeaveReturnDecisionAction.RESTORE_ORIGINAL.value and not bool(item.get("can_restore_original")):
                raise HTTPException(status_code=400, detail="One or more selected future replacement shifts can no longer be restored")
            if action_value == ShiftGuardLeaveReturnDecisionAction.KEEP_REPLACEMENT.value and not bool(item.get("can_keep_replacement")):
                raise HTTPException(status_code=400, detail="One or more selected future replacement shifts cannot be kept as replacement coverage")

            if action_value == ShiftGuardLeaveReturnDecisionAction.KEEP_REPLACEMENT.value:
                kept_replacements += 1
                continue

            original_slot = await self._get_shift_slot_or_404(original_slot_id)
            shift_record = await self._get_shift_or_404(item["shift_id"])
            request_record = await request_manager._get_request_or_404(item["request_id"])
            replacement_slot = (
                await self._get_shift_slot_or_404(item["replacement_slot_id"])
                if str(item.get("replacement_slot_id") or "").strip()
                else None
            )
            replacement_assignment = await self._get_assignment_if_present(item.get("replacement_assignment_id"))

            result = await self._restore_original_slot_from_leave_return(
                leave_record=leave_record,
                original_slot=original_slot,
                shift_record=shift_record,
                request_record=request_record,
                replacement_slot=replacement_slot,
                replacement_assignment=replacement_assignment,
                current_user=current_user,
                note=payload.note,
            )
            restored_slots += int(result["restored_slot_count"])
            cancelled_replacement_slots += int(result["cancelled_replacement_slot_count"])
            cancelled_waves += int(result["cancelled_wave_count"])
            cancelled_assignments += int(result["cancelled_assignment_count"])

        leave_record.leave_status = ShiftGuardLeaveStatus.RETURNED_EARLY
        leave_record.effective_end_at_utc = now
        leave_record.returned_early_at = now
        leave_record.returned_early_by_user_id = str(getattr(current_user, "id", "") or "")
        leave_record.returned_early_by_username = str(getattr(current_user, "username", "") or "")
        leave_record.return_note = self._parse_optional_note(payload.note)
        leave_record.updated_at = now
        await self._engine.save(leave_record)

        summary = {
            "restored_slot_count": restored_slots,
            "cancelled_replacement_slot_count": cancelled_replacement_slots,
            "cancelled_wave_count": cancelled_waves,
            "cancelled_assignment_count": cancelled_assignments,
            "kept_replacement_count": kept_replacements,
            "decision_required_count": int((review.get("summary") or {}).get("decision_required_count") or 0),
        }
        await request_manager._write_activity(
            action="shift_guard_leave_return_reconciled",
            entity_type="shift_guard_leave",
            entity_id=str(leave_record.id),
            current_user=current_user,
            reason=payload.note,
            metadata={
                "guard_tenant_id": leave_record.guard_tenant_id,
                **summary,
            },
        )
        return {
            "message": "Guard leave return reconciled",
            "item": self._serialize_leave(leave_record),
            "summary": summary,
        }

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
        template_record.system_generated = False
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

    async def ensure_future_shift_instances_for_active_schedules(self, limit: int = 200) -> Dict[str, int]:
        request_manager = RequestManager.get_instance()
        schedule_records = [
            record
            for record in await self._engine.find(RequestScheduleTemplateRecord, RequestScheduleTemplateRecord.active == True)
            if bool(getattr(record, "active", False))
        ][: max(int(limit or 0), 0) or 200]

        created_shift_count = 0
        touched_request_ids: set[str] = set()

        for schedule_record in schedule_records:
            request_id = str(getattr(schedule_record, "request_id", "") or "").strip()
            if not request_id:
                continue

            try:
                request_record = await request_manager._get_request_or_404(request_id)
            except HTTPException:
                continue

            if request_record.request_status in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
                continue
            if getattr(request_record, "expired_at", None) is not None:
                continue

            try:
                tzinfo = self._resolve_timezone(str(getattr(schedule_record, "timezone", "") or "").strip())
                start_clock = self._parse_local_time("start_time_local", getattr(schedule_record, "start_time_local", ""))
                end_clock = self._parse_local_time("end_time_local", getattr(schedule_record, "end_time_local", ""))
                recurrence_days = self._normalize_recurrence_days(list(getattr(schedule_record, "recurrence_days", []) or []))
                schedule_payload = SimpleNamespace(
                    start_date=date.fromisoformat(str(getattr(schedule_record, "start_date_local", "") or "").strip()),
                    end_date=(
                        date.fromisoformat(str(getattr(schedule_record, "end_date_local", "") or "").strip())
                        if str(getattr(schedule_record, "end_date_local", "") or "").strip()
                        else None
                    ),
                    schedule_type=getattr(schedule_record, "schedule_type", RequestScheduleType.ONE_TIME),
                    generation_horizon_days=int(getattr(schedule_record, "generation_horizon_days", 30) or 30),
                )
                generated_instances = self._build_shift_instances(
                    request_record=request_record,
                    template_record=schedule_record,
                    payload=schedule_payload,
                    tzinfo=tzinfo,
                    start_clock=start_clock,
                    end_clock=end_clock,
                    recurrence_days=recurrence_days,
                    is_overnight=bool(getattr(schedule_record, "is_overnight", False)),
                )
            except Exception:
                continue

            existing_shifts = await self._engine.find(
                ShiftInstanceRecord,
                ShiftInstanceRecord.schedule_template_id == str(schedule_record.id),
            )
            existing_dates = {
                str(getattr(existing_shift, "shift_date_local", "") or "").strip()
                for existing_shift in existing_shifts
            }

            request_touched = False
            for instance in generated_instances:
                instance_date = str(getattr(instance, "shift_date_local", "") or "").strip()
                if not instance_date or instance_date in existing_dates:
                    continue
                await self._engine.save(instance)
                existing_dates.add(instance_date)
                created_shift_count += 1
                request_touched = True

            if request_touched:
                await self.sync_shift_slots_for_request(request_record)
                touched_request_ids.add(str(request_record.id))

        return {
            "active_schedule_count": len(schedule_records),
            "created_shift_count": created_shift_count,
            "touched_request_count": len(touched_request_ids),
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
        await self._ensure_implicit_shift_slots_for_current_view(current_user, request_id=request_id)
        visible_shift_ids = await self._visible_shift_ids_for_user(current_user)
        if visible_shift_ids is not None and not visible_shift_ids:
            return {
                "items": [],
                "pagination": {"page": max(page, 1), "rows": max(rows, 1), "total_items": 0, "total_pages": 0},
            }

        if request_id:
            record = await request_manager._get_request_or_404(request_id)
            self._assert_request_not_soft_deleted(request_manager, record, detail="Request not found")
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
        request_ids = [str(doc.get("request_id") or "").strip() for doc in docs if str(doc.get("request_id") or "").strip()]
        allowed_request_ids = await self._non_deleted_request_ids(request_ids)
        request_lookup: Dict[str, Dict[str, Any]] = {}
        if allowed_request_ids:
            request_collection = self._engine.get_collection(ClientRequestRecord)
            request_docs = await request_collection.find({
                "_id": {"$in": [ObjectId(request_id) for request_id in allowed_request_ids]},
                "deleted_at": None,
            }).to_list(length=None)
            for request_doc in request_docs:
                request_lookup[str(request_doc.get("_id") or "").strip()] = request_doc
        items = []
        for doc in docs:
            request_id = str(doc.get("request_id") or "").strip()
            if request_id not in allowed_request_ids:
                continue
            shift_record = await self._get_shift_or_404(str(doc.get("_id")))
            shift_record = await self._sync_shift_runtime_exception_states(shift_record)
            items.append(self._serialize_shift(shift_record, request_lookup.get(request_id)))
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
        if self._request_is_soft_deleted(request_manager, request_record):
            raise HTTPException(status_code=404, detail="Shift not found")
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
            "shift": self._serialize_shift(record, request_record),
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
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(shift_record.request_id)
        if self._request_is_soft_deleted(request_manager, request_record):
            raise HTTPException(status_code=404, detail="Shift slot not found")
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
            self._assert_request_not_soft_deleted(request_manager, request_record, detail="Request not found")
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
                request_record = await request_manager._get_request_or_404(shift_record.request_id)
                if self._request_is_soft_deleted(request_manager, request_record):
                    continue
                request_cache[shift_record.request_id] = request_record

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
            if not request_record:
                continue
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
        if not is_platform:
            raise HTTPException(
                status_code=403,
                detail="Assigned guards must use the leave flow within the final 2 hours before shift start",
            )
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
        actor_label = "Platform ops marked" if is_platform else "A guard reported"
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Shift coverage exception reported",
            message=f"{request_title}: {actor_label} this shift slot as {status_label}.",
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
                message=(
                    f"{request_title}: "
                    + ("platform ops marked" if is_platform else "one of your rostered guards reported")
                    + f" this shift slot as {status_label}."
                ),
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

    async def _active_replacement_slots_for_original_slot(
        self,
        *,
        shift_record: ShiftInstanceRecord,
        original_slot: ShiftSlotRecord,
    ) -> List[ShiftSlotRecord]:
        return [
            slot
            for slot in await self._engine.find(ShiftSlotRecord, ShiftSlotRecord.shift_instance_id == str(shift_record.id))
            if str(getattr(slot, "replacement_of_slot_id", "") or "") == str(original_slot.id)
            and getattr(slot, "slot_status", None) not in {ShiftSlotStatus.CANCELLED, ShiftSlotStatus.COMPLETED}
        ]

    async def _open_replacement_slot_for_exception(
        self,
        *,
        original_slot: ShiftSlotRecord,
        shift_record: ShiftInstanceRecord,
        request_record: ClientRequestRecord,
        current_user,
        note: Optional[str],
        max_match_results: int,
        auto_generated: bool,
        notification_title: Optional[str] = None,
        notification_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        request_manager = RequestManager.get_instance()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if shift_record.shift_end_at_utc <= now:
            raise HTTPException(status_code=409, detail="Cannot reopen a shift slot after the shift has ended")

        existing_replacements = await self._active_replacement_slots_for_original_slot(
            shift_record=shift_record,
            original_slot=original_slot,
        )
        if existing_replacements:
            if original_slot.slot_status != ShiftSlotStatus.REPLACEMENT_REQUIRED:
                original_slot.slot_status = ShiftSlotStatus.REPLACEMENT_REQUIRED
                original_slot.updated_at = now
                await self._engine.save(original_slot)
            return {
                "created": False,
                "replacement_slot": existing_replacements[0],
                "wave": None,
            }

        previous_status = self._slot_status_value(original_slot)
        original_slot.slot_status = ShiftSlotStatus.REPLACEMENT_REQUIRED
        original_slot.updated_at = now
        await self._engine.save(original_slot)
        await self._record_slot_event(
            original_slot,
            shift_record,
            request_record,
            current_user,
            ShiftAttendanceEventType.REPLACEMENT_REQUESTED,
            note=note,
            metadata={
                "original_status": previous_status,
                "auto_generated": auto_generated,
            },
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
            original_coverage_source_type=self._coverage_source_value(original_slot) or None,
            original_coverage_tenant_id=str(getattr(original_slot, "coverage_tenant_id", "") or "").strip() or None,
            current_user=current_user,
            max_match_results=max(int(max_match_results or 25), 1),
        )

        title = notification_title or ("Automatic shift replacement opened" if auto_generated else "Shift replacement requested")
        message = notification_message or (
            f"{self._request_display_title(request_record)}: a confirmed no-show triggered automatic replacement coverage."
            if auto_generated
            else f"{self._request_display_title(request_record)}: platform reopened this shift slot for replacement coverage."
        )
        await self._notify_slot_exception(
            slot_record=original_slot,
            shift_record=shift_record,
            request_record=request_record,
            title=title,
            message=message,
            metadata={
                "exception_status": ShiftSlotStatus.REPLACEMENT_REQUIRED.value,
                "replacement_slot_id": str(replacement_slot.id),
                "wave_id": str(wave.id) if wave else None,
                "auto_generated": auto_generated,
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
                "auto_generated": auto_generated,
            },
        )
        return {
            "created": True,
            "replacement_slot": replacement_slot,
            "wave": wave,
        }

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

        existing_replacements = await self._active_replacement_slots_for_original_slot(
            shift_record=shift_record,
            original_slot=original_slot,
        )
        if existing_replacements:
            raise HTTPException(status_code=409, detail="A replacement slot is already open for this shift slot")

        reopened = await self._open_replacement_slot_for_exception(
            original_slot=original_slot,
            shift_record=shift_record,
            request_record=request_record,
            current_user=current_user,
            note=payload.note,
            max_match_results=payload.max_match_results,
            auto_generated=False,
        )
        replacement_slot = reopened["replacement_slot"]
        wave = reopened["wave"]
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
        self._assert_shift_checkin_window_is_open(
            shift_record,
            schedule_record,
            actor_timezone=payload.timezone,
        )
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
        self._assert_shift_has_not_ended(shift_record, action="confirm arrival")
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        await self._assert_client_slot_action_access(request_record, current_user)
        if slot_record.arrived_at is None:
            raise HTTPException(status_code=409, detail="Guard must check in before client confirmation")
        if slot_record.started_at is not None:
            raise HTTPException(status_code=409, detail="This shift slot has already started")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_record.client_confirmed_at = slot_record.client_confirmed_at or now
        slot_record.slot_status = (
            ShiftSlotStatus.ROSTERED
            if getattr(slot_record, "rostered_at", None) is not None
            else ShiftSlotStatus.RESERVED
        )
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
        schedule_record = await self._get_schedule_template_or_404(shift_record.schedule_template_id)
        self._assert_shift_start_window_is_open(
            shift_record,
            schedule_record,
            actor_timezone=payload.timezone,
        )
        now = self._utc_now()
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        if slot_record.arrived_at is None:
            raise HTTPException(status_code=409, detail="Guard must check in before starting the shift")
        if slot_record.started_at is not None:
            raise HTTPException(status_code=409, detail="This shift slot has already started")
        if slot_record.client_confirmed_at is None and not is_platform:
            raise HTTPException(status_code=409, detail="Client confirmation is required before starting the shift")

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
        await self._sync_parent_request_assignment_lifecycle(
            slot_record=slot_record,
            shift_record=shift_record,
            request_record=request_record,
        )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Shift started",
            message=f"{request_record.title}: guard is now in progress on site.",
            category="info",
            source_module="requests",
            action_url=f"/dashboard/requests?shift={shift_record.id}",
            action_label="Review shift",
            metadata={"request_id": str(request_record.id), "shift_id": str(shift_record.id), "slot_id": str(slot_record.id)},
        )
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)

    async def check_out_shift_slot(self, slot_id: str, payload: ShiftSlotCheckOutPayload, current_user) -> Dict[str, Any]:
        slot_record = await self._get_shift_slot_or_404(slot_id)
        _is_platform, _session_tenant = await self._assert_guard_slot_action_access(slot_record, current_user)
        shift_record = await self._get_shift_or_404(slot_record.shift_instance_id)
        request_manager = RequestManager.get_instance()
        request_record = await request_manager._get_request_or_404(slot_record.request_id)
        if slot_record.slot_status != ShiftSlotStatus.IN_PROGRESS or slot_record.started_at is None:
            raise HTTPException(status_code=409, detail="Only in-progress shift slots can be checked out")

        now = self._utc_now()
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
        await self._sync_parent_request_assignment_lifecycle(
            slot_record=slot_record,
            shift_record=shift_record,
            request_record=request_record,
        )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=request_record.client_tenant_id,
            title="Shift checked out",
            message=f"{request_record.title}: guard checked out and shift work was marked complete.",
            category="success",
            source_module="requests",
            action_url=f"/dashboard/requests?shift={shift_record.id}",
            action_label="Review shift",
            metadata={"request_id": str(request_record.id), "shift_id": str(shift_record.id), "slot_id": str(slot_record.id)},
        )
        return await self.get_shift_slot_by_id(slot_id=str(slot_record.id), current_user=current_user)
