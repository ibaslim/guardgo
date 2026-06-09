from datetime import datetime

import pytest
from bson import ObjectId

from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    MatchAddress,
    RequestMatchingPreviewPayload,
)
from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord,
    RequestAssignmentRecord,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    GuardOwnershipType,
    TenantStatus,
    TenantType,
    db_tenant_model,
)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query):
        return _FakeCursor(self._docs)


class FakeEngine:
    def __init__(self, tenants, *, assignments=None, requests=None):
        self.tenants = tenants
        self.assignments = assignments or []
        self.requests = requests or []

    async def find(self, model, query=None, *_args, **_kwargs):
        if model is not db_tenant_model:
            return []

        query_text = str(query or "")
        items = [tenant for tenant in self.tenants if getattr(tenant, "status", None) == TenantStatus.ACTIVE]
        if "'tenant_type': {'$eq': 'service_provider'}" in query_text:
            return [tenant for tenant in items if tenant.tenant_type == TenantType.SERVICE_PROVIDER]
        if "'tenant_type': {'$eq': 'guard'}" in query_text:
            items = [tenant for tenant in items if tenant.tenant_type == TenantType.GUARD]
            if "'ownership_type': {'$eq': 'service_provider'}" in query_text:
                items = [
                    tenant for tenant in items if getattr(tenant, "ownership_type", None) == GuardOwnershipType.SERVICE_PROVIDER
                ]
            return items
        return items

    def get_collection(self, model):
        if model is RequestAssignmentRecord:
            return _FakeCollection(self.assignments)
        if model is ClientRequestRecord:
            return _FakeCollection(self.requests)
        raise AssertionError(f"Unexpected collection request: {model}")


