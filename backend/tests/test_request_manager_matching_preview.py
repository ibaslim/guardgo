from datetime import datetime

import pytest

from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_request_model import RequestFulfillmentMode


@pytest.mark.anyio
async def test_preview_matches_for_request_forwards_requested_window(monkeypatch):
    captured = {}

    class FakeMatcher:
        async def preview_matches(self, payload):
            captured["target_type"] = payload.target_type
            captured["requested_start_at"] = payload.requested_start_at
            captured["requested_end_at"] = payload.requested_end_at
            captured["site_province"] = payload.site_address.province
            return type("PreviewResult", (), {"summary": {}, "results": []})()

    from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager

    monkeypatch.setattr(RequestMatchingManager, "get_instance", staticmethod(lambda: FakeMatcher()))

    manager = object.__new__(RequestManager)
    await manager._preview_matches_for_request(
        RequestFulfillmentMode.INDIVIDUAL_ONLY,
        {
            "site_address": {
                "country": "CA",
                "province": "ON",
                "city": "Toronto",
                "latitude": 43.6532,
                "longitude": -79.3832,
            }
        },
        max_results=25,
        requested_start_at=datetime(2026, 4, 27, 10, 0),
        requested_end_at=datetime(2026, 4, 27, 12, 0),
    )

    assert captured == {
        "target_type": "guard",
        "requested_start_at": datetime(2026, 4, 27, 10, 0),
        "requested_end_at": datetime(2026, 4, 27, 12, 0),
        "site_province": "ON",
    }
