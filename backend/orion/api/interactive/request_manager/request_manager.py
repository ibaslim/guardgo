import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlencode

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
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import PLATFORM_ADMIN_ROLES, normalize_role_value
from orion.services.mongo_manager.shared_model.db_request_model import (
    AssignmentLockReason,
    BroadcastReviewReasonCode,
    ClientRequestCreatePayload,
    ClientRequestRecord,
    ClientRequestStatusUpdatePayload,
    ClientRequestUpdatePayload,
    RequestAdditionalCoveragePayload,
    RequestAssignmentCreatePayload,
    RequestAssignmentOrigin,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestAssignmentStatusUpdatePayload,
    RequestBroadcastWaveRecord,
    RequestFulfillmentMode,
    RequestLockReason,
    RequestPublishPayload,
    RequestPublishUpdatePayload,
    RequestSiteInput,
    RequestStaffingStatus,
    RequestStatus,
    RequestTargetType,
    RequestWaveReviewPayload,
    RequestWaveStatus,
    RequestWaveTrigger,
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
        return {
            "id": str(record.get("_id") if isinstance(record, dict) else record.id),
            "title": record.get("title") if isinstance(record, dict) else record.title,
            "request_status": cls._enum_value(record.get("request_status") if isinstance(record, dict) else record.request_status),
            "staffing_status": cls._enum_value(record.get("staffing_status") if isinstance(record, dict) else record.staffing_status),
            "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
            "target_type": cls._enum_value(record.get("target_type") if isinstance(record, dict) else record.target_type),
            "site_name": ((site_snapshot or {}).get("site_name") or ""),
            "requested_start_at": record.get("requested_start_at") if isinstance(record, dict) else record.requested_start_at,
            "requested_end_at": record.get("requested_end_at") if isinstance(record, dict) else record.requested_end_at,
            "request_revision": int(record.get("request_revision") or 0) if isinstance(record, dict) else record.request_revision,
            "request_expires_at": record.get("request_expires_at") if isinstance(record, dict) else record.request_expires_at,
            "accepted_slots": int(record.get("accepted_slots") or 0) if isinstance(record, dict) else record.accepted_slots,
            "open_slots": int(record.get("open_slots") or 0) if isinstance(record, dict) else record.open_slots,
        }

    @classmethod
    def _serialize(cls, record: ClientRequestRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            guards_required = int(record.get("guards_required") or 0)
            accepted_slots = int(record.get("accepted_slots") or 0)
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "client_tenant_id": record.get("client_tenant_id"),
                "created_by_user_id": record.get("created_by_user_id"),
                "created_by_username": record.get("created_by_username"),
                "title": record.get("title") or "",
                "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
                "target_type": cls._enum_value(record.get("target_type")),
                "requested_guard_type": record.get("requested_guard_type"),
                "guards_required": guards_required,
                "request_status": cls._enum_value(record.get("request_status")),
                "staffing_status": cls._enum_value(record.get("staffing_status")),
                "lock_reason": cls._enum_value(record.get("lock_reason"), default="") or None,
                "site_snapshot": record.get("site_snapshot") or {},
                "special_instructions": record.get("special_instructions"),
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
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }

        return {
            "id": str(record.id),
            "client_tenant_id": record.client_tenant_id,
            "created_by_user_id": record.created_by_user_id,
            "created_by_username": record.created_by_username,
            "title": record.title,
            "fulfillment_mode": cls._resolve_fulfillment_mode_from_record(record).value,
            "target_type": cls._enum_value(record.target_type),
            "requested_guard_type": record.requested_guard_type,
            "guards_required": record.guards_required,
            "request_status": cls._enum_value(record.request_status),
            "staffing_status": cls._enum_value(record.staffing_status),
            "lock_reason": cls._enum_value(record.lock_reason, default="") or None,
            "site_snapshot": record.site_snapshot or {},
            "special_instructions": record.special_instructions,
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
            "created_at": record.created_at,
            "updated_at": record.updated_at,
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
                "broadcast_wave_id": record.get("broadcast_wave_id"),
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
            "id": str(record.id),
            "request_id": record.request_id,
            "client_tenant_id": record.client_tenant_id,
            "assignee_tenant_id": record.assignee_tenant_id,
            "assignee_tenant_type": cls._enum_value(record.assignee_tenant_type),
            "assignment_status": cls._enum_value(record.assignment_status),
            "assignment_origin": cls._enum_value(record.assignment_origin),
            "broadcast_wave_id": record.broadcast_wave_id,
            "request_revision_at_offer": record.request_revision_at_offer,
            "slots_committed": record.slots_committed,
            "response_due_at": record.response_due_at,
            "reconfirmation_due_at": record.reconfirmation_due_at,
            "lock_reason": cls._enum_value(record.lock_reason, default="") or None,
            "candidate_snapshot": record.candidate_snapshot or {},
            "assigned_by_user_id": record.assigned_by_user_id,
            "assigned_by_username": record.assigned_by_username,
            "note": record.note,
            "offered_at": record.offered_at,
            "accepted_at": record.accepted_at,
            "declined_at": record.declined_at,
            "expired_at": record.expired_at,
            "reconfirmation_requested_at": record.reconfirmation_requested_at,
            "reconfirmed_at": record.reconfirmed_at,
            "closed_filled_at": record.closed_filled_at,
            "superseded_at": record.superseded_at,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "cancelled_at": record.cancelled_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "request": request_snapshot or {},
        }

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

        try:
            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid client tenant id")

        if not tenant or tenant.tenant_type != TenantType.CLIENT:
            raise HTTPException(status_code=403, detail="Client request workflow is only available for client tenants")
        if tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Client tenant must be active before requests can be created")
        return tenant

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
            return await request_collection.find({}).to_list(length=None)

        session_tenant = await self._get_session_tenant(current_user)
        tenant_id = str(session_tenant.id)

        if role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            return await request_collection.find({"client_tenant_id": tenant_id}).to_list(length=None)

        if role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
            assignment_docs = await assignment_collection.find({"assignee_tenant_id": tenant_id}).to_list(length=None)
            request_ids = [doc.get("request_id") for doc in assignment_docs if doc.get("request_id")]
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
            return await request_collection.find({"_id": {"$in": object_ids}}).to_list(length=None)

        raise HTTPException(status_code=403, detail="Access forbidden")

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
                "latitude": site_address.get("latitude"),
                "longitude": site_address.get("longitude"),
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
        if (latitude is None) != (longitude is None):
            raise HTTPException(status_code=400, detail="Provide both latitude and longitude or leave both empty")
        if latitude is not None and not (-90 <= latitude <= 90):
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
        if longitude is not None and not (-180 <= longitude <= 180):
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
        requested_start_at: Optional[datetime] = None,
        requested_end_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        request_address = cast(Dict[str, Any], site_snapshot.get("site_address") or {})
        match_payload = RequestMatchingPreviewPayload(
            target_type=target_type,
            site_address=MatchAddress(
                country=str(request_address.get("country") or "CA"),
                province=str(request_address.get("province") or ""),
                city=str(request_address.get("city") or ""),
                latitude=request_address.get("latitude"),
                longitude=request_address.get("longitude"),
            ),
            requested_start_at=requested_start_at,
            requested_end_at=requested_end_at,
            max_results=max_results,
            fallback_to_province_when_missing_geo=True,
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
        requested_start_at: Optional[datetime] = None,
        requested_end_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if fulfillment_mode == RequestFulfillmentMode.HYBRID:
            guard_preview = await self._preview_matches_for_target(
                cast(TargetType, "guard"),
                site_snapshot,
                max_results,
                requested_start_at,
                requested_end_at,
            )
            provider_preview = await self._preview_matches_for_target(
                cast(TargetType, "service_provider"),
                site_snapshot,
                max_results,
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

    async def _has_active_assignment_for_candidate(self, request_id: str, assignee_tenant_id: str) -> bool:
        assignments = await self._get_assignments_for_request(request_id)
        for assignment in assignments:
            if assignment.assignee_tenant_id != str(assignee_tenant_id):
                continue
            if assignment.assignment_status in ACTIONABLE_ASSIGNMENT_STATUSES:
                return True
        return False

    async def _evaluate_broadcast_snapshot(self, record: ClientRequestRecord) -> Dict[str, Any]:
        site_address = cast(Dict[str, Any], (record.site_snapshot or {}).get("site_address") or {})
        province = str(site_address.get("province") or "").strip().upper()
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
            if assignment.assignment_status in COMMITTED_SLOT_STATUSES:
                accepted_slots += self._assignment_slots(assignment)

        previous_open_slots = record.open_slots
        record.accepted_slots = accepted_slots
        record.open_slots = max(int(record.guards_required or 0) - accepted_slots, 0)

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
        for candidate in wave.candidate_snapshots or []:
            if not bool(candidate.get("eligible")):
                continue
            if not bool(candidate.get("broadcast_eligible")):
                continue

            assignee_tenant_id = str(candidate.get("candidate_id") or "").strip()
            if not assignee_tenant_id:
                continue

            if await self._has_active_assignment_for_candidate(str(record.id), assignee_tenant_id):
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
                broadcast_wave_id=str(wave.id),
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
            title="New request offer",
            message=f"{record.title} is available for review.",
            category="info",
            source_module="requests",
            action_url=self._dashboard_requests_url(tab="jobs", assignment_id=str(saved.id)),
            action_label="Review offer",
                metadata={
                    "request_id": str(record.id),
                    "assignment_id": str(saved.id),
                    "broadcast_wave_id": str(wave.id),
                    "request_revision": record.request_revision,
                    "wave_number": wave.wave_number,
                    "assignment_origin": RequestAssignmentOrigin.BROADCAST.value,
                },
            )

        wave.offer_count = created_count
        wave.updated_at = now
        await self._engine.save(wave)
        return created_count

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
        self._validate_request_expiry(record.request_expires_at, record.requested_start_at, require_value=True)
        self._validate_requested_window(record.requested_start_at, record.requested_end_at)

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

        return {
            "message": wave_message,
            "item": self._serialize(record),
            "wave": self._serialize_wave(wave) if wave else None,
        }

    async def create_request(self, payload: ClientRequestCreatePayload, current_user) -> Dict[str, Any]:
        client_tenant = await self._get_client_tenant(current_user)
        client_profile = client_tenant.profile if isinstance(client_tenant.profile, dict) else {}
        site_snapshot = self._resolve_site_snapshot(payload, client_profile)
        title = self._validate_trimmed_title(payload.title)
        self._validate_requested_window(payload.requested_start_at, payload.requested_end_at)
        if payload.request_expires_at is not None:
            self._validate_request_expiry(payload.request_expires_at, payload.requested_start_at, require_value=False)

        preview = await self._preview_matches_for_request(
            payload.fulfillment_mode,
            site_snapshot,
            payload.max_match_results,
            payload.requested_start_at,
            payload.requested_end_at,
        )

        now = datetime.utcnow()
        record = ClientRequestRecord(
            id=ObjectId(),
            client_tenant_id=str(client_tenant.id),
            created_by_user_id=str(getattr(current_user, "id", "") or ""),
            created_by_username=str(getattr(current_user, "username", "") or ""),
            title=title,
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

    async def update_request(self, request_id: str, payload: ClientRequestUpdatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
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

        max_results = payload.max_match_results if payload.max_match_results is not None else 25
        await self._refresh_request_matching(record, max_results)
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)

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

    async def list_requests(self, current_user, page: int = 1, rows: int = 20, keyword: str = "", request_status: str = "", fulfillment_mode: str = "") -> Dict[str, Any]:
        docs = await self._resolve_request_docs_for_role(current_user)
        normalized_keyword = self._normalize_text(keyword)
        normalized_status = self._normalize_text(request_status)
        normalized_fulfillment_mode = self._normalize_text(fulfillment_mode)

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

        return {
            "items": [self._serialize(doc) for doc in page_docs],
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
            },
        }

    async def get_request_by_id(self, request_id: str, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")
        await self._sync_request_runtime_state(record)
        return self._serialize(record)

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
        await self._sync_request_runtime_state(record)
        return self._serialize_assignment(assignment, request_snapshot=self._request_snapshot(record))

    async def publish_request(self, request_id: str, payload: RequestPublishPayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
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
        if "requested_start_at" in provided and payload.requested_start_at != record.requested_start_at:
            record.requested_start_at = payload.requested_start_at
            changed = True
        if "requested_end_at" in provided and payload.requested_end_at != record.requested_end_at:
            record.requested_end_at = payload.requested_end_at
            changed = True
        if "special_instructions" in provided and (payload.special_instructions or "").strip() != (record.special_instructions or ""):
            record.special_instructions = (payload.special_instructions or "").strip() or None
            changed = True
        if "request_expires_at" in provided:
            self._validate_request_expiry(payload.request_expires_at, record.requested_start_at, require_value=True)
            record.request_expires_at = payload.request_expires_at

        self._validate_requested_window(record.requested_start_at, record.requested_end_at)
        self._validate_request_expiry(record.request_expires_at, record.requested_start_at, require_value=True)
        if not changed:
            raise HTTPException(status_code=400, detail="Publish update requires a material request change")

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

        record.request_revision = max(int(record.request_revision or 0) + 1, 1)
        await self._refresh_request_matching(record, payload.max_match_results)
        await self._sync_request_runtime_state(record)

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
        await self._sync_request_runtime_state(record)
        if record.staffing_status == RequestStaffingStatus.EXPIRED:
            raise HTTPException(status_code=400, detail="Expired requests cannot be approved for broadcast")

        await self._set_wave_status(wave, RequestWaveStatus.ACTIVE, current_user=current_user, note=payload.note)
        record.active_wave_id = str(wave.id)
        if record.lock_reason == RequestLockReason.REVIEW_PENDING:
            record.lock_reason = None
        await self._engine.save(record)

        offers = await self._activate_wave(wave, record, current_user)
        await self._sync_request_runtime_state(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Broadcast approved",
            message=f"{record.title}: platform review approved the broadcast wave.",
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
        await self._set_wave_status(wave, RequestWaveStatus.RETURNED, current_user=current_user, note=payload.note)
        record.staffing_status = RequestStaffingStatus.REVIEW_RETURNED
        record.lock_reason = None
        record.active_wave_id = None
        record.updated_at = datetime.utcnow()
        await self._engine.save(record)

        await NotificationManager.get_instance().create_for_tenant_admin_users(
            tenant_id=record.client_tenant_id,
            title="Broadcast returned",
            message=f"{record.title}: platform review returned the request for correction.",
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

    async def create_assignment(self, request_id: str, payload: RequestAssignmentCreatePayload, current_user) -> Dict[str, Any]:
        record = await self._get_request_or_404(request_id)
        session_tenant = await self._get_session_tenant(current_user)
        role_value = self._role_value(current_user)

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
            action_url=self._dashboard_requests_url(tab="jobs", assignment_id=str(saved.id)),
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

    async def list_jobs(self, current_user, page: int = 1, rows: int = 20, assignment_status: str = "", keyword: str = "") -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        session_tenant = await self._get_session_tenant(current_user)
        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)

        if self._is_platform_role(role_value):
            query: Dict[str, Any] = {}
        elif role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            query = {"client_tenant_id": str(session_tenant.id)}
        elif role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            query = {"assignee_tenant_id": str(session_tenant.id)}
        else:
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
        if request_ids:
            request_docs = await request_collection.find({"_id": {"$in": request_ids}}).to_list(length=None)
            for request_doc in request_docs:
                request_lookup[str(request_doc.get("_id"))] = self._request_snapshot(request_doc)

        normalized_keyword = self._normalize_text(keyword)
        filtered_docs: List[Dict[str, Any]] = []
        for doc in docs:
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
        session_tenant = await self._get_session_tenant(current_user)

        is_platform = self._is_platform_write_role(role_value)
        is_assignee = assignment.assignee_tenant_id == str(session_tenant.id)
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
        if next_status == RequestAssignmentStatus.ACCEPTED:
            desired_slots = payload.slots_committed
            if assignment.assignee_tenant_type == RequestTargetType.GUARD:
                desired_slots = 1
            elif desired_slots is None:
                desired_slots = assignment.slots_committed or 0
                if desired_slots <= 0:
                    raise HTTPException(status_code=400, detail="Service provider acceptance requires committed slots")

            available_slots = int(record.open_slots or 0) + reserved_slots
            if int(desired_slots or 0) > available_slots:
                raise HTTPException(status_code=409, detail="All request slots have already been filled")
            assignment.slots_committed = int(desired_slots or 1)

        previous_open_slots = int(record.open_slots or 0)
        now = datetime.utcnow()
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

        await self._sync_request_runtime_state(record)
        if previous_open_slots == 0 and record.open_slots > 0 and record.request_status in {RequestStatus.SUBMITTED, RequestStatus.ASSIGNED} and record.staffing_status != RequestStaffingStatus.EXPIRED:
            await self._create_wave_from_current_snapshot(
                record,
                trigger=RequestWaveTrigger.CAPACITY_REOPENED,
                current_user=current_user,
                refresh_matches=False,
                max_match_results=max(int(record.match_summary.get("returned_count") or 25), 25),
            )

        request_title = record.title
        request_snapshot = self._request_snapshot(record)

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