def _guard_tenant(*, ownership_type=GuardOwnershipType.PLATFORM, weekly_availability=None, preferred_guard_types=None):
    return db_tenant_model(
        tenant_type=TenantType.GUARD,
        status=TenantStatus.ACTIVE,
        ownership_type=ownership_type,
        profile={
            "full_name": "Eligible Guard",
            "home_address": {
                "province": "ON",
                "city": "Toronto",
                "latitude": 43.6532,
                "longitude": -79.3832,
            },
            "operational_region_code": "ON",
            "operational_city_code": "Toronto",
            "max_travel_radius_km": 15,
            "weekly_availability": weekly_availability
            if weekly_availability is not None
            else {
                "Monday": [{"start": "09:00", "end": "17:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
            "preferred_guard_types": preferred_guard_types if preferred_guard_types is not None else ["armed"],
        },
    )


def _provider_tenant(*, city_latitude=43.6532, city_longitude=-79.3832, city_entries=None, guard_categories_offered=None):
    return db_tenant_model(
        tenant_type=TenantType.SERVICE_PROVIDER,
        status=TenantStatus.ACTIVE,
        profile={
            "legal_company_name": "Provider One",
            "head_office_address": {
                "province": "ON",
                "city": "Toronto",
                "latitude": 45.4215,
                "longitude": -75.6972,
            },
            "operating_regions": [
                {
                    "country": "CA",
                    "province": "ON",
                    "region_code": "ON",
                    "city_codes": ["TORONTO"],
                    "coverage_radius_km": 20,
                    "city_entries": city_entries if city_entries is not None else [
                        {
                            "city_code": "TORONTO",
                            "city": "Toronto",
                            "coverage_radius_km": 20,
                            "latitude": city_latitude,
                            "longitude": city_longitude,
                        }
                    ],
                }
            ],
            "guard_categories_offered": guard_categories_offered if guard_categories_offered is not None else ["armed"],
        },
    )


def _linked_provider_guard(
    provider_tenant_id: str,
    *,
    weekly_availability=None,
    preferred_guard_types=None,
    home_latitude=43.6532,
    home_longitude=-79.3832,
    max_travel_radius_km=15,
):
    return db_tenant_model(
        tenant_type=TenantType.GUARD,
        status=TenantStatus.ACTIVE,
        ownership_type=GuardOwnershipType.SERVICE_PROVIDER,
        service_provider_tenant_id=provider_tenant_id,
        profile={
            "full_name": "Provider Guard",
            "home_address": {
                "province": "ON",
                "city": "Toronto",
                "latitude": home_latitude,
                "longitude": home_longitude,
            },
            "operational_region_code": "ON",
            "operational_city_code": "Toronto",
            "max_travel_radius_km": max_travel_radius_km,
            "weekly_availability": weekly_availability
            if weekly_availability is not None
            else {
                "Monday": [{"start": "09:00", "end": "17:00"}],
                "Tuesday": [],
                "Wednesday": [],
                "Thursday": [],
                "Friday": [],
                "Saturday": [],
                "Sunday": [],
            },
            "preferred_guard_types": preferred_guard_types if preferred_guard_types is not None else ["armed"],
        },
    )


def _provider_request_doc(*, requested_start_at, requested_end_at):
    request_id = ObjectId()
    return {
        "_id": request_id,
        "requested_start_at": requested_start_at,
        "requested_end_at": requested_end_at,
    }


def _provider_assignment_doc(*, provider_tenant_id: str, request_id: ObjectId, slots_committed: int):
    return {
        "request_id": str(request_id),
        "assignee_tenant_id": provider_tenant_id,
        "assignee_tenant_type": "service_provider",
        "assignment_scope": "request",
        "assignment_status": "accepted",
        "slots_committed": slots_committed,
    }


@pytest.mark.anyio
async def test_preview_matches_excludes_service_provider_owned_guards():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _guard_tenant(ownership_type=GuardOwnershipType.SERVICE_PROVIDER),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["ownership_excluded_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert len(result.results) == 1
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "ownership_excluded"


@pytest.mark.anyio
async def test_preview_matches_respects_guard_weekly_availability():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _guard_tenant(),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 18, 0),
            requested_end_at=datetime(2026, 4, 27, 20, 0),
        )
    )

    assert result.summary["outside_availability_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert len(result.results) == 1
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "outside_availability"


@pytest.mark.anyio
async def test_preview_matches_marks_guard_missing_geo_ineligible():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _guard_tenant(),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=None,
                longitude=None,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["missing_geo_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "missing_geo"


@pytest.mark.anyio
async def test_preview_matches_keeps_platform_guards_eligible_when_available():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _guard_tenant(),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["eligible_count"] == 1
    assert result.summary["ownership_excluded_count"] == 0
    assert result.summary["outside_availability_count"] == 0
    assert len(result.results) == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_normalizes_canadian_province_labels_and_codes():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        db_tenant_model(
            tenant_type=TenantType.GUARD,
            status=TenantStatus.ACTIVE,
            ownership_type=GuardOwnershipType.PLATFORM,
            profile={
                "full_name": "BC Guard",
                "home_address": {
                    "province": "BC",
                    "city": "Vancouver",
                    "country": "CA",
                    "latitude": 49.282893,
                    "longitude": -123.120664,
                },
                "operational_region_code": "BC",
                "operational_city_code": "VANCOUVER",
                "max_travel_radius_km": 30,
                "weekly_availability": {
                    "Wednesday": [{"start": "09:00", "end": "21:00"}],
                },
                "preferred_guard_types": ["armed"],
            },
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="British Columbia",
                city="Vancouver",
                latitude=49.282445,
                longitude=-123.123067,
            ),
            requested_start_at=datetime(2026, 5, 20, 18, 0),
            requested_end_at=datetime(2026, 5, 20, 20, 0),
        )
    )

    assert result.summary["province_mismatch_count"] == 0
    assert result.summary["outside_availability_count"] == 0
    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_accepts_am_pm_weekly_availability_format():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        db_tenant_model(
            tenant_type=TenantType.GUARD,
            status=TenantStatus.ACTIVE,
            ownership_type=GuardOwnershipType.PLATFORM,
            profile={
                "full_name": "AM PM Guard",
                "home_address": {
                    "province": "BC",
                    "city": "Vancouver",
                    "country": "CA",
                    "latitude": 49.282893,
                    "longitude": -123.120664,
                },
                "operational_region_code": "BC",
                "operational_city_code": "VANCOUVER",
                "max_travel_radius_km": 30,
                "weekly_availability": {
                    "Wednesday": [{"start": "12:00 PM", "end": "9:00 PM"}],
                },
                "preferred_guard_types": ["armed"],
            },
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="British Columbia",
                city="Vancouver",
                latitude=49.282445,
                longitude=-123.123067,
            ),
            requested_start_at=datetime(2026, 5, 20, 18, 0),
            requested_end_at=datetime(2026, 5, 20, 20, 0),
        )
    )

    assert result.summary["outside_availability_count"] == 0
    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_accepts_overnight_window_ending_at_day_boundary():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        db_tenant_model(
            tenant_type=TenantType.GUARD,
            status=TenantStatus.ACTIVE,
            ownership_type=GuardOwnershipType.PLATFORM,
            profile={
                "full_name": "Night Shift Guard",
                "home_address": {
                    "province": "BC",
                    "city": "Vancouver",
                    "country": "CA",
                    "latitude": 49.282893,
                    "longitude": -123.120664,
                },
                "operational_region_code": "BC",
                "operational_city_code": "VANCOUVER",
                "max_travel_radius_km": 30,
                "weekly_availability": {
                    "Wednesday": [{"start": "9:00 PM", "end": "6:00 AM"}],
                },
                "preferred_guard_types": ["armed"],
            },
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="British Columbia",
                city="Vancouver",
                latitude=49.282445,
                longitude=-123.123067,
            ),
            requested_start_at=datetime(2026, 5, 20, 23, 0),
            requested_end_at=datetime(2026, 5, 21, 6, 0),
        )
    )

    assert result.summary["outside_availability_count"] == 0
    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_accepts_wrapped_calendar_style_availability_range():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        db_tenant_model(
            tenant_type=TenantType.GUARD,
            status=TenantStatus.ACTIVE,
            ownership_type=GuardOwnershipType.PLATFORM,
            profile={
                "full_name": "Near Full Day Guard",
                "home_address": {
                    "province": "BC",
                    "city": "Vancouver",
                    "country": "CA",
                    "latitude": 49.282893,
                    "longitude": -123.120664,
                },
                "operational_region_code": "BC",
                "operational_city_code": "VANCOUVER",
                "max_travel_radius_km": 30,
                "weekly_availability": {
                    "Wednesday": [{"start": "12:00 AM", "end": "11:55 PM"}],
                },
                "preferred_guard_types": ["armed"],
            },
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="British Columbia",
                city="Vancouver",
                latitude=49.282445,
                longitude=-123.123067,
            ),
            requested_start_at=datetime(2026, 5, 21, 2, 0),
            requested_end_at=datetime(2026, 5, 21, 3, 0),
        )
    )

    assert result.summary["outside_availability_count"] == 0
    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_accepts_night_request_for_daily_near_full_day_availability():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        db_tenant_model(
            tenant_type=TenantType.GUARD,
            status=TenantStatus.ACTIVE,
            ownership_type=GuardOwnershipType.PLATFORM,
            profile={
                "full_name": "Daily Availability Guard",
                "home_address": {
                    "province": "BC",
                    "city": "Vancouver",
                    "country": "CA",
                    "latitude": 49.282893,
                    "longitude": -123.120664,
                },
                "operational_region_code": "BC",
                "operational_city_code": "VANCOUVER",
                "max_travel_radius_km": 30,
                "weekly_availability": {
                    "Wednesday": [{"start": "12:00 AM", "end": "11:59 PM"}],
                },
                "preferred_guard_types": ["armed"],
            },
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="British Columbia",
                city="Vancouver",
                latitude=49.282445,
                longitude=-123.123067,
            ),
            requested_start_at=datetime(2026, 5, 20, 21, 0),
            requested_end_at=datetime(2026, 5, 21, 1, 0),
        )
    )

    assert result.summary["outside_availability_count"] == 0
    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"


