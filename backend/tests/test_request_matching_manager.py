from datetime import datetime

import pytest

from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    MatchAddress,
    RequestMatchingPreviewPayload,
)
from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager
from orion.services.mongo_manager.shared_model.db_tenant_model import (
    GuardOwnershipType,
    TenantStatus,
    TenantType,
    db_tenant_model,
)


class FakeEngine:
    def __init__(self, tenants):
        self.tenants = tenants

    async def find(self, *_args, **_kwargs):
        return self.tenants


def _guard_tenant(*, ownership_type=GuardOwnershipType.PLATFORM, weekly_availability=None):
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
        },
    )


def _provider_tenant(*, city_latitude=43.6532, city_longitude=-79.3832):
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
                    "city_entries": [
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
        },
    )


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
async def test_preview_matches_prefers_provider_city_entry_coordinates_over_head_office():
    manager = object.__new__(RequestMatchingManager)
    manager._engine = FakeEngine([
        _provider_tenant(),
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
