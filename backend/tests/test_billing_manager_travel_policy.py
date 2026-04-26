from types import SimpleNamespace

import pytest

from orion.api.interactive.billing_manager.billing_manager import BillingManager
from orion.services.mongo_manager.shared_model.db_billing_model import TravelPricingPolicy


class FakeEngine:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.saved = []

    async def find(self, model, *_args, **_kwargs):
        if model is TravelPricingPolicy:
            return list(self.existing)
        return []

    async def find_one(self, model, *args, **_kwargs):
        if model is not TravelPricingPolicy:
            return None

        query = args[0] if args else {}
        requested_scope = _extract_query_value(query, "scope")
        requested_region_code = _extract_query_value(query, "region_code")
        requested_city_code = _extract_query_value(query, "city_code")

        for policy in self.existing:
            if requested_scope is not None and policy.scope != requested_scope:
                continue
            if requested_region_code is not None and policy.region_code != requested_region_code:
                continue
            if requested_city_code is not None and policy.city_code != requested_city_code:
                continue
            return policy
        return None

    async def save(self, model):
        self.saved.append(model)
        if isinstance(model, TravelPricingPolicy) and model not in self.existing:
            self.existing.append(model)
        return model


def _extract_query_value(query, field_name: str):
    if isinstance(query, dict):
        if field_name in query:
            payload = query[field_name]
            if isinstance(payload, dict) and "$eq" in payload:
                return payload["$eq"]
            return payload
        if "$and" in query:
            for entry in query["$and"]:
                value = _extract_query_value(entry, field_name)
                if value is not None:
                    return value
    return None


@pytest.mark.anyio
async def test_resolve_travel_policy_prefers_city_override():
    manager = object.__new__(BillingManager)
    city_policy = TravelPricingPolicy(
        scope=BillingManager.SCOPE_GUARD_TRAVEL_DEFAULT,
        region_code="ON",
        city_code="TORONTO",
        included_radius_km=15,
        rate_per_km=0.55,
    )
    province_policy = TravelPricingPolicy(
        scope=BillingManager.SCOPE_GUARD_TRAVEL_DEFAULT,
        region_code="ON",
        city_code="",
        included_radius_km=10,
        rate_per_km=0.45,
    )
    calls = {"count": 0}

    async def _find_one(_model, *_args, **_kwargs):
        calls["count"] += 1
        return city_policy if calls["count"] == 1 else province_policy

    manager._engine = SimpleNamespace(find_one=_find_one)

    resolved = await manager.resolve_travel_policy(
        BillingManager.SCOPE_GUARD_TRAVEL_DEFAULT,
        "ON",
        "TORONTO",
    )

    assert resolved["source"] == "city_override"
    assert resolved["included_radius_km"] == 15
    assert resolved["rate_per_km"] == 0.55


@pytest.mark.anyio
async def test_resolve_travel_policy_falls_back_to_region_default():
    manager = object.__new__(BillingManager)
    province_policy = TravelPricingPolicy(
        scope=BillingManager.SCOPE_PROVIDER_TRAVEL_DEFAULT,
        region_code="AB",
        city_code="",
        included_radius_km=12,
        rate_per_km=0.4,
        max_auto_match_radius_km=50,
    )
    calls = {"count": 0}

    async def _find_one(_model, *_args, **_kwargs):
        calls["count"] += 1
        return None if calls["count"] == 1 else province_policy

    manager._engine = SimpleNamespace(find_one=_find_one)

    resolved = await manager.resolve_travel_policy(
        BillingManager.SCOPE_PROVIDER_TRAVEL_DEFAULT,
        "AB",
        "AIRDRIE",
    )

    assert resolved["source"] == "region_default"
    assert resolved["included_radius_km"] == 12
    assert resolved["rate_per_km"] == 0.4
    assert resolved["max_auto_match_radius_km"] == 50


@pytest.mark.anyio
async def test_save_guard_travel_policies_creates_records():
    manager = object.__new__(BillingManager)
    manager._engine = FakeEngine()

    result = await manager.save_guard_travel_policies(
        [
            {
                "region_code": "ON",
                "city_code": "",
                "included_radius_km": 10,
                "rate_per_km": 0.45,
                "max_auto_match_radius_km": 60,
                "manual_review_over_km": 80,
            }
        ],
        current_user=SimpleNamespace(username="platformadmin"),
    )

    assert result["updated_count"] == 1
    assert len(manager._engine.saved) == 1
    saved = manager._engine.saved[0]
    assert saved.scope == BillingManager.SCOPE_GUARD_TRAVEL_DEFAULT
    assert saved.region_code == "ON"
    assert saved.city_code == ""
    assert saved.rate_per_km == 0.45


@pytest.mark.anyio
async def test_get_guard_travel_policies_seeds_defaults_when_empty():
    manager = object.__new__(BillingManager)
    engine = FakeEngine()
    manager._engine = engine

    result = await manager.get_guard_travel_policies()

    province_defaults = [row for row in result if not row.get("city_code")]
    assert province_defaults
    assert len(engine.saved) >= len(province_defaults)
    assert province_defaults[0]["included_radius_km"] == 10.0
    assert province_defaults[0]["rate_per_km"] == 0.45