@pytest.mark.anyio
async def test_preview_matches_prefers_provider_city_entry_coordinates_over_head_office():
    provider = _provider_tenant()
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        provider,
        _linked_provider_guard(str(provider.id)),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
        )
    )

    assert result.summary["eligible_count"] == 1
    assert len(result.results) == 1
    assert result.results[0].eligible is True
    assert result.results[0].reason_code == "within_radius"
    assert result.results[0].distance_source == "haversine"
    assert result.results[0].distance_km == pytest.approx(0.0, abs=0.1)
    assert result.results[0].linked_guard_count == 1
    assert result.results[0].available_guard_count == 1


@pytest.mark.anyio
async def test_preview_matches_respects_requested_guard_type_for_guards():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _guard_tenant(preferred_guard_types=["unarmed"]),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="guard",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["guard_type_mismatch_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "guard_type_mismatch"


@pytest.mark.anyio
async def test_preview_matches_uses_best_provider_city_entry_when_request_city_differs():
    provider = _provider_tenant(
        city_entries=[
            {
                "city_code": "TORONTO",
                "city": "Toronto",
                "coverage_radius_km": 20,
                "latitude": 43.6532,
                "longitude": -79.3832,
            },
            {
                "city_code": "VANCOUVER",
                "city": "Vancouver",
                "coverage_radius_km": 20,
                "latitude": 49.2827,
                "longitude": -123.1207,
            },
        ]
    )
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        provider,
        _linked_provider_guard(
            str(provider.id),
            home_latitude=49.2827,
            home_longitude=-123.1207,
            max_travel_radius_km=20,
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Burnaby",
                latitude=49.2730,
                longitude=-123.1037,
            ),
        )
    )

    assert result.summary["eligible_count"] == 1
    assert len(result.results) == 1
    assert result.results[0].eligible is True
    assert result.results[0].city == "Vancouver"
    assert result.results[0].reason_code == "within_radius"
    assert result.results[0].distance_source == "haversine"
    assert result.results[0].available_guard_count == 1


