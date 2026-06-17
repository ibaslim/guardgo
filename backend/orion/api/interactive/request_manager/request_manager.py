import threading
import re
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.activity_manager.activity_manager import ActivityManager
from orion.api.interactive.billing_manager.billing_manager import BillingManager
from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    MatchAddress,
    RequestMatchingPreviewPayload,
    TargetType,
)
from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager
from configs.metadata_constants import CANADIAN_CITIES_BY_PROVINCE_OPTIONS, CANADIAN_PROVINCE_OPTIONS
from orion.constants import constant
from orion.services.mail_manager.mail_manager import mail_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import PLATFORM_ADMIN_ROLES, normalize_role_value
from orion.services.mongo_manager.shared_model.db_billing_model import BillingRate
from orion.services.mongo_manager.shared_model.db_request_model import (
    AssignmentLockReason,
    BroadcastReviewReasonCode,
    ClientRequestCreatePayload,
    ClientRequestRecord,
    ClientRequestSoftDeletePayload,
    ClientRequestStatusUpdatePayload,
    ClientRequestUpdatePayload,
    RequestAdditionalCoveragePayload,
    RequestAssignmentCreatePayload,
    RequestAssignmentOrigin,
    RequestAssignmentRecord,
    RequestAssignmentScope,
    RequestAssignmentStatus,
    RequestAssignmentStatusUpdatePayload,
    RequestBroadcastWaveRecord,
    RequestFulfillmentMode,
    RequestInvoiceDeliveryStatus,
    RequestInvoiceRecord,
    RequestInvoiceStatus,
    RequestInvoiceTrigger,
    RequestLockReason,
    RequestPublishPayload,
    RequestPublishUpdatePayload,
    RequestPricingPreviewPayload,
    RequestScheduleTemplateRecord,
    RequestSiteInput,
    RequestStaffingStatus,
    RequestStatus,
    RequestTargetType,
    RequestWaveReviewPayload,
    RequestWaveStatus,
    RequestWaveTrigger,
    ShiftAttendanceEventType,
    ShiftCoverageSourceType,
    ShiftInstanceRecord,
    ShiftSlotRecord,
    ShiftSlotStatus,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantStatus, TenantType


PLATFORM_WRITE_ROLES = {
    "admin",
    "ops_admin",
    "support_admin",
    "compliance_admin",
}

ACTIONABLE_ASSIGNMENT_STATUSES = {
    RequestAssignmentStatus.OFFERED,
    RequestAssignmentStatus.ACCEPTED,
    RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
    RequestAssignmentStatus.IN_PROGRESS,
}

COMMITTED_SLOT_STATUSES = {
    RequestAssignmentStatus.ACCEPTED,
    RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
    RequestAssignmentStatus.IN_PROGRESS,
    RequestAssignmentStatus.COMPLETED,
}

OPEN_OFFER_STATUSES = {
    RequestAssignmentStatus.OFFERED,
}

REQUEST_TAB_ASSIGNMENT_STATUSES = {
    RequestAssignmentStatus.OFFERED,
    RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
}

DEFAULT_GUARD_PROVIDER_JOB_STATUSES = {
    RequestAssignmentStatus.ACCEPTED,
    RequestAssignmentStatus.IN_PROGRESS,
    RequestAssignmentStatus.COMPLETED,
}

AUTO_COMPLETE_ELAPSED_ASSIGNMENT_STATUSES = {
    RequestAssignmentStatus.ACCEPTED,
    RequestAssignmentStatus.IN_PROGRESS,
}

_FINANCE_SNAPSHOT_UNSET = object()


class RequestManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance() -> "RequestManager":
        if RequestManager.__instance is None:
            with RequestManager.__lock:
                if RequestManager.__instance is None:
                    RequestManager.__instance = RequestManager()
        return RequestManager.__instance

    def __init__(self):
        if RequestManager.__instance is not None:
            raise Exception("RequestManager is a singleton")
        controller = mongo_controller.get_instance()
        if controller is None:
            raise RuntimeError("Mongo controller is not initialized")
        self._engine = controller.get_engine()

    @staticmethod
    def _enum_value(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value

        text = str(value or "").strip()
        if not text:
            return None

        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _as_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        parsed_datetime = RequestManager._as_datetime(value)
        if parsed_datetime:
            return parsed_datetime.date()

        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value)
        except Exception:
            return None
        return parsed if parsed == parsed else None

    @staticmethod
    def _role_value(current_user) -> str:
        return normalize_role_value(getattr(current_user, "role", ""))

    @staticmethod
    def _is_platform_role(role_value: str) -> bool:
        return role_value in PLATFORM_ADMIN_ROLES

    @staticmethod
    def _is_platform_write_role(role_value: str) -> bool:
        return role_value in PLATFORM_WRITE_ROLES

    @staticmethod
    def _validate_trimmed_title(title: str) -> str:
        normalized = str(title or "").strip()
        if len(normalized) < 3:
            raise HTTPException(status_code=400, detail="Request title must be at least 3 non-space characters")
        return normalized

    @staticmethod
    def _validate_requested_window(requested_start_at: Optional[datetime], requested_end_at: Optional[datetime]) -> None:
        if requested_start_at and requested_end_at and requested_end_at <= requested_start_at:
            raise HTTPException(status_code=400, detail="Requested end time must be after start time")

    @classmethod
    def _assert_request_job_status_action_window(
        cls,
        record: ClientRequestRecord,
        next_status: RequestAssignmentStatus,
    ) -> datetime:
        now = datetime.utcnow()
        if next_status not in {RequestAssignmentStatus.IN_PROGRESS, RequestAssignmentStatus.COMPLETED}:
            return now

        requested_start_at = cls._as_datetime(getattr(record, "requested_start_at", None))
        requested_end_at = cls._as_datetime(getattr(record, "requested_end_at", None))

        if next_status == RequestAssignmentStatus.IN_PROGRESS:
            if requested_start_at and now < requested_start_at:
                raise HTTPException(status_code=409, detail="Cannot start this job before its scheduled start time")
            if requested_end_at and requested_end_at <= now:
                raise HTTPException(status_code=409, detail="Cannot start this job after its scheduled end time")
        elif next_status == RequestAssignmentStatus.COMPLETED:
            if requested_start_at and now < requested_start_at:
                raise HTTPException(status_code=409, detail="Cannot complete this job before its scheduled start time")

        return now

    @staticmethod
    def _default_target_type_for_mode(fulfillment_mode: RequestFulfillmentMode) -> RequestTargetType:
        if fulfillment_mode == RequestFulfillmentMode.SERVICE_PROVIDER_ONLY:
            return RequestTargetType.SERVICE_PROVIDER
        return RequestTargetType.GUARD

    @staticmethod
    def _fulfillment_mode_target_types(fulfillment_mode: RequestFulfillmentMode) -> List[RequestTargetType]:
        if fulfillment_mode == RequestFulfillmentMode.INDIVIDUAL_ONLY:
            return [RequestTargetType.GUARD]
        if fulfillment_mode == RequestFulfillmentMode.SERVICE_PROVIDER_ONLY:
            return [RequestTargetType.SERVICE_PROVIDER]
        return [RequestTargetType.GUARD, RequestTargetType.SERVICE_PROVIDER]

    @classmethod
    def _resolve_fulfillment_mode_from_record(cls, record: ClientRequestRecord | Dict[str, Any]) -> RequestFulfillmentMode:
        raw_value = record.get("fulfillment_mode") if isinstance(record, dict) else getattr(record, "fulfillment_mode", None)
        if raw_value:
            if isinstance(raw_value, RequestFulfillmentMode):
                return raw_value
            try:
                return RequestFulfillmentMode(str(raw_value))
            except Exception:
                pass

        raw_target = record.get("target_type") if isinstance(record, dict) else getattr(record, "target_type", None)
        target_value = str(getattr(raw_target, "value", raw_target) or "").strip().lower()
        if target_value == RequestTargetType.SERVICE_PROVIDER.value:
            return RequestFulfillmentMode.SERVICE_PROVIDER_ONLY
        return RequestFulfillmentMode.INDIVIDUAL_ONLY

    @staticmethod
    def _allowed_assignment_transition(current_status: RequestAssignmentStatus, next_status: RequestAssignmentStatus) -> bool:
        allowed = {
            RequestAssignmentStatus.OFFERED: {RequestAssignmentStatus.ACCEPTED, RequestAssignmentStatus.DECLINED},
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED: {RequestAssignmentStatus.ACCEPTED, RequestAssignmentStatus.DECLINED},
            RequestAssignmentStatus.ACCEPTED: {RequestAssignmentStatus.IN_PROGRESS, RequestAssignmentStatus.CANCELLED},
            RequestAssignmentStatus.IN_PROGRESS: {RequestAssignmentStatus.COMPLETED, RequestAssignmentStatus.CANCELLED},
        }
        return next_status in allowed.get(current_status, set())

    @staticmethod
    def _allowed_request_status_transition(current_status: RequestStatus, next_status: RequestStatus) -> bool:
        allowed = {
            RequestStatus.DRAFT: {RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
            RequestStatus.SUBMITTED: {RequestStatus.ASSIGNED, RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED, RequestStatus.CLOSED},
            RequestStatus.ASSIGNED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED, RequestStatus.CLOSED},
            RequestStatus.IN_PROGRESS: {RequestStatus.CANCELLED, RequestStatus.CLOSED},
        }
        return next_status in allowed.get(current_status, set())

    @staticmethod
    def _assignment_slots(record: RequestAssignmentRecord | Dict[str, Any]) -> int:
        raw_value = record.get("slots_committed") if isinstance(record, dict) else getattr(record, "slots_committed", None)
        try:
            slots = int(raw_value)
        except Exception:
            slots = 0
        return slots if slots > 0 else 1

    @staticmethod
    def _assignment_scope_value(record: RequestAssignmentRecord | Dict[str, Any]) -> str:
        raw_value = record.get("assignment_scope") if isinstance(record, dict) else getattr(record, "assignment_scope", None)
        return str(getattr(raw_value, "value", raw_value or RequestAssignmentScope.REQUEST.value))

    @classmethod
    def _should_auto_close_request(
        cls,
        record: ClientRequestRecord,
        assignments: List[RequestAssignmentRecord | Dict[str, Any]],
        *,
        accepted_slots: int,
        now: datetime,
    ) -> bool:
        if record.request_status in {RequestStatus.DRAFT, RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            return False

        request_assignments = [
            assignment
            for assignment in assignments
            if cls._assignment_scope_value(assignment) == RequestAssignmentScope.REQUEST.value
        ]
        if not request_assignments:
            return False

        pending_committed_statuses = {
            RequestAssignmentStatus.ACCEPTED.value,
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value,
            RequestAssignmentStatus.IN_PROGRESS.value,
        }
        active_request_statuses = pending_committed_statuses | {
            RequestAssignmentStatus.OFFERED.value,
        }
        has_pending_committed_work = False
        has_active_request_work = False
        completed_slots = 0

        for assignment in request_assignments:
            status = cls._enum_value(
                assignment.get("assignment_status") if isinstance(assignment, dict) else getattr(assignment, "assignment_status", None)
            )
            if status in pending_committed_statuses:
                has_pending_committed_work = True
            if status in active_request_statuses:
                has_active_request_work = True
            if status == RequestAssignmentStatus.COMPLETED.value:
                completed_slots += cls._assignment_slots(assignment)

        # If all filled request-level work is marked completed, the parent request
        # should stop presenting itself as "in progress", even before the nominal
        # requested end timestamp.
        if accepted_slots > 0 and int(record.open_slots or 0) == 0 and completed_slots >= accepted_slots and not has_pending_committed_work:
            return True

        # If the requested window has elapsed and there is no remaining active
        # request-level work or offer, the request can close itself cleanly.
        requested_end_at = cls._as_datetime(record.requested_end_at)
        return bool(requested_end_at and requested_end_at <= now and not has_active_request_work)

    @staticmethod
    def _wave_shift_replacement_context(record: RequestBroadcastWaveRecord | Dict[str, Any]) -> Optional[Dict[str, Any]]:
        request_snapshot = record.get("request_snapshot") if isinstance(record, dict) else getattr(record, "request_snapshot", {})
        if not isinstance(request_snapshot, dict):
            return None
        context = request_snapshot.get("shift_replacement")
        return dict(context) if isinstance(context, dict) else None

    @staticmethod
    def _dashboard_requests_url(
        *,
        tab: Optional[str] = None,
        request_id: Optional[str] = None,
        assignment_id: Optional[str] = None,
        wave_id: Optional[str] = None,
    ) -> str:
        query: Dict[str, str] = {}
        if tab:
            query["tab"] = tab
        if request_id:
            query["request"] = str(request_id)
        if assignment_id:
            query["job"] = str(assignment_id)
        if wave_id:
            query["wave"] = str(wave_id)
        return f"/dashboard/requests?{urlencode(query)}" if query else "/dashboard/requests"

    @classmethod
    def _request_snapshot(cls, record: ClientRequestRecord | Dict[str, Any]) -> Dict[str, Any]:
        site_snapshot = record.get("site_snapshot") if isinstance(record, dict) else getattr(record, "site_snapshot", {})
        pricing_snapshot = record.get("pricing_snapshot") if isinstance(record, dict) else getattr(record, "pricing_snapshot", {})
        invoicing_snapshot = record.get("invoicing_snapshot") if isinstance(record, dict) else getattr(record, "invoicing_snapshot", {})
        return {
            "id": str(record.get("_id") if isinstance(record, dict) else record.id),
            "title": record.get("title") if isinstance(record, dict) else record.title,
            "timezone": record.get("timezone") if isinstance(record, dict) else getattr(record, "timezone", None),
            "request_status": cls._enum_value(record.get("request_status") if isinstance(record, dict) else record.request_status),
            "staffing_status": cls._enum_value(record.get("staffing_status") if isinstance(record, dict) else record.staffing_status),
            "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
            "target_type": cls._enum_value(record.get("target_type") if isinstance(record, dict) else record.target_type),
            "guards_required": int(record.get("guards_required") or 0) if isinstance(record, dict) else record.guards_required,
            "site_name": ((site_snapshot or {}).get("site_name") or ""),
            "requested_start_at": record.get("requested_start_at") if isinstance(record, dict) else record.requested_start_at,
            "requested_end_at": record.get("requested_end_at") if isinstance(record, dict) else record.requested_end_at,
            "request_revision": int(record.get("request_revision") or 0) if isinstance(record, dict) else record.request_revision,
            "request_expires_at": record.get("request_expires_at") if isinstance(record, dict) else record.request_expires_at,
            "accepted_slots": int(record.get("accepted_slots") or 0) if isinstance(record, dict) else record.accepted_slots,
            "open_slots": int(record.get("open_slots") or 0) if isinstance(record, dict) else record.open_slots,
            "has_schedule": bool(record.get("has_schedule") if isinstance(record, dict) else getattr(record, "has_schedule", False)),
            "pricing_snapshot": pricing_snapshot or {},
            "invoicing_snapshot": invoicing_snapshot or {},
        }

    @classmethod
    def _has_request_pricing_snapshot(cls, snapshot: Any) -> bool:
        if not isinstance(snapshot, dict):
            return False
        return cls._as_float(snapshot.get("client_hourly_quote")) is not None

    async def _ensure_request_doc_finance_snapshot(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if self._has_request_pricing_snapshot(doc.get("pricing_snapshot")):
            return doc

        invoicing_snapshot = doc.get("invoicing_snapshot") if isinstance(doc.get("invoicing_snapshot"), dict) else {}
        finance_snapshot = await self._build_request_pricing_and_invoicing(
            site_snapshot=doc.get("site_snapshot") or {},
            requested_start_at=self._as_datetime(doc.get("requested_start_at")),
            requested_end_at=self._as_datetime(doc.get("requested_end_at")),
            guards_required=int(doc.get("guards_required") or 1),
            invoice_contract_type=invoicing_snapshot.get("contract_type"),
            invoice_cutoff_day=invoicing_snapshot.get("monthly_cutoff_day"),
            invoice_recipient_email=invoicing_snapshot.get("invoice_recipient_email"),
        )
        doc["pricing_snapshot"] = finance_snapshot["pricing_snapshot"]
        merged_invoicing_snapshot = dict(finance_snapshot["invoicing_snapshot"])
        merged_invoicing_snapshot.update(invoicing_snapshot)
        doc["invoicing_snapshot"] = merged_invoicing_snapshot
        return doc

    @staticmethod
    def _is_soft_deleted(record: ClientRequestRecord | Dict[str, Any]) -> bool:
        value = record.get("deleted_at") if isinstance(record, dict) else getattr(record, "deleted_at", None)
        return value is not None

    @classmethod
    def _assert_not_soft_deleted(cls, record: ClientRequestRecord | Dict[str, Any]) -> None:
        if cls._is_soft_deleted(record):
            raise HTTPException(status_code=404, detail="Request not found")

    @classmethod
    def _serialize(cls, record: ClientRequestRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            guards_required = int(record.get("guards_required") or 0)
            accepted_slots = int(record.get("accepted_slots") or 0)
            viewer_assignment = record.get("viewer_assignment")
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "client_tenant_id": record.get("client_tenant_id"),
                "created_by_user_id": record.get("created_by_user_id"),
                "created_by_username": record.get("created_by_username"),
                "title": record.get("title") or "",
                "timezone": record.get("timezone"),
                "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
                "target_type": cls._enum_value(record.get("target_type")),
                "requested_guard_type": record.get("requested_guard_type"),
                "guards_required": guards_required,
                "request_status": cls._enum_value(record.get("request_status")),
                "staffing_status": cls._enum_value(record.get("staffing_status")),
                "lock_reason": cls._enum_value(record.get("lock_reason"), default="") or None,
                "site_snapshot": record.get("site_snapshot") or {},
                "special_instructions": record.get("special_instructions"),
                "pricing_snapshot": record.get("pricing_snapshot") or {},
                "invoicing_snapshot": record.get("invoicing_snapshot") or {},
                "requested_start_at": record.get("requested_start_at"),
                "requested_end_at": record.get("requested_end_at"),
                "request_expires_at": record.get("request_expires_at"),
                "published_at": record.get("published_at"),
                "published_by_user_id": record.get("published_by_user_id"),
                "published_by_username": record.get("published_by_username"),
                "request_revision": int(record.get("request_revision") or 0),
                "accepted_slots": accepted_slots,
                "open_slots": int(record.get("open_slots") if record.get("open_slots") is not None else max(guards_required - accepted_slots, 0)),
                "active_wave_id": record.get("active_wave_id"),
                "last_wave_number": int(record.get("last_wave_number") or 0),
                "expired_at": record.get("expired_at"),
                "match_summary": record.get("match_summary") or {},
                "matched_candidates": record.get("matched_candidates") or [],
                "cancelled_at": record.get("cancelled_at"),
                "closed_at": record.get("closed_at"),
                "deleted_at": record.get("deleted_at"),
                "deleted_by_user_id": record.get("deleted_by_user_id"),
                "deleted_by_username": record.get("deleted_by_username"),
                "deleted_reason": record.get("deleted_reason"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "viewer_assignment": viewer_assignment if isinstance(viewer_assignment, dict) else None,
            }

        viewer_assignment = getattr(record, "viewer_assignment", None)
        return {
            "id": str(record.id),
            "client_tenant_id": record.client_tenant_id,
            "created_by_user_id": record.created_by_user_id,
            "created_by_username": record.created_by_username,
            "title": record.title,
            "timezone": getattr(record, "timezone", None),
            "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
            "target_type": cls._enum_value(record.target_type),
            "requested_guard_type": record.requested_guard_type,
            "guards_required": record.guards_required,
            "request_status": cls._enum_value(record.request_status),
            "staffing_status": cls._enum_value(record.staffing_status),
            "lock_reason": cls._enum_value(record.lock_reason, default="") or None,
            "site_snapshot": record.site_snapshot or {},
            "special_instructions": record.special_instructions,
            "pricing_snapshot": getattr(record, "pricing_snapshot", None) or {},
            "invoicing_snapshot": getattr(record, "invoicing_snapshot", None) or {},
            "requested_start_at": record.requested_start_at,
            "requested_end_at": record.requested_end_at,
            "request_expires_at": record.request_expires_at,
            "published_at": record.published_at,
            "published_by_user_id": record.published_by_user_id,
            "published_by_username": record.published_by_username,
            "request_revision": record.request_revision,
            "accepted_slots": record.accepted_slots,
            "open_slots": record.open_slots,
            "active_wave_id": record.active_wave_id,
            "last_wave_number": record.last_wave_number,
            "expired_at": record.expired_at,
            "match_summary": record.match_summary or {},
            "matched_candidates": record.matched_candidates or [],
            "cancelled_at": record.cancelled_at,
            "closed_at": record.closed_at,
            "deleted_at": record.deleted_at,
            "deleted_by_user_id": record.deleted_by_user_id,
            "deleted_by_username": record.deleted_by_username,
            "deleted_reason": record.deleted_reason,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "viewer_assignment": viewer_assignment if isinstance(viewer_assignment, dict) else None,
        }

    @classmethod
    def _serialize_assignment(cls, record: RequestAssignmentRecord | Dict[str, Any], request_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "request_id": record.get("request_id") or "",
                "client_tenant_id": record.get("client_tenant_id") or "",
                "assignee_tenant_id": record.get("assignee_tenant_id") or "",
                "assignee_tenant_type": cls._enum_value(record.get("assignee_tenant_type")),
                "assignment_status": cls._enum_value(record.get("assignment_status")),
                "assignment_origin": cls._enum_value(record.get("assignment_origin")),
                "assignment_scope": cls._assignment_scope_value(record),
                "broadcast_wave_id": record.get("broadcast_wave_id"),
                "shift_instance_id": record.get("shift_instance_id"),
                "shift_slot_id": record.get("shift_slot_id"),
                "request_revision_at_offer": int(record.get("request_revision_at_offer") or 0),
                "slots_committed": record.get("slots_committed"),
                "response_due_at": record.get("response_due_at"),
                "reconfirmation_due_at": record.get("reconfirmation_due_at"),
                "lock_reason": cls._enum_value(record.get("lock_reason"), default="") or None,
                "candidate_snapshot": record.get("candidate_snapshot") or {},
                "assigned_by_user_id": record.get("assigned_by_user_id") or "",
                "assigned_by_username": record.get("assigned_by_username") or "",
                "note": record.get("note"),
                "offered_at": record.get("offered_at"),
                "accepted_at": record.get("accepted_at"),
                "declined_at": record.get("declined_at"),
                "expired_at": record.get("expired_at"),
                "reconfirmation_requested_at": record.get("reconfirmation_requested_at"),
                "reconfirmed_at": record.get("reconfirmed_at"),
                "closed_filled_at": record.get("closed_filled_at"),
                "superseded_at": record.get("superseded_at"),
                "started_at": record.get("started_at"),
                "completed_at": record.get("completed_at"),
                "cancelled_at": record.get("cancelled_at"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
                "request": request_snapshot or {},
            }

        return {
            "id": str(getattr(record, "id", "") or ""),
            "request_id": getattr(record, "request_id", "") or "",
            "client_tenant_id": getattr(record, "client_tenant_id", "") or "",
            "assignee_tenant_id": getattr(record, "assignee_tenant_id", "") or "",
            "assignee_tenant_type": cls._enum_value(getattr(record, "assignee_tenant_type", None)),
            "assignment_status": cls._enum_value(getattr(record, "assignment_status", None)),
            "assignment_origin": cls._enum_value(getattr(record, "assignment_origin", None)),
            "assignment_scope": cls._assignment_scope_value(record),
            "broadcast_wave_id": getattr(record, "broadcast_wave_id", None),
            "shift_instance_id": getattr(record, "shift_instance_id", None),
            "shift_slot_id": getattr(record, "shift_slot_id", None),
            "request_revision_at_offer": int(getattr(record, "request_revision_at_offer", 0) or 0),
            "slots_committed": getattr(record, "slots_committed", None),
            "response_due_at": getattr(record, "response_due_at", None),
            "reconfirmation_due_at": getattr(record, "reconfirmation_due_at", None),
            "lock_reason": cls._enum_value(getattr(record, "lock_reason", None), default="") or None,
            "candidate_snapshot": getattr(record, "candidate_snapshot", None) or {},
            "assigned_by_user_id": getattr(record, "assigned_by_user_id", "") or "",
            "assigned_by_username": getattr(record, "assigned_by_username", "") or "",
            "note": getattr(record, "note", None),
            "offered_at": getattr(record, "offered_at", None),
            "accepted_at": getattr(record, "accepted_at", None),
            "declined_at": getattr(record, "declined_at", None),
            "expired_at": getattr(record, "expired_at", None),
            "reconfirmation_requested_at": getattr(record, "reconfirmation_requested_at", None),
            "reconfirmed_at": getattr(record, "reconfirmed_at", None),
            "closed_filled_at": getattr(record, "closed_filled_at", None),
            "superseded_at": getattr(record, "superseded_at", None),
            "started_at": getattr(record, "started_at", None),
            "completed_at": getattr(record, "completed_at", None),
            "cancelled_at": getattr(record, "cancelled_at", None),
            "created_at": getattr(record, "created_at", None),
            "updated_at": getattr(record, "updated_at", None),
            "request": request_snapshot or {},
        }

    @staticmethod
    def _assignment_sort_key(record: RequestAssignmentRecord | Dict[str, Any]) -> tuple[int, float]:
        status_value = (
            record.get("assignment_status") if isinstance(record, dict) else getattr(record, "assignment_status", None)
        )
        normalized_status = RequestManager._enum_value(status_value)
        priority = {
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value: 0,
            RequestAssignmentStatus.OFFERED.value: 1,
            RequestAssignmentStatus.ACCEPTED.value: 2,
            RequestAssignmentStatus.IN_PROGRESS.value: 3,
            RequestAssignmentStatus.COMPLETED.value: 4,
            RequestAssignmentStatus.CANCELLED.value: 5,
            RequestAssignmentStatus.DECLINED.value: 6,
            RequestAssignmentStatus.EXPIRED.value: 7,
            RequestAssignmentStatus.CLOSED_FILLED.value: 8,
            RequestAssignmentStatus.SUPERSEDED.value: 9,
        }.get(normalized_status, 99)
        updated_at = RequestManager._as_datetime(
            record.get("updated_at") if isinstance(record, dict) else getattr(record, "updated_at", None)
        ) or datetime.min
        recency_rank = -(updated_at.timestamp()) if updated_at != datetime.min else float("inf")
        return priority, recency_rank

    def _best_assignment_doc_for_request(
        self,
        assignment_docs: List[Dict[str, Any]],
        *,
        statuses: Optional[set[RequestAssignmentStatus]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        allowed_status_values = {status.value for status in statuses} if statuses else None
        selected: Dict[str, Dict[str, Any]] = {}
        for doc in assignment_docs:
            request_id = str(doc.get("request_id") or "").strip()
            status_value = self._enum_value(doc.get("assignment_status"))
            if not request_id:
                continue
            if allowed_status_values is not None and status_value not in allowed_status_values:
                continue

            current = selected.get(request_id)
            if current is None or self._assignment_sort_key(doc) < self._assignment_sort_key(current):
                selected[request_id] = doc
        return selected

    async def _resolve_viewer_assignment_for_request(self, request_id: str, current_user) -> Optional[Dict[str, Any]]:
        role_value = self._role_value(current_user)
        if role_value not in {"guard_admin", "sp_admin"}:
            return None

        session_tenant = await self._get_session_tenant(current_user)
        if session_tenant.tenant_type not in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            return None

        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        assignment_docs = await assignment_collection.find({
            "request_id": str(request_id),
            "assignee_tenant_id": str(session_tenant.id),
        }).to_list(length=None)
        best = self._best_assignment_doc_for_request(assignment_docs).get(str(request_id))
        if not best:
            return None
        return self._serialize_assignment(best)

    @classmethod
    def _serialize_wave(cls, record: RequestBroadcastWaveRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "request_id": record.get("request_id") or "",
                "client_tenant_id": record.get("client_tenant_id") or "",
                "request_revision": int(record.get("request_revision") or 0),
                "wave_number": int(record.get("wave_number") or 0),
                "trigger": cls._enum_value(record.get("trigger")),
                "wave_status": cls._enum_value(record.get("wave_status")),
                "request_snapshot": record.get("request_snapshot") or {},
                "match_summary_snapshot": record.get("match_summary_snapshot") or {},
                "candidate_snapshots": record.get("candidate_snapshots") or [],
                "review_reason_codes": record.get("review_reason_codes") or [],
                "review_findings": record.get("review_findings") or [],
                "review_note": record.get("review_note"),
                "reviewed_by_user_id": record.get("reviewed_by_user_id"),
                "reviewed_by_username": record.get("reviewed_by_username"),
                "review_requested_at": record.get("review_requested_at"),
                "reviewed_at": record.get("reviewed_at"),
                "returned_at": record.get("returned_at"),
                "activated_at": record.get("activated_at"),
                "wave_expires_at": record.get("wave_expires_at"),
                "filled_at": record.get("filled_at"),
                "expired_at": record.get("expired_at"),
                "superseded_at": record.get("superseded_at"),
                "cancelled_at": record.get("cancelled_at"),
                "open_slots_at_send": int(record.get("open_slots_at_send") or 0),
                "offer_count": int(record.get("offer_count") or 0),
                "accepted_slots_at_close": int(record.get("accepted_slots_at_close") or 0),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }

        return {
            "id": str(record.id),
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "request_revision": record.request_revision,
            "wave_number": record.wave_number,
            "trigger": cls._enum_value(record.trigger),
            "wave_status": cls._enum_value(record.wave_status),
            "request_snapshot": record.request_snapshot or {},
            "match_summary_snapshot": record.match_summary_snapshot or {},
            "candidate_snapshots": record.candidate_snapshots or [],
            "review_reason_codes": record.review_reason_codes or [],
            "review_findings": record.review_findings or [],
            "review_note": record.review_note,
            "reviewed_by_user_id": record.reviewed_by_user_id,
            "reviewed_by_username": record.reviewed_by_username,
            "review_requested_at": record.review_requested_at,
            "reviewed_at": record.reviewed_at,
            "returned_at": record.returned_at,
            "activated_at": record.activated_at,
            "wave_expires_at": record.wave_expires_at,
            "filled_at": record.filled_at,
            "expired_at": record.expired_at,
            "superseded_at": record.superseded_at,
            "cancelled_at": record.cancelled_at,
            "open_slots_at_send": record.open_slots_at_send,
            "offer_count": record.offer_count,
            "accepted_slots_at_close": record.accepted_slots_at_close,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @classmethod
    def _serialize_invoice(cls, record: RequestInvoiceRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "request_id": record.get("request_id") or "",
                "client_tenant_id": record.get("client_tenant_id") or "",
                "request_revision": int(record.get("request_revision") or 0),
                "trigger": cls._enum_value(record.get("trigger")),
                "invoice_number": record.get("invoice_number") or "",
                "contract_type": record.get("contract_type") or "",
                "billing_cycle": record.get("billing_cycle") or "",
                "charge_timing": record.get("charge_timing") or "",
                "monthly_cutoff_day": record.get("monthly_cutoff_day"),
                "billing_period_start_local": record.get("billing_period_start_local"),
                "billing_period_end_local": record.get("billing_period_end_local"),
                "billing_period_label": record.get("billing_period_label"),
                "currency": record.get("currency") or "CAD",
                "rate_basis": record.get("rate_basis"),
                "guards_required": int(record.get("guards_required") or 0),
                "client_hourly_quote": record.get("client_hourly_quote"),
                "requested_hours_per_position": record.get("requested_hours_per_position"),
                "estimated_total_hours": record.get("estimated_total_hours"),
                "estimated_amount": record.get("estimated_amount"),
                "estimated_guard_payout": record.get("estimated_guard_payout"),
                "estimated_provider_payout": record.get("estimated_provider_payout"),
                "estimated_company_margin_with_guard": record.get("estimated_company_margin_with_guard"),
                "estimated_company_margin_with_provider": record.get("estimated_company_margin_with_provider"),
                "invoice_recipient_email": record.get("invoice_recipient_email"),
                "invoice_status": cls._enum_value(record.get("invoice_status")),
                "payment_status": record.get("payment_status") or "",
                "email_delivery_status": cls._enum_value(record.get("email_delivery_status")),
                "email_delivery_error": record.get("email_delivery_error"),
                "emailed_at": record.get("emailed_at"),
                "line_items": record.get("line_items") or [],
                "note": record.get("note"),
                "created_by_user_id": record.get("created_by_user_id"),
                "created_by_username": record.get("created_by_username"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }

        return {
            "id": str(record.id),
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "request_revision": record.request_revision,
            "trigger": cls._enum_value(record.trigger),
            "invoice_number": record.invoice_number,
            "contract_type": record.contract_type,
            "billing_cycle": record.billing_cycle,
            "charge_timing": record.charge_timing,
            "monthly_cutoff_day": record.monthly_cutoff_day,
            "billing_period_start_local": record.billing_period_start_local,
            "billing_period_end_local": record.billing_period_end_local,
            "billing_period_label": record.billing_period_label,
            "currency": record.currency,
            "rate_basis": record.rate_basis,
            "guards_required": record.guards_required,
            "client_hourly_quote": record.client_hourly_quote,
            "requested_hours_per_position": record.requested_hours_per_position,
            "estimated_total_hours": record.estimated_total_hours,
            "estimated_amount": record.estimated_amount,
            "estimated_guard_payout": record.estimated_guard_payout,
            "estimated_provider_payout": record.estimated_provider_payout,
            "estimated_company_margin_with_guard": record.estimated_company_margin_with_guard,
            "estimated_company_margin_with_provider": record.estimated_company_margin_with_provider,
            "invoice_recipient_email": record.invoice_recipient_email,
            "invoice_status": cls._enum_value(record.invoice_status),
            "payment_status": record.payment_status,
            "email_delivery_status": cls._enum_value(record.email_delivery_status),
            "email_delivery_error": record.email_delivery_error,
            "emailed_at": record.emailed_at,
            "line_items": record.line_items or [],
            "note": record.note,
            "created_by_user_id": record.created_by_user_id,
            "created_by_username": record.created_by_username,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _assignee_invoice_allowed_statuses() -> set[str]:
        return {
            RequestAssignmentStatus.ACCEPTED.value,
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value,
            RequestAssignmentStatus.IN_PROGRESS.value,
            RequestAssignmentStatus.COMPLETED.value,
        }

    @staticmethod
    def _rollup_assignee_assignment_status(statuses: set[str]) -> str:
        for candidate in (
            RequestAssignmentStatus.IN_PROGRESS.value,
            RequestAssignmentStatus.ACCEPTED.value,
            RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value,
            RequestAssignmentStatus.COMPLETED.value,
        ):
            if candidate in statuses:
                return candidate
        return ""

    @classmethod
    def _invoice_assignee_hourly_rate(
        cls,
        invoice_record: RequestInvoiceRecord | Dict[str, Any],
        assignee_tenant_type: str,
    ) -> Optional[float]:
        if isinstance(invoice_record, dict):
            payout_total = (
                invoice_record.get("estimated_provider_payout")
                if assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER.value
                else invoice_record.get("estimated_guard_payout")
            )
            estimated_total_hours = invoice_record.get("estimated_total_hours")
        else:
            payout_total = (
                invoice_record.estimated_provider_payout
                if assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER.value
                else invoice_record.estimated_guard_payout
            )
            estimated_total_hours = invoice_record.estimated_total_hours

        payout_value = cls._as_float(payout_total)
        hours_value = cls._as_float(estimated_total_hours)
        if payout_value is None or hours_value is None or hours_value <= 0:
            return None
        return round(payout_value / hours_value, 2)

    @classmethod
    def _build_assignee_invoice_line_items(
        cls,
        invoice_record: RequestInvoiceRecord | Dict[str, Any],
        *,
        committed_slots: int,
        assignee_tenant_type: str,
    ) -> Dict[str, Any]:
        raw_line_items = invoice_record.get("line_items") if isinstance(invoice_record, dict) else invoice_record.line_items
        line_items = list(raw_line_items or [])
        payout_hourly_rate = cls._invoice_assignee_hourly_rate(invoice_record, assignee_tenant_type)

        assignee_line_items: List[Dict[str, Any]] = []
        total_hours = 0.0
        total_amount = 0.0

        for item in line_items:
            metadata = item.get("metadata") or {}
            hours_per_position = cls._as_float(metadata.get("hours_per_position"))
            if hours_per_position is None:
                request_quantity = cls._as_float(item.get("quantity"))
                request_guard_count = cls._as_float(metadata.get("guards_required"))
                if request_quantity is not None and request_guard_count and request_guard_count > 0:
                    hours_per_position = round(request_quantity / request_guard_count, 2)
            if hours_per_position is None or hours_per_position <= 0:
                continue

            quantity = round(hours_per_position * max(int(committed_slots or 1), 1), 2)
            amount = round((payout_hourly_rate or 0.0) * quantity, 2) if payout_hourly_rate is not None else None
            total_hours += quantity
            total_amount += amount or 0.0

            assignee_line_items.append({
                "description": item.get("description") or "Coverage payout",
                "service_date_local": item.get("service_date_local"),
                "unit": item.get("unit") or "hour",
                "quantity": quantity,
                "unit_rate": payout_hourly_rate,
                "amount": amount,
                "metadata": {
                    "committed_slots": max(int(committed_slots or 1), 1),
                    "hours_per_position": round(hours_per_position, 2),
                    "request_guards_required": metadata.get("guards_required"),
                    "start_at_local": metadata.get("start_at_local"),
                    "end_at_local": metadata.get("end_at_local"),
                },
            })

        return {
            "payout_hourly_rate": payout_hourly_rate,
            "line_items": assignee_line_items,
            "estimated_total_hours": round(total_hours, 2) if assignee_line_items else None,
            "estimated_amount": round(total_amount, 2) if assignee_line_items and payout_hourly_rate is not None else None,
        }

    @classmethod
    def _serialize_assignee_invoice(
        cls,
        invoice_record: RequestInvoiceRecord | Dict[str, Any],
        *,
        assignee_tenant_type: str,
        committed_slots: int,
        coverage_status: str = "",
        request_title: str = "",
        site_name: str = "",
    ) -> Dict[str, Any]:
        base = cls._serialize_invoice(invoice_record)
        payout_summary = cls._build_assignee_invoice_line_items(
            invoice_record,
            committed_slots=max(int(committed_slots or 1), 1),
            assignee_tenant_type=assignee_tenant_type,
        )
        return {
            "id": base["id"],
            "request_id": base["request_id"],
            "invoice_number": base["invoice_number"],
            "request_title": request_title,
            "site_name": site_name,
            "assignee_tenant_type": assignee_tenant_type,
            "coverage_status": coverage_status,
            "contract_type": base["contract_type"],
            "billing_cycle": base["billing_cycle"],
            "charge_timing": base["charge_timing"],
            "billing_period_start_local": base["billing_period_start_local"],
            "billing_period_end_local": base["billing_period_end_local"],
            "billing_period_label": base["billing_period_label"],
            "currency": base["currency"],
            "committed_slots": max(int(committed_slots or 1), 1),
            "payout_hourly_rate": payout_summary["payout_hourly_rate"],
            "estimated_total_hours": payout_summary["estimated_total_hours"],
            "estimated_amount": payout_summary["estimated_amount"],
            "invoice_status": base["invoice_status"],
            "line_items": payout_summary["line_items"],
            "note": base["note"],
            "created_at": base["created_at"],
            "updated_at": base["updated_at"],
        }

    @staticmethod
    def _week_bounds(anchor: date) -> tuple[date, date]:
        week_start = anchor - timedelta(days=anchor.weekday())
        return week_start, week_start + timedelta(days=6)

    @staticmethod
    def _safe_zoneinfo(value: Any) -> ZoneInfo:
        timezone_name = str(value or "").strip() or "UTC"
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return ZoneInfo("UTC")

    @classmethod
    def _date_ranges_overlap(
        cls,
        start_a: Any,
        end_a: Any,
        start_b: Any,
        end_b: Any,
    ) -> bool:
        start_a_date = cls._as_date(start_a)
        end_a_date = cls._as_date(end_a) or start_a_date
        start_b_date = cls._as_date(start_b)
        end_b_date = cls._as_date(end_b) or start_b_date
        if not start_a_date or not end_a_date or not start_b_date or not end_b_date:
            return False
        return max(start_a_date, start_b_date) <= min(end_a_date, end_b_date)

    @classmethod
    def _weekly_assignee_invoice_id(
        cls,
        *,
        request_id: str,
        assignee_tenant_id: str,
        assignee_tenant_type: str,
        billing_period_start_local: str,
    ) -> str:
        return (
            f"weekly:{str(assignee_tenant_type or '').strip().lower()}:"
            f"{str(assignee_tenant_id or '').strip()}:"
            f"{str(request_id or '').strip()}:"
            f"{str(billing_period_start_local or '').strip()}"
        )

    @classmethod
    def _weekly_assignee_invoice_number(
        cls,
        *,
        request_id: str,
        assignee_tenant_id: str,
        billing_period_start_local: str,
    ) -> str:
        request_token = str(request_id or "").replace("-", "")[-4:].upper() or "REQ"
        assignee_token = str(assignee_tenant_id or "").replace("-", "")[-4:].upper() or "TEN"
        try:
            period_token = date.fromisoformat(str(billing_period_start_local or "").strip()).strftime("%Y%m%d")
        except Exception:
            period_token = str(billing_period_start_local or "").replace("-", "")[:8] or datetime.utcnow().strftime("%Y%m%d")
        return f"PINV-{period_token}-{assignee_token}-{request_token}"

    @classmethod
    def _localize_utc_datetime(cls, value: Any, tzinfo: ZoneInfo) -> Optional[datetime]:
        parsed = cls._as_datetime(value)
        if not parsed:
            return None
        utc_value = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        return utc_value.astimezone(tzinfo)

    @classmethod
    def _shift_slot_duration_hours(
        cls,
        slot_doc: Dict[str, Any],
        shift_doc: Dict[str, Any],
    ) -> Optional[float]:
        actual_start = (
            cls._as_datetime(slot_doc.get("actual_start_at"))
            or cls._as_datetime(slot_doc.get("started_at"))
            or cls._as_datetime(shift_doc.get("shift_start_at_utc"))
        )
        actual_end = (
            cls._as_datetime(slot_doc.get("actual_end_at"))
            or cls._as_datetime(slot_doc.get("checked_out_at"))
            or cls._as_datetime(slot_doc.get("completed_at"))
            or cls._as_datetime(shift_doc.get("shift_end_at_utc"))
        )
        if actual_start and actual_end and actual_end > actual_start:
            return round(max((actual_end - actual_start).total_seconds() / 3600.0, 0.0), 2)
        return cls._calculate_requested_hours(
            cls._as_datetime(shift_doc.get("shift_start_at_utc")),
            cls._as_datetime(shift_doc.get("shift_end_at_utc")),
        )

    @classmethod
    def _build_weekly_assignee_line_item(
        cls,
        *,
        request_title: str,
        service_date_local: date,
        payout_hourly_rate: float,
        total_hours: float,
        completed_slots: int,
        request_guards_required: int,
        local_start: Optional[datetime],
        local_end: Optional[datetime],
    ) -> Dict[str, Any]:
        hours_per_position = round(total_hours / max(int(completed_slots or 1), 1), 2)
        return {
            "description": f"{request_title} - {service_date_local.isoformat()}",
            "service_date_local": service_date_local.isoformat(),
            "unit": "hour",
            "quantity": round(total_hours, 2),
            "unit_rate": round(payout_hourly_rate, 2),
            "amount": round(payout_hourly_rate * total_hours, 2),
            "metadata": {
                "committed_slots": max(int(completed_slots or 1), 1),
                "hours_per_position": hours_per_position,
                "request_guards_required": max(int(request_guards_required or 1), 1),
                "start_at_local": local_start.isoformat() if local_start else None,
                "end_at_local": local_end.isoformat() if local_end else None,
            },
        }

    async def _build_short_term_assignee_invoice_items(
        self,
        *,
        request_ids: List[str],
        assignment_map: Dict[str, Dict[str, Any]],
        request_lookup: Dict[str, Dict[str, Any]],
        assignee_tenant_type: str,
    ) -> List[Dict[str, Any]]:
        if not request_ids:
            return []

        invoice_collection = self._engine.get_collection(RequestInvoiceRecord)
        invoice_docs = await invoice_collection.find({
            "request_id": {"$in": request_ids},
        }).sort("created_at", -1).to_list(length=None)

        items: List[Dict[str, Any]] = []
        for invoice_doc in invoice_docs:
            request_id = str(invoice_doc.get("request_id") or "").strip()
            assignment_summary = assignment_map.get(request_id)
            if not assignment_summary:
                continue

            request_summary = request_lookup.get(request_id, {})
            items.append(self._serialize_assignee_invoice(
                invoice_doc,
                assignee_tenant_type=assignee_tenant_type,
                committed_slots=int(assignment_summary.get("committed_slots") or 1),
                coverage_status=self._rollup_assignee_assignment_status(set(assignment_summary.get("statuses") or set())),
                request_title=str(request_summary.get("title") or "").strip(),
                site_name=str(request_summary.get("site_name") or "").strip(),
            ))

        return items

    async def _build_long_term_assignee_weekly_invoice_items(
        self,
        *,
        request_ids: List[str],
        assignment_map: Dict[str, Dict[str, Any]],
        request_lookup: Dict[str, Dict[str, Any]],
        assignee_tenant_id: str,
        assignee_tenant_type: str,
    ) -> List[Dict[str, Any]]:
        normalized_request_ids = [
            str(request_id or "").strip()
            for request_id in request_ids
            if str(request_id or "").strip()
        ]
        if not normalized_request_ids:
            return []

        shift_collection = self._engine.get_collection(ShiftInstanceRecord)
        slot_collection = self._engine.get_collection(ShiftSlotRecord)
        shift_docs = await shift_collection.find({
            "request_id": {"$in": normalized_request_ids},
        }).to_list(length=None)
        slot_docs = await slot_collection.find({
            "request_id": {"$in": normalized_request_ids},
        }).to_list(length=None)

        shift_lookup = {
            str(shift_doc.get("_id") or "").strip(): shift_doc
            for shift_doc in shift_docs
            if str(shift_doc.get("_id") or "").strip()
        }

        grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
        now_utc = datetime.utcnow()

        for slot_doc in slot_docs:
            request_id = str(slot_doc.get("request_id") or "").strip()
            if not request_id or request_id not in request_lookup:
                continue
            if assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER.value:
                if str(slot_doc.get("service_provider_tenant_id") or "").strip() != assignee_tenant_id:
                    continue
            else:
                if str(slot_doc.get("assigned_guard_tenant_id") or "").strip() != assignee_tenant_id:
                    continue
            if self._as_datetime(slot_doc.get("completed_at")) is None:
                continue

            shift_id = str(slot_doc.get("shift_instance_id") or "").strip()
            shift_doc = shift_lookup.get(shift_id)
            if not shift_doc:
                continue

            try:
                service_date_local = date.fromisoformat(str(shift_doc.get("shift_date_local") or "").strip())
            except Exception:
                continue

            timezone_name = str(shift_doc.get("timezone") or request_lookup[request_id].get("timezone") or "UTC").strip() or "UTC"
            tzinfo = self._safe_zoneinfo(timezone_name)
            today_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tzinfo).date()
            week_start, week_end = self._week_bounds(service_date_local)
            if week_end >= today_local:
                continue

            request_summary = request_lookup[request_id]
            payout_hourly_rate = self._as_float(
                request_summary.get("provider_hourly_pay")
                if assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER.value
                else request_summary.get("guard_hourly_pay")
            )
            if payout_hourly_rate is None:
                continue

            duration_hours = self._shift_slot_duration_hours(slot_doc, shift_doc)
            if duration_hours is None or duration_hours <= 0:
                continue

            group_key = (request_id, week_start.isoformat())
            group = grouped.setdefault(group_key, {
                "request_id": request_id,
                "week_start": week_start,
                "week_end": week_end,
                "request_title": str(request_summary.get("title") or "").strip() or "Coverage payout",
                "site_name": str(request_summary.get("site_name") or "").strip(),
                "timezone": timezone_name,
                "currency": str(request_summary.get("currency") or "CAD"),
                "request_guards_required": max(int(request_summary.get("guards_required") or 1), 1),
                "request_committed_slots": max(int((assignment_map.get(request_id) or {}).get("committed_slots") or 1), 1),
                "payout_hourly_rate": round(payout_hourly_rate, 2),
                "completed_at_latest": None,
                "line_groups": {},
            })

            line_key = str(shift_doc.get("_id") or "").strip() or service_date_local.isoformat()
            line_group = group["line_groups"].setdefault(line_key, {
                "service_date_local": service_date_local,
                "total_hours": 0.0,
                "completed_slots": 0,
                "local_start": None,
                "local_end": None,
                "completed_at_latest": None,
            })
            line_group["total_hours"] += float(duration_hours)
            line_group["completed_slots"] += 1

            local_start = self._localize_utc_datetime(
                slot_doc.get("actual_start_at") or slot_doc.get("started_at") or shift_doc.get("shift_start_at_utc"),
                tzinfo,
            )
            local_end = self._localize_utc_datetime(
                slot_doc.get("actual_end_at") or slot_doc.get("checked_out_at") or slot_doc.get("completed_at") or shift_doc.get("shift_end_at_utc"),
                tzinfo,
            )
            if local_start and (line_group["local_start"] is None or local_start < line_group["local_start"]):
                line_group["local_start"] = local_start
            if local_end and (line_group["local_end"] is None or local_end > line_group["local_end"]):
                line_group["local_end"] = local_end

            completed_at = self._as_datetime(slot_doc.get("completed_at"))
            if completed_at and (line_group["completed_at_latest"] is None or completed_at > line_group["completed_at_latest"]):
                line_group["completed_at_latest"] = completed_at
            if completed_at and (group["completed_at_latest"] is None or completed_at > group["completed_at_latest"]):
                group["completed_at_latest"] = completed_at

        items: List[Dict[str, Any]] = []
        for group in grouped.values():
            line_items: List[Dict[str, Any]] = []
            total_hours = 0.0
            total_amount = 0.0

            ordered_line_groups = sorted(
                group["line_groups"].values(),
                key=lambda item: item["service_date_local"],
            )
            for line_group in ordered_line_groups:
                line_item = self._build_weekly_assignee_line_item(
                    request_title=group["request_title"],
                    service_date_local=line_group["service_date_local"],
                    payout_hourly_rate=group["payout_hourly_rate"],
                    total_hours=round(float(line_group["total_hours"]), 2),
                    completed_slots=int(line_group["completed_slots"] or 0),
                    request_guards_required=group["request_guards_required"],
                    local_start=line_group["local_start"],
                    local_end=line_group["local_end"],
                )
                line_items.append(line_item)
                total_hours += float(line_item["quantity"] or 0.0)
                total_amount += float(line_item["amount"] or 0.0)

            if not line_items:
                continue

            billing_period_start_local = group["week_start"].isoformat()
            billing_period_end_local = group["week_end"].isoformat()
            completed_at_latest = group["completed_at_latest"] or now_utc
            items.append({
                "id": self._weekly_assignee_invoice_id(
                    request_id=group["request_id"],
                    assignee_tenant_id=assignee_tenant_id,
                    assignee_tenant_type=assignee_tenant_type,
                    billing_period_start_local=billing_period_start_local,
                ),
                "request_id": group["request_id"],
                "invoice_number": self._weekly_assignee_invoice_number(
                    request_id=group["request_id"],
                    assignee_tenant_id=assignee_tenant_id,
                    billing_period_start_local=billing_period_start_local,
                ),
                "request_title": group["request_title"],
                "site_name": group["site_name"],
                "assignee_tenant_type": assignee_tenant_type,
                "coverage_status": RequestAssignmentStatus.COMPLETED.value,
                "contract_type": "long_term",
                "billing_cycle": "weekly",
                "charge_timing": "weekly_cutoff",
                "billing_period_start_local": billing_period_start_local,
                "billing_period_end_local": billing_period_end_local,
                "billing_period_label": f"{group['week_start'].strftime('%b %d, %Y')} - {group['week_end'].strftime('%b %d, %Y')}",
                "currency": group["currency"],
                "committed_slots": group["request_committed_slots"],
                "payout_hourly_rate": group["payout_hourly_rate"],
                "estimated_total_hours": round(total_hours, 2),
                "estimated_amount": round(total_amount, 2),
                "invoice_status": RequestInvoiceStatus.ISSUED.value,
                "line_items": line_items,
                "note": "Weekly payout invoice generated from completed scheduled coverage after the weekly cutoff.",
                "created_at": completed_at_latest,
                "updated_at": completed_at_latest,
            })

        return items

    async def _build_assignee_invoice_items(
        self,
        *,
        assignee_tenant_id: str,
        assignee_tenant_type: str,
        assignment_map: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        request_ids = list(assignment_map.keys())
        if not request_ids:
            return []

        request_collection = self._engine.get_collection(ClientRequestRecord)
        request_object_ids: List[ObjectId] = []
        for request_id in request_ids:
            try:
                request_object_ids.append(ObjectId(request_id))
            except Exception:
                continue

        request_docs = await request_collection.find({"_id": {"$in": request_object_ids}}).to_list(length=None) if request_object_ids else []
        request_lookup: Dict[str, Dict[str, Any]] = {}
        short_term_request_ids: List[str] = []
        long_term_request_ids: List[str] = []

        for doc in request_docs:
            request_id = str(doc.get("_id") or "").strip()
            pricing_snapshot = doc.get("pricing_snapshot") if isinstance(doc.get("pricing_snapshot"), dict) else {}
            invoicing_snapshot = doc.get("invoicing_snapshot") if isinstance(doc.get("invoicing_snapshot"), dict) else {}
            request_lookup[request_id] = {
                "title": str(doc.get("title") or "").strip(),
                "site_name": str((doc.get("site_snapshot") or {}).get("site_name") or "").strip(),
                "timezone": str(doc.get("timezone") or "").strip() or "UTC",
                "currency": str(pricing_snapshot.get("currency") or "CAD"),
                "guards_required": int(doc.get("guards_required") or pricing_snapshot.get("guards_required") or 1),
                "guard_hourly_pay": pricing_snapshot.get("guard_hourly_pay"),
                "provider_hourly_pay": pricing_snapshot.get("provider_hourly_pay"),
                "contract_type": self._normalize_invoice_contract_type(invoicing_snapshot.get("contract_type")),
            }
            if request_lookup[request_id]["contract_type"] == "long_term":
                long_term_request_ids.append(request_id)
            else:
                short_term_request_ids.append(request_id)

        items = await self._build_short_term_assignee_invoice_items(
            request_ids=short_term_request_ids,
            assignment_map=assignment_map,
            request_lookup=request_lookup,
            assignee_tenant_type=assignee_tenant_type,
        )
        items.extend(await self._build_long_term_assignee_weekly_invoice_items(
            request_ids=long_term_request_ids,
            assignment_map=assignment_map,
            request_lookup=request_lookup,
            assignee_tenant_id=assignee_tenant_id,
            assignee_tenant_type=assignee_tenant_type,
        ))
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return items

    async def _build_platform_finance_context(
        self,
        request_ids: List[str],
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        normalized_request_ids = [
            str(request_id or "").strip()
            for request_id in request_ids
            if str(request_id or "").strip()
        ]
        if not normalized_request_ids:
            return {}, {}, {}

        request_object_ids: List[ObjectId] = []
        for request_id in normalized_request_ids:
            try:
                request_object_ids.append(ObjectId(request_id))
            except Exception:
                continue

        request_collection = self._engine.get_collection(ClientRequestRecord)
        request_docs = await request_collection.find({
            "_id": {"$in": request_object_ids},
        }).to_list(length=None) if request_object_ids else []

        request_lookup: Dict[str, Dict[str, Any]] = {}
        client_tenant_ids: List[str] = []
        for doc in request_docs:
            request_id = str(doc.get("_id") or "").strip()
            pricing_snapshot = doc.get("pricing_snapshot") if isinstance(doc.get("pricing_snapshot"), dict) else {}
            invoicing_snapshot = doc.get("invoicing_snapshot") if isinstance(doc.get("invoicing_snapshot"), dict) else {}
            client_tenant_id = str(doc.get("client_tenant_id") or "").strip()
            if client_tenant_id:
                client_tenant_ids.append(client_tenant_id)
            request_lookup[request_id] = {
                "request_id": request_id,
                "client_tenant_id": client_tenant_id,
                "title": str(doc.get("title") or "").strip(),
                "site_name": str((doc.get("site_snapshot") or {}).get("site_name") or "").strip(),
                "timezone": str(doc.get("timezone") or "").strip() or "UTC",
                "currency": str(pricing_snapshot.get("currency") or "CAD"),
                "contract_type": self._normalize_invoice_contract_type(invoicing_snapshot.get("contract_type")),
                "client_hourly_quote": pricing_snapshot.get("client_hourly_quote"),
                "guard_hourly_pay": pricing_snapshot.get("guard_hourly_pay"),
                "provider_hourly_pay": pricing_snapshot.get("provider_hourly_pay"),
                "guard_company_margin": pricing_snapshot.get("guard_company_margin"),
                "provider_company_commission": pricing_snapshot.get("provider_company_commission"),
            }

        invoice_collection = self._engine.get_collection(RequestInvoiceRecord)
        invoice_docs = await invoice_collection.find({
            "request_id": {"$in": normalized_request_ids},
        }).sort("created_at", -1).to_list(length=None)

        invoice_lookup: Dict[str, List[Dict[str, Any]]] = {}
        for doc in invoice_docs:
            request_id = str(doc.get("request_id") or "").strip()
            if not request_id:
                continue
            invoice_lookup.setdefault(request_id, []).append(doc)
            client_tenant_id = str(doc.get("client_tenant_id") or "").strip()
            if client_tenant_id:
                client_tenant_ids.append(client_tenant_id)
            request_entry = request_lookup.setdefault(request_id, {"request_id": request_id})
            if not request_entry.get("client_tenant_id") and client_tenant_id:
                request_entry["client_tenant_id"] = client_tenant_id
            if request_entry.get("client_hourly_quote") is None and doc.get("client_hourly_quote") is not None:
                request_entry["client_hourly_quote"] = doc.get("client_hourly_quote")

        client_labels = await self._build_tenant_label_lookup(client_tenant_ids) if client_tenant_ids else {}
        return request_lookup, invoice_lookup, client_labels

    @classmethod
    def _match_client_invoice_for_platform_item(
        cls,
        item: Dict[str, Any],
        candidate_invoices: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not candidate_invoices:
            return None

        normalized_invoice_number = str(item.get("invoice_number") or "").strip()
        if normalized_invoice_number:
            for candidate in candidate_invoices:
                if str(candidate.get("invoice_number") or "").strip() == normalized_invoice_number:
                    return candidate

        overlapping = [
            candidate
            for candidate in candidate_invoices
            if cls._date_ranges_overlap(
                item.get("billing_period_start_local"),
                item.get("billing_period_end_local"),
                candidate.get("billing_period_start_local"),
                candidate.get("billing_period_end_local"),
            )
        ]
        pool = overlapping or candidate_invoices
        pool = sorted(
            pool,
            key=lambda candidate: (
                str(candidate.get("billing_period_start_local") or ""),
                str(candidate.get("updated_at") or candidate.get("created_at") or ""),
            ),
            reverse=True,
        )
        return pool[0] if pool else None

    @classmethod
    def _enrich_platform_payout_invoice_item(
        cls,
        item: Dict[str, Any],
        *,
        request_summary: Dict[str, Any],
        candidate_invoices: List[Dict[str, Any]],
        client_label: str = "",
    ) -> Dict[str, Any]:
        enriched = dict(item)
        matched_invoice = cls._match_client_invoice_for_platform_item(enriched, candidate_invoices)
        serialized_invoice = cls._serialize_invoice(matched_invoice) if matched_invoice else {}

        client_hourly_quote = cls._as_float(
            serialized_invoice.get("client_hourly_quote")
            if serialized_invoice
            else request_summary.get("client_hourly_quote")
        )
        payout_hourly_rate = cls._as_float(enriched.get("payout_hourly_rate"))
        total_hours = cls._as_float(enriched.get("estimated_total_hours"))
        payout_total = cls._as_float(enriched.get("estimated_amount"))

        estimated_client_revenue = round(client_hourly_quote * total_hours, 2) if client_hourly_quote is not None and total_hours is not None else None
        estimated_platform_earning = round(estimated_client_revenue - payout_total, 2) if estimated_client_revenue is not None and payout_total is not None else None
        platform_cut_hourly_rate = round(max(client_hourly_quote - payout_hourly_rate, 0.0), 2) if client_hourly_quote is not None and payout_hourly_rate is not None else None
        platform_margin_percent = round((estimated_platform_earning / estimated_client_revenue) * 100, 2) if estimated_client_revenue and estimated_platform_earning is not None else None

        request_client_tenant_id = str(
            request_summary.get("client_tenant_id")
            or serialized_invoice.get("client_tenant_id")
            or ""
        ).strip()
        contract_type = str(enriched.get("contract_type") or request_summary.get("contract_type") or "").strip()
        reporting_basis = "attendance_realized_hours" if str(enriched.get("billing_cycle") or "").strip() == "weekly" else "request_invoice_estimate"

        enriched.update({
            "client_tenant_id": request_client_tenant_id or None,
            "client_label": client_label or request_client_tenant_id or None,
            "client_hourly_quote": client_hourly_quote,
            "estimated_client_revenue": estimated_client_revenue,
            "estimated_platform_earning": estimated_platform_earning,
            "platform_cut_hourly_rate": platform_cut_hourly_rate,
            "platform_margin_percent": platform_margin_percent,
            "linked_client_invoice_id": serialized_invoice.get("id"),
            "linked_client_invoice_number": serialized_invoice.get("invoice_number"),
            "linked_client_invoice_status": serialized_invoice.get("invoice_status"),
            "linked_client_payment_status": serialized_invoice.get("payment_status"),
            "linked_client_invoice_period_label": serialized_invoice.get("billing_period_label"),
            "linked_client_invoice_trigger": serialized_invoice.get("trigger"),
            "reporting_basis": reporting_basis,
            "reporting_note": (
                "Client revenue is normalized from completed attendance against the saved client hourly quote for weekly payout reporting."
                if contract_type == "long_term" and str(enriched.get("billing_cycle") or "").strip() == "weekly"
                else "Client revenue is aligned to the issued request invoice estimate for this payout invoice."
            ),
        })
        return enriched

    @classmethod
    def _build_platform_payout_summary(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_client_revenue = 0.0
        total_payout = 0.0
        total_platform_earning = 0.0
        total_hours = 0.0
        total_guard_payout = 0.0
        total_provider_payout = 0.0
        total_guard_earning = 0.0
        total_provider_earning = 0.0

        for item in items:
            client_revenue = float(cls._as_float(item.get("estimated_client_revenue")) or 0.0)
            payout = float(cls._as_float(item.get("estimated_amount")) or 0.0)
            earning = float(cls._as_float(item.get("estimated_platform_earning")) or 0.0)
            hours = float(cls._as_float(item.get("estimated_total_hours")) or 0.0)
            tenant_type = str(item.get("assignee_tenant_type") or "").strip().lower()

            total_client_revenue += client_revenue
            total_payout += payout
            total_platform_earning += earning
            total_hours += hours

            if tenant_type == RequestTargetType.SERVICE_PROVIDER.value:
                total_provider_payout += payout
                total_provider_earning += earning
            else:
                total_guard_payout += payout
                total_guard_earning += earning

        margin_percent = round((total_platform_earning / total_client_revenue) * 100, 2) if total_client_revenue > 0 else None
        return {
            "invoice_count": len(items),
            "total_client_revenue": round(total_client_revenue, 2),
            "total_payout": round(total_payout, 2),
            "total_platform_earning": round(total_platform_earning, 2),
            "total_hours": round(total_hours, 2),
            "total_guard_payout": round(total_guard_payout, 2),
            "total_provider_payout": round(total_provider_payout, 2),
            "total_guard_earning": round(total_guard_earning, 2),
            "total_provider_earning": round(total_provider_earning, 2),
            "platform_margin_percent": margin_percent,
        }

    async def _collect_platform_assignee_invoice_scopes(self) -> List[Dict[str, Any]]:
        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        assignment_docs = await assignment_collection.find({}).to_list(length=None)
        allowed_statuses = self._assignee_invoice_allowed_statuses()
        scopes: Dict[tuple[str, str], Dict[str, Any]] = {}

        for doc in assignment_docs:
            if self._assignment_scope_value(doc) != RequestAssignmentScope.REQUEST.value:
                continue
            status_value = self._enum_value(doc.get("assignment_status"))
            if status_value not in allowed_statuses:
                continue

            tenant_id = str(doc.get("assignee_tenant_id") or "").strip()
            tenant_type = str(doc.get("assignee_tenant_type") or "").strip().lower()
            request_id = str(doc.get("request_id") or "").strip()
            if not tenant_id or not tenant_type or not request_id:
                continue

            scope_key = (tenant_id, tenant_type)
            scope = scopes.setdefault(scope_key, {
                "tenant_id": tenant_id,
                "assignee_tenant_type": tenant_type,
                "assignment_map": {},
            })
            request_entry = scope["assignment_map"].setdefault(request_id, {
                "committed_slots": 0,
                "statuses": set(),
            })
            request_entry["committed_slots"] += self._assignment_slots(doc)
            request_entry["statuses"].add(status_value)

        return list(scopes.values())

    async def _get_tenant(self, tenant_id: str):
        try:
            return await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            return None

    async def _get_request_or_404(self, request_id: str) -> ClientRequestRecord:
        try:
            object_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request id")

        record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request not found")
        return record

    async def _get_wave_or_404(self, wave_id: str) -> RequestBroadcastWaveRecord:
        try:
            object_id = ObjectId(wave_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid wave id")

        record = await self._engine.find_one(RequestBroadcastWaveRecord, RequestBroadcastWaveRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request wave not found")
        return record

    async def _get_assignment_or_404(self, assignment_id: str) -> RequestAssignmentRecord:
        try:
            object_id = ObjectId(assignment_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid assignment id")

        record = await self._engine.find_one(RequestAssignmentRecord, RequestAssignmentRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return record

    async def _get_client_tenant(self, current_user):
        tenant_id = str(getattr(current_user, "tenant_uuid", "") or "")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Invalid client tenant association")

        return await self._get_active_client_tenant_by_id(tenant_id)

    async def _get_active_client_tenant_by_id(self, tenant_id: str):
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Client tenant is required")

        try:
            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid client tenant id")

        if not tenant or tenant.tenant_type != TenantType.CLIENT:
            raise HTTPException(status_code=403, detail="Client request workflow is only available for client tenants")
        if tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Client tenant must be active before requests can be created")
        return tenant

    async def _resolve_request_client_tenant(self, payload: ClientRequestCreatePayload, current_user):
        role_value = self._role_value(current_user)
        if self._is_platform_write_role(role_value):
            return await self._get_active_client_tenant_by_id(str(payload.client_tenant_id or "").strip())
        return await self._get_client_tenant(current_user)

    @staticmethod
    def _assert_client_billing_method(profile: Dict[str, Any]) -> None:
        billing_method = profile.get("billing_method") if isinstance(profile, dict) else None
        if not isinstance(billing_method, dict):
            raise HTTPException(status_code=403, detail="Client billing method is required before creating requests")

        method = str(billing_method.get("method") or billing_method.get("type") or "").strip().lower()
        cardholder_name = str(billing_method.get("cardholder_name") or billing_method.get("cardholderName") or "").strip()
        last4 = str(billing_method.get("last4") or billing_method.get("card_last4") or "").strip()
        expiry_month = str(billing_method.get("expiry_month") or billing_method.get("expiryMonth") or "").strip()
        expiry_year = str(billing_method.get("expiry_year") or billing_method.get("expiryYear") or "").strip()

        if method not in {"credit_card", "debit_card"}:
            raise HTTPException(status_code=403, detail="Client billing method is required before creating requests")
        if not cardholder_name or not re.fullmatch(r"\d{4}", last4) or not re.fullmatch(r"(0[1-9]|1[0-2])", expiry_month) or not re.fullmatch(r"\d{2,4}", expiry_year):
            raise HTTPException(status_code=403, detail="Client billing method is required before creating requests")

    @staticmethod
    def _normalize_province_code(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        normalized = text.upper()
        valid_codes = {option["value"] for option in CANADIAN_PROVINCE_OPTIONS}
        if normalized in valid_codes:
            return normalized
        for option in CANADIAN_PROVINCE_OPTIONS:
            if option["label"].lower() == text.lower():
                return option["value"]
        return ""

    @staticmethod
    def _normalize_city_code(province_code: str, value: Any) -> str:
        normalized_province = str(province_code or "").strip().upper()
        text = str(value or "").strip()
        if not normalized_province or not text:
            return ""
        options = CANADIAN_CITIES_BY_PROVINCE_OPTIONS.get(normalized_province, [])
        normalized = text.upper()
        for option in options:
            if option["value"] == normalized:
                return option["value"]
        for option in options:
            if option["label"].lower() == text.lower():
                return option["value"]
        return ""

    @staticmethod
    def _resolve_rate_field(requested_start_at: Optional[datetime]) -> str:
        start = RequestManager._as_datetime(requested_start_at)
        if not start:
            return "standard_rate"
        return "weekend_rate" if start.weekday() >= 5 else "standard_rate"

    async def _resolve_scoped_rate(
        self,
        scopes: List[str],
        province_code: str,
        city_code: str,
        rate_field: str,
    ) -> float:
        if not province_code:
            return 0.0

        normalized_city = str(city_code or "").strip().upper()
        for scope in scopes:
            if normalized_city:
                city_match = await self._engine.find_one(
                    BillingRate,
                    (BillingRate.scope == scope)
                    & (BillingRate.region_code == province_code)
                    & (BillingRate.city_code == normalized_city),
                )
                if city_match:
                    return round(float(getattr(city_match, rate_field, 0.0) or 0.0), 2)

            province_match = await self._engine.find_one(
                BillingRate,
                (BillingRate.scope == scope)
                & (BillingRate.region_code == province_code)
                & (BillingRate.city_code == ""),
            )
            if province_match:
                return round(float(getattr(province_match, rate_field, 0.0) or 0.0), 2)

        return 0.0

    @staticmethod
    def _calculate_requested_hours(start_at: Optional[datetime], end_at: Optional[datetime]) -> Optional[float]:
        start = RequestManager._as_datetime(start_at)
        end = RequestManager._as_datetime(end_at)
        if not start or not end or end <= start:
            return None
        return round(max((end - start).total_seconds() / 3600.0, 0.0), 2)

    @staticmethod
    def _normalize_invoice_contract_type(contract_type: Any) -> str:
        normalized = str(contract_type or "").strip().lower()
        if normalized in {"long_term", "long-term", "longterm", "monthly"}:
            return "long_term"
        return "short_term"

    @staticmethod
    def _derive_invoice_contract_type_for_schedule(schedule_type: Any) -> str:
        normalized = str(getattr(schedule_type, "value", schedule_type) or "").strip().lower()
        if normalized == RequestScheduleType.ONE_TIME.value:
            return "short_term"
        if normalized in {RequestScheduleType.DATE_RANGE.value, RequestScheduleType.RECURRING_WEEKLY.value}:
            return "long_term"
        return "short_term"

    async def _refresh_request_finance_snapshot(
        self,
        record: ClientRequestRecord,
        *,
        invoice_contract_type: Any = _FINANCE_SNAPSHOT_UNSET,
        invoice_cutoff_day: Any = _FINANCE_SNAPSHOT_UNSET,
        invoice_recipient_email: Any = _FINANCE_SNAPSHOT_UNSET,
    ) -> Dict[str, Dict[str, Any]]:
        invoicing_snapshot = record.invoicing_snapshot if isinstance(getattr(record, "invoicing_snapshot", None), dict) else {}
        resolved_contract_type = (
            invoicing_snapshot.get("contract_type")
            if invoice_contract_type is _FINANCE_SNAPSHOT_UNSET
            else invoice_contract_type
        )
        resolved_cutoff_day = (
            invoicing_snapshot.get("monthly_cutoff_day")
            if invoice_cutoff_day is _FINANCE_SNAPSHOT_UNSET
            else invoice_cutoff_day
        )
        resolved_recipient_email = (
            invoicing_snapshot.get("invoice_recipient_email")
            if invoice_recipient_email is _FINANCE_SNAPSHOT_UNSET
            else invoice_recipient_email
        )

        finance_snapshot = await self._build_request_pricing_and_invoicing(
            site_snapshot=record.site_snapshot or {},
            requested_start_at=record.requested_start_at,
            requested_end_at=record.requested_end_at,
            guards_required=int(record.guards_required or 1),
            invoice_contract_type=resolved_contract_type,
            invoice_cutoff_day=resolved_cutoff_day,
            invoice_recipient_email=resolved_recipient_email,
        )
        record.pricing_snapshot = finance_snapshot["pricing_snapshot"]
        record.invoicing_snapshot = finance_snapshot["invoicing_snapshot"]
        return finance_snapshot

    async def _sync_request_finance_snapshot_for_schedule(
        self,
        record: ClientRequestRecord,
        schedule_record: RequestScheduleTemplateRecord,
    ) -> Dict[str, Dict[str, Any]]:
        finance_snapshot = await self._refresh_request_finance_snapshot(
            record,
            invoice_contract_type=self._derive_invoice_contract_type_for_schedule(
                getattr(schedule_record, "schedule_type", None),
            ),
        )
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)
        return finance_snapshot

    @staticmethod
    def _format_invoice_currency(value: Any) -> str:
        amount = RequestManager._as_float(value)
        if amount is None:
            return "TBD"
        return f"${amount:.2f} CAD"

    @staticmethod
    def _normalize_invoice_trigger(reason: Any) -> RequestInvoiceTrigger:
        normalized = str(getattr(reason, "value", reason) or "").strip().lower()
        if normalized == RequestInvoiceTrigger.PUBLISH_UPDATE.value:
            return RequestInvoiceTrigger.PUBLISH_UPDATE
        if normalized == RequestInvoiceTrigger.ADDITIONAL_COVERAGE.value:
            return RequestInvoiceTrigger.ADDITIONAL_COVERAGE
        if normalized == RequestInvoiceTrigger.SCHEDULE_UPDATED.value:
            return RequestInvoiceTrigger.SCHEDULE_UPDATED
        if normalized == RequestInvoiceTrigger.MONTHLY_ADVANCE.value:
            return RequestInvoiceTrigger.MONTHLY_ADVANCE
        return RequestInvoiceTrigger.INITIAL_PUBLISH

    def _resolve_invoice_timezone(
        self,
        record: ClientRequestRecord,
        schedule_record: Optional[RequestScheduleTemplateRecord] = None,
    ) -> ZoneInfo:
        timezone_name = str(
            getattr(schedule_record, "timezone", None)
            or getattr(record, "timezone", None)
            or "UTC",
        ).strip() or "UTC"
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return ZoneInfo("UTC")

    @staticmethod
    def _shift_month(anchor: date, months: int) -> date:
        month_index = (anchor.month - 1) + int(months or 0)
        year = anchor.year + (month_index // 12)
        month = (month_index % 12) + 1
        return date(year, month, 1)

    @classmethod
    def _month_bounds(cls, anchor: date) -> tuple[date, date]:
        month_start = date(anchor.year, anchor.month, 1)
        next_month_start = cls._shift_month(month_start, 1)
        return month_start, next_month_start - timedelta(days=1)

    @staticmethod
    def _parse_invoice_local_time(field_name: str, value: Any) -> time:
        try:
            return datetime.strptime(str(value or "").strip(), "%H:%M").time()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from exc

    @classmethod
    def _build_invoice_number(
        cls,
        record: ClientRequestRecord,
        *,
        billing_period_start_local: Optional[str],
        issued_at: datetime,
    ) -> str:
        request_token = str(getattr(record, "id", "") or "").replace("-", "")[-6:].upper() or "REQ"
        period_token = ""
        if billing_period_start_local:
            try:
                period_token = date.fromisoformat(billing_period_start_local).strftime("%Y%m")
            except Exception:
                period_token = billing_period_start_local.replace("-", "")[:6]
        if not period_token:
            period_token = issued_at.strftime("%Y%m%d")
        return f"INV-{period_token}-{request_token}"

    @staticmethod
    def _build_invoice_line_item(
        *,
        description: str,
        service_date_local: date,
        guards_required: int,
        client_hourly_quote: float,
        hours_per_position: float,
        local_start: datetime,
        local_end: datetime,
    ) -> Dict[str, Any]:
        quantity = round(hours_per_position * max(int(guards_required or 1), 1), 2)
        amount = round(client_hourly_quote * quantity, 2)
        return {
            "description": description,
            "service_date_local": service_date_local.isoformat(),
            "unit": "hour",
            "quantity": quantity,
            "unit_rate": round(client_hourly_quote, 2),
            "amount": amount,
            "metadata": {
                "guards_required": max(int(guards_required or 1), 1),
                "hours_per_position": round(hours_per_position, 2),
                "start_at_local": local_start.isoformat(),
                "end_at_local": local_end.isoformat(),
            },
        }

    def _build_short_term_invoice_details(
        self,
        record: ClientRequestRecord,
        *,
        schedule_record: Optional[RequestScheduleTemplateRecord],
    ) -> Optional[Dict[str, Any]]:
        pricing_snapshot = record.pricing_snapshot if isinstance(getattr(record, "pricing_snapshot", None), dict) else {}
        client_hourly_quote = self._as_float(pricing_snapshot.get("client_hourly_quote"))
        if client_hourly_quote is None:
            return None

        tzinfo = self._resolve_invoice_timezone(record, schedule_record)
        local_start: Optional[datetime] = None
        local_end: Optional[datetime] = None

        if schedule_record and self._enum_value(getattr(schedule_record, "schedule_type", None)) == "one_time":
            occurrence_date = date.fromisoformat(str(getattr(schedule_record, "start_date_local", "") or "").strip())
            start_clock = self._parse_invoice_local_time("start_time_local", getattr(schedule_record, "start_time_local", ""))
            end_clock = self._parse_invoice_local_time("end_time_local", getattr(schedule_record, "end_time_local", ""))
            local_start = datetime.combine(occurrence_date, start_clock, tzinfo=tzinfo)
            local_end_date = occurrence_date + timedelta(days=1) if bool(getattr(schedule_record, "is_overnight", False)) else occurrence_date
            local_end = datetime.combine(local_end_date, end_clock, tzinfo=tzinfo)
        else:
            start_at = self._as_datetime(getattr(record, "requested_start_at", None))
            end_at = self._as_datetime(getattr(record, "requested_end_at", None))
            if start_at and end_at:
                local_start = start_at.replace(tzinfo=timezone.utc).astimezone(tzinfo)
                local_end = end_at.replace(tzinfo=timezone.utc).astimezone(tzinfo)

        if not local_start or not local_end or local_end <= local_start:
            return None

        hours_per_position = round(max((local_end - local_start).total_seconds() / 3600.0, 0.0), 2)
        service_date = local_start.date()
        line_items = [self._build_invoice_line_item(
            description=str(getattr(record, "title", "") or "Client request coverage").strip() or "Client request coverage",
            service_date_local=service_date,
            guards_required=int(pricing_snapshot.get("guards_required") or record.guards_required or 1),
            client_hourly_quote=client_hourly_quote,
            hours_per_position=hours_per_position,
            local_start=local_start,
            local_end=local_end,
        )]
        return {
            "billing_period_start_local": service_date.isoformat(),
            "billing_period_end_local": local_end.date().isoformat(),
            "billing_period_label": service_date.strftime("%b %d, %Y"),
            "line_items": line_items,
        }

    def _iter_schedule_dates_for_period(
        self,
        schedule_record: RequestScheduleTemplateRecord,
        *,
        period_start: date,
        period_end: date,
    ) -> List[date]:
        try:
            schedule_start = date.fromisoformat(str(getattr(schedule_record, "start_date_local", "") or "").strip())
        except Exception:
            return []
        schedule_end_raw = str(getattr(schedule_record, "end_date_local", "") or "").strip()
        schedule_end = date.fromisoformat(schedule_end_raw) if schedule_end_raw else schedule_start

        effective_start = max(period_start, schedule_start)
        effective_end = min(period_end, schedule_end)
        if effective_end < effective_start:
            return []

        schedule_type = self._enum_value(getattr(schedule_record, "schedule_type", None))
        if schedule_type == "one_time":
            return [schedule_start] if effective_start <= schedule_start <= effective_end else []

        recurrence_days = {
            token.strip().lower()
            for token in list(getattr(schedule_record, "recurrence_days", []) or [])
            if str(token or "").strip()
        }
        weekday_map = {
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
        allowed_weekdays = {weekday_map[token] for token in recurrence_days if token in weekday_map}

        current = effective_start
        results: List[date] = []
        while current <= effective_end:
            if schedule_type == "date_range" or current.weekday() in allowed_weekdays:
                results.append(current)
            current += timedelta(days=1)
        return results

    def _build_long_term_invoice_details(
        self,
        record: ClientRequestRecord,
        *,
        schedule_record: RequestScheduleTemplateRecord,
        cutoff_day: int,
    ) -> Optional[Dict[str, Any]]:
        pricing_snapshot = record.pricing_snapshot if isinstance(getattr(record, "pricing_snapshot", None), dict) else {}
        client_hourly_quote = self._as_float(pricing_snapshot.get("client_hourly_quote"))
        if client_hourly_quote is None:
            return None

        tzinfo = self._resolve_invoice_timezone(record, schedule_record)
        today_local = datetime.now(tzinfo).date()
        anchor = date(today_local.year, today_local.month, 1)
        if today_local.day >= max(int(cutoff_day or 1), 1):
            anchor = self._shift_month(anchor, 1)
        period_start, period_end = self._month_bounds(anchor)

        occurrence_dates = self._iter_schedule_dates_for_period(
            schedule_record,
            period_start=period_start,
            period_end=period_end,
        )
        if not occurrence_dates:
            return None

        start_clock = self._parse_invoice_local_time("start_time_local", getattr(schedule_record, "start_time_local", ""))
        end_clock = self._parse_invoice_local_time("end_time_local", getattr(schedule_record, "end_time_local", ""))
        guards_required = int(pricing_snapshot.get("guards_required") or record.guards_required or 1)
        line_items: List[Dict[str, Any]] = []

        for occurrence_date in occurrence_dates:
            local_start = datetime.combine(occurrence_date, start_clock, tzinfo=tzinfo)
            local_end_date = occurrence_date + timedelta(days=1) if bool(getattr(schedule_record, "is_overnight", False)) else occurrence_date
            local_end = datetime.combine(local_end_date, end_clock, tzinfo=tzinfo)
            if local_end <= local_start:
                continue
            hours_per_position = round(max((local_end - local_start).total_seconds() / 3600.0, 0.0), 2)
            line_items.append(self._build_invoice_line_item(
                description=f"{str(getattr(record, 'title', '') or 'Client request coverage').strip() or 'Client request coverage'} - {occurrence_date.isoformat()}",
                service_date_local=occurrence_date,
                guards_required=guards_required,
                client_hourly_quote=client_hourly_quote,
                hours_per_position=hours_per_position,
                local_start=local_start,
                local_end=local_end,
            ))

        if not line_items:
            return None

        return {
            "billing_period_start_local": period_start.isoformat(),
            "billing_period_end_local": period_end.isoformat(),
            "billing_period_label": period_start.strftime("%B %Y"),
            "line_items": line_items,
        }

    @staticmethod
    def _summarize_invoice_line_items(line_items: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        total_hours = 0.0
        total_amount = 0.0
        first_hours: Optional[float] = None
        for item in line_items:
            quantity = RequestManager._as_float(item.get("quantity")) or 0.0
            amount = RequestManager._as_float(item.get("amount")) or 0.0
            hours_per_position = RequestManager._as_float((item.get("metadata") or {}).get("hours_per_position"))
            total_hours += quantity
            total_amount += amount
            if first_hours is None and hours_per_position is not None:
                first_hours = hours_per_position
        return {
            "requested_hours_per_position": round(first_hours, 2) if first_hours is not None else None,
            "estimated_total_hours": round(total_hours, 2),
            "estimated_amount": round(total_amount, 2),
        }

    async def _find_existing_invoice(
        self,
        *,
        request_id: str,
        contract_type: str,
        billing_period_start_local: str,
        billing_period_end_local: str,
    ) -> Optional[RequestInvoiceRecord]:
        return await self._engine.find_one(
            RequestInvoiceRecord,
            (RequestInvoiceRecord.request_id == str(request_id))
            & (RequestInvoiceRecord.contract_type == contract_type)
            & (RequestInvoiceRecord.billing_period_start_local == billing_period_start_local)
            & (RequestInvoiceRecord.billing_period_end_local == billing_period_end_local),
        )

    @staticmethod
    def _invoice_material_snapshot(invoice_record: RequestInvoiceRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(invoice_record, dict):
            return {
                "request_revision": int(invoice_record.get("request_revision") or 0),
                "trigger": RequestManager._enum_value(invoice_record.get("trigger")),
                "billing_cycle": invoice_record.get("billing_cycle") or "",
                "charge_timing": invoice_record.get("charge_timing") or "",
                "monthly_cutoff_day": invoice_record.get("monthly_cutoff_day"),
                "billing_period_start_local": invoice_record.get("billing_period_start_local"),
                "billing_period_end_local": invoice_record.get("billing_period_end_local"),
                "billing_period_label": invoice_record.get("billing_period_label"),
                "guards_required": int(invoice_record.get("guards_required") or 0),
                "client_hourly_quote": RequestManager._as_float(invoice_record.get("client_hourly_quote")),
                "requested_hours_per_position": RequestManager._as_float(invoice_record.get("requested_hours_per_position")),
                "estimated_total_hours": RequestManager._as_float(invoice_record.get("estimated_total_hours")),
                "estimated_amount": RequestManager._as_float(invoice_record.get("estimated_amount")),
                "invoice_recipient_email": invoice_record.get("invoice_recipient_email"),
                "line_items": invoice_record.get("line_items") or [],
                "note": invoice_record.get("note"),
            }
        return {
            "request_revision": int(invoice_record.request_revision or 0),
            "trigger": RequestManager._enum_value(invoice_record.trigger),
            "billing_cycle": invoice_record.billing_cycle,
            "charge_timing": invoice_record.charge_timing,
            "monthly_cutoff_day": invoice_record.monthly_cutoff_day,
            "billing_period_start_local": invoice_record.billing_period_start_local,
            "billing_period_end_local": invoice_record.billing_period_end_local,
            "billing_period_label": invoice_record.billing_period_label,
            "guards_required": int(invoice_record.guards_required or 0),
            "client_hourly_quote": RequestManager._as_float(invoice_record.client_hourly_quote),
            "requested_hours_per_position": RequestManager._as_float(invoice_record.requested_hours_per_position),
            "estimated_total_hours": RequestManager._as_float(invoice_record.estimated_total_hours),
            "estimated_amount": RequestManager._as_float(invoice_record.estimated_amount),
            "invoice_recipient_email": invoice_record.invoice_recipient_email,
            "line_items": invoice_record.line_items or [],
            "note": invoice_record.note,
        }

    async def _sync_request_invoice_state(self, record: ClientRequestRecord, *, current_user, reason: Any) -> Dict[str, Any]:
        pricing_snapshot = record.pricing_snapshot if isinstance(getattr(record, "pricing_snapshot", None), dict) else {}
        invoicing_snapshot = record.invoicing_snapshot if isinstance(getattr(record, "invoicing_snapshot", None), dict) else {}
        trigger = self._normalize_invoice_trigger(reason)
        contract_type = self._normalize_invoice_contract_type(invoicing_snapshot.get("contract_type"))
        recipient_email = str(invoicing_snapshot.get("invoice_recipient_email") or "").strip() or None
        schedule_record = await self._get_active_schedule_template(str(record.id))

        invoice_details: Optional[Dict[str, Any]] = None
        if contract_type == "long_term":
            cutoff_day = invoicing_snapshot.get("monthly_cutoff_day")
            if cutoff_day is None:
                return {"action": "skipped", "invoice": None}
            if schedule_record is None:
                return {"action": "skipped", "invoice": None}
            invoice_details = self._build_long_term_invoice_details(
                record,
                schedule_record=schedule_record,
                cutoff_day=int(cutoff_day),
            )
        else:
            invoice_details = self._build_short_term_invoice_details(record, schedule_record=schedule_record)

        if not invoice_details:
            return {"action": "skipped", "invoice": None}

        billing_period_start_local = str(invoice_details.get("billing_period_start_local") or "").strip()
        billing_period_end_local = str(invoice_details.get("billing_period_end_local") or "").strip()
        line_items = list(invoice_details.get("line_items") or [])
        if not billing_period_start_local or not billing_period_end_local or not line_items:
            return {"action": "skipped", "invoice": None}

        issued_at = datetime.utcnow()
        summary = self._summarize_invoice_line_items(line_items)
        guards_required = int(pricing_snapshot.get("guards_required") or record.guards_required or 1)
        client_hourly_quote = self._as_float(pricing_snapshot.get("client_hourly_quote"))
        estimated_total_hours = self._as_float(summary.get("estimated_total_hours"))
        estimated_amount = self._as_float(summary.get("estimated_amount"))
        requested_hours_per_position = self._as_float(summary.get("requested_hours_per_position"))
        note = (
            f"Advance invoice for {invoice_details['billing_period_label']} scheduled coverage."
            if contract_type == "long_term"
            else "Invoice issued for the scheduled one-time coverage window."
        )
        invoice_payload = {
            "request_revision": max(int(record.request_revision or 0), 1),
            "trigger": trigger,
            "contract_type": contract_type,
            "billing_cycle": str(invoicing_snapshot.get("billing_cycle") or ("monthly" if contract_type == "long_term" else "per_request")),
            "charge_timing": str(invoicing_snapshot.get("charge_timing") or ("advance_monthly" if contract_type == "long_term" else "on_the_go")),
            "monthly_cutoff_day": invoicing_snapshot.get("monthly_cutoff_day"),
            "billing_period_start_local": billing_period_start_local,
            "billing_period_end_local": billing_period_end_local,
            "billing_period_label": str(invoice_details.get("billing_period_label") or "").strip() or None,
            "currency": str(pricing_snapshot.get("currency") or "CAD"),
            "rate_basis": str(pricing_snapshot.get("rate_basis") or "") or None,
            "guards_required": guards_required,
            "client_hourly_quote": client_hourly_quote,
            "requested_hours_per_position": requested_hours_per_position,
            "estimated_total_hours": estimated_total_hours,
            "estimated_amount": estimated_amount,
            "estimated_guard_payout": round((self._as_float(pricing_snapshot.get("guard_hourly_pay")) or 0.0) * (estimated_total_hours or 0.0), 2) if estimated_total_hours is not None else None,
            "estimated_provider_payout": round((self._as_float(pricing_snapshot.get("provider_hourly_pay")) or 0.0) * (estimated_total_hours or 0.0), 2) if estimated_total_hours is not None else None,
            "estimated_company_margin_with_guard": round((self._as_float(pricing_snapshot.get("guard_company_margin")) or 0.0) * (estimated_total_hours or 0.0), 2) if estimated_total_hours is not None else None,
            "estimated_company_margin_with_provider": round((self._as_float(pricing_snapshot.get("provider_company_commission")) or 0.0) * (estimated_total_hours or 0.0), 2) if estimated_total_hours is not None else None,
            "invoice_recipient_email": recipient_email,
            "payment_status": str(pricing_snapshot.get("mock_payment_status") or "pending_capture"),
            "line_items": line_items,
            "note": note,
        }

        existing_invoice = await self._find_existing_invoice(
            request_id=str(record.id),
            contract_type=contract_type,
            billing_period_start_local=billing_period_start_local,
            billing_period_end_local=billing_period_end_local,
        )
        previous_snapshot = self._invoice_material_snapshot(existing_invoice) if existing_invoice else None
        next_snapshot = self._invoice_material_snapshot({**invoice_payload, "trigger": trigger})

        if existing_invoice and previous_snapshot == next_snapshot:
            latest_snapshot = dict(invoicing_snapshot)
            latest_snapshot["invoice_status"] = self._enum_value(existing_invoice.invoice_status, RequestInvoiceStatus.ISSUED.value)
            latest_snapshot["latest_invoice_id"] = str(existing_invoice.id)
            latest_snapshot["latest_invoice_number"] = existing_invoice.invoice_number
            latest_snapshot["last_invoice_issued_at"] = existing_invoice.updated_at or existing_invoice.created_at
            latest_snapshot["email_delivery_status"] = self._enum_value(existing_invoice.email_delivery_status)
            record.invoicing_snapshot = latest_snapshot
            record.updated_at = datetime.utcnow()
            await self._engine.save(record)
            return {"action": "unchanged", "invoice": existing_invoice}

        created = existing_invoice is None
        if created:
            invoice_record = RequestInvoiceRecord(
                id=ObjectId(),
                request_id=str(record.id),
                client_tenant_id=record.client_tenant_id,
                invoice_number=self._build_invoice_number(
                    record,
                    billing_period_start_local=billing_period_start_local,
                    issued_at=issued_at,
                ),
                created_by_user_id=str(getattr(current_user, "id", "") or "") or None,
                created_by_username=str(getattr(current_user, "username", "") or "") or None,
                created_at=issued_at,
                updated_at=issued_at,
                **invoice_payload,
                invoice_status=RequestInvoiceStatus.ISSUED,
                email_delivery_status=(
                    RequestInvoiceDeliveryStatus.PENDING
                    if recipient_email
                    else RequestInvoiceDeliveryStatus.NOT_REQUESTED
                ),
            )
        else:
            invoice_record = existing_invoice
            invoice_record.request_revision = invoice_payload["request_revision"]
            invoice_record.trigger = trigger
            invoice_record.contract_type = contract_type
            invoice_record.billing_cycle = str(invoice_payload["billing_cycle"])
            invoice_record.charge_timing = str(invoice_payload["charge_timing"])
            invoice_record.monthly_cutoff_day = invoice_payload["monthly_cutoff_day"]
            invoice_record.billing_period_start_local = billing_period_start_local
            invoice_record.billing_period_end_local = billing_period_end_local
            invoice_record.billing_period_label = invoice_payload["billing_period_label"]
            invoice_record.currency = str(invoice_payload["currency"])
            invoice_record.rate_basis = invoice_payload["rate_basis"]
            invoice_record.guards_required = guards_required
            invoice_record.client_hourly_quote = client_hourly_quote
            invoice_record.requested_hours_per_position = requested_hours_per_position
            invoice_record.estimated_total_hours = estimated_total_hours
            invoice_record.estimated_amount = estimated_amount
            invoice_record.estimated_guard_payout = invoice_payload["estimated_guard_payout"]
            invoice_record.estimated_provider_payout = invoice_payload["estimated_provider_payout"]
            invoice_record.estimated_company_margin_with_guard = invoice_payload["estimated_company_margin_with_guard"]
            invoice_record.estimated_company_margin_with_provider = invoice_payload["estimated_company_margin_with_provider"]
            invoice_record.invoice_recipient_email = recipient_email
            invoice_record.payment_status = str(invoice_payload["payment_status"])
            invoice_record.line_items = line_items
            invoice_record.note = note
            invoice_record.invoice_status = RequestInvoiceStatus.REVISED
            invoice_record.email_delivery_status = (
                RequestInvoiceDeliveryStatus.PENDING
                if recipient_email
                else RequestInvoiceDeliveryStatus.NOT_REQUESTED
            )
            invoice_record.email_delivery_error = None
            invoice_record.updated_at = issued_at

        saved_invoice = await self._engine.save(invoice_record)

        next_invoicing_snapshot = dict(invoicing_snapshot)
        next_invoicing_snapshot["invoice_status"] = self._enum_value(saved_invoice.invoice_status)
        next_invoicing_snapshot["latest_invoice_id"] = str(saved_invoice.id)
        next_invoicing_snapshot["latest_invoice_number"] = saved_invoice.invoice_number
        next_invoicing_snapshot["last_invoice_issued_at"] = issued_at
        next_invoicing_snapshot["email_delivery_status"] = self._enum_value(saved_invoice.email_delivery_status)
        record.invoicing_snapshot = next_invoicing_snapshot
        record.updated_at = issued_at
        await self._engine.save(record)

        if recipient_email:
            email_sent = await self._send_request_invoice_email(
                record,
                saved_invoice,
                reason=trigger,
                is_revision=not created,
            )
            saved_invoice.email_delivery_status = (
                RequestInvoiceDeliveryStatus.SENT
                if email_sent
                else RequestInvoiceDeliveryStatus.FAILED
            )
            if email_sent:
                saved_invoice.emailed_at = datetime.utcnow()
                saved_invoice.email_delivery_error = None
            else:
                saved_invoice.email_delivery_error = "Invoice email dispatch failed"
            saved_invoice.updated_at = datetime.utcnow()
            next_invoicing_snapshot["email_delivery_status"] = self._enum_value(saved_invoice.email_delivery_status)
            record.invoicing_snapshot = next_invoicing_snapshot
            record.updated_at = datetime.utcnow()
            await self._engine.save(saved_invoice)
            await self._engine.save(record)

        return {"action": "created" if created else "updated", "invoice": saved_invoice}

    async def _send_request_invoice_email(
        self,
        record: ClientRequestRecord,
        invoice_record: RequestInvoiceRecord,
        *,
        reason: Any,
        is_revision: bool,
    ) -> bool:
        recipient_email = str(getattr(invoice_record, "invoice_recipient_email", None) or "").strip()
        if not recipient_email:
            return False

        template = getattr(constant, "mail_template", None)
        if template is None:
            print(f"[RequestManager] Invoice email skipped for request {record.id}: mail template unavailable")
            return False

        normalized_reason = self._enum_value(reason)
        contract_type = self._normalize_invoice_contract_type(getattr(invoice_record, "contract_type", None))
        header = "Advance Invoice Ready" if contract_type == "long_term" else "Invoice Ready"
        if is_revision:
            header = "Invoice Updated"

        subject_prefix = "Updated invoice" if is_revision else "Invoice"
        subject = f"{subject_prefix} {invoice_record.invoice_number} for {record.title}"
        reason_text = {
            RequestWaveTrigger.PUBLISH_UPDATE.value: "The invoice was updated because the request details changed.",
            RequestWaveTrigger.ADDITIONAL_COVERAGE.value: "The invoice was updated because additional coverage was requested.",
            RequestInvoiceTrigger.SCHEDULE_UPDATED.value: "The invoice was updated because the coverage schedule changed.",
            RequestInvoiceTrigger.MONTHLY_ADVANCE.value: "The next monthly advance invoice is ready for the upcoming billing period.",
        }.get(
            normalized_reason,
            "A client invoice is ready for this request.",
        )

        estimated_charge = self._format_invoice_currency(invoice_record.estimated_amount)
        client_hourly_quote = self._format_invoice_currency(invoice_record.client_hourly_quote)
        billing_cycle = str(invoice_record.billing_cycle or "per_request").replace("_", " ")
        charge_timing = str(invoice_record.charge_timing or "on_the_go").replace("_", " ")
        period_label = str(invoice_record.billing_period_label or "").strip()
        period_start = str(invoice_record.billing_period_start_local or "").strip()
        period_end = str(invoice_record.billing_period_end_local or "").strip()

        body_text = (
            f"{reason_text}<br><br>"
            f"Request: <strong>{record.title}</strong><br>"
            f"Invoice number: <strong>{invoice_record.invoice_number}</strong><br>"
            f"Invoice amount: <strong>{estimated_charge}</strong><br>"
            f"Client hourly quote: <strong>{client_hourly_quote}</strong><br>"
            f"Billing cycle: <strong>{billing_cycle.title()}</strong><br>"
            f"Charge timing: <strong>{charge_timing.title()}</strong>"
        )
        if period_label:
            body_text += f"<br>Billing period: <strong>{period_label}</strong>"
        elif period_start and period_end:
            body_text += f"<br>Billing period: <strong>{period_start}</strong> to <strong>{period_end}</strong>"
        if contract_type == "long_term" and invoice_record.monthly_cutoff_day is not None:
            body_text += f"<br>Monthly cutoff day: <strong>{int(invoice_record.monthly_cutoff_day)}</strong>"
        body_text += (
            f"<br>Scheduled invoice lines: <strong>{len(invoice_record.line_items or [])}</strong>"
            "<br><br>Client payment capture is still mocked inside the platform until gateway automation is enabled, "
            "but this email reflects the actual invoice document and scheduled totals."
        )

        html_content = template.render(
            username=str((record.site_snapshot or {}).get("site_name") or "Client Billing"),
            email=recipient_email,
            subject=subject,
            lurlHeading="",
            url="",
            header=header,
            body_text=body_text,
        )

        try:
            await mail_manager.get_instance().send_verification_mail(
                to=recipient_email,
                subject=subject,
                body=html_content,
            )
        except Exception as exc:
            print(f"[RequestManager] Failed to send invoice email for request {record.id}: {exc}")
            return False
        return True

    async def _build_request_pricing_and_invoicing(
        self,
        *,
        site_snapshot: Dict[str, Any],
        requested_start_at: Optional[datetime],
        requested_end_at: Optional[datetime],
        guards_required: int,
        invoice_contract_type: Any,
        invoice_cutoff_day: Optional[int],
        invoice_recipient_email: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        site_address = site_snapshot.get("site_address") if isinstance(site_snapshot, dict) else {}
        province_code = self._normalize_province_code((site_address or {}).get("province"))
        city_code = self._normalize_city_code(province_code, (site_address or {}).get("city"))
        rate_field = self._resolve_rate_field(requested_start_at)

        guard_base_rate = await self._resolve_scoped_rate(
            [BillingManager.SCOPE_GUARD_DEFAULT, BillingManager.SCOPE_GUARD_DEFAULT_LEGACY],
            province_code,
            city_code,
            rate_field,
        )
        provider_base_rate = await self._resolve_scoped_rate(
            [BillingManager.SCOPE_PROVIDER_DEFAULT],
            province_code,
            city_code,
            rate_field,
        )
        guard_margin_default = await self._resolve_scoped_rate(
            [BillingManager.SCOPE_GUARD_MARGIN_DEFAULT],
            province_code,
            city_code,
            rate_field,
        )
        provider_commission_default = await self._resolve_scoped_rate(
            [BillingManager.SCOPE_PROVIDER_COMMISSION_DEFAULT],
            province_code,
            city_code,
            rate_field,
        )

        guard_quote = round(guard_base_rate + guard_margin_default, 2)
        provider_quote = round(provider_base_rate + provider_commission_default, 2)
        client_hourly_quote = round(max(guard_quote, provider_quote), 2)

        guard_company_margin = round(max(client_hourly_quote - guard_base_rate, 0.0), 2)
        provider_company_commission = round(max(client_hourly_quote - provider_base_rate, 0.0), 2)

        requested_hours = self._calculate_requested_hours(requested_start_at, requested_end_at)
        normalized_guards_required = max(int(guards_required or 1), 1)
        estimated_total_hours = round(requested_hours * normalized_guards_required, 2) if requested_hours is not None else None

        pricing_snapshot = {
            "currency": "CAD",
            "rate_basis": "hourly",
            "rate_field": rate_field,
            "location": {
                "province_code": province_code,
                "city_code": city_code,
                "province": str((site_address or {}).get("province") or "").strip(),
                "city": str((site_address or {}).get("city") or "").strip(),
            },
            "guards_required": normalized_guards_required,
            "client_hourly_quote": client_hourly_quote,
            "guard_hourly_pay": round(guard_base_rate, 2),
            "guard_company_margin": guard_company_margin,
            "provider_hourly_pay": round(provider_base_rate, 2),
            "provider_company_commission": provider_company_commission,
            "requested_hours_per_position": requested_hours,
            "estimated_total_hours": estimated_total_hours,
            "estimated_client_charge": round(client_hourly_quote * estimated_total_hours, 2) if estimated_total_hours is not None else None,
            "estimated_guard_payout": round(guard_base_rate * estimated_total_hours, 2) if estimated_total_hours is not None else None,
            "estimated_provider_payout": round(provider_base_rate * estimated_total_hours, 2) if estimated_total_hours is not None else None,
            "estimated_company_margin_with_guard": round(guard_company_margin * estimated_total_hours, 2) if estimated_total_hours is not None else None,
            "estimated_company_margin_with_provider": round(provider_company_commission * estimated_total_hours, 2) if estimated_total_hours is not None else None,
            "mock_payment_status": "pending_capture",
            "calculation_version": "mock_v1",
        }

        contract_type = self._normalize_invoice_contract_type(invoice_contract_type)
        cutoff_day = int(invoice_cutoff_day) if invoice_cutoff_day is not None else None
        if contract_type == "long_term" and (cutoff_day is None or cutoff_day < 1 or cutoff_day > 28):
            cutoff_day = 1

        invoicing_snapshot = {
            "contract_type": contract_type,
            "billing_cycle": "monthly" if contract_type == "long_term" else "per_request",
            "charge_timing": "advance_monthly" if contract_type == "long_term" else "on_the_go",
            "monthly_cutoff_day": cutoff_day if contract_type == "long_term" else None,
            "invoice_delivery_channel": "email",
            "invoice_recipient_email": str(invoice_recipient_email or "").strip() or None,
            "invoice_status": RequestInvoiceStatus.PENDING.value,
            "invoice_note": (
                "Invoices are generated one month in advance on the monthly cutoff and emailed to the client."
                if contract_type == "long_term"
                else "A one-time invoice is issued for this coverage window when the request is published."
            ),
        }

        return {
            "pricing_snapshot": pricing_snapshot,
            "invoicing_snapshot": invoicing_snapshot,
        }

    @staticmethod
    def _client_tenant_label(tenant: Any) -> str:
        profile = tenant.profile if isinstance(getattr(tenant, "profile", None), dict) else {}
        legal_entity_name = str(profile.get("legal_entity_name") or "").strip()
        primary_contact = cast(Dict[str, Any], profile.get("primary_contact") or {})
        primary_contact_name = str(primary_contact.get("name") or "").strip()
        return (
            legal_entity_name
            or primary_contact_name
            or str(getattr(tenant, "name", "") or "").strip()
            or str(getattr(tenant, "id", "") or "").strip()
        )

    @staticmethod
    def _extract_tenant_name(profile: Optional[Dict[str, Any]]) -> str:
        if not isinstance(profile, dict):
            return ""
        for key in ["legal_company_name", "trading_name", "legal_entity_name", "full_name", "company_name", "name"]:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        primary_contact = cast(Dict[str, Any], profile.get("primary_contact") or {})
        representative = cast(Dict[str, Any], profile.get("primary_representative") or {})
        for candidate in [primary_contact.get("name"), representative.get("name")]:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    async def _build_client_tenant_label_lookup(self, tenant_ids: List[str]) -> Dict[str, str]:
        normalized_ids: List[str] = []
        object_ids: List[ObjectId] = []
        label_lookup: Dict[str, str] = {}
        seen_ids = set()

        for raw_tenant_id in tenant_ids:
            tenant_id = str(raw_tenant_id or "").strip()
            if not tenant_id or tenant_id in seen_ids:
                continue
            seen_ids.add(tenant_id)
            normalized_ids.append(tenant_id)
            try:
                object_ids.append(ObjectId(tenant_id))
            except Exception:
                label_lookup[tenant_id] = tenant_id

        if object_ids:
            collection = self._engine.get_collection(db_tenant_model)
            docs = await collection.find({"_id": {"$in": object_ids}}).to_list(length=None)
            for doc in docs:
                tenant_id = str(doc.get("_id") or "")
                profile = cast(Dict[str, Any], doc.get("profile") or {})
                label_lookup[tenant_id] = self._client_tenant_label(SimpleNamespace(
                    id=tenant_id,
                    profile=profile,
                    name=str(doc.get("name") or ""),
                ))

        for tenant_id in normalized_ids:
            label_lookup.setdefault(tenant_id, tenant_id)

        return label_lookup

    async def _build_tenant_label_lookup(self, tenant_ids: List[str]) -> Dict[str, str]:
        normalized_ids: List[str] = []
        object_ids: List[ObjectId] = []
        label_lookup: Dict[str, str] = {}
        seen_ids = set()

        for raw_tenant_id in tenant_ids:
            tenant_id = str(raw_tenant_id or "").strip()
            if not tenant_id or tenant_id in seen_ids:
                continue
            seen_ids.add(tenant_id)
            normalized_ids.append(tenant_id)
            try:
                object_ids.append(ObjectId(tenant_id))
            except Exception:
                label_lookup[tenant_id] = tenant_id

        if object_ids:
            collection = self._engine.get_collection(db_tenant_model)
            docs = await collection.find({"_id": {"$in": object_ids}}).to_list(length=None)
            for doc in docs:
                tenant_id = str(doc.get("_id") or "")
                profile = cast(Dict[str, Any], doc.get("profile") or {})
                label_lookup[tenant_id] = (
                    self._extract_tenant_name(profile)
                    or str(doc.get("name") or "").strip()
                    or tenant_id
                )

        for tenant_id in normalized_ids:
            label_lookup.setdefault(tenant_id, tenant_id)

        return label_lookup

    async def _serialize_requests_with_client_tenant_labels(self, docs: List[ClientRequestRecord | Dict[str, Any]]) -> List[Dict[str, Any]]:
        serialized = [self._serialize(doc) for doc in docs]
        label_lookup = await self._build_client_tenant_label_lookup([
            str(item.get("client_tenant_id") or "")
            for item in serialized
        ])

        for item in serialized:
            tenant_id = str(item.get("client_tenant_id") or "").strip()
            item["client_tenant_label"] = label_lookup.get(tenant_id, tenant_id)

        return serialized

    async def list_request_client_tenants(self, current_user, keyword: str = "", rows: int = 100) -> Dict[str, Any]:
        if not self._is_platform_role(self._role_value(current_user)):
            raise HTTPException(status_code=403, detail="Access forbidden")

        collection = self._engine.get_collection(db_tenant_model)
        docs = await collection.find({
            "tenant_type": TenantType.CLIENT.value,
            "status": TenantStatus.ACTIVE.value,
        }).to_list(length=None)

        normalized_keyword = self._normalize_text(keyword)
        items: List[Dict[str, Any]] = []
        for doc in docs:
            tenant_id = str(doc.get("_id") or "")
            profile = cast(Dict[str, Any], doc.get("profile") or {})
            label = self._client_tenant_label(SimpleNamespace(
                id=tenant_id,
                profile=profile,
                name=str(doc.get("name") or ""),
            ))
            if normalized_keyword and normalized_keyword not in self._normalize_text(label):
                continue
            sites = profile.get("sites") if isinstance(profile.get("sites"), list) else []
            items.append({
                "id": tenant_id,
                "label": label,
                "site_count": len(sites),
                "primary_contact_name": str(cast(Dict[str, Any], profile.get("primary_contact") or {}).get("name") or "").strip(),
                "status": str(doc.get("status") or ""),
            })

        items.sort(key=lambda item: self._normalize_text(item.get("label")))
        limited_rows = max(int(rows or 100), 1)
        return {
            "items": items[:limited_rows],
            "total_items": len(items),
        }

    async def get_request_client_tenant_snapshot(self, tenant_id: str, current_user) -> Dict[str, Any]:
        if not self._is_platform_write_role(self._role_value(current_user)):
            raise HTTPException(status_code=403, detail="Access forbidden")

        tenant = await self._get_active_client_tenant_by_id(tenant_id)
        return {
            "id": str(tenant.id),
            "tenant_type": tenant.tenant_type,
            "status": tenant.status,
            "label": self._client_tenant_label(tenant),
            "profile": tenant.profile if isinstance(tenant.profile, dict) else {},
        }

    async def _get_session_tenant(self, current_user):
        tenant_id = str(getattr(current_user, "tenant_uuid", "") or "")
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Invalid tenant association")

        tenant = await self._get_tenant(tenant_id)
        if not tenant:
            raise HTTPException(status_code=400, detail="Invalid tenant association")

        role_value = self._role_value(current_user)
        if not self._is_platform_role(role_value) and tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Tenant must be active")
        return tenant

    async def _resolve_request_docs_for_role(self, current_user) -> List[Dict[str, Any]]:
        role_value = self._role_value(current_user)
        request_collection = self._engine.get_collection(ClientRequestRecord)

        if self._is_platform_role(role_value):
            return await request_collection.find({"deleted_at": None}).to_list(length=None)

        session_tenant = await self._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)

        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            return await request_collection.find({"client_tenant_id": tenant_id, "deleted_at": None}).to_list(length=None)

        if role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
            assignment_docs = await assignment_collection.find({"assignee_tenant_id": tenant_id}).to_list(length=None)
            relevant_assignments = self._best_assignment_doc_for_request(
                assignment_docs,
                statuses=REQUEST_TAB_ASSIGNMENT_STATUSES,
            )
            request_ids = [request_id for request_id in relevant_assignments.keys() if request_id]
            if not request_ids:
                return []

            object_ids = []
            for request_id in request_ids:
                try:
                    object_ids.append(ObjectId(str(request_id)))
                except Exception:
                    continue
            if not object_ids:
                return []
            request_docs = await request_collection.find({"_id": {"$in": object_ids}, "deleted_at": None}).to_list(length=None)
            for request_doc in request_docs:
                serialized_assignment = relevant_assignments.get(str(request_doc.get("_id") or ""))
                request_doc["viewer_assignment"] = self._serialize_assignment(serialized_assignment) if serialized_assignment else None
            return request_docs

        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _request_ids_with_active_schedules(self, request_ids: List[str]) -> set[str]:
        normalized_ids = [str(request_id).strip() for request_id in request_ids if str(request_id or "").strip()]
        if not normalized_ids:
            return set()
        schedule_collection = self._engine.get_collection(RequestScheduleTemplateRecord)
        schedule_docs = await schedule_collection.find({
            "request_id": {"$in": normalized_ids},
            "active": True,
        }).to_list(length=None)
        return {
            str(schedule_doc.get("request_id") or "").strip()
            for schedule_doc in schedule_docs
            if str(schedule_doc.get("request_id") or "").strip()
        }

    async def _request_has_active_schedule(self, request_id: str) -> bool:
        return request_id in await self._request_ids_with_active_schedules([request_id])

    async def _get_active_schedule_template(self, request_id: str) -> Optional[RequestScheduleTemplateRecord]:
        return await self._engine.find_one(
            RequestScheduleTemplateRecord,
            (RequestScheduleTemplateRecord.request_id == str(request_id))
            & (RequestScheduleTemplateRecord.active == True),
        )

    async def _can_view_request(self, record: ClientRequestRecord, current_user) -> bool:
        role_value = self._role_value(current_user)
        if self._is_platform_role(role_value):
            return True

        session_tenant = await self._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)

        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            return record.client_tenant_id == tenant_id

        if role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
            count = await assignment_collection.count_documents({
                "request_id": str(record.id),
                "assignee_tenant_id": tenant_id,
            })
            return count > 0
        return False

    async def _assert_request_write_access(self, record: ClientRequestRecord, current_user) -> None:
        role_value = self._role_value(current_user)
        if self._is_platform_write_role(role_value):
            return

        session_tenant = await self._get_session_tenant(current_user)
        if not (
            role_value == "client_admin"
            and session_tenant.tenant_type == TenantType.CLIENT
            and record.client_tenant_id == str(session_tenant.id)
        ):
            raise HTTPException(status_code=403, detail="Only platform admins or owning client admins can modify this request")

    async def _write_activity(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        current_user,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> None:
        try:
            await ActivityManager.get_instance().log_event(
                module="requests",
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_id=str(getattr(current_user, "id", "") or ""),
                actor_username=str(getattr(current_user, "username", "") or ""),
                actor_role=self._role_value(current_user),
                previous_status=previous_status,
                new_status=new_status,
                reason=reason,
                metadata=metadata or {},
                severity=severity,
            )
        except Exception:
            return

    def _resolve_saved_site_snapshot(self, client_profile: Dict[str, Any], site_index: int) -> Dict[str, Any]:
        raw_sites = client_profile.get("sites") if isinstance(client_profile.get("sites"), list) else []
        if not raw_sites:
            raise HTTPException(status_code=400, detail="Add at least one client site before creating a request")
        if site_index < 0 or site_index >= len(raw_sites):
            raise HTTPException(status_code=400, detail="Selected site is invalid")

        site: Dict[str, Any] = raw_sites[site_index] if isinstance(raw_sites[site_index], dict) else {}
        raw_site_address = site.get("site_address")
        site_address = cast(Dict[str, Any], raw_site_address) if isinstance(raw_site_address, dict) else {}
        latitude = self._as_float(site_address.get("latitude"))
        longitude = self._as_float(site_address.get("longitude"))
        if latitude is None or longitude is None:
            raise HTTPException(
                status_code=400,
                detail="Selected client site must have latitude and longitude before it can be used for requests",
            )
        if not (-90 <= latitude <= 90):
            raise HTTPException(status_code=400, detail="Selected client site latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail="Selected client site longitude must be between -180 and 180")
        return {
            "site_index": site_index,
            "site_source": "saved",
            "site_id": str(site.get("site_id") or ""),
            "site_name": str(site.get("site_name") or site.get("siteName") or "").strip(),
            "site_manager_contact": str(site.get("site_manager_contact") or site.get("siteManagerContact") or "").strip(),
            "manager_email": str(site.get("manager_email") or site.get("managerEmail") or "").strip(),
            "number_of_guards_required": site.get("number_of_guards_required") if site.get("number_of_guards_required") is not None else site.get("numberOfGuardsRequired"),
            "site_type": site.get("site_type") or site.get("siteType"),
            "site_address": {
                "street": str(site_address.get("street") or "").strip(),
                "city": str(site_address.get("city") or "").strip(),
                "country": str(site_address.get("country") or "CA").strip(),
                "province": str(site_address.get("province") or "").strip(),
                "postal_code": str(site_address.get("postal_code") or site_address.get("postalCode") or "").strip(),
                "latitude": latitude,
                "longitude": longitude,
            },
        }

    def _resolve_site_input_snapshot(self, site_input: RequestSiteInput) -> Dict[str, Any]:
        site_address_model = site_input.site_address
        site_address = site_address_model.model_dump() if hasattr(site_address_model, "model_dump") else dict(site_address_model)

        site_name = str(site_input.site_name or "").strip()
        city = str(site_address.get("city") or "").strip()
        province = str(site_address.get("province") or "").strip()
        country = str(site_address.get("country") or "CA").strip() or "CA"
        street = str(site_address.get("street") or "").strip()
        postal_code = str(site_address.get("postal_code") or site_address.get("postalCode") or "").strip()
        latitude = self._as_float(site_address.get("latitude"))
        longitude = self._as_float(site_address.get("longitude"))

        if not site_name:
            raise HTTPException(status_code=400, detail="Site name is required")
        if not city:
            raise HTTPException(status_code=400, detail="Site city is required")
        if not province:
            raise HTTPException(status_code=400, detail="Site province/state is required")
        if latitude is None or longitude is None:
            raise HTTPException(status_code=400, detail="Site latitude and longitude are required")
        if not (-90 <= latitude <= 90):
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")

        return {
            "site_index": -1,
            "site_source": "request",
            "site_id": "",
            "site_name": site_name,
            "site_manager_contact": str(site_input.site_manager_contact or "").strip(),
            "manager_email": str(site_input.manager_email or "").strip(),
            "number_of_guards_required": None,
            "site_type": str(site_input.site_type or "").strip() or None,
            "google_maps_url": str(site_input.google_maps_url or "").strip(),
            "site_address": {
                "street": street,
                "city": city,
                "country": country,
                "province": province,
                "postal_code": postal_code,
                "latitude": latitude,
                "longitude": longitude,
            },
        }

    def _validated_site_snapshot_coordinates(
        self,
        site_snapshot: Dict[str, Any],
        *,
        detail_prefix: str = "Request site",
    ) -> tuple[float, float]:
        site_address = cast(Dict[str, Any], site_snapshot.get("site_address") or {})
        latitude = self._as_float(site_address.get("latitude"))
        longitude = self._as_float(site_address.get("longitude"))
        if latitude is None or longitude is None:
            raise HTTPException(status_code=400, detail=f"{detail_prefix} latitude and longitude are required")
        if not (-90 <= latitude <= 90):
            raise HTTPException(status_code=400, detail=f"{detail_prefix} latitude must be between -90 and 90")
        if not (-180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail=f"{detail_prefix} longitude must be between -180 and 180")
        return latitude, longitude

    def _resolve_site_snapshot(self, payload: ClientRequestCreatePayload, client_profile: Dict[str, Any]) -> Dict[str, Any]:
        if payload.site:
            return self._resolve_site_input_snapshot(payload.site)
        if payload.site_index is None:
            raise HTTPException(status_code=400, detail="Provide request site details or select a saved site")
        return self._resolve_saved_site_snapshot(client_profile, payload.site_index)

    async def _preview_matches_for_target(
        self,
        target_type: TargetType,
        site_snapshot: Dict[str, Any],
        max_results: int,
        requested_guard_type: Optional[str] = None,
        requested_start_at: Optional[datetime] = None,
        requested_end_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        request_address = cast(Dict[str, Any], site_snapshot.get("site_address") or {})
        latitude, longitude = self._validated_site_snapshot_coordinates(site_snapshot)
        match_payload = RequestMatchingPreviewPayload(
            target_type=target_type,
            site_address=MatchAddress(
                country=str(request_address.get("country") or "CA"),
                province=str(request_address.get("province") or ""),
                city=str(request_address.get("city") or ""),
                latitude=latitude,
                longitude=longitude,
            ),
            requested_guard_type=(requested_guard_type or "").strip() or None,
            requested_start_at=requested_start_at,
            requested_end_at=requested_end_at,
            max_results=max_results,
            fallback_to_province_when_missing_geo=False,
        )
        preview = await RequestMatchingManager.get_instance().preview_matches(match_payload)
        return {
            "summary": preview.summary,
            "results": [candidate.model_dump() for candidate in preview.results],
        }

    def _summarize_candidates(self, candidates: List[Dict[str, Any]], fulfillment_mode: RequestFulfillmentMode) -> Dict[str, Any]:
        summary = {
            "target_type": "hybrid" if fulfillment_mode == RequestFulfillmentMode.HYBRID else (
                RequestTargetType.SERVICE_PROVIDER.value if fulfillment_mode == RequestFulfillmentMode.SERVICE_PROVIDER_ONLY else RequestTargetType.GUARD.value
            ),
            "total_candidates": len(candidates),
            "eligible_count": len([candidate for candidate in candidates if bool(candidate.get("eligible"))]),
            "ownership_excluded_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "ownership_excluded"]),
            "outside_availability_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "outside_availability"]),
            "outside_radius_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "outside_radius"]),
            "province_mismatch_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "province_mismatch"]),
            "city_mismatch_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "city_mismatch"]),
            "guard_type_mismatch_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "guard_type_mismatch"]),
            "insufficient_capacity_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "insufficient_capacity"]),
            "missing_geo_count": len([candidate for candidate in candidates if candidate.get("reason_code") == "missing_geo"]),
            "returned_count": len(candidates),
        }
        if fulfillment_mode == RequestFulfillmentMode.HYBRID:
            for target_type in (RequestTargetType.GUARD.value, RequestTargetType.SERVICE_PROVIDER.value):
                subset = [candidate for candidate in candidates if str(candidate.get("target_type") or "") == target_type]
                summary[target_type] = {
                    "total_count": len(subset),
                    "eligible_count": len([candidate for candidate in subset if bool(candidate.get("eligible"))]),
                    "ineligible_count": len([candidate for candidate in subset if not bool(candidate.get("eligible"))]),
                }
        return summary

    async def _preview_matches_for_request(
        self,
        fulfillment_mode: RequestFulfillmentMode,
        site_snapshot: Dict[str, Any],
        max_results: int,
        requested_guard_type: Optional[str] = None,
        requested_start_at: Optional[datetime] = None,
        requested_end_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if fulfillment_mode == RequestFulfillmentMode.HYBRID:
            guard_preview = await self._preview_matches_for_target(
                cast(TargetType, "guard"),
                site_snapshot,
                max_results,
                requested_guard_type,
                requested_start_at,
                requested_end_at,
            )
            provider_preview = await self._preview_matches_for_target(
                cast(TargetType, "service_provider"),
                site_snapshot,
                max_results,
                requested_guard_type,
                requested_start_at,
                requested_end_at,
            )
            results = list(guard_preview["results"]) + list(provider_preview["results"])
            results.sort(
                key=lambda item: (
                    0 if bool(item.get("eligible")) else 1,
                    item.get("distance_km") if item.get("distance_km") is not None else 999999,
                    str(item.get("candidate_name") or "").lower(),
                )
            )
            return {
                "summary": self._summarize_candidates(results, fulfillment_mode),
                "results": results,
            }

        target_type = cast(TargetType, "service_provider" if fulfillment_mode == RequestFulfillmentMode.SERVICE_PROVIDER_ONLY else "guard")
        preview = await self._preview_matches_for_target(
            target_type,
            site_snapshot,
            max_results,
            requested_guard_type,
            requested_start_at,
            requested_end_at,
        )
        preview["summary"] = self._summarize_candidates(preview["results"], fulfillment_mode)
        return preview

    @staticmethod
    def _validate_request_expiry(
        request_expires_at: Optional[datetime],
        requested_start_at: Optional[datetime],
        *,
        require_value: bool = False,
    ) -> None:
        if require_value and request_expires_at is None:
            raise HTTPException(status_code=400, detail="Request expiry is required before publishing")

        if request_expires_at is None:
            return

        now = datetime.utcnow()
        if request_expires_at <= now:
            raise HTTPException(status_code=400, detail="Request expiry must be in the future")
        if requested_start_at and request_expires_at > requested_start_at:
            raise HTTPException(status_code=400, detail="Request expiry cannot be after the requested start time")

    @staticmethod
    def _compute_wave_expires_at(record: ClientRequestRecord, now: Optional[datetime] = None) -> datetime:
        now = now or datetime.utcnow()
        candidates = []
        if record.request_expires_at:
            candidates.append(record.request_expires_at)
        if record.requested_start_at:
            candidates.append(record.requested_start_at - timedelta(hours=2))
        deadline = min(candidates) if candidates else now + timedelta(hours=2)
        minimum = now + timedelta(minutes=15)
        if deadline < minimum:
            if record.request_expires_at and record.request_expires_at < minimum:
                return record.request_expires_at
            return minimum
        return deadline

    @staticmethod
    def _compute_reconfirmation_due_at(record: ClientRequestRecord, now: Optional[datetime] = None) -> datetime:
        now = now or datetime.utcnow()
        candidates = []
        if record.request_expires_at:
            candidates.append(record.request_expires_at)
        if record.requested_start_at:
            candidates.append(record.requested_start_at - timedelta(hours=1))
        deadline = min(candidates) if candidates else now + timedelta(hours=1)
        minimum = now + timedelta(minutes=10)
        if deadline < minimum:
            if record.request_expires_at and record.request_expires_at < minimum:
                return record.request_expires_at
            return minimum
        return deadline

    async def _refresh_request_matching(self, record: ClientRequestRecord, max_results: int) -> None:
        preview = await self._preview_matches_for_request(
            self._resolve_fulfillment_mode_from_record(record),
            record.site_snapshot or {},
            max_results,
            record.requested_guard_type,
            record.requested_start_at,
            record.requested_end_at,
        )
        record.target_type = self._default_target_type_for_mode(self._resolve_fulfillment_mode_from_record(record))
        record.match_summary = preview["summary"]
        record.matched_candidates = preview["results"]

    async def _get_assignments_for_request(self, request_id: str) -> List[RequestAssignmentRecord]:
        return await self._engine.find(RequestAssignmentRecord, RequestAssignmentRecord.request_id == str(request_id))

    async def _get_waves_for_request(self, request_id: str) -> List[RequestBroadcastWaveRecord]:
        return await self._engine.find(RequestBroadcastWaveRecord, RequestBroadcastWaveRecord.request_id == str(request_id))

    async def _has_active_assignment_for_candidate(
        self,
        request_id: str,
        assignee_tenant_id: str,
        *,
        shift_slot_id: Optional[str] = None,
    ) -> bool:
        assignments = await self._get_assignments_for_request(request_id)
        for assignment in assignments:
            if assignment.assignee_tenant_id != str(assignee_tenant_id):
                continue
            if assignment.assignment_status not in ACTIONABLE_ASSIGNMENT_STATUSES:
                continue
            if self._assignment_scope_value(assignment) == RequestAssignmentScope.REQUEST.value:
                return True
            if shift_slot_id and str(getattr(assignment, "shift_slot_id", "") or "") == str(shift_slot_id):
                return True
        return False

    async def _evaluate_broadcast_snapshot(self, record: ClientRequestRecord) -> Dict[str, Any]:
        site_address = cast(Dict[str, Any], (record.site_snapshot or {}).get("site_address") or {})
        country = RequestMatchingManager._normalize_country_code(site_address.get("country") or "CA")
        province = RequestMatchingManager._normalize_region_code(site_address.get("province"), country)
        city = str(site_address.get("city") or "").strip()
        latitude = site_address.get("latitude")
        longitude = site_address.get("longitude")
        request_missing_geo = latitude is None or longitude is None

        review_codes: List[str] = []
        review_findings: List[Dict[str, Any]] = []
        evaluated_candidates: List[Dict[str, Any]] = []
        policy_cache: Dict[str, Dict[str, Any]] = {}

        if request_missing_geo:
            review_codes.append(BroadcastReviewReasonCode.MISSING_GEO.value)
            review_findings.append({"scope": "request", "reason_code": BroadcastReviewReasonCode.MISSING_GEO.value})

        if not province or not city:
            review_codes.append(BroadcastReviewReasonCode.AMBIGUOUS_LOCATION.value)
            review_findings.append({"scope": "request", "reason_code": BroadcastReviewReasonCode.AMBIGUOUS_LOCATION.value})

        for raw_candidate in record.matched_candidates or []:
            candidate = dict(raw_candidate)
            candidate["broadcast_eligible"] = False
            candidate["broadcast_outcome"] = "ineligible"
            candidate["broadcast_reason_code"] = "ineligible"

            if not bool(candidate.get("eligible")):
                evaluated_candidates.append(candidate)
                continue

            target_type = str(candidate.get("target_type") or RequestTargetType.GUARD.value)
            scope = (
                BillingManager.SCOPE_PROVIDER_TRAVEL_DEFAULT
                if target_type == RequestTargetType.SERVICE_PROVIDER.value
                else BillingManager.SCOPE_GUARD_TRAVEL_DEFAULT
            )
            cache_key = f"{scope}:{province}:{city.upper()}"
            if cache_key not in policy_cache:
                policy_cache[cache_key] = await BillingManager.get_instance().resolve_travel_policy(scope, province, city)
            policy = policy_cache[cache_key]

            if policy.get("source") == "system_default":
                candidate["broadcast_eligible"] = True
                candidate["broadcast_outcome"] = "pending_review"
                candidate["broadcast_reason_code"] = BroadcastReviewReasonCode.TRAVEL_POLICY_MISSING.value
                review_codes.append(BroadcastReviewReasonCode.TRAVEL_POLICY_MISSING.value)
                review_findings.append({
                    "candidate_id": str(candidate.get("candidate_id") or ""),
                    "reason_code": BroadcastReviewReasonCode.TRAVEL_POLICY_MISSING.value,
                })
                evaluated_candidates.append(candidate)
                continue

            if request_missing_geo or str(candidate.get("distance_source") or "") == "province_fallback":
                candidate["broadcast_eligible"] = True
                candidate["broadcast_outcome"] = "pending_review"
                candidate["broadcast_reason_code"] = BroadcastReviewReasonCode.DISTANCE_UNVERIFIED.value
                review_codes.append(BroadcastReviewReasonCode.DISTANCE_UNVERIFIED.value)
                review_findings.append({
                    "candidate_id": str(candidate.get("candidate_id") or ""),
                    "reason_code": BroadcastReviewReasonCode.DISTANCE_UNVERIFIED.value,
                })
                evaluated_candidates.append(candidate)
                continue

            policy_result = BillingManager.evaluate_broadcast_distance(candidate.get("distance_km"), policy)
            candidate["broadcast_outcome"] = policy_result["outcome"]
            candidate["broadcast_reason_code"] = policy_result["reason_code"]
            candidate["broadcast_eligible"] = policy_result["outcome"] != "outside_policy"

            if policy_result["outcome"] == "pending_review":
                review_codes.append(policy_result["reason_code"])
                review_findings.append({
                    "candidate_id": str(candidate.get("candidate_id") or ""),
                    "reason_code": policy_result["reason_code"],
                })

            evaluated_candidates.append(candidate)

        deduped_codes = []
        for code in review_codes:
            if code and code not in deduped_codes:
                deduped_codes.append(code)

        return {
            "requires_review": len(deduped_codes) > 0,
            "review_reason_codes": deduped_codes,
            "review_findings": review_findings,
            "candidate_snapshots": evaluated_candidates,
        }

    async def _set_wave_status(
        self,
        wave: RequestBroadcastWaveRecord,
        next_status: RequestWaveStatus,
        *,
        current_user=None,
        note: Optional[str] = None,
    ) -> RequestBroadcastWaveRecord:
        now = datetime.utcnow()
        wave.wave_status = next_status
        wave.updated_at = now
        if note is not None:
            wave.review_note = note.strip() or wave.review_note
        if current_user is not None:
            wave.reviewed_by_user_id = str(getattr(current_user, "id", "") or "")
            wave.reviewed_by_username = str(getattr(current_user, "username", "") or "")
            wave.reviewed_at = now
        if next_status == RequestWaveStatus.ACTIVE:
            wave.activated_at = now
        elif next_status == RequestWaveStatus.RETURNED:
            wave.returned_at = now
        elif next_status == RequestWaveStatus.FILLED:
            wave.filled_at = now
        elif next_status == RequestWaveStatus.EXPIRED:
            wave.expired_at = now
        elif next_status == RequestWaveStatus.SUPERSEDED:
            wave.superseded_at = now
        elif next_status == RequestWaveStatus.CANCELLED:
            wave.cancelled_at = now
        return await self._engine.save(wave)

    async def _close_open_offers_for_request(
        self,
        record: ClientRequestRecord,
        *,
        to_status: RequestAssignmentStatus,
        lock_reason: AssignmentLockReason,
        wave_id: Optional[str] = None,
    ) -> int:
        now = datetime.utcnow()
        updated_count = 0
        assignments = await self._get_assignments_for_request(str(record.id))
        for assignment in assignments:
            if assignment.assignment_status not in OPEN_OFFER_STATUSES:
                continue
            if wave_id and assignment.broadcast_wave_id != wave_id:
                continue
            assignment.assignment_status = to_status
            assignment.lock_reason = lock_reason
            assignment.updated_at = now
            if to_status == RequestAssignmentStatus.EXPIRED:
                assignment.expired_at = now
            elif to_status == RequestAssignmentStatus.CLOSED_FILLED:
                assignment.closed_filled_at = now
            elif to_status == RequestAssignmentStatus.SUPERSEDED:
                assignment.superseded_at = now
            elif to_status == RequestAssignmentStatus.CANCELLED:
                assignment.cancelled_at = now
            await self._engine.save(assignment)
            updated_count += 1
        return updated_count

    async def _supersede_previous_waves(self, record: ClientRequestRecord) -> None:
        waves = await self._get_waves_for_request(str(record.id))
        for wave in waves:
            if wave.wave_status not in {RequestWaveStatus.ACTIVE, RequestWaveStatus.PENDING_REVIEW}:
                continue
            if wave.wave_status == RequestWaveStatus.ACTIVE:
                await self._close_open_offers_for_request(
                    record,
                    to_status=RequestAssignmentStatus.SUPERSEDED,
                    lock_reason=AssignmentLockReason.SUPERSEDED,
                    wave_id=str(wave.id),
                )
            await self._set_wave_status(wave, RequestWaveStatus.SUPERSEDED)
        record.active_wave_id = None

    async def _sync_request_assignments_for_manual_close(self, record: ClientRequestRecord) -> None:
        now = datetime.utcnow()
        assignments = await self._get_assignments_for_request(str(record.id))
        for assignment in assignments:
            if self._assignment_scope_value(assignment) != RequestAssignmentScope.REQUEST.value:
                continue

            current_status = getattr(assignment, "assignment_status", None)
            if current_status == RequestAssignmentStatus.IN_PROGRESS:
                assignment.assignment_status = RequestAssignmentStatus.COMPLETED
                assignment.completed_at = getattr(assignment, "completed_at", None) or now
                assignment.started_at = getattr(assignment, "started_at", None) or now
                assignment.updated_at = now
                await self._engine.save(assignment)
                continue

            if current_status in {
                RequestAssignmentStatus.ACCEPTED,
                RequestAssignmentStatus.RECONFIRMATION_REQUIRED,
            }:
                if getattr(assignment, "started_at", None) is not None:
                    assignment.assignment_status = RequestAssignmentStatus.COMPLETED
                    assignment.completed_at = getattr(assignment, "completed_at", None) or now
                else:
                    assignment.assignment_status = RequestAssignmentStatus.CANCELLED
                    assignment.cancelled_at = getattr(assignment, "cancelled_at", None) or now
                assignment.updated_at = now
                await self._engine.save(assignment)

    async def _mark_assignments_reconfirmation_required(self, record: ClientRequestRecord) -> None:
        now = datetime.utcnow()
        due_at = self._compute_reconfirmation_due_at(record, now=now)
        assignments = await self._get_assignments_for_request(str(record.id))
        for assignment in assignments:
            if assignment.assignment_status != RequestAssignmentStatus.ACCEPTED:
                continue
            if assignment.started_at is not None:
                continue
            assignment.assignment_status = RequestAssignmentStatus.RECONFIRMATION_REQUIRED
            assignment.reconfirmation_requested_at = now
            assignment.reconfirmation_due_at = due_at
            assignment.updated_at = now
            await self._engine.save(assignment)
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=assignment.assignee_tenant_id,
                title="Request update requires reconfirmation",
                message=f"{record.title} was updated. Please reconfirm this request assignment.",
                category="warning",
                source_module="requests",
                action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
                action_label="Review request",
                metadata={
                    "request_id": str(record.id),
                    "assignment_id": str(assignment.id),
                    "assignment_status": RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value,
                    "request_revision": record.request_revision,
                },
            )

    async def _sync_request_runtime_state(self, record: ClientRequestRecord) -> ClientRequestRecord:
        now = datetime.utcnow()

        if record.request_expires_at and record.request_expires_at <= now and record.request_status not in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            if record.staffing_status != RequestStaffingStatus.EXPIRED:
                record.staffing_status = RequestStaffingStatus.EXPIRED
                record.lock_reason = RequestLockReason.REQUEST_EXPIRED
                record.expired_at = now
                record.updated_at = now
                await self._engine.save(record)
                await self._close_open_offers_for_request(
                    record,
                    to_status=RequestAssignmentStatus.EXPIRED,
                    lock_reason=AssignmentLockReason.REQUEST_EXPIRED,
                )
                if record.active_wave_id:
                    wave = await self._get_wave_or_404(record.active_wave_id)
                    await self._set_wave_status(wave, RequestWaveStatus.EXPIRED)
                    record.active_wave_id = None
                    await self._engine.save(record)

        assignments = await self._get_assignments_for_request(str(record.id))
        accepted_slots = 0
        for assignment in assignments:
            if self._assignment_scope_value(assignment) != RequestAssignmentScope.REQUEST.value:
                continue
            if assignment.assignment_status in COMMITTED_SLOT_STATUSES:
                accepted_slots += self._assignment_slots(assignment)

        previous_open_slots = record.open_slots
        record.accepted_slots = accepted_slots
        record.open_slots = max(int(record.guards_required or 0) - accepted_slots, 0)
        should_auto_close_request = self._should_auto_close_request(
            record,
            assignments,
            accepted_slots=accepted_slots,
            now=now,
        )

        if record.request_status == RequestStatus.CANCELLED:
            record.lock_reason = RequestLockReason.REQUEST_CANCELLED
        elif record.request_status == RequestStatus.CLOSED:
            record.lock_reason = RequestLockReason.REQUEST_CLOSED
        elif record.staffing_status != RequestStaffingStatus.EXPIRED:
            if record.staffing_status == RequestStaffingStatus.PENDING_REVIEW and record.lock_reason == RequestLockReason.REVIEW_PENDING:
                pass
            elif (
                record.staffing_status == RequestStaffingStatus.REVIEW_RETURNED
                and record.active_wave_id is None
                and accepted_slots == 0
                and record.open_slots > 0
            ):
                pass
            elif record.open_slots == 0 and record.guards_required > 0 and accepted_slots > 0:
                record.staffing_status = RequestStaffingStatus.FILLED
                record.lock_reason = RequestLockReason.FILLED
            elif accepted_slots > 0:
                record.staffing_status = RequestStaffingStatus.PARTIALLY_FILLED
                if record.lock_reason == RequestLockReason.FILLED:
                    record.lock_reason = None
            else:
                record.staffing_status = RequestStaffingStatus.OPEN
                if record.lock_reason == RequestLockReason.FILLED:
                    record.lock_reason = None

        if should_auto_close_request and record.request_status not in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            record.request_status = RequestStatus.CLOSED
            record.closed_at = record.closed_at or now
            record.lock_reason = RequestLockReason.REQUEST_CLOSED

        record.updated_at = now
        await self._engine.save(record)

        if previous_open_slots > 0 and record.open_slots == 0 and record.staffing_status == RequestStaffingStatus.FILLED:
            await self._close_open_offers_for_request(
                record,
                to_status=RequestAssignmentStatus.CLOSED_FILLED,
                lock_reason=AssignmentLockReason.FILLED,
            )
            if record.active_wave_id:
                try:
                    wave = await self._get_wave_or_404(record.active_wave_id)
                except HTTPException:
                    wave = None
                if wave and wave.wave_status == RequestWaveStatus.ACTIVE:
                    wave.accepted_slots_at_close = record.accepted_slots
                    await self._set_wave_status(wave, RequestWaveStatus.FILLED)
                    record.active_wave_id = None
                    await self._engine.save(record)

        return record

    async def _activate_wave(self, wave: RequestBroadcastWaveRecord, record: ClientRequestRecord, current_user) -> int:
        now = datetime.utcnow()
        created_count = 0
        shift_replacement = self._wave_shift_replacement_context(wave)
        replacement_slot_id = str((shift_replacement or {}).get("replacement_slot_id") or "").strip()
        replacement_shift_id = str((shift_replacement or {}).get("shift_instance_id") or "").strip()
        for candidate in wave.candidate_snapshots or []:
            if not bool(candidate.get("eligible")):
                continue
            if not bool(candidate.get("broadcast_eligible")):
                continue

            assignee_tenant_id = str(candidate.get("candidate_id") or "").strip()
            if not assignee_tenant_id:
                continue

            if await self._has_active_assignment_for_candidate(
                str(record.id),
                assignee_tenant_id,
                shift_slot_id=replacement_slot_id or None,
            ):
                continue

            assignee_target_type = RequestTargetType(
                str(candidate.get("target_type") or RequestTargetType.GUARD.value)
            )
            assignment = RequestAssignmentRecord(
                id=ObjectId(),
                request_id=str(record.id),
                client_tenant_id=record.client_tenant_id,
                assignee_tenant_id=assignee_tenant_id,
                assignee_tenant_type=assignee_target_type,
                assignment_status=RequestAssignmentStatus.OFFERED,
                assignment_origin=RequestAssignmentOrigin.BROADCAST,
                assignment_scope=RequestAssignmentScope.SHIFT_REPLACEMENT if shift_replacement else RequestAssignmentScope.REQUEST,
                broadcast_wave_id=str(wave.id),
                shift_instance_id=replacement_shift_id or None,
                shift_slot_id=replacement_slot_id or None,
                request_revision_at_offer=record.request_revision,
                response_due_at=wave.wave_expires_at,
                candidate_snapshot=candidate,
                assigned_by_user_id=str(getattr(current_user, "id", "") or ""),
                assigned_by_username=str(getattr(current_user, "username", "") or ""),
                offered_at=now,
                created_at=now,
                updated_at=now,
            )
            saved = await self._engine.save(assignment)
            created_count += 1

            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=assignee_tenant_id,
                title="Shift replacement offer" if shift_replacement else "New request offer",
                message=(
                    f"{record.title}: a shift replacement offer is available for review."
                    if shift_replacement
                    else f"{record.title} is available for review."
                ),
                category="info",
                source_module="requests",
                action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
                action_label="Review offer",
                metadata={
                    "request_id": str(record.id),
                    "assignment_id": str(saved.id),
                    "broadcast_wave_id": str(wave.id),
                    "request_revision": record.request_revision,
                    "wave_number": wave.wave_number,
                    "assignment_origin": RequestAssignmentOrigin.BROADCAST.value,
                    "assignment_scope": RequestAssignmentScope.SHIFT_REPLACEMENT.value if shift_replacement else RequestAssignmentScope.REQUEST.value,
                    "shift_slot_id": replacement_slot_id or None,
                },
            )

        wave.offer_count = created_count
        wave.updated_at = now
        await self._engine.save(wave)
        return created_count

    async def create_shift_replacement_wave(
        self,
        record: ClientRequestRecord,
        *,
        shift_instance_id: str,
        original_slot_id: str,
        replacement_slot_id: str,
        original_coverage_source_type: Optional[str] = None,
        original_coverage_tenant_id: Optional[str] = None,
        current_user,
        max_match_results: int,
    ) -> Optional[RequestBroadcastWaveRecord]:
        evaluation = await self._evaluate_broadcast_snapshot(record)
        now = datetime.utcnow()
        normalized_original_source = str(original_coverage_source_type or "").strip().lower()
        platform_review_required = normalized_original_source == ShiftCoverageSourceType.DIRECT_GUARD.value
        wave_status = (
            RequestWaveStatus.PENDING_REVIEW
            if evaluation["requires_review"] or platform_review_required
            else RequestWaveStatus.ACTIVE
        )
        request_snapshot = self._request_snapshot(record)
        request_snapshot["shift_replacement"] = {
            "shift_instance_id": str(shift_instance_id),
            "original_slot_id": str(original_slot_id),
            "replacement_slot_id": str(replacement_slot_id),
            "original_coverage_source_type": normalized_original_source or None,
            "original_coverage_tenant_id": str(original_coverage_tenant_id or "").strip() or None,
            "platform_review_required": platform_review_required,
        }
        wave = RequestBroadcastWaveRecord(
            id=ObjectId(),
            request_id=str(record.id),
            client_tenant_id=record.client_tenant_id,
            request_revision=record.request_revision,
            wave_number=int(record.last_wave_number or 0) + 1,
            trigger=RequestWaveTrigger.CAPACITY_REOPENED,
            wave_status=wave_status,
            request_snapshot=request_snapshot,
            match_summary_snapshot=record.match_summary or {},
            candidate_snapshots=evaluation["candidate_snapshots"],
            review_reason_codes=evaluation["review_reason_codes"],
            review_findings=evaluation["review_findings"],
            review_requested_at=now if evaluation["requires_review"] or platform_review_required else None,
            wave_expires_at=self._compute_wave_expires_at(record, now=now),
            open_slots_at_send=1,
            created_at=now,
            updated_at=now,
        )
        saved_wave = await self._engine.save(wave)
        record.last_wave_number = saved_wave.wave_number
        record.updated_at = now
        await self._engine.save(record)
        if saved_wave.wave_status == RequestWaveStatus.ACTIVE:
            await self._activate_wave(saved_wave, record, current_user)
        return saved_wave

    async def _create_wave_from_current_snapshot(
        self,
        record: ClientRequestRecord,
        *,
        trigger: RequestWaveTrigger,
        current_user,
        refresh_matches: bool,
        max_match_results: int,
    ) -> Optional[RequestBroadcastWaveRecord]:
        if refresh_matches:
            await self._refresh_request_matching(record, max_match_results)

        await self._sync_request_runtime_state(record)
        if record.open_slots <= 0:
            return None

        evaluation = await self._evaluate_broadcast_snapshot(record)
        now = datetime.utcnow()
        wave_status = RequestWaveStatus.PENDING_REVIEW if evaluation["requires_review"] else RequestWaveStatus.ACTIVE
        wave = RequestBroadcastWaveRecord(
            id=ObjectId(),
            request_id=str(record.id),
            client_tenant_id=record.client_tenant_id,
            request_revision=record.request_revision,
            wave_number=int(record.last_wave_number or 0) + 1,
            trigger=trigger,
            wave_status=wave_status,
            request_snapshot=self._request_snapshot(record),
            match_summary_snapshot=record.match_summary or {},
            candidate_snapshots=evaluation["candidate_snapshots"],
            review_reason_codes=evaluation["review_reason_codes"],
            review_findings=evaluation["review_findings"],
            review_requested_at=now if evaluation["requires_review"] else None,
            wave_expires_at=self._compute_wave_expires_at(record, now=now),
            open_slots_at_send=record.open_slots,
            created_at=now,
            updated_at=now,
        )
        saved_wave = await self._engine.save(wave)

        record.last_wave_number = saved_wave.wave_number
        record.active_wave_id = str(saved_wave.id) if saved_wave.wave_status == RequestWaveStatus.ACTIVE else None
        if evaluation["requires_review"]:
            record.staffing_status = RequestStaffingStatus.PENDING_REVIEW
            record.lock_reason = RequestLockReason.REVIEW_PENDING
        record.updated_at = now
        await self._engine.save(record)

        if saved_wave.wave_status == RequestWaveStatus.ACTIVE:
            await self._activate_wave(saved_wave, record, current_user)
            if record.lock_reason == RequestLockReason.REVIEW_PENDING:
                record.lock_reason = None
                await self._engine.save(record)

        return saved_wave

    async def _publish_existing_request(
        self,
        record: ClientRequestRecord,
        *,
        current_user,
        max_match_results: int,
        trigger: RequestWaveTrigger,
        increment_revision: bool,
    ) -> Dict[str, Any]:
        if record.requested_start_at is None or record.requested_end_at is None:
            raise HTTPException(status_code=400, detail="Requested start and end times are required before publishing")
        self._validated_site_snapshot_coordinates(record.site_snapshot or {})
        self._validate_requested_window(record.requested_start_at, record.requested_end_at)
        self._validate_request_expiry(record.request_expires_at, record.requested_start_at, require_value=True)

        if increment_revision:
            record.request_revision = max(int(record.request_revision or 0) + 1, 1)
        else:
            record.request_revision = max(int(record.request_revision or 0), 1)

        now = datetime.utcnow()
        record.request_status = RequestStatus.SUBMITTED
        record.target_type = self._default_target_type_for_mode(self._resolve_fulfillment_mode_from_record(record))
        record.published_at = record.published_at or now
        record.published_by_user_id = str(getattr(current_user, "id", "") or "")
        record.published_by_username = str(getattr(current_user, "username", "") or "")
        record.updated_at = now
        await self._engine.save(record)

        wave = await self._create_wave_from_current_snapshot(
            record,
            trigger=trigger,
            current_user=current_user,
            refresh_matches=True,
            max_match_results=max_match_results,
        )
        await self._sync_request_runtime_state(record)

        wave_message = "Request published"
        if wave and wave.wave_status == RequestWaveStatus.PENDING_REVIEW:
            wave_message = "Request submitted for platform review"
        elif wave is None:
            wave_message = "Request updated without opening new offers"

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Client request updated",
            message=f"{record.title}: {wave_message.lower()}.",
            category="success" if wave_message == "Request published" else "info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Open requests",
            metadata={
                "request_id": str(record.id),
                "request_status": record.request_status.value,
                "staffing_status": record.staffing_status.value,
                "active_wave_id": str(wave.id) if wave else None,
            },
        )

        await self._write_activity(
            action="request_published" if trigger == RequestWaveTrigger.INITIAL_PUBLISH else f"request_{trigger.value}",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=RequestStatus.DRAFT.value if trigger == RequestWaveTrigger.INITIAL_PUBLISH else RequestStatus.SUBMITTED.value,
            new_status=RequestStatus.SUBMITTED.value,
            metadata={"trigger": trigger.value, "wave_id": str(wave.id) if wave else None},
        )

        try:
            await self._sync_request_invoice_state(record, current_user=current_user, reason=trigger)
        except Exception as exc:
            print(f"[RequestManager] Invoice sync failed for request {record.id}: {exc}")

        return {
            "message": wave_message,
            "item": self._serialize(record),
            "wave": self._serialize_wave(wave) if wave else None,
        }

    async def create_request(self, payload: ClientRequestCreatePayload, current_user) -> Dict[str, Any]:
        client_tenant = await self._resolve_request_client_tenant(payload, current_user)
        client_profile = client_tenant.profile if isinstance(client_tenant.profile, dict) else {}
        self._assert_client_billing_method(client_profile)
        site_snapshot = self._resolve_site_snapshot(payload, client_profile)
        title = self._validate_trimmed_title(payload.title)
        self._validate_requested_window(payload.requested_start_at, payload.requested_end_at)
        if payload.request_expires_at is not None:
            self._validate_request_expiry(payload.request_expires_at, payload.requested_start_at, require_value=False)

        preview = await self._preview_matches_for_request(
            payload.fulfillment_mode,
            site_snapshot,
            payload.max_match_results,
            payload.requested_guard_type,
            payload.requested_start_at,
            payload.requested_end_at,
        )
        finance_snapshot = await self._build_request_pricing_and_invoicing(
            site_snapshot=site_snapshot,
            requested_start_at=payload.requested_start_at,
            requested_end_at=payload.requested_end_at,
            guards_required=int(payload.guards_required or 1),
            invoice_contract_type=payload.invoice_contract_type,
            invoice_cutoff_day=payload.invoice_cutoff_day,
            invoice_recipient_email=payload.invoice_recipient_email,
        )

        now = datetime.utcnow()
        record = ClientRequestRecord(
            id=ObjectId(),
            client_tenant_id=str(client_tenant.id),
            created_by_user_id=str(getattr(current_user, "id", "") or ""),
            created_by_username=str(getattr(current_user, "username", "") or ""),
            title=title,
            timezone=(payload.timezone or "").strip() or None,
            fulfillment_mode=payload.fulfillment_mode,
            target_type=self._default_target_type_for_mode(payload.fulfillment_mode),
            requested_guard_type=(payload.requested_guard_type or "").strip() or None,
            guards_required=int(payload.guards_required or 1),
            request_status=RequestStatus.DRAFT,
            staffing_status=RequestStaffingStatus.OPEN,
            accepted_slots=0,
            open_slots=int(payload.guards_required or 1),
            site_snapshot=site_snapshot,
            special_instructions=(payload.special_instructions or "").strip() or None,
            pricing_snapshot=finance_snapshot["pricing_snapshot"],
            invoicing_snapshot=finance_snapshot["invoicing_snapshot"],
            requested_start_at=payload.requested_start_at,
            requested_end_at=payload.requested_end_at,
            request_expires_at=payload.request_expires_at,
            match_summary=preview["summary"],
            matched_candidates=preview["results"],
            created_at=now,
            updated_at=now,
        )
        saved = await self._engine.save(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=str(client_tenant.id),
            title="Request draft saved",
            message=f"{title} was saved as a draft with {preview['summary'].get('eligible_count', 0)} eligible matches.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(saved.id)),
            action_label="Open requests",
            metadata={"request_id": str(saved.id), "request_status": RequestStatus.DRAFT.value},
        )

        await self._write_activity(
            action="request_created",
            entity_type="request",
            entity_id=str(saved.id),
            current_user=current_user,
            new_status=RequestStatus.DRAFT.value,
            metadata={"fulfillment_mode": payload.fulfillment_mode.value},
        )

        if not payload.commit:
            return {
                "message": "Request draft saved",
                "item": self._serialize(saved),
            }

        return await self._publish_existing_request(
            saved,
            current_user=current_user,
            max_match_results=payload.max_match_results,
            trigger=RequestWaveTrigger.INITIAL_PUBLISH,
            increment_revision=False,
        )

    async def preview_request_pricing(self, payload: RequestPricingPreviewPayload, current_user) -> Dict[str, Any]:
        client_tenant = await self._resolve_request_client_tenant(payload, current_user)
        client_profile = client_tenant.profile if isinstance(client_tenant.profile, dict) else {}
        self._assert_client_billing_method(client_profile)
        site_snapshot = self._resolve_site_snapshot(payload, client_profile)
        self._validate_requested_window(payload.requested_start_at, payload.requested_end_at)

        finance_snapshot = await self._build_request_pricing_and_invoicing(
            site_snapshot=site_snapshot,
            requested_start_at=payload.requested_start_at,
            requested_end_at=payload.requested_end_at,
            guards_required=int(payload.guards_required or 1),
            invoice_contract_type=payload.invoice_contract_type,
            invoice_cutoff_day=payload.invoice_cutoff_day,
            invoice_recipient_email=payload.invoice_recipient_email,
        )

        return {
            "pricing": finance_snapshot["pricing_snapshot"],
            "invoicing": finance_snapshot["invoicing_snapshot"],
        }

    async def update_request(self, request_id: str, payload: ClientRequestUpdatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._assert_request_write_access(record, current_user)
        await self._sync_request_runtime_state(record)

        provided = payload.model_dump(exclude_unset=True)
        if record.request_status != RequestStatus.DRAFT:
            material_fields = {
                "fulfillment_mode",
                "site",
                "requested_guard_type",
                "guards_required",
                "requested_start_at",
                "requested_end_at",
                "special_instructions",
                "invoice_contract_type",
                "invoice_cutoff_day",
                "invoice_recipient_email",
            }
            attempted_material_fields = [key for key in provided if key in material_fields]
            if attempted_material_fields:
                raise HTTPException(
                    status_code=409,
                    detail="Live request material changes must use publish update or additional coverage endpoints",
                )
            if record.staffing_status == RequestStaffingStatus.EXPIRED:
                raise HTTPException(status_code=400, detail="Expired requests cannot be edited")

            if "title" in provided and payload.title is not None:
                record.title = self._validate_trimmed_title(payload.title)
            if "request_expires_at" in provided:
                self._validate_request_expiry(payload.request_expires_at, record.requested_start_at, require_value=False)
                record.request_expires_at = payload.request_expires_at
            record.updated_at = datetime.utcnow()
            await self._engine.save(record)
            await self._sync_request_runtime_state(record)
            return {
                "message": "Request updated",
                "item": self._serialize(record),
            }

        if "title" in provided and payload.title is not None:
            record.title = self._validate_trimmed_title(payload.title)
        if "fulfillment_mode" in provided and payload.fulfillment_mode is not None:
            record.fulfillment_mode = payload.fulfillment_mode
            record.target_type = self._default_target_type_for_mode(payload.fulfillment_mode)
        if "requested_guard_type" in provided:
            record.requested_guard_type = (payload.requested_guard_type or "").strip() or None
        if "guards_required" in provided and payload.guards_required is not None:
            record.guards_required = int(payload.guards_required)
            record.open_slots = max(record.guards_required - int(record.accepted_slots or 0), 0)
        if "special_instructions" in provided:
            record.special_instructions = (payload.special_instructions or "").strip() or None
        if "timezone" in provided:
            record.timezone = (payload.timezone or "").strip() or None
        if "requested_start_at" in provided:
            record.requested_start_at = payload.requested_start_at
        if "requested_end_at" in provided:
            record.requested_end_at = payload.requested_end_at
        if "request_expires_at" in provided:
            self._validate_request_expiry(payload.request_expires_at, record.requested_start_at, require_value=False)
            record.request_expires_at = payload.request_expires_at
        self._validate_requested_window(record.requested_start_at, record.requested_end_at)

        if "site" in provided and payload.site is not None:
            record.site_snapshot = self._resolve_site_input_snapshot(payload.site)

        await self._refresh_request_finance_snapshot(
            record,
            invoice_contract_type=payload.invoice_contract_type if "invoice_contract_type" in provided else _FINANCE_SNAPSHOT_UNSET,
            invoice_cutoff_day=payload.invoice_cutoff_day if "invoice_cutoff_day" in provided else _FINANCE_SNAPSHOT_UNSET,
            invoice_recipient_email=payload.invoice_recipient_email if "invoice_recipient_email" in provided else _FINANCE_SNAPSHOT_UNSET,
        )

        max_results = payload.max_match_results if payload.max_match_results is not None else 25
        await self._refresh_request_matching(record, max_results)
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)
        from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager

        await RequestShiftManager.get_instance().sync_shift_slots_for_request(record)

        await self._write_activity(
            action="request_updated",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=RequestStatus.DRAFT.value,
            new_status=RequestStatus.DRAFT.value,
            metadata={"request_id": str(record.id), "fulfillment_mode": self._resolve_fulfillment_mode_from_record(record).value},
        )

        return {
            "message": "Request draft updated",
            "item": self._serialize(record),
        }

    async def list_requests(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
        keyword: str = "",
        request_status: str = "",
        fulfillment_mode: str = "",
        client_tenant_id: str = "",
    ) -> Dict[str, Any]:
        docs = await self._resolve_request_docs_for_role(current_user)
        normalized_keyword = self._normalize_text(keyword)
        normalized_status = self._normalize_text(request_status)
        normalized_fulfillment_mode = self._normalize_text(fulfillment_mode)
        normalized_client_tenant_id = str(client_tenant_id or "").strip()

        filtered_docs: List[Dict[str, Any]] = []
        for doc in docs:
            title = self._normalize_text(doc.get("title"))
            current_status = self._normalize_text(doc.get("request_status"))
            current_mode = self._normalize_text(doc.get("fulfillment_mode")) or self._normalize_text(self._resolve_fulfillment_mode_from_record(doc).value)
            site_name = self._normalize_text((doc.get("site_snapshot") or {}).get("site_name"))
            guard_type = self._normalize_text(doc.get("requested_guard_type"))

            if normalized_status and current_status != normalized_status:
                continue
            if normalized_fulfillment_mode and current_mode != normalized_fulfillment_mode:
                continue
            if normalized_client_tenant_id and str(doc.get("client_tenant_id") or "") != normalized_client_tenant_id:
                continue
            if normalized_keyword and normalized_keyword not in " ".join([title, site_name, guard_type]):
                continue
            filtered_docs.append(doc)

        filtered_docs.sort(key=lambda item: item.get("created_at") or datetime.min, reverse=True)

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(filtered_docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = filtered_docs[start:end]
        for doc in page_docs:
            if isinstance(doc, dict):
                await self._ensure_request_doc_finance_snapshot(doc)

        return {
            "items": await self._serialize_requests_with_client_tenant_labels(page_docs),
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "keyword": keyword,
                "request_status": request_status,
                "fulfillment_mode": fulfillment_mode,
                "client_tenant_id": client_tenant_id,
            },
        }

    async def get_request_by_id(self, request_id: str, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._sync_request_runtime_state(record)
        if not self._has_request_pricing_snapshot(getattr(record, "pricing_snapshot", None)):
            await self._refresh_request_finance_snapshot(record)
        serialized = self._serialize(record)
        viewer_assignment = await self._resolve_viewer_assignment_for_request(str(record.id), current_user)
        if viewer_assignment:
            serialized["viewer_assignment"] = viewer_assignment
        tenant_id = str(serialized.get("client_tenant_id") or "").strip()
        label_lookup = await self._build_client_tenant_label_lookup([tenant_id])
        serialized["client_tenant_label"] = label_lookup.get(tenant_id, tenant_id)
        return serialized

    async def _assert_request_invoice_view_access(self, record: ClientRequestRecord, current_user) -> None:
        role_value = self._role_value(current_user)
        if self._is_platform_role(role_value):
            return
        if role_value == "client_admin":
            session_tenant = await self._get_session_tenant(current_user)
            if session_tenant.tenant_type == TenantType.CLIENT and str(session_tenant.id) == str(record.client_tenant_id):
                return
        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _get_assignee_invoice_scope(self, current_user) -> Dict[str, str]:
        role_value = self._role_value(current_user)
        session_tenant = await self._get_session_tenant(current_user)

        if role_value == "guard_admin" and session_tenant.tenant_type == TenantType.GUARD:
            return {
                "tenant_id": str(session_tenant.id),
                "assignee_tenant_type": RequestTargetType.GUARD.value,
            }

        if role_value == "sp_admin" and session_tenant.tenant_type == TenantType.SERVICE_PROVIDER:
            return {
                "tenant_id": str(session_tenant.id),
                "assignee_tenant_type": RequestTargetType.SERVICE_PROVIDER.value,
            }

        raise HTTPException(status_code=403, detail="Access forbidden")

    async def _collect_assignee_invoice_assignment_map(
        self,
        *,
        assignee_tenant_id: str,
        request_ids: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        query: Dict[str, Any] = {"assignee_tenant_id": assignee_tenant_id}
        normalized_request_ids = [
            str(request_id or "").strip()
            for request_id in list(request_ids or [])
            if str(request_id or "").strip()
        ]
        if normalized_request_ids:
            query["request_id"] = {"$in": normalized_request_ids}

        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        assignment_docs = await assignment_collection.find(query).to_list(length=None)

        relevant: Dict[str, Dict[str, Any]] = {}
        allowed_statuses = self._assignee_invoice_allowed_statuses()
        for doc in assignment_docs:
            if self._assignment_scope_value(doc) != RequestAssignmentScope.REQUEST.value:
                continue

            status_value = self._enum_value(doc.get("assignment_status"))
            if status_value not in allowed_statuses:
                continue

            request_id = str(doc.get("request_id") or "").strip()
            if not request_id:
                continue

            entry = relevant.setdefault(request_id, {
                "committed_slots": 0,
                "statuses": set(),
            })
            entry["committed_slots"] += self._assignment_slots(doc)
            entry["statuses"].add(status_value)

        return relevant

    async def list_my_invoices(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        scope = await self._get_assignee_invoice_scope(current_user)
        assignment_map = await self._collect_assignee_invoice_assignment_map(
            assignee_tenant_id=scope["tenant_id"],
        )
        if not assignment_map:
            safe_rows = rows if rows and rows > 0 else 20
            safe_page = page if page and page > 0 else 1
            return {
                "items": [],
                "pagination": {
                    "page": safe_page,
                    "rows": safe_rows,
                    "total_items": 0,
                    "total_pages": 0,
                },
            }
        items = await self._build_assignee_invoice_items(
            assignee_tenant_id=scope["tenant_id"],
            assignee_tenant_type=scope["assignee_tenant_type"],
            assignment_map=assignment_map,
        )

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(items)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows

        return {
            "items": items[start:end],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def get_my_invoice_by_id(
        self,
        invoice_id: str,
        current_user,
    ) -> Dict[str, Any]:
        scope = await self._get_assignee_invoice_scope(current_user)
        assignment_map = await self._collect_assignee_invoice_assignment_map(
            assignee_tenant_id=scope["tenant_id"],
        )
        items = await self._build_assignee_invoice_items(
            assignee_tenant_id=scope["tenant_id"],
            assignee_tenant_type=scope["assignee_tenant_type"],
            assignment_map=assignment_map,
        )
        for item in items:
            if str(item.get("id") or "").strip() == str(invoice_id or "").strip():
                return item
        raise HTTPException(status_code=404, detail="Invoice not found")

    async def list_platform_payout_invoices(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
        keyword: str = "",
        assignee_tenant_type: str = "",
    ) -> Dict[str, Any]:
        if not self._is_platform_role(self._role_value(current_user)):
            raise HTTPException(status_code=403, detail="Access forbidden")

        normalized_type = str(assignee_tenant_type or "").strip().lower()
        scopes = await self._collect_platform_assignee_invoice_scopes()
        tenant_labels = await self._build_tenant_label_lookup([scope["tenant_id"] for scope in scopes])

        items: List[Dict[str, Any]] = []
        for scope in scopes:
            scope_type = str(scope.get("assignee_tenant_type") or "").strip().lower()
            if normalized_type and scope_type != normalized_type:
                continue
            scope_items = await self._build_assignee_invoice_items(
                assignee_tenant_id=str(scope.get("tenant_id") or "").strip(),
                assignee_tenant_type=scope_type,
                assignment_map=cast(Dict[str, Dict[str, Any]], scope.get("assignment_map") or {}),
            )
            assignee_label = tenant_labels.get(str(scope.get("tenant_id") or "").strip(), str(scope.get("tenant_id") or "").strip())
            for item in scope_items:
                item["assignee_tenant_id"] = str(scope.get("tenant_id") or "").strip()
                item["assignee_label"] = assignee_label
                items.append(item)

        request_lookup, invoice_lookup, client_labels = await self._build_platform_finance_context([
            str(item.get("request_id") or "").strip()
            for item in items
        ])
        items = [
            self._enrich_platform_payout_invoice_item(
                item,
                request_summary=request_lookup.get(str(item.get("request_id") or "").strip(), {}),
                candidate_invoices=invoice_lookup.get(str(item.get("request_id") or "").strip(), []),
                client_label=client_labels.get(
                    str(request_lookup.get(str(item.get("request_id") or "").strip(), {}).get("client_tenant_id") or "").strip(),
                    "",
                ),
            )
            for item in items
        ]

        normalized_keyword = self._normalize_text(keyword)
        if normalized_keyword:
            items = [
                item for item in items
                if normalized_keyword in self._normalize_text(item.get("invoice_number"))
                or normalized_keyword in self._normalize_text(item.get("request_title"))
                or normalized_keyword in self._normalize_text(item.get("site_name"))
                or normalized_keyword in self._normalize_text(item.get("assignee_label"))
                or normalized_keyword in self._normalize_text(item.get("assignee_tenant_id"))
                or normalized_keyword in self._normalize_text(item.get("client_label"))
                or normalized_keyword in self._normalize_text(item.get("linked_client_invoice_number"))
            ]

        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        summary = self._build_platform_payout_summary(items)
        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(items)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        return {
            "items": items[start:end],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "keyword": str(keyword or "").strip(),
                "assignee_tenant_type": normalized_type,
            },
            "summary": summary,
        }

    async def get_platform_payout_invoice_by_id(
        self,
        invoice_id: str,
        current_user,
    ) -> Dict[str, Any]:
        if not self._is_platform_role(self._role_value(current_user)):
            raise HTTPException(status_code=403, detail="Access forbidden")

        scopes = await self._collect_platform_assignee_invoice_scopes()
        tenant_labels = await self._build_tenant_label_lookup([scope["tenant_id"] for scope in scopes])
        normalized_invoice_id = str(invoice_id or "").strip()

        for scope in scopes:
            scope_items = await self._build_assignee_invoice_items(
                assignee_tenant_id=str(scope.get("tenant_id") or "").strip(),
                assignee_tenant_type=str(scope.get("assignee_tenant_type") or "").strip().lower(),
                assignment_map=cast(Dict[str, Dict[str, Any]], scope.get("assignment_map") or {}),
            )
            assignee_id = str(scope.get("tenant_id") or "").strip()
            assignee_label = tenant_labels.get(assignee_id, assignee_id)
            for item in scope_items:
                if str(item.get("id") or "").strip() != normalized_invoice_id:
                    continue
                item["assignee_tenant_id"] = assignee_id
                item["assignee_label"] = assignee_label
                request_lookup, invoice_lookup, client_labels = await self._build_platform_finance_context([str(item.get("request_id") or "").strip()])
                request_summary = request_lookup.get(str(item.get("request_id") or "").strip(), {})
                client_label = client_labels.get(str(request_summary.get("client_tenant_id") or "").strip(), "")
                return self._enrich_platform_payout_invoice_item(
                    item,
                    request_summary=request_summary,
                    candidate_invoices=invoice_lookup.get(str(item.get("request_id") or "").strip(), []),
                    client_label=client_label,
                )

        raise HTTPException(status_code=404, detail="Invoice not found")

    async def list_request_invoices(
        self,
        request_id: str,
        current_user,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        await self._assert_request_invoice_view_access(record, current_user)

        collection = self._engine.get_collection(RequestInvoiceRecord)
        docs = await collection.find({"request_id": str(record.id)}).sort("created_at", -1).to_list(length=None)

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = docs[start:end]

        return {
            "items": [self._serialize_invoice(doc) for doc in page_docs],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def get_request_invoice_by_id(
        self,
        request_id: str,
        invoice_id: str,
        current_user,
    ) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        await self._assert_request_invoice_view_access(record, current_user)

        try:
            object_id = ObjectId(invoice_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Invoice not found")

        collection = self._engine.get_collection(RequestInvoiceRecord)
        docs = await collection.find({
            "_id": object_id,
            "request_id": str(record.id),
        }).to_list(length=1)
        if not docs:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return self._serialize_invoice(docs[0])

    async def get_request_wave_by_id(self, wave_id: str, current_user) -> Dict[str, Any]:
        wave = await self._get_wave_or_404(wave_id)
        record = await self._get_request_or_404(wave.request_id)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._sync_request_runtime_state(record)
        return self._serialize_wave(wave)

    async def get_job_by_id(self, assignment_id: str, current_user) -> Dict[str, Any]:
        assignment = await self._get_assignment_or_404(assignment_id)
        role_value = self._role_value(current_user)
        if self._is_platform_role(role_value):
            pass
        else:
            session_tenant = await self._get_session_tenant(current_user)
            tenant_id = str(session_tenant.id)
            if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
                if assignment.client_tenant_id != tenant_id:
                    raise HTTPException(status_code=403, detail="Access forbidden")
            elif role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
                if assignment.assignee_tenant_id != tenant_id:
                    raise HTTPException(status_code=403, detail="Access forbidden")
            else:
                raise HTTPException(status_code=403, detail="Access forbidden")

        record = await self._get_request_or_404(assignment.request_id)
        self._assert_not_soft_deleted(record)
        await self._sync_request_runtime_state(record)
        if not self._has_request_pricing_snapshot(getattr(record, "pricing_snapshot", None)):
            await self._refresh_request_finance_snapshot(record)
        if (
            self._assignment_scope_value(assignment) == RequestAssignmentScope.REQUEST.value
            and assignment.assignment_status in COMMITTED_SLOT_STATUSES
            and not await self._request_has_active_schedule(str(record.id))
        ):
            from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager

            await RequestShiftManager.get_instance().sync_shift_slots_for_request(record)
            assignment = await self._get_assignment_or_404(assignment_id)
        request_snapshot = self._request_snapshot(record)
        request_snapshot["has_schedule"] = await self._request_has_active_schedule(str(record.id))
        assignment = await self._auto_complete_elapsed_assignment_record(assignment, request_snapshot)
        return self._serialize_assignment(assignment, request_snapshot=request_snapshot)

    async def publish_request(self, request_id: str, payload: RequestPublishPayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._assert_request_write_access(record, current_user)
        if record.request_status != RequestStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Only draft requests can be published")
        return await self._publish_existing_request(
            record,
            current_user=current_user,
            max_match_results=payload.max_match_results,
            trigger=RequestWaveTrigger.INITIAL_PUBLISH,
            increment_revision=False,
        )

    async def publish_request_update(self, request_id: str, payload: RequestPublishUpdatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._assert_request_write_access(record, current_user)
        await self._sync_request_runtime_state(record)

        if record.request_status == RequestStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Use publish on draft requests")
        if record.request_status == RequestStatus.IN_PROGRESS:
            raise HTTPException(status_code=400, detail="Material updates are blocked once work is in progress")
        if record.staffing_status == RequestStaffingStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="Expired requests cannot be updated")

        provided = payload.model_dump(exclude_unset=True)
        changed = False
        invoicing_snapshot = record.invoicing_snapshot if isinstance(getattr(record, "invoicing_snapshot", None), dict) else {}
        current_invoice_contract_type = self._normalize_invoice_contract_type(invoicing_snapshot.get("contract_type"))
        next_invoice_contract_type = current_invoice_contract_type
        current_invoice_cutoff_day = invoicing_snapshot.get("monthly_cutoff_day")
        next_invoice_cutoff_day = current_invoice_cutoff_day
        current_invoice_recipient_email = str(invoicing_snapshot.get("invoice_recipient_email") or "").strip() or None
        next_invoice_recipient_email = current_invoice_recipient_email

        if "fulfillment_mode" in provided and payload.fulfillment_mode is not None and payload.fulfillment_mode != record.fulfillment_mode:
            record.fulfillment_mode = payload.fulfillment_mode
            record.target_type = self._default_target_type_for_mode(payload.fulfillment_mode)
            changed = True
        if "site" in provided and payload.site is not None:
            record.site_snapshot = self._resolve_site_input_snapshot(payload.site)
            changed = True
        if "requested_guard_type" in provided and (payload.requested_guard_type or "").strip() != (record.requested_guard_type or ""):
            record.requested_guard_type = (payload.requested_guard_type or "").strip() or None
            changed = True
        if "timezone" in provided and (payload.timezone or "").strip() != (record.timezone or ""):
            record.timezone = (payload.timezone or "").strip() or None
            changed = True
        if "requested_start_at" in provided and payload.requested_start_at != record.requested_start_at:
            record.requested_start_at = payload.requested_start_at
            changed = True
        if "requested_end_at" in provided and payload.requested_end_at != record.requested_end_at:
            record.requested_end_at = payload.requested_end_at
            changed = True
        if "special_instructions" in provided and (payload.special_instructions or "").strip() != (record.special_instructions or ""):
            record.special_instructions = (payload.special_instructions or "").strip() or None
            changed = True
        if "invoice_contract_type" in provided:
            next_invoice_contract_type = self._normalize_invoice_contract_type(payload.invoice_contract_type)
            if next_invoice_contract_type != current_invoice_contract_type:
                changed = True
        if "invoice_cutoff_day" in provided:
            next_invoice_cutoff_day = payload.invoice_cutoff_day
            if next_invoice_cutoff_day != current_invoice_cutoff_day:
                changed = True
        if "invoice_recipient_email" in provided:
            next_invoice_recipient_email = str(payload.invoice_recipient_email or "").strip() or None
            if next_invoice_recipient_email != current_invoice_recipient_email:
                changed = True
        if "request_expires_at" in provided:
            self._validate_request_expiry(payload.request_expires_at, record.requested_start_at, require_value=True)
            record.request_expires_at = payload.request_expires_at

        self._validate_requested_window(record.requested_start_at, record.requested_end_at)
        self._validate_request_expiry(record.request_expires_at, record.requested_start_at, require_value=True)
        if not changed:
            raise HTTPException(status_code=400, detail="Publish update requires a material request change")

        await self._refresh_request_finance_snapshot(
            record,
            invoice_contract_type=next_invoice_contract_type,
            invoice_cutoff_day=next_invoice_cutoff_day,
            invoice_recipient_email=next_invoice_recipient_email,
        )

        await self._supersede_previous_waves(record)
        await self._mark_assignments_reconfirmation_required(record)
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)
        await self._sync_request_runtime_state(record)

        return await self._publish_existing_request(
            record,
            current_user=current_user,
            max_match_results=payload.max_match_results,
            trigger=RequestWaveTrigger.PUBLISH_UPDATE,
            increment_revision=True,
        )

    async def request_additional_coverage(self, request_id: str, payload: RequestAdditionalCoveragePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._assert_request_write_access(record, current_user)
        await self._sync_request_runtime_state(record)

        if record.request_status == RequestStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Additional coverage is only available for published requests")
        if record.staffing_status == RequestStaffingStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="Expired requests cannot be updated")

        record.guards_required = int(record.guards_required or 0) + int(payload.additional_slots or 0)
        if payload.request_expires_at is not None:
            self._validate_request_expiry(payload.request_expires_at, record.requested_start_at, require_value=True)
            record.request_expires_at = payload.request_expires_at

        await self._refresh_request_finance_snapshot(record)

        record.request_revision = max(int(record.request_revision or 0) + 1, 1)
        await self._refresh_request_matching(record, payload.max_match_results)
        await self._sync_request_runtime_state(record)
        from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager

        await RequestShiftManager.get_instance().sync_shift_slots_for_request(record)

        wave = await self._create_wave_from_current_snapshot(
            record,
            trigger=RequestWaveTrigger.ADDITIONAL_COVERAGE,
            current_user=current_user,
            refresh_matches=False,
            max_match_results=payload.max_match_results,
        )

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Additional coverage requested",
            message=f"{record.title}: additional coverage request has been issued.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Open requests",
            metadata={"request_id": str(record.id), "wave_id": str(wave.id) if wave else None},
        )

        try:
            await self._sync_request_invoice_state(record, current_user=current_user, reason=RequestInvoiceTrigger.ADDITIONAL_COVERAGE)
        except Exception as exc:
            print(f"[RequestManager] Invoice sync failed for request {record.id}: {exc}")

        return {
            "message": "Additional coverage requested",
            "item": self._serialize(record),
            "wave": self._serialize_wave(wave) if wave else None,
        }

    async def list_request_waves(self, request_id: str, current_user, page: int = 1, rows: int = 20) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")

        collection = self._engine.get_collection(RequestBroadcastWaveRecord)
        docs = await collection.find({"request_id": str(record.id)}).sort("wave_number", -1).to_list(length=None)
        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = docs[start:end]

        return {
            "items": [self._serialize_wave(doc) for doc in page_docs],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }

    async def list_review_waves(
        self,
        current_user,
        page: int = 1,
        rows: int = 20,
        wave_status: str = "",
        trigger: str = "",
        request_id: str = "",
        client_tenant_id: str = "",
    ) -> Dict[str, Any]:
        if not self._is_platform_role(self._role_value(current_user)):
            raise HTTPException(status_code=403, detail="Access forbidden")

        collection = self._engine.get_collection(RequestBroadcastWaveRecord)
        docs = await collection.find({}).sort("created_at", -1).to_list(length=None)
        normalized_status = self._normalize_text(wave_status)
        normalized_trigger = self._normalize_text(trigger)

        filtered_docs = []
        for doc in docs:
            if normalized_status and self._normalize_text(doc.get("wave_status")) != normalized_status:
                continue
            if normalized_trigger and self._normalize_text(doc.get("trigger")) != normalized_trigger:
                continue
            if request_id and str(doc.get("request_id") or "") != str(request_id):
                continue
            if client_tenant_id and str(doc.get("client_tenant_id") or "") != str(client_tenant_id):
                continue
            filtered_docs.append(doc)

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(filtered_docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = filtered_docs[start:end]

        return {
            "items": [self._serialize_wave(doc) for doc in page_docs],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "wave_status": wave_status,
                "trigger": trigger,
                "request_id": request_id,
                "client_tenant_id": client_tenant_id,
            },
        }

    async def approve_request_wave(self, wave_id: str, payload: RequestWaveReviewPayload, current_user) -> Dict[str, Any]:
        wave = await self._get_wave_or_404(wave_id)
        if wave.wave_status != RequestWaveStatus.PENDING_REVIEW:
            raise HTTPException(status_code=400, detail="Only pending-review waves can be approved")

        record = await self._get_request_or_404(wave.request_id)
        shift_replacement = self._wave_shift_replacement_context(wave)
        await self._sync_request_runtime_state(record)
        if record.staffing_status == RequestStaffingStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="Expired requests cannot be approved for broadcast")

        await self._set_wave_status(wave, RequestWaveStatus.ACTIVE, current_user=current_user, note=payload.note)
        if not shift_replacement:
            record.active_wave_id = str(wave.id)
        if not shift_replacement and record.lock_reason == RequestLockReason.REVIEW_PENDING:
            record.lock_reason = None
        await self._engine.save(record)

        offers = await self._activate_wave(wave, record, current_user)
        await self._sync_request_runtime_state(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Replacement wave approved" if shift_replacement else "Broadcast approved",
            message=(
                f"{record.title}: platform review approved the shift replacement wave."
                if shift_replacement
                else f"{record.title}: platform review approved the broadcast wave."
            ),
            category="success",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Open requests",
            metadata={"request_id": str(record.id), "wave_id": str(wave.id), "offer_count": offers},
        )

        return {
            "message": "Request wave approved and broadcast",
            "item": self._serialize_wave(wave),
        }

    async def return_request_wave(self, wave_id: str, payload: RequestWaveReviewPayload, current_user) -> Dict[str, Any]:
        wave = await self._get_wave_or_404(wave_id)
        if wave.wave_status != RequestWaveStatus.PENDING_REVIEW:
            raise HTTPException(status_code=400, detail="Only pending-review waves can be returned")

        record = await self._get_request_or_404(wave.request_id)
        shift_replacement = self._wave_shift_replacement_context(wave)
        await self._set_wave_status(wave, RequestWaveStatus.RETURNED, current_user=current_user, note=payload.note)
        if not shift_replacement:
            record.staffing_status = RequestStaffingStatus.REVIEW_RETURNED
            record.lock_reason = None
            record.active_wave_id = None
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Replacement wave returned" if shift_replacement else "Broadcast returned",
            message=(
                f"{record.title}: platform review returned the shift replacement wave."
                if shift_replacement
                else f"{record.title}: platform review returned the request for correction."
            ),
            category="warning",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Open requests",
            metadata={"request_id": str(record.id), "wave_id": str(wave.id)},
        )

        return {
            "message": "Request wave returned to client",
            "item": self._serialize_wave(wave),
        }

    async def update_request_status(self, request_id: str, payload: ClientRequestStatusUpdatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._assert_request_write_access(record, current_user)

        if self._is_platform_write_role(self._role_value(current_user)) and payload.reason is None:
            raise HTTPException(status_code=400, detail="Reason is required for platform admin overrides")
        if payload.request_status not in {RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            raise HTTPException(status_code=400, detail="Only cancel and close are supported through this endpoint")
        if not self._allowed_request_status_transition(record.request_status, payload.request_status):
            raise HTTPException(status_code=400, detail=f"Invalid request transition from {record.request_status.value} to {payload.request_status.value}")

        previous_status = record.request_status.value
        record.request_status = payload.request_status
        record.updated_at = datetime.utcnow()
        if payload.request_status == RequestStatus.CANCELLED:
            record.cancelled_at = datetime.utcnow()
            record.lock_reason = RequestLockReason.REQUEST_CANCELLED
            await self._close_open_offers_for_request(
                record,
                to_status=RequestAssignmentStatus.CANCELLED,
                lock_reason=AssignmentLockReason.REQUEST_CANCELLED,
            )
            for wave in await self._get_waves_for_request(str(record.id)):
                if wave.wave_status in {RequestWaveStatus.ACTIVE, RequestWaveStatus.PENDING_REVIEW}:
                    await self._set_wave_status(wave, RequestWaveStatus.CANCELLED)
        if payload.request_status == RequestStatus.CLOSED:
            record.closed_at = datetime.utcnow()
            record.lock_reason = RequestLockReason.REQUEST_CLOSED
        await self._engine.save(record)
        if payload.request_status == RequestStatus.CLOSED:
            await self._sync_request_assignments_for_manual_close(record)
        await self._sync_request_runtime_state(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Client request updated",
            message=f"{record.title} is now {payload.request_status.value}.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="View requests",
            metadata={"request_id": str(record.id), "request_status": payload.request_status.value},
        )

        await self._write_activity(
            action="request_status_updated",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=previous_status,
            new_status=payload.request_status.value,
            reason=payload.reason,
            metadata={"client_tenant_id": record.client_tenant_id},
            severity="warning" if payload.request_status == RequestStatus.CANCELLED else "info",
        )

        return {
            "message": "Client request updated",
            "item": self._serialize(record),
        }

    async def soft_delete_request(self, request_id: str, payload: ClientRequestSoftDeletePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        role_value = self._role_value(current_user)
        if not self._is_platform_write_role(role_value):
            raise HTTPException(status_code=403, detail="Only platform admins can remove client requests from the dashboard")
        if self._is_soft_deleted(record):
            raise HTTPException(status_code=409, detail="Request has already been removed from the dashboard")
        await self._sync_request_runtime_state(record)

        if record.request_status not in {RequestStatus.DRAFT, RequestStatus.CANCELLED, RequestStatus.CLOSED}:
            raise HTTPException(status_code=400, detail="Only draft, cancelled, or closed requests can be removed from the dashboard")

        now = datetime.utcnow()
        reason = str(payload.reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Reason is required")

        record.deleted_at = now
        record.deleted_by_user_id = str(getattr(current_user, "id", "") or "")
        record.deleted_by_username = str(getattr(current_user, "username", "") or "")
        record.deleted_reason = reason
        record.updated_at = now
        await self._engine.save(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Client request removed",
            message=f"{record.title} was removed from the dashboard by a platform admin.",
            category="warning",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests"),
            action_label="Open requests",
            metadata={"request_id": str(record.id), "deleted_at": now.isoformat()},
        )

        await self._write_activity(
            action="request_soft_deleted",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=record.request_status.value,
            new_status="soft_deleted",
            reason=reason,
            metadata={"client_tenant_id": record.client_tenant_id},
            severity="warning",
        )

        return {
            "message": "Client request removed from the dashboard",
            "item": self._serialize(record),
        }

    async def create_assignment(self, request_id: str, payload: RequestAssignmentCreatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        self._assert_not_soft_deleted(record)
        role_value = self._role_value(current_user)
        session_tenant = None if self._is_platform_write_role(role_value) else await self._get_session_tenant(current_user)

        if not self._is_platform_write_role(role_value):
            if role_value != "client_admin" or session_tenant.tenant_type != TenantType.CLIENT:
                raise HTTPException(status_code=403, detail="Only client admins or platform admins can assign requests")
            if record.client_tenant_id != str(session_tenant.id):
                raise HTTPException(status_code=403, detail="Request does not belong to your tenant")

        await self._sync_request_runtime_state(record)
        if record.request_status == RequestStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Only published requests can be assigned")
        if record.staffing_status == RequestStaffingStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="Expired requests cannot be assigned")
        if record.open_slots <= 0:
            raise HTTPException(status_code=409, detail="All request slots have already been filled")

        candidate_tenant_id = str(payload.candidate_tenant_id or "").strip()
        eligible_candidates = [
            candidate for candidate in (record.matched_candidates or [])
            if str(candidate.get("candidate_id") or "") == candidate_tenant_id and bool(candidate.get("eligible"))
        ]
        if not eligible_candidates:
            raise HTTPException(status_code=400, detail="Candidate must exist in eligible matching results")

        candidate_snapshot = dict(eligible_candidates[0])
        assignee_tenant = await self._get_tenant(candidate_tenant_id)
        if not assignee_tenant:
            raise HTTPException(status_code=400, detail="Candidate tenant not found")
        if assignee_tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Candidate tenant must be active")

        candidate_target_type = RequestTargetType(str(candidate_snapshot.get("target_type") or RequestTargetType.GUARD.value))
        expected_tenant_type = TenantType.GUARD if candidate_target_type == RequestTargetType.GUARD else TenantType.SERVICE_PROVIDER
        if assignee_tenant.tenant_type != expected_tenant_type:
            raise HTTPException(status_code=400, detail="Candidate tenant type does not match matching results")
        if await self._has_active_assignment_for_candidate(str(record.id), str(assignee_tenant.id)):
            raise HTTPException(status_code=409, detail="An active assignment for this candidate already exists")

        now = datetime.utcnow()
        assignment = RequestAssignmentRecord(
            id=ObjectId(),
            request_id=str(record.id),
            client_tenant_id=record.client_tenant_id,
            assignee_tenant_id=str(assignee_tenant.id),
            assignee_tenant_type=candidate_target_type,
            assignment_status=RequestAssignmentStatus.OFFERED,
            assignment_origin=RequestAssignmentOrigin.MANUAL,
            request_revision_at_offer=record.request_revision,
            response_due_at=record.request_expires_at,
            candidate_snapshot=candidate_snapshot,
            assigned_by_user_id=str(getattr(current_user, "id", "") or ""),
            assigned_by_username=str(getattr(current_user, "username", "") or ""),
            note=(payload.note or "").strip() or None,
            offered_at=now,
            created_at=now,
            updated_at=now,
        )
        saved = await self._engine.save(assignment)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=str(assignee_tenant.id),
            title="New job offer",
            message=f"{record.title} has been assigned to your tenant.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Review offer",
            metadata={"request_id": str(record.id), "assignment_id": str(saved.id)},
        )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Candidate assigned",
            message=f"{candidate_snapshot.get('candidate_name') or 'Candidate'} was assigned to {record.title}.",
            category="success",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="View request",
            metadata={"request_id": str(record.id), "assignment_id": str(saved.id)},
        )

        await self._write_activity(
            action="request_assigned",
            entity_type="assignment",
            entity_id=str(saved.id),
            current_user=current_user,
            new_status=RequestAssignmentStatus.OFFERED.value,
            metadata={"request_id": str(record.id), "assignee_tenant_id": str(assignee_tenant.id)},
        )

        return {
            "message": "Request assigned",
            "item": self._serialize_assignment(saved, request_snapshot=self._request_snapshot(record)),
        }

    async def _auto_complete_elapsed_assignment_docs(
        self,
        assignment_docs: List[Dict[str, Any]],
        request_lookup: Dict[str, Dict[str, Any]],
        assignment_collection,
    ) -> set[str]:
        now = datetime.utcnow()
        touched_request_ids: set[str] = set()
        for doc in assignment_docs:
            if self._assignment_scope_value(doc) != RequestAssignmentScope.REQUEST.value:
                continue

            current_status = self._enum_value(doc.get("assignment_status"))
            if current_status not in {status.value for status in AUTO_COMPLETE_ELAPSED_ASSIGNMENT_STATUSES}:
                continue

            request_snapshot = request_lookup.get(str(doc.get("request_id") or ""), {})
            if bool(request_snapshot.get("has_schedule")):
                continue
            requested_end_at = self._as_datetime(request_snapshot.get("requested_end_at"))
            if requested_end_at is None or requested_end_at > now:
                continue

            completed_at = doc.get("completed_at") or now
            doc["assignment_status"] = RequestAssignmentStatus.COMPLETED.value
            doc["completed_at"] = completed_at
            doc["updated_at"] = now
            await assignment_collection.update_one(
                {"_id": doc.get("_id")},
                {"$set": {
                    "assignment_status": RequestAssignmentStatus.COMPLETED.value,
                    "completed_at": completed_at,
                    "updated_at": now,
                }},
            )
            request_id = str(doc.get("request_id") or "").strip()
            if request_id:
                touched_request_ids.add(request_id)
        return touched_request_ids

    async def _auto_complete_elapsed_assignment_record(
        self,
        assignment: RequestAssignmentRecord,
        request_snapshot: Dict[str, Any],
    ) -> RequestAssignmentRecord:
        if self._assignment_scope_value(assignment) != RequestAssignmentScope.REQUEST.value:
            return assignment

        if assignment.assignment_status not in AUTO_COMPLETE_ELAPSED_ASSIGNMENT_STATUSES:
            return assignment

        if bool(request_snapshot.get("has_schedule")):
            return assignment

        requested_end_at = self._as_datetime(request_snapshot.get("requested_end_at"))
        if requested_end_at is None or requested_end_at > datetime.utcnow():
            return assignment

        now = datetime.utcnow()
        assignment.assignment_status = RequestAssignmentStatus.COMPLETED
        assignment.completed_at = assignment.completed_at or now
        assignment.updated_at = now
        await self._engine.save(assignment)
        return assignment

    async def list_jobs(self, current_user, page: int = 1, rows: int = 20, assignment_status: str = "", keyword: str = "") -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)

        if self._is_platform_role(role_value):
            query: Dict[str, Any] = {}
            session_tenant = None
        else:
            session_tenant = await self._get_session_tenant(current_user)

        if role_value == "client_admin" and session_tenant and session_tenant.tenant_type == TenantType.CLIENT:
            query = {"client_tenant_id": str(session_tenant.id)}
        elif role_value in {"guard_admin", "sp_admin"} and session_tenant and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            query = {"assignee_tenant_id": str(session_tenant.id)}
        elif not self._is_platform_role(role_value):
            raise HTTPException(status_code=403, detail="Access forbidden")

        normalized_status = self._normalize_text(assignment_status)
        if normalized_status:
            query["assignment_status"] = normalized_status

        docs = await assignment_collection.find(query).sort("updated_at", -1).to_list(length=None)
        request_collection = self._engine.get_collection(ClientRequestRecord)
        request_ids: List[ObjectId] = []
        for doc in docs:
            request_id = doc.get("request_id")
            if not request_id:
                continue
            try:
                request_ids.append(ObjectId(str(request_id)))
            except Exception:
                continue

        request_lookup: Dict[str, Dict[str, Any]] = {}
        active_schedule_request_ids: set[str] = set()
        if request_ids:
            request_docs = await request_collection.find({"_id": {"$in": request_ids}, "deleted_at": None}).to_list(length=None)
            active_schedule_request_ids = await self._request_ids_with_active_schedules([
                str(request_doc.get("_id") or "")
                for request_doc in request_docs
            ])
            for request_doc in request_docs:
                await self._ensure_request_doc_finance_snapshot(request_doc)
                request_doc["has_schedule"] = str(request_doc.get("_id") or "") in active_schedule_request_ids
                request_lookup[str(request_doc.get("_id"))] = self._request_snapshot(request_doc)

        should_auto_complete_elapsed_jobs = role_value in {"guard_admin", "sp_admin"}
        touched_request_ids: set[str] = set()
        if should_auto_complete_elapsed_jobs:
            touched_request_ids = await self._auto_complete_elapsed_assignment_docs(docs, request_lookup, assignment_collection)
        for request_id in touched_request_ids:
            if request_id not in request_lookup:
                continue
            try:
                request_record = await self._get_request_or_404(request_id)
            except HTTPException:
                continue
            if self._is_soft_deleted(request_record):
                continue
            await self._sync_request_runtime_state(request_record)
            setattr(request_record, "has_schedule", request_id in active_schedule_request_ids)
            request_lookup[request_id] = self._request_snapshot(request_record)

        normalized_keyword = self._normalize_text(keyword)
        filtered_docs: List[Dict[str, Any]] = []
        default_visible_statuses = (
            {status.value for status in DEFAULT_GUARD_PROVIDER_JOB_STATUSES}
            if not normalized_status and role_value in {"client_admin", "guard_admin", "sp_admin"}
            else None
        )
        for doc in docs:
            if normalized_status and self._enum_value(doc.get("assignment_status")) != normalized_status:
                continue
            if default_visible_statuses is not None and self._enum_value(doc.get("assignment_status")) not in default_visible_statuses:
                continue
            if str(doc.get("request_id") or "") not in request_lookup:
                continue
            request_snapshot = request_lookup.get(str(doc.get("request_id")), {})
            searchable_text = " ".join([
                self._normalize_text(request_snapshot.get("title")),
                self._normalize_text(request_snapshot.get("site_name")),
                self._normalize_text((doc.get("candidate_snapshot") or {}).get("candidate_name")),
            ])
            if normalized_keyword and normalized_keyword not in searchable_text:
                continue
            filtered_docs.append(doc)

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1
        total_items = len(filtered_docs)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        start = (safe_page - 1) * safe_rows
        end = start + safe_rows
        page_docs = filtered_docs[start:end]

        return {
            "items": [
                self._serialize_assignment(doc, request_snapshot=request_lookup.get(str(doc.get("request_id")), {}))
                for doc in page_docs
            ],
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "assignment_status": assignment_status,
                "keyword": keyword,
            },
        }

    async def update_job_status(self, assignment_id: str, payload: RequestAssignmentStatusUpdatePayload, current_user) -> Dict[str, Any]:
        assignment = await self._get_assignment_or_404(assignment_id)
        role_value = self._role_value(current_user)
        assignment_scope = self._assignment_scope_value(assignment)

        is_platform = self._is_platform_write_role(role_value)
        session_tenant = None if is_platform else await self._get_session_tenant(current_user)
        is_assignee = False if session_tenant is None else assignment.assignee_tenant_id == str(session_tenant.id)
        if not is_platform and not is_assignee:
            raise HTTPException(status_code=403, detail="Access forbidden")
        if not is_platform and role_value not in {"guard_admin", "sp_admin"}:
            raise HTTPException(status_code=403, detail="Only assigned guard/service-provider users can update job status")

        current_status = assignment.assignment_status
        next_status = payload.assignment_status
        if not is_platform and not self._allowed_assignment_transition(current_status, next_status):
            raise HTTPException(status_code=400, detail=f"Invalid transition from {current_status.value} to {next_status.value}")
        if next_status in {RequestAssignmentStatus.CANCELLED, RequestAssignmentStatus.DECLINED} and not (payload.reason or "").strip():
            raise HTTPException(status_code=400, detail="Reason is required when declining or cancelling a job")

        record = await self._get_request_or_404(assignment.request_id)
        await self._sync_request_runtime_state(record)

        if assignment.lock_reason in {
            AssignmentLockReason.FILLED,
            AssignmentLockReason.WAVE_EXPIRED,
            AssignmentLockReason.REQUEST_EXPIRED,
            AssignmentLockReason.SUPERSEDED,
            AssignmentLockReason.REQUEST_CANCELLED,
        }:
            raise HTTPException(status_code=409, detail="This offer is no longer actionable")

        reserved_slots = self._assignment_slots(assignment) if current_status in COMMITTED_SLOT_STATUSES else 0
        if assignment_scope == RequestAssignmentScope.SHIFT_REPLACEMENT.value and next_status in {
            RequestAssignmentStatus.IN_PROGRESS,
            RequestAssignmentStatus.COMPLETED,
        }:
            raise HTTPException(status_code=409, detail="Shift replacement jobs must use shift attendance actions instead of job status actions")
        if (
            assignment_scope == RequestAssignmentScope.REQUEST.value
            and next_status in {RequestAssignmentStatus.IN_PROGRESS, RequestAssignmentStatus.COMPLETED}
            and await self._request_has_active_schedule(str(record.id))
        ):
            raise HTTPException(
                status_code=409,
                detail="Scheduled request jobs must use shift attendance actions instead of generic job status actions",
            )
        if next_status == RequestAssignmentStatus.ACCEPTED and assignment_scope == RequestAssignmentScope.REQUEST.value:
            desired_slots = payload.slots_committed
            if assignment.assignee_tenant_type == RequestTargetType.GUARD:
                desired_slots = 1
            elif desired_slots is None:
                desired_slots = assignment.slots_committed or 0
                if desired_slots <= 0:
                    raise HTTPException(status_code=400, detail="Service provider acceptance requires committed slots")

            if assignment.assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER:
                request_address = cast(Dict[str, Any], record.site_snapshot.get("site_address") or {})
                request_latitude, request_longitude = self._validated_site_snapshot_coordinates(record.site_snapshot or {})
                provider_capacity = await RequestMatchingManager.get_instance().provider_available_guard_capacity(
                    assignment.assignee_tenant_id,
                    RequestMatchingPreviewPayload(
                        target_type="guard",
                        site_address=MatchAddress(
                            country=str(request_address.get("country") or "CA"),
                            province=str(request_address.get("province") or ""),
                            city=str(request_address.get("city") or ""),
                            latitude=request_latitude,
                            longitude=request_longitude,
                        ),
                        requested_guard_type=(record.requested_guard_type or "").strip() or None,
                        requested_start_at=record.requested_start_at,
                        requested_end_at=record.requested_end_at,
                        max_results=500,
                        fallback_to_province_when_missing_geo=False,
                    ),
                )
                available_provider_guards = int(provider_capacity.get("available_guard_count") or 0)
                if available_provider_guards <= 0:
                    raise HTTPException(
                        status_code=409,
                        detail="Service provider has no available linked guards for this request window",
                    )
                if int(desired_slots or 0) > available_provider_guards:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Service provider only has {available_provider_guards} available linked "
                            "guard(s) for this request window"
                        ),
                    )

            available_slots = int(record.open_slots or 0) + reserved_slots
            if int(desired_slots or 0) > available_slots:
                raise HTTPException(status_code=409, detail="All request slots have already been filled")
            assignment.slots_committed = int(desired_slots or 1)
        elif next_status == RequestAssignmentStatus.ACCEPTED and assignment_scope == RequestAssignmentScope.SHIFT_REPLACEMENT.value:
            assignment.slots_committed = 1

        previous_open_slots = int(record.open_slots or 0)
        now = self._assert_request_job_status_action_window(record, next_status)
        assignment.assignment_status = next_status
        assignment.updated_at = now
        if next_status == RequestAssignmentStatus.ACCEPTED:
            assignment.accepted_at = assignment.accepted_at or now
            if current_status == RequestAssignmentStatus.RECONFIRMATION_REQUIRED:
                assignment.reconfirmed_at = now
        elif next_status == RequestAssignmentStatus.DECLINED:
            assignment.declined_at = now
        elif next_status == RequestAssignmentStatus.IN_PROGRESS:
            assignment.started_at = now
        elif next_status == RequestAssignmentStatus.COMPLETED:
            assignment.completed_at = now
        elif next_status == RequestAssignmentStatus.CANCELLED:
            assignment.cancelled_at = now
        if payload.reason is not None:
            assignment.note = payload.reason.strip() or assignment.note
        await self._engine.save(assignment)

        if next_status == RequestAssignmentStatus.IN_PROGRESS and record.request_status in {RequestStatus.SUBMITTED, RequestStatus.ASSIGNED}:
            record.request_status = RequestStatus.IN_PROGRESS
            await self._engine.save(record)

        if assignment_scope == RequestAssignmentScope.REQUEST.value:
            await self._sync_request_runtime_state(record)
        if assignment_scope == RequestAssignmentScope.REQUEST.value and previous_open_slots == 0 and record.open_slots > 0 and record.request_status in {RequestStatus.SUBMITTED, RequestStatus.ASSIGNED} and record.staffing_status != RequestStaffingStatus.EXPIRED:
            await self._create_wave_from_current_snapshot(
                record,
                trigger=RequestWaveTrigger.CAPACITY_REOPENED,
                current_user=current_user,
                refresh_matches=False,
                max_match_results=max(int(record.match_summary.get("returned_count") or 25), 25),
            )

        if assignment_scope == RequestAssignmentScope.SHIFT_REPLACEMENT.value and next_status == RequestAssignmentStatus.ACCEPTED:
            from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager

            shift_manager = RequestShiftManager.get_instance()
            if not assignment.shift_slot_id:
                raise HTTPException(status_code=400, detail="Shift replacement assignment is missing shift slot context")
            slot_record = await shift_manager._get_shift_slot_or_404(assignment.shift_slot_id)
            if slot_record.slot_status != ShiftSlotStatus.OPEN:
                raise HTTPException(status_code=409, detail="This replacement shift slot is no longer open")
            slot_record.parent_assignment_id = str(assignment.id)
            slot_record.coverage_source_type = (
                ShiftCoverageSourceType.SERVICE_PROVIDER
                if assignment.assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER
                else ShiftCoverageSourceType.DIRECT_GUARD
            )
            slot_record.coverage_tenant_id = assignment.assignee_tenant_id
            slot_record.service_provider_tenant_id = (
                assignment.assignee_tenant_id if assignment.assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER else None
            )
            slot_record.assigned_guard_tenant_id = (
                assignment.assignee_tenant_id if assignment.assignee_tenant_type == RequestTargetType.GUARD else None
            )
            slot_record.slot_status = ShiftSlotStatus.RESERVED
            slot_record.rostered_at = now if assignment.assignee_tenant_type == RequestTargetType.SERVICE_PROVIDER else None
            slot_record.guard_unavailable_reported_at = None
            slot_record.arrived_at = None
            slot_record.client_confirmed_at = None
            slot_record.started_at = None
            slot_record.checked_out_at = None
            slot_record.completed_at = None
            slot_record.no_show_confirmed_at = None
            slot_record.geo_check_passed = None
            slot_record.actual_start_at = None
            slot_record.actual_end_at = None
            slot_record.updated_at = now
            await shift_manager._engine.save(slot_record)
            shift_record = await shift_manager._get_shift_or_404(slot_record.shift_instance_id)
            await shift_manager._record_slot_event(
                slot_record,
                shift_record,
                record,
                current_user,
                ShiftAttendanceEventType.REPLACEMENT_ASSIGNED,
                note=payload.reason,
                metadata={"assignment_id": str(assignment.id), "assignee_tenant_id": assignment.assignee_tenant_id},
            )
            await shift_manager._refresh_shift_progress(shift_record)

        if (
            assignment_scope == RequestAssignmentScope.REQUEST.value
            and (next_status in COMMITTED_SLOT_STATUSES or current_status in COMMITTED_SLOT_STATUSES)
        ):
            from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager

            await RequestShiftManager.get_instance().sync_shift_slots_for_request(record)
            assignment = await self._get_assignment_or_404(str(assignment.id))

        request_title = record.title
        request_snapshot = self._request_snapshot(record)
        request_snapshot["has_schedule"] = await self._request_has_active_schedule(str(record.id))

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=assignment.client_tenant_id,
            title="Job status updated",
            message=f"{request_title}: assignment is now {next_status.value}.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="requests", request_id=str(record.id)),
            action_label="Open requests",
            metadata={"assignment_id": str(assignment.id), "request_id": assignment.request_id, "assignment_status": next_status.value},
        )
        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=assignment.assignee_tenant_id,
            title="Job status updated",
            message=f"{request_title}: assignment is now {next_status.value}.",
            category="success" if next_status in {RequestAssignmentStatus.ACCEPTED, RequestAssignmentStatus.COMPLETED} else "info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="jobs", assignment_id=str(assignment.id)),
            action_label="Open jobs",
            metadata={"assignment_id": str(assignment.id), "request_id": assignment.request_id, "assignment_status": next_status.value},
        )

        await self._write_activity(
            action="assignment_status_updated",
            entity_type="assignment",
            entity_id=str(assignment.id),
            current_user=current_user,
            previous_status=current_status.value,
            new_status=next_status.value,
            reason=payload.reason,
            metadata={"request_id": assignment.request_id},
            severity="warning" if next_status in {RequestAssignmentStatus.CANCELLED, RequestAssignmentStatus.DECLINED} else "info",
        )

        return {
            "message": "Job status updated",
            "item": self._serialize_assignment(assignment, request_snapshot=request_snapshot),
        }
