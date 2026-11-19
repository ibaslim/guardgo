from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestRecord, ShiftAttendanceEventRecord, ShiftInstanceRecord, ShiftSlotRecord,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantType


class Cursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, key, direction=None):
        if isinstance(key, list):
            self.documents.sort(key=lambda doc: (doc["arrived_at"], doc["_id"]))
        else:
            self.documents.sort(key=lambda doc: doc[key], reverse=direction == -1)
        return self

    async def to_list(self, length=None):
        return list(self.documents)


class Collection:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def find(self, query):
        self.queries.append(query)
        def matches(doc):
            for key, expected in query.items():
                actual = doc.get(key)
                if isinstance(expected, dict):
                    if "$in" in expected and actual not in expected["$in"]: return False
                    if "$nin" in expected and actual in expected["$nin"]: return False
                    if "$ne" in expected and actual == expected["$ne"]: return False
                    if "$gt" in expected and (actual is None or actual <= expected["$gt"]): return False
                elif actual != expected:
                    return False
            return True
        return Cursor([doc for doc in self.docs if matches(doc)])


@pytest.mark.anyio
async def test_pending_arrivals_scope_filters_and_paging(monkeypatch):
    now = datetime.utcnow()
    request_id, shift_id, ended_id, cancelled_id = [ObjectId() for _ in range(4)]
    slots = [{"_id": ObjectId(), "request_id": str(request_id), "shift_instance_id": str(shift_id),
              "client_tenant_id": "client-a", "slot_number": i, "slot_status": "client_confirmation_pending",
              "arrived_at": now - timedelta(minutes=110-i), "assigned_guard_tenant_id": "guard-a"} for i in range(110)]
    slots += [dict(slots[0], _id=ObjectId(), client_tenant_id="client-b"),
              dict(slots[0], _id=ObjectId(), shift_instance_id=str(ended_id)),
              dict(slots[0], _id=ObjectId(), shift_instance_id=str(cancelled_id)),
              dict(slots[0], _id=ObjectId(), client_confirmed_at=now)]
    shifts = [{"_id": shift_id, "instance_status": "staffed", "shift_end_at_utc": now + timedelta(hours=1)},
              {"_id": ended_id, "instance_status": "staffed", "shift_end_at_utc": now - timedelta(seconds=1)},
              {"_id": cancelled_id, "instance_status": "cancelled", "shift_end_at_utc": now + timedelta(hours=1)}]
    requests = [{"_id": request_id, "request_status": "submitted", "title": "Patrol", "site_snapshot": {"site_name": "HQ"}}]
    events = [{"shift_slot_id": str(slots[0]["_id"]), "event_type": "arrived", "timestamp": now, "distance_meters": 42.6}]
    collections = {ShiftSlotRecord: Collection(slots), ShiftInstanceRecord: Collection(shifts),
                   ClientRequestRecord: Collection(requests), ShiftAttendanceEventRecord: Collection(events)}
    manager = object.__new__(RequestShiftManager)
    manager._engine = SimpleNamespace(get_collection=lambda model: collections[model])
    class RequestManagerStub:
        _role_value = staticmethod(lambda user: user.role)
        _is_platform_write_role = staticmethod(lambda role: role == "admin")
        async def _get_session_tenant(self, user): return SimpleNamespace(id=user.tenant, tenant_type=TenantType.CLIENT)
        async def _build_tenant_label_lookup(self, ids): return {guard: "Sam Carter" for guard in ids}
    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: RequestManagerStub()))
    user = SimpleNamespace(role="client_admin", tenant="client-a")
    first = await manager.list_pending_arrivals(user, page=1, rows=100)
    second = await manager.list_pending_arrivals(user, page=2, rows=100)
    assert first["total"] == second["total"] == 110
    assert len(first["items"]) == 100 and len(second["items"]) == 10
    assert len({item["slot_id"] for item in first["items"] + second["items"]}) == 110
    assert first["items"][0]["assigned_guard_name"] == "Sam Carter"
    assert first["items"][0]["distance_meters"] == 42.6
    assert collections[ShiftSlotRecord].queries[0]["client_tenant_id"] == "client-a"
    other = await manager.list_pending_arrivals(SimpleNamespace(role="client_admin", tenant="client-b"))
    assert other["total"] == 1
    platform = await manager.list_pending_arrivals(SimpleNamespace(role="admin"), rows=1)
    assert platform["total"] == 111
    filtered = await manager.list_pending_arrivals(user, request_id=str(request_id), shift_id=str(shift_id), rows=1)
    assert filtered["total"] == 110
    empty = await manager.list_pending_arrivals(user, request_id=str(ObjectId()))
    assert empty == {"items": [], "total": 0, "page": 1, "rows": 20}
    with pytest.raises(HTTPException) as exc:
        await manager.list_pending_arrivals(SimpleNamespace(role="guard_admin"))
    assert exc.value.status_code == 403


def test_pending_predicate_requires_matching_slot_and_active_shift():
    now = datetime.utcnow()
    slot = {"slot_status": "client_confirmation_pending", "arrived_at": now, "client_confirmed_at": None, "started_at": None}
    shift = {"instance_status": "staffed", "shift_end_at_utc": now + timedelta(hours=1)}
    assert RequestShiftManager._is_pending_arrival(slot, shift, now)
    for key, value in [("arrived_at", None), ("client_confirmed_at", now), ("started_at", now), ("slot_status", "reserved")]:
        assert not RequestShiftManager._is_pending_arrival(dict(slot, **{key: value}), shift, now)
    assert not RequestShiftManager._is_pending_arrival(slot, dict(shift, instance_status="completed"), now)
    assert not RequestShiftManager._is_pending_arrival(slot, dict(shift, shift_end_at_utc=now), now)