@pytest.mark.anyio
async def test_preview_matches_marks_provider_city_mismatch_without_geo_or_exact_city():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _provider_tenant(
            city_entries=[
                {
                    "city_code": "TORONTO",
                    "city": "Toronto",
                    "coverage_radius_km": 20,
                    "latitude": 43.6532,
                    "longitude": -79.3832,
                }
            ]
        ),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Ottawa",
                latitude=None,
                longitude=None,
            ),
        )
    )

    assert result.summary["city_mismatch_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "city_mismatch"


@pytest.mark.anyio
async def test_preview_matches_respects_requested_guard_type_for_providers():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _provider_tenant(guard_categories_offered=["unarmed"]),
    ])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            requested_guard_type="armed",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
        )
    )

    assert result.summary["guard_type_mismatch_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "guard_type_mismatch"


@pytest.mark.anyio
async def test_preview_matches_marks_provider_insufficient_capacity_without_linked_guards():
    provider = _provider_tenant()
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([provider])

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["insufficient_capacity_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "insufficient_capacity"
    assert result.results[0].linked_guard_count == 0
    assert result.results[0].available_guard_count == 0


@pytest.mark.anyio
async def test_preview_matches_reduces_provider_available_capacity_for_overlapping_committed_work():
    provider = _provider_tenant()
    overlapping_request = _provider_request_doc(
        requested_start_at=datetime(2026, 4, 27, 9, 0),
        requested_end_at=datetime(2026, 4, 27, 13, 0),
    )
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine(
        [
            provider,
            _linked_provider_guard(str(provider.id)),
            _linked_provider_guard(str(provider.id), home_latitude=43.6540, home_longitude=-79.3840),
        ],
        assignments=[
            _provider_assignment_doc(
                provider_tenant_id=str(provider.id),
                request_id=overlapping_request["_id"],
                slots_committed=1,
            )
        ],
        requests=[overlapping_request],
    )

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["eligible_count"] == 1
    assert result.results[0].eligible is True
    assert result.results[0].linked_guard_count == 2
    assert result.results[0].eligible_guard_count == 2
    assert result.results[0].reserved_guard_count == 1
    assert result.results[0].available_guard_count == 1


@pytest.mark.anyio
async def test_preview_matches_marks_provider_insufficient_capacity_when_overlapping_commitments_exhaust_guards():
    provider = _provider_tenant()
    overlapping_request = _provider_request_doc(
        requested_start_at=datetime(2026, 4, 27, 9, 0),
        requested_end_at=datetime(2026, 4, 27, 13, 0),
    )
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine(
        [
            provider,
            _linked_provider_guard(str(provider.id)),
            _linked_provider_guard(str(provider.id), home_latitude=43.6540, home_longitude=-79.3840),
        ],
        assignments=[
            _provider_assignment_doc(
                provider_tenant_id=str(provider.id),
                request_id=overlapping_request["_id"],
                slots_committed=2,
            )
        ],
        requests=[overlapping_request],
    )

    result = await manager.preview_matches(
        RequestMatchingPreviewPayload(
            target_type="service_provider",
            site_address=MatchAddress(
                country="CA",
                province="ON",
                city="Toronto",
                latitude=43.6532,
                longitude=-79.3832,
            ),
            requested_start_at=datetime(2026, 4, 27, 10, 0),
            requested_end_at=datetime(2026, 4, 27, 12, 0),
        )
    )

    assert result.summary["insufficient_capacity_count"] == 1
    assert result.summary["eligible_count"] == 0
    assert result.results[0].eligible is False
    assert result.results[0].reason_code == "insufficient_capacity"
    assert result.results[0].eligible_guard_count == 2
    assert result.results[0].reserved_guard_count == 2
    assert result.results[0].available_guard_count == 0
