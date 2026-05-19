from datetime import datetime
from typing import Optional, Literal, List

from pydantic import BaseModel, Field


DistanceSource = Literal["haversine", "province_fallback"]
ReasonCode = Literal[
    "within_radius",
    "outside_radius",
    "province_mismatch",
    "city_mismatch",
    "missing_geo",
    "ownership_excluded",
    "outside_availability",
    "guard_type_mismatch",
    "insufficient_capacity",
]
TargetType = Literal["guard", "service_provider"]


class MatchAddress(BaseModel):
    country: str = "CA"
    province: str = ""
    city: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RequestMatchingPreviewPayload(BaseModel):
    target_type: TargetType = "guard"
    site_address: MatchAddress
    requested_guard_type: Optional[str] = None
    requested_start_at: Optional[datetime] = None
    requested_end_at: Optional[datetime] = None
    max_results: int = Field(default=50, ge=1, le=500)
    fallback_to_province_when_missing_geo: bool = False


class RequestMatchCandidate(BaseModel):
    candidate_id: str
    candidate_name: str
    target_type: TargetType
    province: str
    city: str = ""
    eligible: bool
    reason_code: ReasonCode
    distance_source: DistanceSource
    distance_km: Optional[float] = None
    distance_mi: Optional[float] = None
    radius_km: Optional[float] = None
    radius_mi: Optional[float] = None
    linked_guard_count: Optional[int] = None
    eligible_guard_count: Optional[int] = None
    reserved_guard_count: Optional[int] = None
    available_guard_count: Optional[int] = None


class RequestMatchingPreviewResult(BaseModel):
    summary: dict
    results: List[RequestMatchCandidate]
