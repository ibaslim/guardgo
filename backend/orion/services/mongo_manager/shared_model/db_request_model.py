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
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


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
    candidate_snapshot: Dict[str, Any] = {}
    assigned_by_user_id: str = Field(index=True)
    assigned_by_username: str = ""
    note: Optional[str] = None
    offered_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
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


class ClientRequestListFilters(BaseModel):
    page: int = 1
    rows: int = 20
    keyword: str = ""
    request_status: str = ""
    fulfillment_mode: str = ""
