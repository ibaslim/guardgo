import math
import threading
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    RequestMatchingPreviewPayload,
    RequestMatchingPreviewResult,
    RequestMatchCandidate,
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
        parts = text.split(":")
        if len(parts) < 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except Exception:
            return None
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
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
    ) -> RequestMatchCandidate:
        request_address = payload.site_address
        request_province = self._normalize_text(request_address.province)

        home_address = profile.get("home_address") if isinstance(profile.get("home_address"), dict) else {}
        province = self._normalize_text(profile.get("operational_region_code") or home_address.get("province"))
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
        if normalized_ownership == GuardOwnershipType.SERVICE_PROVIDER.value:
            candidate.reason_code = "ownership_excluded"
            candidate.distance_source = "province_fallback"
            return candidate

        if request_province and province != request_province:
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

    def _candidate_from_provider_region(
        self,
        tenant_id: str,
        profile: Dict[str, Any],
        region: Dict[str, Any],
        payload: RequestMatchingPreviewPayload,
    ) -> RequestMatchCandidate:
        request_address = payload.site_address
        request_province = self._normalize_text(request_address.province)
        request_city_text = self._normalize_text(request_address.city)

        province = self._normalize_text(region.get("region_code") or region.get("province"))

        city_codes = region.get("city_codes") if isinstance(region.get("city_codes"), list) else []
        city_labels = region.get("city_labels") if isinstance(region.get("city_labels"), list) else []
        city = self._first_non_empty_string([
            city_labels[0] if city_labels else "",
            city_codes[0] if city_codes else "",
            region.get("city"),
        ])

        radius_km = self._as_float(region.get("coverage_radius_km"))
        city_entries = region.get("city_entries") if isinstance(region.get("city_entries"), list) else []
        region_lat = self._as_float(region.get("latitude"))
        region_lon = self._as_float(region.get("longitude"))
        if city_entries:
            matched_entry = None
            for entry in city_entries:
                if not isinstance(entry, dict):
                    continue
                entry_city_code = self._normalize_text(entry.get("city_code"))
                entry_city_name = self._normalize_text(entry.get("city"))
                if request_city_text and (request_city_text == entry_city_code or request_city_text == entry_city_name):
                    matched_entry = entry
                    break

            if matched_entry is None:
                matched_entry = city_entries[0] if isinstance(city_entries[0], dict) else None

            if matched_entry is not None:
                radius_km = self._as_float(matched_entry.get("coverage_radius_km"))
                city = self._first_non_empty_string([
                    matched_entry.get("city"),
                    matched_entry.get("city_code"),
                    city,
                ])
                region_lat = self._as_float(matched_entry.get("latitude"))
                region_lon = self._as_float(matched_entry.get("longitude"))

        if region_lat is None or region_lon is None:
            head_office = profile.get("head_office_address") if isinstance(profile.get("head_office_address"), dict) else {}
            region_lat = self._as_float(head_office.get("latitude"))
            region_lon = self._as_float(head_office.get("longitude"))

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
            radius_km=normalize_km_for_storage(radius_km) if radius_km is not None else None,
            radius_mi=km_to_miles(radius_km) if radius_km is not None else None,
        )

        if request_province and province != request_province:
            return candidate

        if radius_km is None:
            candidate.eligible = True
            candidate.reason_code = "within_radius"
            candidate.distance_source = "province_fallback"
            return candidate

        if None in [region_lat, region_lon, req_lat, req_lon]:
            candidate.reason_code = "missing_geo"
            candidate.distance_source = "province_fallback"
            candidate.eligible = bool(payload.fallback_to_province_when_missing_geo)
            return candidate

        distance_km = normalize_km_for_storage(self._haversine_km(region_lat, region_lon, req_lat, req_lon))
        distance_mi = km_to_miles(distance_km)
        candidate.distance_km = distance_km
        candidate.distance_mi = distance_mi
        candidate.distance_source = "haversine"

        if distance_km <= radius_km:
            candidate.eligible = True
            candidate.reason_code = "within_radius"
        else:
            candidate.eligible = False
            candidate.reason_code = "outside_radius"

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
                elif candidate.reason_code == "province_mismatch":
                    rank = 1

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = candidate

            if best_candidate is not None:
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
            "missing_geo_count": len([r for r in full_results if r.reason_code == "missing_geo"]),
            "returned_count": len(results),
        }

        return RequestMatchingPreviewResult(summary=summary, results=results)
