from datetime import datetime, date
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


class RequestAssignmentScope(str, Enum):
    REQUEST = "request"
    SHIFT_REPLACEMENT = "shift_replacement"


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


class RequestScheduleType(str, Enum):
    ONE_TIME = "one_time"
    DATE_RANGE = "date_range"
    RECURRING_WEEKLY = "recurring_weekly"


class ShiftInstanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    PARTIALLY_STAFFED = "partially_staffed"
    STAFFED = "staffed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ShiftCoverageSourceType(str, Enum):
    DIRECT_GUARD = "direct_guard"
    SERVICE_PROVIDER = "service_provider"


class ShiftSlotStatus(str, Enum):
    OPEN = "open"
    RESERVED = "reserved"
    ROSTERED = "rostered"
    UNAVAILABLE = "unavailable"
    LATE_RISK = "late_risk"
    ARRIVAL_PENDING = "arrival_pending"
    CLIENT_CONFIRMATION_PENDING = "client_confirmation_pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW_SUSPECTED = "no_show_suspected"
    NO_SHOW_CONFIRMED = "no_show_confirmed"
    REPLACEMENT_REQUIRED = "replacement_required"
    CANCELLED = "cancelled"


class ShiftAttendanceEventType(str, Enum):
    UNAVAILABLE_REPORTED = "unavailable_reported"
    CHECKIN_ATTEMPTED = "checkin_attempted"
    ARRIVED = "arrived"
    GEO_FAILED = "geo_failed"
    CLIENT_CONFIRMED = "client_confirmed"
    OPS_START_OVERRIDE = "ops_start_override"
    STARTED = "started"
    CHECKOUT = "checkout"
    COMPLETED = "completed"
    NO_SHOW_SUSPECTED = "no_show_suspected"
    NO_SHOW_CONFIRMED = "no_show_confirmed"
    REPLACEMENT_REQUESTED = "replacement_requested"
    REPLACEMENT_ASSIGNED = "replacement_assigned"


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
    deleted_at: Optional[datetime] = Field(default=None, index=True)
    deleted_by_user_id: Optional[str] = Field(default=None, index=True)
    deleted_by_username: Optional[str] = None
    deleted_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class RequestAssignmentRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    assignee_tenant_id: str = Field(index=True)
    assignee_tenant_type: RequestTargetType = Field(index=True)
    assignment_status: RequestAssignmentStatus = Field(default=RequestAssignmentStatus.OFFERED, index=True)
    assignment_origin: RequestAssignmentOrigin = Field(default=RequestAssignmentOrigin.MANUAL, index=True)
    assignment_scope: RequestAssignmentScope = Field(default=RequestAssignmentScope.REQUEST, index=True)
    broadcast_wave_id: Optional[str] = Field(default=None, index=True)
    shift_instance_id: Optional[str] = Field(default=None, index=True)
    shift_slot_id: Optional[str] = Field(default=None, index=True)
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


class RequestScheduleTemplateRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    timezone: str = Field(index=True)
    schedule_type: RequestScheduleType = Field(index=True)
    start_date_local: str = Field(index=True)
    end_date_local: Optional[str] = Field(default=None, index=True)
    start_time_local: str = ""
    end_time_local: str = ""
    is_overnight: bool = False
    recurrence_days: List[str] = []
    generation_horizon_days: int = 30
    roster_due_offset_minutes: int = 120
    unavailable_cutoff_minutes: int = 120
    late_grace_minutes: int = 15
    no_show_cutoff_minutes: int = 30
    checkin_geofence_meters: int = 200
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ShiftInstanceRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    schedule_template_id: str = Field(index=True)
    shift_date_local: str = Field(index=True)
    shift_start_at_utc: datetime = Field(index=True)
    shift_end_at_utc: datetime = Field(index=True)
    timezone: str = Field(index=True)
    instance_status: ShiftInstanceStatus = Field(default=ShiftInstanceStatus.SCHEDULED, index=True)
    slots_required: int = 1
    slots_staffed: int = 0
    slots_checked_in: int = 0
    slots_completed: int = 0
    client_action_required: bool = False
    roster_due_at: Optional[datetime] = Field(default=None, index=True)
    created_from_revision: int = Field(default=0, index=True)
    cancel_reason: Optional[str] = None
    reduction_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ShiftSlotRecord(Model):
    shift_instance_id: str = Field(index=True)
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    parent_assignment_id: Optional[str] = Field(default=None, index=True)
    slot_number: int = Field(index=True)
    coverage_slot_index: int = Field(default=0, index=True)
    coverage_source_type: Optional[ShiftCoverageSourceType] = Field(default=None, index=True)
    coverage_tenant_id: Optional[str] = Field(default=None, index=True)
    service_provider_tenant_id: Optional[str] = Field(default=None, index=True)
    assigned_guard_tenant_id: Optional[str] = Field(default=None, index=True)
    slot_status: ShiftSlotStatus = Field(default=ShiftSlotStatus.OPEN, index=True)
    replacement_of_slot_id: Optional[str] = Field(default=None, index=True)
    rostered_at: Optional[datetime] = None
    roster_due_at: Optional[datetime] = Field(default=None, index=True)
    guard_unavailable_reported_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    client_confirmed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    no_show_confirmed_at: Optional[datetime] = None
    geo_check_passed: Optional[bool] = None
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ShiftAttendanceEventRecord(Model):
    shift_slot_id: str = Field(index=True)
    shift_instance_id: str = Field(index=True)
    request_id: str = Field(index=True)
    event_type: ShiftAttendanceEventType = Field(index=True)
    actor_user_id: Optional[str] = Field(default=None, index=True)
    actor_role: Optional[str] = Field(default=None, index=True)
    guard_tenant_id: Optional[str] = Field(default=None, index=True)
    service_provider_tenant_id: Optional[str] = Field(default=None, index=True)
    client_tenant_id: Optional[str] = Field(default=None, index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_meters: Optional[float] = None
    note: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ClientRequestCreatePayload(BaseModel):
    title: str = PydanticField(min_length=3, max_length=140)
    fulfillment_mode: RequestFulfillmentMode = RequestFulfillmentMode.INDIVIDUAL_ONLY
    client_tenant_id: Optional[str] = PydanticField(default=None, min_length=1, max_length=80)
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


class ClientRequestSoftDeletePayload(BaseModel):
    reason: str = PydanticField(min_length=3, max_length=500)


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


class RequestScheduleUpsertPayload(BaseModel):
    timezone: str = PydanticField(min_length=1, max_length=80)
    schedule_type: RequestScheduleType
    start_date: date
    end_date: Optional[date] = None
    start_time_local: str = PydanticField(min_length=5, max_length=5, pattern=r"^\d{2}:\d{2}$")
    end_time_local: str = PydanticField(min_length=5, max_length=5, pattern=r"^\d{2}:\d{2}$")
    recurrence_days: List[str] = []
    generation_horizon_days: int = PydanticField(default=30, ge=1, le=90)
    roster_due_offset_minutes: int = PydanticField(default=120, ge=0, le=1440)
    unavailable_cutoff_minutes: int = PydanticField(default=120, ge=0, le=1440)
    late_grace_minutes: int = PydanticField(default=15, ge=0, le=240)
    no_show_cutoff_minutes: int = PydanticField(default=30, ge=0, le=480)
    checkin_geofence_meters: int = PydanticField(default=200, ge=25, le=5000)
    active: bool = True


class ShiftListFilters(BaseModel):
    page: int = 1
    rows: int = 20
    request_id: str = ""
    instance_status: str = ""
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class ProviderRosterSelectionPayload(BaseModel):
    slot_id: str = PydanticField(min_length=1, max_length=80)
    guard_tenant_id: str = PydanticField(min_length=1, max_length=80)


class ProviderRosterPayload(BaseModel):
    assignments: List[ProviderRosterSelectionPayload] = PydanticField(default_factory=list, min_length=1)


class ShiftSlotCheckInPayload(BaseModel):
    latitude: float
    longitude: float
    note: Optional[str] = PydanticField(default=None, max_length=500)


class ShiftSlotClientConfirmPayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)


class ShiftSlotStartPayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)


class ShiftSlotCheckOutPayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)


class ShiftSlotUnavailablePayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)


class ShiftSlotReopenPayload(BaseModel):
    note: Optional[str] = PydanticField(default=None, max_length=500)
    max_match_results: int = PydanticField(default=25, ge=1, le=200)


class ClientRequestListFilters(BaseModel):
    page: int = 1
    rows: int = 20
    keyword: str = ""
    request_status: str = ""
    fulfillment_mode: str = ""
