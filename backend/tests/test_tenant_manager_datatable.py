from datetime import datetime, timezone

import pytest

from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantStatus, TenantType


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return self.docs


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs
        self.filter = None

    def find(self, query):
        self.filter = query
        return FakeCursor(self.docs)


class FakeEngine:
    def __init__(self, docs):
        self.collection = FakeCollection(docs)

    def get_collection(self, _model):
        return self.collection


def _doc(_id, name, tenant_type, status, created_at):
    return {
        "_id": _id,
        "profile": {"name": name},
        "tenant_type": tenant_type,
        "status": status,
        "verified": False,
        "subscription": False,
        "user_quota": 2,
        "approvals_required": 2,
        "approval_actors": [],
        "created_at": created_at,
        "updated_at": created_at,
        "verified_date": None,
    }


@pytest.mark.anyio
async def test_get_tenants_datatable_filters_and_sorts_by_name():
    docs = [
        _doc("1", "Zeta Guard", TenantType.GUARD.value, TenantStatus.PENDING_ACTIVATION.value, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        _doc("2", "Alpha Guard", TenantType.GUARD.value, TenantStatus.PENDING_VERIFICATION.value, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _doc("3", "Client Co", TenantType.CLIENT.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(docs)

    result = await manager.get_tenants_datatable(
        page=1,
        rows=10,
        tenant_type="guard",
        tenant_status="pending_activation",
        keyword="guard",
        sort_by="name",
        sort_order="asc",
    )

    assert len(result["items"]) == 2
    assert result["items"][0]["name"] == "Alpha Guard"
    assert result["items"][1]["name"] == "Zeta Guard"
    assert result["items"][0]["status"] == TenantStatus.PENDING_ACTIVATION.value
    assert result["pagination"]["total_items"] == 2


@pytest.mark.anyio
async def test_get_tenants_datatable_defaults_rows_page_and_sort_field():
    docs = [
        _doc("1", "Tenant A", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        _doc("2", "Tenant B", TenantType.CLIENT.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(docs)

    result = await manager.get_tenants_datatable(
        page=0,
        rows=0,
        sort_by="unknown_field",
        sort_order="desc",
    )

    assert result["pagination"]["page"] == 1
    assert result["pagination"]["rows"] == 10
    assert result["filters"]["sort_by"] == "created_at"
    assert result["filters"]["sort_order"] == "desc"
    assert len(result["items"]) == 2


@pytest.mark.anyio
async def test_get_tenants_datatable_sorts_by_id_ascending():
    docs = [
        _doc("z-id", "Tenant Z", TenantType.CLIENT.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 3, tzinfo=timezone.utc)),
        _doc("a-id", "Tenant A", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(docs)

    result = await manager.get_tenants_datatable(page=1, rows=10, sort_by="id", sort_order="asc")

    assert [item["id"] for item in result["items"]] == ["a-id", "z-id"]


@pytest.mark.anyio
async def test_get_tenants_datatable_keyword_matches_id_and_profile():
    docs = [
        _doc("tenant-123", "Acme Security", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _doc("tenant-999", "Other Corp", TenantType.CLIENT.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(docs)

    by_id = await manager.get_tenants_datatable(page=1, rows=10, keyword="123")
    assert len(by_id["items"]) == 1
    assert by_id["items"][0]["id"] == "tenant-123"

    by_profile_name = await manager.get_tenants_datatable(page=1, rows=10, keyword="acme")
    assert len(by_profile_name["items"]) == 1
    assert by_profile_name["items"][0]["name"] == "Acme Security"


@pytest.mark.anyio
async def test_get_tenants_datatable_pagination_bounds():
    docs = [
        _doc("1", "Tenant 1", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _doc("2", "Tenant 2", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        _doc("3", "Tenant 3", TenantType.GUARD.value, TenantStatus.ACTIVE.value, datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]
    manager = object.__new__(TenantManager)
    manager._engine = FakeEngine(docs)

    result = await manager.get_tenants_datatable(page=2, rows=2, sort_by="created_at", sort_order="asc")

    assert result["pagination"]["total_items"] == 3
    assert result["pagination"]["total_pages"] == 2
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == "3"
