from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from odmantic import Model, Field
from pydantic import BaseModel, Field as PydanticField


class RequestStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class RequestTargetType(str, Enum):
    GUARD = "guard"
    SERVICE_PROVIDER = "service_provider"


class RequestFulfillmentMode(str, Enum):
    INDIVIDUAL_ONLY = "individual_only"
    SERVICE_PROVIDER_ONLY = "service_provider_only"
    HYBRID = "hybrid"


class RequestAssignmentStatus(str, Enum):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    RECONFIRMATION_REQUIRED = "reconfirmation_required"
    DECLINED = "declined"
    EXPIRED = "expired"
    CLOSED_FILLED = "closed_filled"
    SUPERSEDED = "superseded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequestAssignmentOrigin(str, Enum):
    MANUAL = "manual"
    BROADCAST = "broadcast"


class RequestStaffingStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    REVIEW_RETURNED = "review_returned"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    EXPIRED = "expired"


class RequestLockReason(str, Enum):
    REVIEW_PENDING = "review_pending"
    FILLED = "filled"
    REQUEST_EXPIRED = "request_expired"
    REQUEST_CANCELLED = "request_cancelled"
    REQUEST_CLOSED = "request_closed"


class AssignmentLockReason(str, Enum):
    FILLED = "filled"
    WAVE_EXPIRED = "wave_expired"
    REQUEST_EXPIRED = "request_expired"
    SUPERSEDED = "superseded"
    REQUEST_CANCELLED = "request_cancelled"


class RequestWaveTrigger(str, Enum):
    INITIAL_PUBLISH = "initial_publish"
    PUBLISH_UPDATE = "publish_update"
    ADDITIONAL_COVERAGE = "additional_coverage"
    CAPACITY_REOPENED = "capacity_reopened"


class RequestWaveStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    RETURNED = "returned"
    FILLED = "filled"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class BroadcastReviewReasonCode(str, Enum):
    MISSING_GEO = "missing_geo"
    DISTANCE_UNVERIFIED = "distance_unverified"
    TRAVEL_POLICY_MISSING = "travel_policy_missing"
    AMBIGUOUS_LOCATION = "ambiguous_location"
    MANUAL_REVIEW_DISTANCE = "manual_review_distance"


class RequestSiteSnapshot(BaseModel):
    site_index: int = 0
    site_source: str = "saved"
    site_id: str = ""
    site_name: str = ""
    site_manager_contact: str = ""
    manager_email: str = ""
    number_of_guards_required: Optional[int] = None
    site_type: Optional[str] = None
    site_address: Dict[str, Any] = {}


class RequestSiteAddressInput(BaseModel):
    street: str = ""
    city: str = ""
    country: str = "CA"
    province: str = ""
    postal_code: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RequestSiteInput(BaseModel):
    site_name: str = PydanticField(min_length=2, max_length=140)
    site_manager_contact: Optional[str] = PydanticField(default=None, max_length=160)
    manager_email: Optional[str] = PydanticField(default=None, max_length=254)
    site_type: Optional[str] = PydanticField(default=None, max_length=100)
    google_maps_url: Optional[str] = PydanticField(default=None, max_length=1000)
    site_address: RequestSiteAddressInput = PydanticField(default_factory=RequestSiteAddressInput)


