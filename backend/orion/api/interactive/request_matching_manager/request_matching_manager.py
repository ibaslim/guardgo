import math
import threading
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    RequestMatchingPreviewPayload,
    RequestMatchingPreviewResult,
    RequestMatchCandidate,
)
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord,
    RequestAssignmentRecord,
    RequestAssignmentScope,
    RequestAssignmentStatus,
)
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    GuardOwnershipType,
    db_tenant_model,
    TenantType,
    TenantStatus,
)

from configs.distance_units import km_to_miles, normalize_km_for_storage


class RequestMatchingManager:
    __instance = None
    __lock = threading.Lock()
    _WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    _DAY_BOUNDARY_HOUR = 6
    _COUNTRY_ALIASES = {
        "CANADA": "CA",
        "CA": "CA",
        "UNITED STATES": "US",
        "UNITED STATES OF AMERICA": "US",
        "USA": "US",
        "US": "US",
    }
    _CANADA_REGION_ALIASES = {
        "AB": "AB",
        "ALBERTA": "AB",
        "BC": "BC",
        "BRITISH COLUMBIA": "BC",
        "MB": "MB",
        "MANITOBA": "MB",
        "NB": "NB",
        "NEW BRUNSWICK": "NB",
        "NL": "NL",
        "NEWFOUNDLAND AND LABRADOR": "NL",
        "NS": "NS",
        "NOVA SCOTIA": "NS",
        "NT": "NT",
        "NORTHWEST TERRITORIES": "NT",
        "NU": "NU",
        "NUNAVUT": "NU",
        "ON": "ON",
        "ONTARIO": "ON",
        "PE": "PE",
        "PRINCE EDWARD ISLAND": "PE",
        "QC": "QC",
        "QUEBEC": "QC",
        "SK": "SK",
        "SASKATCHEWAN": "SK",
        "YT": "YT",
        "YUKON": "YT",
        "YUKON TERRITORY": "YT",
    }
    _PROVIDER_COMMITTED_ASSIGNMENT_STATUSES = {
        RequestAssignmentStatus.ACCEPTED.value,
        RequestAssignmentStatus.RECONFIRMATION_REQUIRED.value,
        RequestAssignmentStatus.IN_PROGRESS.value,
    }

    @staticmethod
    def get_instance() -> "RequestMatchingManager":
        if RequestMatchingManager.__instance is None:
            with RequestMatchingManager.__lock:
                if RequestMatchingManager.__instance is None:
                    RequestMatchingManager.__instance = RequestMatchingManager()
        return RequestMatchingManager.__instance

    def __init__(self):
        if RequestMatchingManager.__instance is not None:
            raise Exception("RequestMatchingManager is a singleton")
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def _extract_tenant_name(profile: Any, tenant_id: str) -> str:
        if not isinstance(profile, dict):
            return tenant_id
        for key in ["legal_company_name", "trading_name", "legal_entity_name", "full_name", "company_name", "name"]:
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return tenant_id

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value)
            if math.isfinite(parsed):
                return parsed
            return None
        except Exception:
            return None

    @staticmethod
    def _get_nested(source: Dict[str, Any], path: List[str], default: Any = None) -> Any:
        node: Any = source
        for key in path:
            if not isinstance(node, dict):
                return default
            node = node.get(key)
            if node is None:
                return default
        return node

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip().upper()

    @classmethod
    def _normalize_country_code(cls, value: Any) -> str:
        normalized = cls._normalize_text(value)
        return cls._COUNTRY_ALIASES.get(normalized, normalized)

    @classmethod
    def _normalize_region_code(cls, value: Any, country: Any = None) -> str:
        normalized = cls._normalize_text(value)
        normalized_country = cls._normalize_country_code(country)
        if normalized_country == "CA":
            return cls._CANADA_REGION_ALIASES.get(normalized, normalized)
        return normalized

    @classmethod
    def _normalized_text_set(cls, values: Any) -> set[str]:
        if not isinstance(values, list):
            return set()
        return {cls._normalize_text(value) for value in values if cls._normalize_text(value)}

    @staticmethod
    def _first_non_empty_string(values: List[Any]) -> str:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return ""

    @staticmethod
    def _normalize_datetime_wall_clock(value: Optional[datetime]) -> Optional[datetime]:
        if not isinstance(value, datetime):
            return None
        return value.replace(tzinfo=None)

    @classmethod
    def _windows_overlap(
        cls,
        start_a: Optional[datetime],
        end_a: Optional[datetime],
        start_b: Optional[datetime],
        end_b: Optional[datetime],
    ) -> bool:
        normalized_start_a = cls._normalize_datetime_wall_clock(start_a)
        normalized_end_a = cls._normalize_datetime_wall_clock(end_a)
        normalized_start_b = cls._normalize_datetime_wall_clock(start_b)
        normalized_end_b = cls._normalize_datetime_wall_clock(end_b)
        if (
            normalized_start_a is None
            or normalized_end_a is None
            or normalized_start_b is None
            or normalized_end_b is None
        ):
            return False
        if normalized_end_a <= normalized_start_a or normalized_end_b <= normalized_start_b:
            return False
        return normalized_start_a < normalized_end_b and normalized_start_b < normalized_end_a

    @classmethod
    def _weekday_name(cls, weekday_index: int) -> str:
        return cls._WEEKDAY_NAMES[weekday_index % 7]

    @classmethod
    def _logical_day_name(cls, moment: datetime) -> str:
        if moment.time() >= time(cls._DAY_BOUNDARY_HOUR, 0):
            return cls._weekday_name(moment.weekday())
        return cls._weekday_name(moment.weekday() - 1)

    @classmethod
    def _next_logical_day_boundary(cls, moment: datetime) -> datetime:
        boundary_today = datetime.combine(moment.date(), time(cls._DAY_BOUNDARY_HOUR, 0))
        if moment < boundary_today:
            return boundary_today
        return boundary_today + timedelta(days=1)

    @classmethod
    def _logical_minutes_since_boundary(cls, moment: datetime) -> int:
        minute_of_day = (moment.hour * 60) + moment.minute
        if minute_of_day >= cls._DAY_BOUNDARY_HOUR * 60:
            return minute_of_day - (cls._DAY_BOUNDARY_HOUR * 60)
        return minute_of_day + ((24 - cls._DAY_BOUNDARY_HOUR) * 60)

    @staticmethod
    def _parse_time_value(raw_value: Any) -> Optional[int]:
        text = str(raw_value or "").strip()
        if not text:
            return None
        normalized = " ".join(text.upper().split())

        meridiem = None
        if normalized.endswith("AM") or normalized.endswith("PM"):
            meridiem = normalized[-2:]
            normalized = normalized[:-2].strip()

        parts = normalized.split(":")
        if len(parts) < 2:
            return None

        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except Exception:
            return None

        if minute < 0 or minute > 59:
            return None

        if meridiem:
            if hour < 1 or hour > 12:
                return None
            if meridiem == "AM":
                hour = 0 if hour == 12 else hour
            else:
                hour = 12 if hour == 12 else hour + 12
        elif hour < 0 or hour > 23:
            return None

        return (hour * 60) + minute

    @classmethod
    def _normalize_availability_minutes(cls, minute_of_day: int) -> int:
        if minute_of_day >= cls._DAY_BOUNDARY_HOUR * 60:
            return minute_of_day - (cls._DAY_BOUNDARY_HOUR * 60)
        return minute_of_day + ((24 - cls._DAY_BOUNDARY_HOUR) * 60)

    @classmethod
    def _availability_windows_for_day(cls, weekly_availability: Any, day_name: str) -> List[tuple[int, int]]:
        if not isinstance(weekly_availability, dict):
            return []

        raw_ranges = weekly_availability.get(day_name)
        if not isinstance(raw_ranges, list):
            return []

        windows: List[tuple[int, int]] = []
        for entry in raw_ranges:
            if not isinstance(entry, dict):
                continue
            start_minutes = cls._parse_time_value(entry.get("start"))
            end_minutes = cls._parse_time_value(entry.get("end"))
            if start_minutes is None or end_minutes is None:
                continue
            normalized_start = cls._normalize_availability_minutes(start_minutes)
            normalized_end = cls._normalize_availability_minutes(end_minutes)
            if normalized_end <= normalized_start:
                continue
            windows.append((normalized_start, normalized_end))

        if not windows:
            return []

        windows.sort(key=lambda item: item[0])
        merged: List[tuple[int, int]] = [windows[0]]
        for start_minute, end_minute in windows[1:]:
            last_start, last_end = merged[-1]
            if start_minute <= last_end:
                merged[-1] = (last_start, max(last_end, end_minute))
                continue
            merged.append((start_minute, end_minute))
        return merged

    @classmethod
    def _is_request_window_within_weekly_availability(
        cls,
        weekly_availability: Any,
        requested_start_at: Optional[datetime],
        requested_end_at: Optional[datetime],
    ) -> bool:
        start_at = cls._normalize_datetime_wall_clock(requested_start_at)
        end_at = cls._normalize_datetime_wall_clock(requested_end_at)

        if start_at is None or end_at is None:
            return True

        if end_at <= start_at:
            return False

        cursor = start_at
        while cursor < end_at:
            segment_day = cls._logical_day_name(cursor)
            segment_end = min(end_at, cls._next_logical_day_boundary(cursor))
            start_offset = cls._logical_minutes_since_boundary(cursor)
            end_offset = cls._logical_minutes_since_boundary(segment_end)
            if segment_end == end_at and end_offset == 0 and end_at > start_at:
                end_offset = 24 * 60
            windows = cls._availability_windows_for_day(weekly_availability, segment_day)
            if not any(window_start <= start_offset and end_offset <= window_end for window_start, window_end in windows):
                return False
            cursor = segment_end

        return True

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_km = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return earth_radius_km * c

    def _candidate_from_guard(
        self,
        tenant_id: str,
        ownership_type: Any,
        profile: Dict[str, Any],
        payload: RequestMatchingPreviewPayload,
        *,
        allow_provider_owned: bool = False,
    ) -> RequestMatchCandidate:
        request_address = payload.site_address
        request_country = self._normalize_country_code(request_address.country)
        request_province = self._normalize_region_code(request_address.province, request_country)

        home_address = profile.get("home_address") if isinstance(profile.get("home_address"), dict) else {}
        home_country = self._normalize_country_code(home_address.get("country") or request_country)
        province = self._normalize_region_code(
            profile.get("operational_region_code") or home_address.get("province"),
            home_country,
        )
        city = self._first_non_empty_string([
            profile.get("operational_city_code"),
            home_address.get("city"),
        ])

        max_radius_km = self._as_float(profile.get("max_travel_radius_km"))
        lat = self._as_float(home_address.get("latitude"))
        lon = self._as_float(home_address.get("longitude"))
        req_lat = self._as_float(request_address.latitude)
        req_lon = self._as_float(request_address.longitude)

        candidate = RequestMatchCandidate(
            candidate_id=tenant_id,
            candidate_name=self._extract_tenant_name(profile, tenant_id),
            target_type="guard",
            province=province,
            city=city,
            eligible=False,
            reason_code="province_mismatch",
            distance_source="province_fallback",
            radius_km=normalize_km_for_storage(max_radius_km) if max_radius_km is not None else None,
            radius_mi=km_to_miles(max_radius_km) if max_radius_km is not None else None,
        )

        normalized_ownership = str(getattr(ownership_type, "value", ownership_type) or "").strip().lower()
        if not allow_provider_owned and normalized_ownership == GuardOwnershipType.SERVICE_PROVIDER.value:
            candidate.reason_code = "ownership_excluded"
            candidate.distance_source = "province_fallback"
            return candidate

        if request_province and province != request_province:
            return candidate

        requested_guard_type = self._normalize_text(payload.requested_guard_type)
        if requested_guard_type:
            preferred_guard_types = self._normalized_text_set(profile.get("preferred_guard_types"))
            if requested_guard_type not in preferred_guard_types:
                candidate.reason_code = "guard_type_mismatch"
                candidate.distance_source = "province_fallback"
                return candidate

        if not self._is_request_window_within_weekly_availability(
            profile.get("weekly_availability"),
            payload.requested_start_at,
            payload.requested_end_at,
        ):
            candidate.reason_code = "outside_availability"
            candidate.distance_source = "province_fallback"
            return candidate

        if max_radius_km is None:
            # No radius means unconstrained within province-level filtering.
            candidate.eligible = True
            candidate.reason_code = "within_radius"
            candidate.distance_source = "province_fallback"
            return candidate

        if None in [lat, lon, req_lat, req_lon]:
            candidate.reason_code = "missing_geo"
            candidate.distance_source = "province_fallback"
            candidate.eligible = bool(payload.fallback_to_province_when_missing_geo)
            return candidate

        distance_km = normalize_km_for_storage(self._haversine_km(lat, lon, req_lat, req_lon))
        distance_mi = km_to_miles(distance_km)
        candidate.distance_km = distance_km
        candidate.distance_mi = distance_mi
        candidate.distance_source = "haversine"

        if distance_km <= max_radius_km:
            candidate.eligible = True
            candidate.reason_code = "within_radius"
        else:
            candidate.eligible = False
            candidate.reason_code = "outside_radius"

        return candidate

    def _provider_guard_capacity_from_tenants(
        self,
        provider_tenant_id: str,
        guards: List[db_tenant_model],
        payload: RequestMatchingPreviewPayload,
        reserved_guard_count: int = 0,
    ) -> Dict[str, int]:
        normalized_provider_id = str(provider_tenant_id or "").strip()
        linked_guards = [
            guard
            for guard in guards
            if str(getattr(guard, "service_provider_tenant_id", "") or "").strip() == normalized_provider_id
        ]

        eligible_guard_count = 0
        for guard in linked_guards:
            profile = guard.profile if isinstance(guard.profile, dict) else {}
            candidate = self._candidate_from_guard(
                str(guard.id),
                getattr(guard, "ownership_type", None),
                profile,
                payload,
                allow_provider_owned=True,
            )
            if candidate.eligible:
                eligible_guard_count += 1

        normalized_reserved_guard_count = max(int(reserved_guard_count or 0), 0)
        available_guard_count = max(eligible_guard_count - normalized_reserved_guard_count, 0)

        return {
            "linked_guard_count": len(linked_guards),
            "eligible_guard_count": eligible_guard_count,
            "reserved_guard_count": normalized_reserved_guard_count,
            "available_guard_count": available_guard_count,
        }

    async def _provider_reserved_capacity_by_provider(
        self,
        payload: RequestMatchingPreviewPayload,
    ) -> Dict[str, int]:
        if payload.requested_start_at is None or payload.requested_end_at is None:
            return {}

        assignment_collection = self._engine.get_collection(RequestAssignmentRecord)
        assignment_docs = await assignment_collection.find({
            "assignee_tenant_type": "service_provider",
            "assignment_scope": RequestAssignmentScope.REQUEST.value,
            "assignment_status": {"$in": sorted(self._PROVIDER_COMMITTED_ASSIGNMENT_STATUSES)},
        }).to_list(length=None)

        request_ids = []
        for assignment_doc in assignment_docs:
            request_id = str(assignment_doc.get("request_id") or "").strip()
            if ObjectId.is_valid(request_id):
                request_ids.append(ObjectId(request_id))
        if not request_ids:
            return {}

        request_collection = self._engine.get_collection(ClientRequestRecord)
        request_docs = await request_collection.find({"_id": {"$in": request_ids}}).to_list(length=None)
        request_windows: Dict[str, tuple[Optional[datetime], Optional[datetime]]] = {}
        for request_doc in request_docs:
            request_id = str(request_doc.get("_id") or "").strip()
            if not request_id:
                continue
            request_windows[request_id] = (
                request_doc.get("requested_start_at"),
                request_doc.get("requested_end_at"),
            )

        reserved_slots_by_provider: Dict[str, int] = {}
        for assignment_doc in assignment_docs:
            provider_id = str(assignment_doc.get("assignee_tenant_id") or "").strip()
            request_id = str(assignment_doc.get("request_id") or "").strip()
            if not provider_id or not request_id:
                continue
            request_window = request_windows.get(request_id)
            if not request_window:
                continue
            if not self._windows_overlap(
                payload.requested_start_at,
                payload.requested_end_at,
                request_window[0],
                request_window[1],
            ):
                continue
            reserved_slots_by_provider[provider_id] = reserved_slots_by_provider.get(provider_id, 0) + int(
                assignment_doc.get("slots_committed") or 1
            )

        return reserved_slots_by_provider

    async def provider_available_guard_capacity(
        self,
        provider_tenant_id: str,
        payload: RequestMatchingPreviewPayload,
    ) -> Dict[str, int]:
        guards = await self._engine.find(
            db_tenant_model,
            (db_tenant_model.tenant_type == TenantType.GUARD)
            & (db_tenant_model.status == TenantStatus.ACTIVE)
            & (db_tenant_model.ownership_type == GuardOwnershipType.SERVICE_PROVIDER),
        )
        reserved_capacity = await self._provider_reserved_capacity_by_provider(payload)
        return self._provider_guard_capacity_from_tenants(
            provider_tenant_id,
            guards,
            payload,
            reserved_guard_count=reserved_capacity.get(str(provider_tenant_id or "").strip(), 0),
        )

    def _candidate_from_provider_region(
        self,
        tenant_id: str,
        profile: Dict[str, Any],
        region: Dict[str, Any],
        payload: RequestMatchingPreviewPayload,
    ) -> RequestMatchCandidate:
        request_address = payload.site_address
        request_country = self._normalize_country_code(request_address.country)
        request_province = self._normalize_region_code(request_address.province, request_country)
        request_city_text = self._normalize_text(request_address.city)
        requested_guard_type = self._normalize_text(payload.requested_guard_type)

        region_country = self._normalize_country_code(region.get("country") or request_country)
        province = self._normalize_region_code(region.get("region_code") or region.get("province"), region_country)

        city_codes = region.get("city_codes") if isinstance(region.get("city_codes"), list) else []
        city_labels = region.get("city_labels") if isinstance(region.get("city_labels"), list) else []
        city = self._first_non_empty_string([
            city_labels[0] if city_labels else "",
            city_codes[0] if city_codes else "",
            region.get("city"),
        ])

        city_entries = region.get("city_entries") if isinstance(region.get("city_entries"), list) else []
        region_radius_km = self._as_float(region.get("coverage_radius_km"))
        req_lat = self._as_float(request_address.latitude)
        req_lon = self._as_float(request_address.longitude)

        candidate = RequestMatchCandidate(
            candidate_id=tenant_id,
            candidate_name=self._extract_tenant_name(profile, tenant_id),
            target_type="service_provider",
            province=province,
            city=city,
            eligible=False,
            reason_code="province_mismatch",
            distance_source="province_fallback",
            radius_km=normalize_km_for_storage(region_radius_km) if region_radius_km is not None else None,
            radius_mi=km_to_miles(region_radius_km) if region_radius_km is not None else None,
        )

        if request_province and province != request_province:
            return candidate

        if requested_guard_type:
            offered_guard_types = self._normalized_text_set(profile.get("guard_categories_offered"))
            if requested_guard_type not in offered_guard_types:
                candidate.reason_code = "guard_type_mismatch"
                candidate.distance_source = "province_fallback"
                return candidate

        candidate_sources: List[Dict[str, Any]] = []
        if city_entries:
            exact_matches = []
            fallback_entries = []
            for entry in city_entries:
                if not isinstance(entry, dict):
                    continue
                entry_city_code = self._normalize_text(entry.get("city_code"))
                entry_city_name = self._normalize_text(entry.get("city"))
                if request_city_text and (request_city_text == entry_city_code or request_city_text == entry_city_name):
                    exact_matches.append(entry)
                fallback_entries.append(entry)

            if exact_matches:
                candidate_sources = exact_matches
            elif req_lat is not None and req_lon is not None:
                candidate_sources = fallback_entries
            else:
                candidate.reason_code = "city_mismatch"
                candidate.distance_source = "province_fallback"
                return candidate

        if not candidate_sources:
            candidate_sources = [region]

        best_distance_candidate: Optional[RequestMatchCandidate] = None
        best_distance_rank = -1
        for source in candidate_sources:
            source_radius_km = self._as_float(source.get("coverage_radius_km"))
            source_city = self._first_non_empty_string([
                source.get("city"),
                source.get("city_code"),
                city,
            ])
            source_lat = self._as_float(source.get("latitude"))
            source_lon = self._as_float(source.get("longitude"))
            if source_lat is None or source_lon is None:
                head_office = profile.get("head_office_address") if isinstance(profile.get("head_office_address"), dict) else {}
                source_lat = self._as_float(head_office.get("latitude"))
                source_lon = self._as_float(head_office.get("longitude"))

            current_candidate = RequestMatchCandidate(
                candidate_id=tenant_id,
                candidate_name=self._extract_tenant_name(profile, tenant_id),
                target_type="service_provider",
                province=province,
                city=source_city,
                eligible=False,
                reason_code="province_mismatch",
                distance_source="province_fallback",
                radius_km=normalize_km_for_storage(source_radius_km) if source_radius_km is not None else None,
                radius_mi=km_to_miles(source_radius_km) if source_radius_km is not None else None,
            )

            if source_radius_km is None:
                current_candidate.eligible = True
                current_candidate.reason_code = "within_radius"
                current_candidate.distance_source = "province_fallback"
            elif None in [source_lat, source_lon, req_lat, req_lon]:
                current_candidate.reason_code = "missing_geo"
                current_candidate.distance_source = "province_fallback"
                current_candidate.eligible = bool(payload.fallback_to_province_when_missing_geo)
            else:
                distance_km = normalize_km_for_storage(self._haversine_km(source_lat, source_lon, req_lat, req_lon))
                distance_mi = km_to_miles(distance_km)
                current_candidate.distance_km = distance_km
                current_candidate.distance_mi = distance_mi
                current_candidate.distance_source = "haversine"

                if distance_km <= source_radius_km:
                    current_candidate.eligible = True
                    current_candidate.reason_code = "within_radius"
                else:
                    current_candidate.eligible = False
                    current_candidate.reason_code = "outside_radius"

            current_rank = 0
            if current_candidate.reason_code == "within_radius" and current_candidate.eligible:
                current_rank = 4
            elif current_candidate.reason_code == "missing_geo" and current_candidate.eligible:
                current_rank = 3
            elif current_candidate.reason_code == "outside_radius":
                current_rank = 2
            elif current_candidate.reason_code == "city_mismatch":
                current_rank = 1

            if current_rank > best_distance_rank:
                best_distance_rank = current_rank
                best_distance_candidate = current_candidate
                continue

            if (
                current_rank == best_distance_rank
                and best_distance_candidate is not None
                and current_candidate.distance_km is not None
                and (
                    best_distance_candidate.distance_km is None
                    or current_candidate.distance_km < best_distance_candidate.distance_km
                )
            ):
                best_distance_candidate = current_candidate

        if best_distance_candidate is not None:
            return best_distance_candidate

        return candidate

    async def preview_matches(self, payload: RequestMatchingPreviewPayload) -> RequestMatchingPreviewResult:
        target_type = payload.target_type
        requested_type = TenantType.GUARD if target_type == "guard" else TenantType.SERVICE_PROVIDER

        tenants = await self._engine.find(
            db_tenant_model,
            (db_tenant_model.tenant_type == requested_type)
            & (db_tenant_model.status == TenantStatus.ACTIVE),
        )

        results: List[RequestMatchCandidate] = []
        provider_guards_by_provider_id: Dict[str, List[db_tenant_model]] = {}
        provider_reserved_capacity_by_provider_id: Dict[str, int] = {}

        if target_type == "service_provider":
            provider_guards = await self._engine.find(
                db_tenant_model,
                (db_tenant_model.tenant_type == TenantType.GUARD)
                & (db_tenant_model.status == TenantStatus.ACTIVE)
                & (db_tenant_model.ownership_type == GuardOwnershipType.SERVICE_PROVIDER),
            )
            for guard in provider_guards:
                provider_id = str(getattr(guard, "service_provider_tenant_id", "") or "").strip()
                if not provider_id:
                    continue
                provider_guards_by_provider_id.setdefault(provider_id, []).append(guard)
            provider_reserved_capacity_by_provider_id = await self._provider_reserved_capacity_by_provider(payload)

        for tenant in tenants:
            tenant_id = str(tenant.id)
            profile = tenant.profile if isinstance(tenant.profile, dict) else {}

            if target_type == "guard":
                results.append(self._candidate_from_guard(tenant_id, getattr(tenant, "ownership_type", None), profile, payload))
                continue

            operating_regions = profile.get("operating_regions") if isinstance(profile.get("operating_regions"), list) else []
            if not operating_regions:
                empty_region = {
                    "province": self._get_nested(profile, ["head_office_address", "province"], ""),
                    "region_code": self._get_nested(profile, ["head_office_address", "province"], ""),
                    "city": self._get_nested(profile, ["head_office_address", "city"], ""),
                    "city_codes": [],
                    "coverage_radius_km": None,
                    "latitude": self._get_nested(profile, ["head_office_address", "latitude"], None),
                    "longitude": self._get_nested(profile, ["head_office_address", "longitude"], None),
                }
                operating_regions = [empty_region]

            best_candidate: Optional[RequestMatchCandidate] = None
            best_rank = -1
            for region in operating_regions:
                if not isinstance(region, dict):
                    continue
                candidate = self._candidate_from_provider_region(tenant_id, profile, region, payload)
                rank = 0
                if candidate.reason_code == "within_radius" and candidate.eligible:
                    rank = 4
                elif candidate.reason_code == "missing_geo" and candidate.eligible:
                    rank = 3
                elif candidate.reason_code == "outside_radius":
                    rank = 2
                elif candidate.reason_code == "city_mismatch":
                    rank = 1
                elif candidate.reason_code == "province_mismatch":
                    rank = 0

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = candidate

            if best_candidate is not None:
                if best_candidate.eligible:
                    provider_capacity = self._provider_guard_capacity_from_tenants(
                        tenant_id,
                        provider_guards_by_provider_id.get(tenant_id, []),
                        payload,
                        reserved_guard_count=provider_reserved_capacity_by_provider_id.get(tenant_id, 0),
                    )
                    best_candidate.linked_guard_count = provider_capacity["linked_guard_count"]
                    best_candidate.eligible_guard_count = provider_capacity["eligible_guard_count"]
                    best_candidate.reserved_guard_count = provider_capacity["reserved_guard_count"]
                    best_candidate.available_guard_count = provider_capacity["available_guard_count"]
                    if provider_capacity["available_guard_count"] <= 0:
                        best_candidate.eligible = False
                        best_candidate.reason_code = "insufficient_capacity"
                results.append(best_candidate)

        results.sort(
            key=lambda item: (
                0 if item.eligible else 1,
                item.distance_km if item.distance_km is not None else 999999,
                item.candidate_name.lower(),
            )
        )

        full_results = list(results)

        if len(results) > payload.max_results:
            results = results[:payload.max_results]

        summary = {
            "target_type": target_type,
            "total_candidates": len(full_results),
            "eligible_count": len([r for r in full_results if r.eligible]),
            "ownership_excluded_count": len([r for r in full_results if r.reason_code == "ownership_excluded"]),
            "outside_availability_count": len([r for r in full_results if r.reason_code == "outside_availability"]),
            "outside_radius_count": len([r for r in full_results if r.reason_code == "outside_radius"]),
            "province_mismatch_count": len([r for r in full_results if r.reason_code == "province_mismatch"]),
            "city_mismatch_count": len([r for r in full_results if r.reason_code == "city_mismatch"]),
            "guard_type_mismatch_count": len([r for r in full_results if r.reason_code == "guard_type_mismatch"]),
            "insufficient_capacity_count": len([r for r in full_results if r.reason_code == "insufficient_capacity"]),
            "missing_geo_count": len([r for r in full_results if r.reason_code == "missing_geo"]),
            "returned_count": len(results),
        }

        return RequestMatchingPreviewResult(summary=summary, results=results)
