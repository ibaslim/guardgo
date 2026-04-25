import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.activity_manager.activity_manager import ActivityManager
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
    ClientRequestCreatePayload,
    ClientRequestRecord,
    ClientRequestStatusUpdatePayload,
    ClientRequestUpdatePayload,
    RequestAssignmentCreatePayload,
    RequestAssignmentRecord,
    RequestAssignmentStatus,
    RequestAssignmentStatusUpdatePayload,
    RequestSiteInput,
    RequestStatus,
    RequestTargetType,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantStatus, TenantType


PLATFORM_WRITE_ROLES = {
    "admin",
    "ops_admin",
    "support_admin",
    "compliance_admin",
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
    def _target_type_to_tenant_type(target_type: RequestTargetType) -> TenantType:
        return TenantType.GUARD if target_type == RequestTargetType.GUARD else TenantType.SERVICE_PROVIDER

    @staticmethod
    def _allowed_assignment_transition(current_status: RequestAssignmentStatus, next_status: RequestAssignmentStatus) -> bool:
        allowed = {
            RequestAssignmentStatus.OFFERED: {RequestAssignmentStatus.ACCEPTED, RequestAssignmentStatus.DECLINED},
            RequestAssignmentStatus.ACCEPTED: {RequestAssignmentStatus.IN_PROGRESS, RequestAssignmentStatus.CANCELLED},
            RequestAssignmentStatus.IN_PROGRESS: {RequestAssignmentStatus.COMPLETED, RequestAssignmentStatus.CANCELLED},
        }
        return next_status in allowed.get(current_status, set())

    @staticmethod
    def _allowed_request_status_transition(current_status: RequestStatus, next_status: RequestStatus) -> bool:
        allowed = {
            RequestStatus.DRAFT: {RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
            RequestStatus.SUBMITTED: {RequestStatus.ASSIGNED, RequestStatus.CANCELLED, RequestStatus.CLOSED},
            RequestStatus.ASSIGNED: {RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED, RequestStatus.CLOSED},
            RequestStatus.IN_PROGRESS: {RequestStatus.CLOSED, RequestStatus.CANCELLED},
        }
        return next_status in allowed.get(current_status, set())

    @staticmethod
    def _serialize(record: ClientRequestRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "client_tenant_id": record.get("client_tenant_id"),
                "created_by_user_id": record.get("created_by_user_id"),
                "created_by_username": record.get("created_by_username"),
                "title": record.get("title") or "",
                "target_type": record.get("target_type"),
                "requested_guard_type": record.get("requested_guard_type"),
                "guards_required": record.get("guards_required") or 0,
                "request_status": record.get("request_status"),
                "site_snapshot": record.get("site_snapshot") or {},
                "special_instructions": record.get("special_instructions"),
                "requested_start_at": record.get("requested_start_at"),
                "requested_end_at": record.get("requested_end_at"),
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
            "target_type": record.target_type.value if hasattr(record.target_type, 'value') else str(record.target_type),
            "requested_guard_type": record.requested_guard_type,
            "guards_required": record.guards_required,
            "request_status": record.request_status.value if hasattr(record.request_status, 'value') else str(record.request_status),
            "site_snapshot": record.site_snapshot or {},
            "special_instructions": record.special_instructions,
            "requested_start_at": record.requested_start_at,
            "requested_end_at": record.requested_end_at,
            "match_summary": record.match_summary or {},
            "matched_candidates": record.matched_candidates or [],
            "cancelled_at": record.cancelled_at,
            "closed_at": record.closed_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _serialize_assignment(record: RequestAssignmentRecord | Dict[str, Any], request_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if isinstance(record, dict):
            return {
                "id": str(record.get("_id") or record.get("id") or ""),
                "request_id": record.get("request_id") or "",
                "client_tenant_id": record.get("client_tenant_id") or "",
                "assignee_tenant_id": record.get("assignee_tenant_id") or "",
                "assignee_tenant_type": record.get("assignee_tenant_type") or "",
                "assignment_status": record.get("assignment_status") or "",
                "candidate_snapshot": record.get("candidate_snapshot") or {},
                "assigned_by_user_id": record.get("assigned_by_user_id") or "",
                "assigned_by_username": record.get("assigned_by_username") or "",
                "note": record.get("note"),
                "offered_at": record.get("offered_at"),
                "accepted_at": record.get("accepted_at"),
                "declined_at": record.get("declined_at"),
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
            "assignee_tenant_type": record.assignee_tenant_type.value if hasattr(record.assignee_tenant_type, "value") else str(record.assignee_tenant_type),
            "assignment_status": record.assignment_status.value if hasattr(record.assignment_status, "value") else str(record.assignment_status),
            "candidate_snapshot": record.candidate_snapshot or {},
            "assigned_by_user_id": record.assigned_by_user_id,
            "assigned_by_username": record.assigned_by_username,
            "note": record.note,
            "offered_at": record.offered_at,
            "accepted_at": record.accepted_at,
            "declined_at": record.declined_at,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "cancelled_at": record.cancelled_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "request": request_snapshot or {},
        }

    async def _get_tenant(self, tenant_id: str):
        try:
            return await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            return None

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
        tenant_type = session_tenant.tenant_type

        if role_value == "client_admin" and tenant_type == TenantType.CLIENT:
            return await request_collection.find({"client_tenant_id": tenant_id}).to_list(length=None)

        if role_value in {"guard_admin", "sp_admin"} and tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
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
            # Activity logs are best-effort and should not break request flows.
            return

    def _resolve_saved_site_snapshot(self, client_profile: Dict[str, Any], site_index: int) -> Dict[str, Any]:
        raw_sites = client_profile.get("sites") if isinstance(client_profile.get("sites"), list) else []
        if not raw_sites:
            raise HTTPException(status_code=400, detail="Add at least one client site before creating a request")
        if site_index < 0 or site_index >= len(raw_sites):
            raise HTTPException(status_code=400, detail="Selected site is invalid")

        site: Dict[str, Any] = raw_sites[site_index] if isinstance(raw_sites[site_index], dict) else {}
        raw_site_address = site.get("site_address")
        if isinstance(raw_site_address, dict):
            site_address: Dict[str, Any] = cast(Dict[str, Any], raw_site_address)
        else:
            site_address = {}
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

    async def _preview_matches_for_request(self, target_type: RequestTargetType, site_snapshot: Dict[str, Any], max_results: int) -> Any:
        request_address = cast(Dict[str, Any], site_snapshot.get("site_address") or {})
        normalized_target = cast(TargetType, "service_provider" if target_type == RequestTargetType.SERVICE_PROVIDER else "guard")
        match_payload = RequestMatchingPreviewPayload(
            target_type=normalized_target,
            site_address=MatchAddress(
                country=str(request_address.get("country") or "CA"),
                province=str(request_address.get("province") or ""),
                city=str(request_address.get("city") or ""),
                latitude=request_address.get("latitude"),
                longitude=request_address.get("longitude"),
            ),
            max_results=max_results,
            fallback_to_province_when_missing_geo=True,
        )
        return await RequestMatchingManager.get_instance().preview_matches(match_payload)

    async def _ensure_request_is_editable(self, record: ClientRequestRecord) -> None:
        if record.request_status != RequestStatus.DRAFT:
            raise HTTPException(status_code=400, detail="Only draft requests can be edited")

    async def create_request(self, payload: ClientRequestCreatePayload, current_user) -> Dict[str, Any]:
        client_tenant = await self._get_client_tenant(current_user)
        client_profile = client_tenant.profile if isinstance(client_tenant.profile, dict) else {}
        site_snapshot = self._resolve_site_snapshot(payload, client_profile)
        match_preview = await self._preview_matches_for_request(payload.target_type, site_snapshot, payload.max_match_results)
        title = self._validate_trimmed_title(payload.title)
        self._validate_requested_window(payload.requested_start_at, payload.requested_end_at)

        request_status = RequestStatus.SUBMITTED if payload.commit else RequestStatus.DRAFT

        now = datetime.utcnow()
        record = ClientRequestRecord(
            id=ObjectId(),
            client_tenant_id=str(client_tenant.id),
            created_by_user_id=str(getattr(current_user, "id", "") or ""),
            created_by_username=str(getattr(current_user, "username", "") or ""),
            title=title,
            target_type=payload.target_type,
            requested_guard_type=(payload.requested_guard_type or "").strip() or None,
            guards_required=int(payload.guards_required or 1),
            request_status=request_status,
            site_snapshot=site_snapshot,
            special_instructions=(payload.special_instructions or "").strip() or None,
            requested_start_at=payload.requested_start_at,
            requested_end_at=payload.requested_end_at,
            match_summary=match_preview.summary,
            matched_candidates=[candidate.model_dump() for candidate in match_preview.results],
            created_at=now,
            updated_at=now,
        )
        saved = await self._engine.save(record)

        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=str(client_tenant.id),
            title="Client request created" if payload.commit else "Request draft saved",
            message=f"{title} was {'submitted' if payload.commit else 'saved as draft'} with {match_preview.summary.get('eligible_count', 0)} eligible candidate matches.",
            category="success" if payload.commit else "info",
            source_module="requests",
            action_url="/dashboard/requests",
            action_label="Open requests",
            metadata={
                "request_id": str(saved.id),
                "target_type": match_preview.summary.get("target_type"),
                "eligible_count": match_preview.summary.get("eligible_count", 0),
                "request_status": request_status.value,
            },
        )

        await self._write_activity(
            action="request_created",
            entity_type="request",
            entity_id=str(saved.id),
            current_user=current_user,
            new_status=request_status.value,
            metadata={"target_type": payload.target_type.value},
        )

        return {
            "message": "Client request created" if payload.commit else "Request draft saved",
            "item": self._serialize(saved),
        }

    async def update_request(self, request_id: str, payload: ClientRequestUpdatePayload, current_user) -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        try:
            object_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request id")

        record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request not found")

        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")

        if not self._is_platform_write_role(role_value):
            session_tenant = await self._get_session_tenant(current_user)
            if not (role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT and record.client_tenant_id == str(session_tenant.id)):
                raise HTTPException(status_code=403, detail="Only platform admins or owning client admins can edit requests")

        await self._ensure_request_is_editable(record)
        provided = payload.model_dump(exclude_unset=True)

        if "title" in provided and payload.title is not None:
            record.title = self._validate_trimmed_title(payload.title)
        if "target_type" in provided and payload.target_type is not None:
            record.target_type = payload.target_type
        if "requested_guard_type" in provided:
            record.requested_guard_type = (payload.requested_guard_type or "").strip() or None
        if "guards_required" in provided and payload.guards_required is not None:
            record.guards_required = int(payload.guards_required)
        if "special_instructions" in provided:
            record.special_instructions = (payload.special_instructions or "").strip() or None

        if "requested_start_at" in provided:
            record.requested_start_at = payload.requested_start_at
        if "requested_end_at" in provided:
            record.requested_end_at = payload.requested_end_at

        self._validate_requested_window(record.requested_start_at, record.requested_end_at)

        if "site" in provided and payload.site is not None:
            record.site_snapshot = self._resolve_site_input_snapshot(payload.site)

        max_results = payload.max_match_results if payload.max_match_results is not None else 25
        match_preview = await self._preview_matches_for_request(record.target_type, record.site_snapshot or {}, max_results)
        record.match_summary = match_preview.summary
        record.matched_candidates = [candidate.model_dump() for candidate in match_preview.results]
        record.updated_at = datetime.utcnow()

        await self._engine.save(record)

        await self._write_activity(
            action="request_updated",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=RequestStatus.DRAFT.value,
            new_status=RequestStatus.DRAFT.value,
            metadata={"request_id": str(record.id)},
        )

        return {
            "message": "Request draft updated",
            "item": self._serialize(record),
        }

    async def list_requests(self, current_user, page: int = 1, rows: int = 20, keyword: str = "", request_status: str = "", target_type: str = "") -> Dict[str, Any]:
        docs = await self._resolve_request_docs_for_role(current_user)

        normalized_keyword = self._normalize_text(keyword)
        normalized_status = self._normalize_text(request_status)
        normalized_target = self._normalize_text(target_type)

        filtered_docs: List[Dict[str, Any]] = []
        for doc in docs:
            title = self._normalize_text(doc.get("title"))
            current_status = self._normalize_text(doc.get("request_status"))
            current_target = self._normalize_text(doc.get("target_type"))
            site_name = self._normalize_text((doc.get("site_snapshot") or {}).get("site_name"))
            guard_type = self._normalize_text(doc.get("requested_guard_type"))

            if normalized_status and current_status != normalized_status:
                continue
            if normalized_target and current_target != normalized_target:
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
                "target_type": target_type,
            },
        }

    async def get_request_by_id(self, request_id: str, current_user) -> Dict[str, Any]:
        try:
            object_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request id")

        record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request not found")

        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")

        return self._serialize(record)

    async def update_request_status(self, request_id: str, payload: ClientRequestStatusUpdatePayload, current_user) -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        try:
            object_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request id")

        record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == object_id)
        if not record:
            raise HTTPException(status_code=404, detail="Request not found")

        if not await self._can_view_request(record, current_user):
            raise HTTPException(status_code=403, detail="Access forbidden")

        if not self._is_platform_write_role(role_value):
            session_tenant = await self._get_session_tenant(current_user)
            if not (role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT and record.client_tenant_id == str(session_tenant.id)):
                raise HTTPException(status_code=403, detail="Only platform admins or owning client admins can update request status")

        if self._is_platform_write_role(role_value) and payload.reason is None:
            raise HTTPException(status_code=400, detail="Reason is required for platform admin overrides")

        previous_status = record.request_status.value if hasattr(record.request_status, "value") else str(record.request_status)
        if not self._allowed_request_status_transition(record.request_status, payload.request_status):
            raise HTTPException(status_code=400, detail=f"Invalid request transition from {record.request_status.value} to {payload.request_status.value}")

        record.request_status = payload.request_status
        record.updated_at = datetime.utcnow()
        if payload.request_status == RequestStatus.CANCELLED:
            record.cancelled_at = datetime.utcnow()
        if payload.request_status == RequestStatus.CLOSED:
            record.closed_at = datetime.utcnow()
        await self._engine.save(record)

        new_status = payload.request_status.value if hasattr(payload.request_status, "value") else str(payload.request_status)

        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=record.client_tenant_id,
            title="Client request updated",
            message=f"{record.title} is now {payload.request_status.value}.",
            category="info",
            source_module="requests",
            action_url="/dashboard/requests",
            action_label="View requests",
            metadata={"request_id": str(record.id), "request_status": payload.request_status.value},
        )

        await self._write_activity(
            action="request_status_updated",
            entity_type="request",
            entity_id=str(record.id),
            current_user=current_user,
            previous_status=previous_status,
            new_status=new_status,
            reason=payload.reason,
            metadata={"client_tenant_id": record.client_tenant_id},
            severity="warning" if payload.request_status == RequestStatus.CANCELLED else "info",
        )

        return {
            "message": "Client request updated",
            "item": self._serialize(record),
        }

    async def create_assignment(self, request_id: str, payload: RequestAssignmentCreatePayload, current_user) -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        try:
            object_id = ObjectId(request_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request id")

        request_record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == object_id)
        if not request_record:
            raise HTTPException(status_code=404, detail="Request not found")

        session_tenant = await self._get_session_tenant(current_user)
        if not self._is_platform_write_role(role_value):
            if role_value != "client_admin" or session_tenant.tenant_type != TenantType.CLIENT:
                raise HTTPException(status_code=403, detail="Only client admins or platform admins can assign requests")
            if request_record.client_tenant_id != str(session_tenant.id):
                raise HTTPException(status_code=403, detail="Request does not belong to your tenant")

        if request_record.request_status != RequestStatus.SUBMITTED:
            raise HTTPException(status_code=400, detail="Only submitted requests can be assigned")

        candidate_tenant_id = str(payload.candidate_tenant_id or "").strip()
        eligible_candidates = [
            candidate for candidate in (request_record.matched_candidates or [])
            if str(candidate.get("candidate_id") or "") == candidate_tenant_id and bool(candidate.get("eligible"))
        ]
        if not eligible_candidates:
            raise HTTPException(status_code=400, detail="Candidate must exist in eligible matching results")

        candidate_snapshot = eligible_candidates[0]
        assignee_tenant = await self._get_tenant(candidate_tenant_id)
        if not assignee_tenant:
            raise HTTPException(status_code=400, detail="Candidate tenant not found")

        expected_type = self._target_type_to_tenant_type(request_record.target_type)
        if assignee_tenant.tenant_type != expected_type:
            raise HTTPException(status_code=400, detail="Candidate tenant type does not match request target type")
        if assignee_tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="Candidate tenant must be active")

        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        active_assignment_count = await assignment_collection.count_documents({
            "request_id": str(request_record.id),
            "assignee_tenant_id": str(assignee_tenant.id),
            "assignment_status": {"$in": [
                RequestAssignmentStatus.OFFERED.value,
                RequestAssignmentStatus.ACCEPTED.value,
                RequestAssignmentStatus.IN_PROGRESS.value,
            ]},
        })
        if active_assignment_count > 0:
            raise HTTPException(status_code=409, detail="An active assignment for this candidate already exists")

        now = datetime.utcnow()
        assignment = RequestAssignmentRecord(
            request_id=str(request_record.id),
            client_tenant_id=request_record.client_tenant_id,
            assignee_tenant_id=str(assignee_tenant.id),
            assignee_tenant_type=request_record.target_type,
            assignment_status=RequestAssignmentStatus.OFFERED,
            candidate_snapshot=candidate_snapshot,
            assigned_by_user_id=str(getattr(current_user, "id", "") or ""),
            assigned_by_username=str(getattr(current_user, "username", "") or ""),
            note=(payload.note or "").strip() or None,
            offered_at=now,
            created_at=now,
            updated_at=now,
            id=ObjectId(),
        )
        saved = await self._engine.save(assignment)

        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=str(assignee_tenant.id),
            title="New job offer",
            message=f"{request_record.title} has been assigned to your tenant.",
            category="info",
            source_module="requests",
            action_url="/dashboard/requests",
            action_label="Review offer",
            metadata={"request_id": str(request_record.id), "assignment_id": str(saved.id)},
        )
        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=request_record.client_tenant_id,
            title="Candidate assigned",
            message=f"{candidate_snapshot.get('candidate_name') or 'Candidate'} was assigned to {request_record.title}.",
            category="success",
            source_module="requests",
            action_url="/dashboard/requests",
            action_label="View request",
            metadata={"request_id": str(request_record.id), "assignment_id": str(saved.id)},
        )

        await self._write_activity(
            action="request_assigned",
            entity_type="assignment",
            entity_id=str(saved.id),
            current_user=current_user,
            new_status=RequestAssignmentStatus.OFFERED.value,
            metadata={
                "request_id": str(request_record.id),
                "assignee_tenant_id": str(assignee_tenant.id),
                "candidate_name": candidate_snapshot.get("candidate_name"),
            },
        )

        request_snapshot = {
            "id": str(request_record.id),
            "title": request_record.title,
            "request_status": request_record.request_status.value,
            "target_type": request_record.target_type.value,
            "site_name": (request_record.site_snapshot or {}).get("site_name") or "",
            "requested_start_at": request_record.requested_start_at,
            "requested_end_at": request_record.requested_end_at,
        }
        return {
            "message": "Request assigned",
            "item": self._serialize_assignment(saved, request_snapshot=request_snapshot),
        }

    async def list_jobs(self, current_user, page: int = 1, rows: int = 20, assignment_status: str = "", keyword: str = "") -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        session_tenant = await self._get_session_tenant(current_user)
        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)

        query: Dict[str, Any] = {}
        if self._is_platform_role(role_value):
            query = {}
        elif role_value == "client_admin" and session_tenant.tenant_type == TenantType.CLIENT:
            query = {"client_tenant_id": str(session_tenant.id)}
        elif role_value in {"guard_admin", "sp_admin"} and session_tenant.tenant_type in {TenantType.GUARD, TenantType.SERVICE_PROVIDER}:
            query = {"assignee_tenant_id": str(session_tenant.id)}
        else:
            raise HTTPException(status_code=403, detail="Access forbidden")

        normalized_status = self._normalize_text(assignment_status)
        if normalized_status:
            query["assignment_status"] = normalized_status

        docs = await assignment_collection.find(query).to_list(length=None)
        docs.sort(key=lambda item: item.get("updated_at") or datetime.min, reverse=True)

        request_collection = self._engine.get_collection(ClientRequestRecord)
        request_ids = []
        for doc in docs:
            request_id = doc.get("request_id")
            if request_id:
                try:
                    request_ids.append(ObjectId(str(request_id)))
                except Exception:
                    continue

        request_lookup: Dict[str, Dict[str, Any]] = {}
        if request_ids:
            request_docs = await request_collection.find({"_id": {"$in": request_ids}}).to_list(length=None)
            for request_doc in request_docs:
                request_lookup[str(request_doc.get("_id"))] = {
                    "id": str(request_doc.get("_id")),
                    "title": request_doc.get("title") or "",
                    "request_status": request_doc.get("request_status") or "",
                    "target_type": request_doc.get("target_type") or "",
                    "site_name": ((request_doc.get("site_snapshot") or {}).get("site_name") or ""),
                    "requested_start_at": request_doc.get("requested_start_at"),
                    "requested_end_at": request_doc.get("requested_end_at"),
                }

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

    async def _auto_progress_request_on_assignment_event(self, request_record: ClientRequestRecord, new_assignment_status: RequestAssignmentStatus, current_user) -> None:
        """
        Automatically transition request status based on assignment lifecycle events.
        - SUBMITTED → ASSIGNED when first assignment is created (offered).
        - ASSIGNED → IN_PROGRESS when first assignment reaches in_progress.
        - IN_PROGRESS → (stays) when other assignments progress.
        - Auto-close never happens; explicit close required.
        """
        if new_assignment_status != RequestAssignmentStatus.OFFERED and new_assignment_status != RequestAssignmentStatus.IN_PROGRESS:
            return

        current_request_status = request_record.request_status
        new_request_status: Optional[RequestStatus] = None

        if new_assignment_status == RequestAssignmentStatus.OFFERED and current_request_status == RequestStatus.SUBMITTED:
            new_request_status = RequestStatus.ASSIGNED
        elif new_assignment_status == RequestAssignmentStatus.IN_PROGRESS and current_request_status in {RequestStatus.SUBMITTED, RequestStatus.ASSIGNED}:
            new_request_status = RequestStatus.IN_PROGRESS

        if new_request_status and self._allowed_request_status_transition(current_request_status, new_request_status):
            request_record.request_status = new_request_status
            request_record.updated_at = datetime.utcnow()
            await self._engine.save(request_record)

            await self._write_activity(
                action="request_auto_progressed",
                entity_type="request",
                entity_id=str(request_record.id),
                current_user=current_user,
                previous_status=current_request_status.value,
                new_status=new_request_status.value,
                metadata={"trigger": "assignment_event", "assignment_status": new_assignment_status.value},
            )

    async def update_job_status(self, assignment_id: str, payload: RequestAssignmentStatusUpdatePayload, current_user) -> Dict[str, Any]:
        role_value = self._role_value(current_user)
        session_tenant = await self._get_session_tenant(current_user)

        try:
            object_id = ObjectId(assignment_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid assignment id")

        assignment = await self._engine.find_one(RequestAssignmentRecord, RequestAssignmentRecord.id == object_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

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

        now = datetime.utcnow()
        assignment.assignment_status = next_status
        assignment.updated_at = now
        if next_status == RequestAssignmentStatus.ACCEPTED:
            assignment.accepted_at = now
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

        request_record = await self._engine.find_one(ClientRequestRecord, ClientRequestRecord.id == ObjectId(assignment.request_id))
        if request_record:
            await self._auto_progress_request_on_assignment_event(request_record, next_status, current_user)

        request_title = request_record.title if request_record else "Request"

        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=assignment.client_tenant_id,
            title="Job status updated",
            message=f"{request_title}: assignment is now {next_status.value}.",
            category="info",
            source_module="requests",
            action_url="/dashboard/requests",
            action_label="Open requests",
            metadata={"assignment_id": str(assignment.id), "request_id": assignment.request_id, "assignment_status": next_status.value},
        )
        await NotificationManager.get_instance().create_for_tenant_users(
            tenant_id=assignment.assignee_tenant_id,
            title="Job status updated",
            message=f"{request_title}: assignment is now {next_status.value}.",
            category="success" if next_status in {RequestAssignmentStatus.ACCEPTED, RequestAssignmentStatus.COMPLETED} else "info",
            source_module="requests",
            action_url="/dashboard/requests",
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

        request_snapshot = {
            "id": str(request_record.id) if request_record else assignment.request_id,
            "title": request_record.title if request_record else "",
            "request_status": request_record.request_status.value if request_record else "",
            "target_type": request_record.target_type.value if request_record else "",
            "site_name": ((request_record.site_snapshot or {}).get("site_name") if request_record else "") or "",
            "requested_start_at": request_record.requested_start_at if request_record else None,
            "requested_end_at": request_record.requested_end_at if request_record else None,
        }
        return {
            "message": "Job status updated",
            "item": self._serialize_assignment(assignment, request_snapshot=request_snapshot),
        }
