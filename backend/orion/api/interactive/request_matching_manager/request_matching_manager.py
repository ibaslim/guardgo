import math
import threading
from typing import Any, Dict, List, Optional

from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    RequestMatchingPreviewPayload,
    RequestMatchingPreviewResult,
    RequestMatchCandidate,
)
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantType, TenantStatus

from configs.distance_units import km_to_miles, normalize_km_for_storage


class RequestMatchingManager:
    __instance = None
    __lock = threading.Lock()

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

        if request_province and province != request_province:
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
        region_lat = self._as_float(region.get("latitude"))
        region_lon = self._as_float(region.get("longitude"))

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
                results.append(self._candidate_from_guard(tenant_id, profile, payload))
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
            "outside_radius_count": len([r for r in full_results if r.reason_code == "outside_radius"]),
            "province_mismatch_count": len([r for r in full_results if r.reason_code == "province_mismatch"]),
            "missing_geo_count": len([r for r in full_results if r.reason_code == "missing_geo"]),
            "returned_count": len(results),
        }

        return RequestMatchingPreviewResult(summary=summary, results=results)