class ClientRequestRecord(Model):
    client_tenant_id: str = Field(index=True)
    created_by_user_id: str = Field(index=True)
    created_by_username: str = ""
    title: str = Field(index=True)
    fulfillment_mode: RequestFulfillmentMode = Field(default=RequestFulfillmentMode.INDIVIDUAL_ONLY, index=True)
    target_type: RequestTargetType = Field(index=True)
    requested_guard_type: Optional[str] = Field(default=None, index=True)
    guards_required: int = Field(default=1)
    request_status: RequestStatus = Field(default=RequestStatus.SUBMITTED, index=True)
    site_snapshot: Dict[str, Any] = {}
    special_instructions: Optional[str] = None
    requested_start_at: Optional[datetime] = None
    requested_end_at: Optional[datetime] = None
    request_expires_at: Optional[datetime] = Field(default=None, index=True)
    published_at: Optional[datetime] = Field(default=None, index=True)
    published_by_user_id: Optional[str] = Field(default=None, index=True)
    published_by_username: Optional[str] = None
    request_revision: int = Field(default=0, index=True)
    staffing_status: RequestStaffingStatus = Field(default=RequestStaffingStatus.OPEN, index=True)
    lock_reason: Optional[RequestLockReason] = Field(default=None, index=True)
    accepted_slots: int = Field(default=0)
    open_slots: int = Field(default=1)
    active_wave_id: Optional[str] = Field(default=None, index=True)
    last_wave_number: int = Field(default=0)
    expired_at: Optional[datetime] = Field(default=None, index=True)
    match_summary: Dict[str, Any] = {}
    matched_candidates: List[Dict[str, Any]] = []
    cancelled_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RequestAssignmentRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    assignee_tenant_id: str = Field(index=True)
    assignee_tenant_type: RequestTargetType = Field(index=True)
    assignment_status: RequestAssignmentStatus = Field(default=RequestAssignmentStatus.OFFERED, index=True)
    assignment_origin: RequestAssignmentOrigin = Field(default=RequestAssignmentOrigin.MANUAL, index=True)
    broadcast_wave_id: Optional[str] = Field(default=None, index=True)
    request_revision_at_offer: int = Field(default=0, index=True)
    slots_committed: Optional[int] = None
    response_due_at: Optional[datetime] = Field(default=None, index=True)
    reconfirmation_due_at: Optional[datetime] = Field(default=None, index=True)
    lock_reason: Optional[AssignmentLockReason] = Field(default=None, index=True)
    candidate_snapshot: Dict[str, Any] = {}
    assigned_by_user_id: str = Field(index=True)
    assigned_by_username: str = ""
    note: Optional[str] = None
    offered_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    reconfirmation_requested_at: Optional[datetime] = None
    reconfirmed_at: Optional[datetime] = None
    closed_filled_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RequestBroadcastWaveRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    request_revision: int = Field(default=0, index=True)
    wave_number: int = Field(default=0, index=True)
    trigger: RequestWaveTrigger = Field(default=RequestWaveTrigger.INITIAL_PUBLISH, index=True)
    wave_status: RequestWaveStatus = Field(default=RequestWaveStatus.PENDING_REVIEW, index=True)
    request_snapshot: Dict[str, Any] = {}
    match_summary_snapshot: Dict[str, Any] = {}
    candidate_snapshots: List[Dict[str, Any]] = []
    review_reason_codes: List[str] = []
    review_findings: List[Dict[str, Any]] = []
    review_note: Optional[str] = None
    reviewed_by_user_id: Optional[str] = Field(default=None, index=True)
    reviewed_by_username: Optional[str] = None
    review_requested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    wave_expires_at: Optional[datetime] = Field(default=None, index=True)
    filled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    open_slots_at_send: int = Field(default=0)
    offer_count: int = Field(default=0)
    accepted_slots_at_close: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ClientRequestCreatePayload(BaseModel):
    title: str = PydanticField(min_length=3, max_length=140)
    fulfillment_mode: RequestFulfillmentMode = RequestFulfillmentMode.INDIVIDUAL_ONLY
    site_index: Optional[int] = PydanticField(default=None, ge=0)
    site: Optional[RequestSiteInput] = None
    requested_guard_type: Optional[str] = None
    guards_required: int = PydanticField(default=1, ge=1, le=500)
    requested_start_at: Optional[datetime] = None
    requested_end_at: Optional[datetime] = None
    request_expires_at: Optional[datetime] = None
    special_instructions: Optional[str] = PydanticField(default=None, max_length=2000)
    max_match_results: int = PydanticField(default=25, ge=1, le=100)
    commit: bool = True


class ClientRequestUpdatePayload(BaseModel):
    title: Optional[str] = PydanticField(default=None, min_length=3, max_length=140)
    fulfillment_mode: Optional[RequestFulfillmentMode] = None
    site: Optional[RequestSiteInput] = None
    requested_guard_type: Optional[str] = None
    guards_required: Optional[int] = PydanticField(default=None, ge=1, le=500)
    requested_start_at: Optional[datetime] = None
    requested_end_at: Optional[datetime] = None
    request_expires_at: Optional[datetime] = None
    special_instructions: Optional[str] = PydanticField(default=None, max_length=2000)
    max_match_results: Optional[int] = PydanticField(default=None, ge=1, le=100)


class ClientRequestStatusUpdatePayload(BaseModel):
    request_status: RequestStatus
    reason: Optional[str] = PydanticField(default=None, max_length=500)


class RequestAssignmentCreatePayload(BaseModel):
    candidate_tenant_id: str = PydanticField(min_length=1, max_length=80)
    note: Optional[str] = PydanticField(default=None, max_length=500)


class RequestAssignmentStatusUpdatePayload(BaseModel):
    assignment_status: RequestAssignmentStatus
    reason: Optional[str] = PydanticField(default=None, max_length=500)
    slots_committed: Optional[int] = PydanticField(default=None, ge=1, le=500)


class RequestPublishPayload(BaseModel):
    max_match_results: int = PydanticField(default=25, ge=1, le=100)


class RequestPublishUpdatePayload(BaseModel):
    fulfillment_mode: Optional[RequestFulfillmentMode] = None
    site: Optional[RequestSiteInput] = None
    requested_guard_type: Optional[str] = None
    requested_start_at: Optional[datetime] = None
    requested_end_at: Optional[datetime] = None
    request_expires_at: Optional[datetime] = None
    special_instructions: Optional[str] = PydanticField(default=None, max_length=2000)
    max_match_results: int = PydanticField(default=25, ge=1, le=100)


class RequestAdditionalCoveragePayload(BaseModel):
    additional_slots: int = PydanticField(ge=1, le=500)
    request_expires_at: Optional[datetime] = None
    max_match_results: int = PydanticField(default=25, ge=1, le=100)


class RequestWaveReviewPayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)


class RequestWaveListFilters(BaseModel):
    page: int = 1
    rows: int = 20
    wave_status: str = ""
    trigger: str = ""
    request_id: str = ""
    client_tenant_id: str = ""


class ClientRequestListFilters(BaseModel):
    page: int = 1
    rows: int = 20
    keyword: str = ""
    request_status: str = ""
    fulfillment_mode: str = ""
