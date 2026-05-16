from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from configs.app_dependency import get_current_role, get_current_status, get_current_user
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from routes.request_routes import request_routes


def _app(role=user_role.CLIENT_ADMIN):
    app = FastAPI()
    app.include_router(request_routes)
    current_user = SimpleNamespace(username="tester", role=role, tenant_uuid="507f1f77bcf86cd799439011")

    async def _current_user():
        return current_user

    async def _current_role():
        return role

    async def _current_status():
        return UserStatus.ACTIVE

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_role] = _current_role
    app.dependency_overrides[get_current_status] = _current_status
    return app


@pytest.mark.anyio
async def test_list_client_requests_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_requests(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
        response = await client.get("/api/requests?page=2&rows=5&keyword=night&request_status=draft&fulfillment_mode=individual_only")

    assert response.status_code == 200
    assert captured["page"] == 2
    assert captured["rows"] == 5
    assert captured["keyword"] == "night"
    assert captured["request_status"] == "draft"
    assert captured["fulfillment_mode"] == "individual_only"
    assert captured["current_user"].username == "tester"


@pytest.mark.anyio
async def test_create_client_request_calls_manager(monkeypatch):
    captured = {}

    class FakeManager:
        async def create_request(self, payload, current_user):
            captured["title"] = payload.title
            captured["fulfillment_mode"] = payload.fulfillment_mode.value
            captured["user"] = current_user.username
            return {"id": "req-1", "title": payload.title}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests",
            json={"title": "Night shift", "fulfillment_mode": "individual_only", "guards_required": 2, "commit": True},
        )

    assert response.status_code == 201
    assert captured == {"title": "Night shift", "fulfillment_mode": "individual_only", "user": "tester"}


@pytest.mark.anyio
async def test_create_client_request_forbidden_for_guard_admin(monkeypatch):
    class FakeManager:
        async def create_request(self, payload, current_user):
            return {"id": "req-1"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests",
            json={"title": "Night shift", "fulfillment_mode": "individual_only", "guards_required": 2, "commit": True},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_assign_client_request_forwards_request_id_and_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def create_assignment(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["candidate"] = payload.candidate_tenant_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"assignment_id": "as-1", "request_id": request_id}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-22/assign",
            json={"candidate_tenant_id": "tenant-9", "note": "priority"},
        )

    assert response.status_code == 201
    assert captured == {
        "request_id": "req-22",
        "candidate": "tenant-9",
        "note": "priority",
        "user": "tester",
    }


@pytest.mark.anyio
async def test_list_request_jobs_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_jobs(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/jobs?page=3&rows=10&assignment_status=offered&keyword=night")

    assert response.status_code == 200
    assert captured["page"] == 3
    assert captured["rows"] == 10
    assert captured["assignment_status"] == "offered"
    assert captured["keyword"] == "night"


@pytest.mark.anyio
async def test_update_request_job_status_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def update_job_status(self, assignment_id, payload, current_user):
            captured["assignment_id"] = assignment_id
            captured["status"] = payload.assignment_status.value
            captured["user"] = current_user.username
            return {"assignment_id": assignment_id, "assignment_status": payload.assignment_status.value}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.patch(
            "/api/jobs/as-1/status",
            json={"assignment_status": "accepted", "reason": "ready"},
        )

    assert response.status_code == 200
    assert captured == {"assignment_id": "as-1", "status": "accepted", "user": "tester"}


@pytest.mark.anyio
async def test_update_client_request_status_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def update_request_status(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["request_status"] = payload.request_status.value
            captured["user"] = current_user.username
            return {"id": request_id, "request_status": payload.request_status.value}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.patch(
            "/api/requests/req-2/status",
            json={"request_status": "submitted", "reason": "ready"},
        )

    assert response.status_code == 200
    assert captured == {"request_id": "req-2", "request_status": "submitted", "user": "tester"}


@pytest.mark.anyio
async def test_soft_delete_client_request_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def soft_delete_request(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["reason"] = payload.reason
            captured["user"] = current_user.username
            return {"id": request_id, "deleted_reason": payload.reason}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-9/soft-delete",
            json={"reason": "Duplicate request raised during QA."},
        )

    assert response.status_code == 200
    assert captured == {
        "request_id": "req-9",
        "reason": "Duplicate request raised during QA.",
        "user": "tester",
    }


@pytest.mark.anyio
async def test_publish_client_request_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def publish_request(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["max_match_results"] = payload.max_match_results
            captured["user"] = current_user.username
            return {"id": request_id, "message": "published"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-7/publish",
            json={"max_match_results": 15},
        )

    assert response.status_code == 200
    assert captured == {"request_id": "req-7", "max_match_results": 15, "user": "tester"}


@pytest.mark.anyio
async def test_get_client_request_wave_forwards_wave_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_request_wave_by_id(self, wave_id, current_user):
            captured["wave_id"] = wave_id
            captured["user"] = current_user.username
            return {"id": wave_id}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.OPS_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/request-waves/wave-77")

    assert response.status_code == 200
    assert captured == {"wave_id": "wave-77", "user": "tester"}


@pytest.mark.anyio
async def test_get_request_schedule_forwards_request_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_request_schedule(self, request_id, current_user):
            captured["request_id"] = request_id
            captured["user"] = current_user.username
            return {"schedule": {"request_id": request_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/requests/req-55/schedule")

    assert response.status_code == 200
    assert captured == {"request_id": "req-55", "user": "tester"}


@pytest.mark.anyio
async def test_list_shift_exceptions_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_shift_exceptions(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.OPS_ADMIN)), base_url="http://test") as client:
        response = await client.get(
            "/api/shift-exceptions?page=2&rows=5&exception_status=no_show_suspected&request_id=req-44"
            "&date_from=2026-05-01&date_to=2026-05-02"
        )

    assert response.status_code == 200
    assert captured["page"] == 2
    assert captured["rows"] == 5
    assert captured["exception_status"] == "no_show_suspected"
    assert captured["request_id"] == "req-44"
    assert str(captured["date_from"]) == "2026-05-01"
    assert str(captured["date_to"]) == "2026-05-02"
    assert captured["current_user"].username == "tester"


@pytest.mark.anyio
async def test_upsert_request_schedule_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def upsert_request_schedule(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["schedule_type"] = payload.schedule_type.value
            captured["timezone"] = payload.timezone
            captured["user"] = current_user.username
            return {"schedule": {"request_id": request_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-55/schedule",
            json={
                "timezone": "Asia/Karachi",
                "schedule_type": "one_time",
                "start_date": "2026-06-01",
                "start_time_local": "08:00",
                "end_time_local": "16:00",
            },
        )

    assert response.status_code == 200
    assert captured == {
        "request_id": "req-55",
        "schedule_type": "one_time",
        "timezone": "Asia/Karachi",
        "user": "tester",
    }


@pytest.mark.anyio
async def test_list_request_shifts_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_shifts(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.OPS_ADMIN)), base_url="http://test") as client:
        response = await client.get(
            "/api/shifts?page=2&rows=5&request_id=req-1&instance_status=scheduled&date_from=2026-06-01&date_to=2026-06-03"
        )

    assert response.status_code == 200
    assert captured["page"] == 2
    assert captured["rows"] == 5
    assert captured["request_id"] == "req-1"
    assert captured["instance_status"] == "scheduled"
    assert captured["date_from"].isoformat() == "2026-06-01"
    assert captured["date_to"].isoformat() == "2026-06-03"
    assert captured["current_user"].username == "tester"


@pytest.mark.anyio
async def test_get_request_shift_forwards_shift_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_shift_by_id(self, shift_id, current_user):
            captured["shift_id"] = shift_id
            captured["user"] = current_user.username
            return {"shift": {"id": shift_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/shifts/shift-22")

    assert response.status_code == 200
    assert captured == {"shift_id": "shift-22", "user": "tester"}


@pytest.mark.anyio
async def test_get_request_shift_slot_forwards_slot_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_shift_slot_by_id(self, slot_id, current_user):
            captured["slot_id"] = slot_id
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/shift-slots/slot-22")

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-22", "user": "tester"}


@pytest.mark.anyio
async def test_roster_request_shift_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def roster_shift(self, shift_id, payload, current_user):
            captured["shift_id"] = shift_id
            captured["first_slot"] = payload.assignments[0].slot_id
            captured["first_guard"] = payload.assignments[0].guard_tenant_id
            captured["user"] = current_user.username
            return {"shift": {"id": shift_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.SP_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shifts/shift-9/roster",
            json={"assignments": [{"slot_id": "slot-1", "guard_tenant_id": "guard-1"}]},
        )

    assert response.status_code == 200
    assert captured == {
        "shift_id": "shift-9",
        "first_slot": "slot-1",
        "first_guard": "guard-1",
        "user": "tester",
    }


@pytest.mark.anyio
async def test_check_in_request_shift_slot_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def check_in_shift_slot(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["latitude"] = payload.latitude
            captured["longitude"] = payload.longitude
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/check-in",
            json={"latitude": 24.86, "longitude": 67.01, "note": "arrived"},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "latitude": 24.86, "longitude": 67.01, "user": "tester"}


@pytest.mark.anyio
async def test_report_request_shift_slot_unavailable_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def report_shift_slot_unavailable(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/report-unavailable",
            json={"note": "family emergency"},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "note": "family emergency", "user": "tester"}


@pytest.mark.anyio
async def test_reopen_request_shift_slot_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def reopen_shift_slot(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["note"] = payload.note
            captured["max_match_results"] = payload.max_match_results
            captured["user"] = current_user.username
            return {"replacement_slot": {"id": "slot-r"}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.OPS_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/reopen",
            json={"note": "replace urgently", "max_match_results": 30},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "note": "replace urgently", "max_match_results": 30, "user": "tester"}


@pytest.mark.anyio
async def test_confirm_request_shift_slot_arrival_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def confirm_shift_slot_arrival(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/client-confirm",
            json={"note": "confirmed"},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "note": "confirmed", "user": "tester"}


@pytest.mark.anyio
async def test_start_request_shift_slot_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def start_shift_slot(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/start",
            json={"note": "starting"},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "note": "starting", "user": "tester"}


@pytest.mark.anyio
async def test_check_out_request_shift_slot_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def check_out_shift_slot(self, slot_id, payload, current_user):
            captured["slot_id"] = slot_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"slot": {"id": slot_id}}

    monkeypatch.setattr(RequestShiftManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/shift-slots/slot-1/check-out",
            json={"note": "done"},
        )

    assert response.status_code == 200
    assert captured == {"slot_id": "slot-1", "note": "done", "user": "tester"}


@pytest.mark.anyio
async def test_publish_client_request_update_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def publish_request_update(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["requested_start_at"] = payload.requested_start_at
            captured["user"] = current_user.username
            return {"id": request_id, "message": "publish-update"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-8/publish-update",
            json={"requested_start_at": "2026-05-16T18:00:00Z", "max_match_results": 25},
        )

    assert response.status_code == 200
    assert captured["request_id"] == "req-8"
    assert captured["requested_start_at"] is not None
    assert captured["user"] == "tester"


@pytest.mark.anyio
async def test_request_additional_coverage_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def request_additional_coverage(self, request_id, payload, current_user):
            captured["request_id"] = request_id
            captured["additional_slots"] = payload.additional_slots
            captured["user"] = current_user.username
            return {"id": request_id, "message": "additional-coverage"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/requests/req-9/additional-coverage",
            json={"additional_slots": 2, "max_match_results": 30},
        )

    assert response.status_code == 200
    assert captured == {"request_id": "req-9", "additional_slots": 2, "user": "tester"}


@pytest.mark.anyio
async def test_get_request_job_forwards_assignment_id(monkeypatch):
    captured = {}

    class FakeManager:
        async def get_job_by_id(self, assignment_id, current_user):
            captured["assignment_id"] = assignment_id
            captured["user"] = current_user.username
            return {"id": assignment_id}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.GUARD_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/jobs/as-55")

    assert response.status_code == 200
    assert captured == {"assignment_id": "as-55", "user": "tester"}


@pytest.mark.anyio
async def test_list_client_request_waves_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_request_waves(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.CLIENT_ADMIN)), base_url="http://test") as client:
        response = await client.get("/api/requests/req-10/waves?page=2&rows=5")

    assert response.status_code == 200
    assert captured["request_id"] == "req-10"
    assert captured["page"] == 2
    assert captured["rows"] == 5
    assert captured["current_user"].username == "tester"


@pytest.mark.anyio
async def test_list_request_review_waves_forwards_filters(monkeypatch):
    captured = {}

    class FakeManager:
        async def list_review_waves(self, **kwargs):
            captured.update(kwargs)
            return {"items": [], "pagination": {"page": kwargs["page"], "rows": kwargs["rows"]}}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.OPS_ADMIN)), base_url="http://test") as client:
        response = await client.get(
            "/api/request-review-waves?page=3&rows=10&wave_status=pending_review&trigger=initial_publish&request_id=req-11&client_tenant_id=tenant-2"
        )

    assert response.status_code == 200
    assert captured["page"] == 3
    assert captured["rows"] == 10
    assert captured["wave_status"] == "pending_review"
    assert captured["trigger"] == "initial_publish"
    assert captured["request_id"] == "req-11"
    assert captured["client_tenant_id"] == "tenant-2"
    assert captured["current_user"].username == "tester"


@pytest.mark.anyio
async def test_approve_request_review_wave_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def approve_request_wave(self, wave_id, payload, current_user):
            captured["wave_id"] = wave_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"id": wave_id, "message": "approved"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/request-review-waves/wave-1/approve",
            json={"note": "approved for broadcast"},
        )

    assert response.status_code == 200
    assert captured == {"wave_id": "wave-1", "note": "approved for broadcast", "user": "tester"}


@pytest.mark.anyio
async def test_return_request_review_wave_forwards_payload(monkeypatch):
    captured = {}

    class FakeManager:
        async def return_request_wave(self, wave_id, payload, current_user):
            captured["wave_id"] = wave_id
            captured["note"] = payload.note
            captured["user"] = current_user.username
            return {"id": wave_id, "message": "returned"}

    monkeypatch.setattr(RequestManager, "get_instance", staticmethod(lambda: FakeManager()))

    async with AsyncClient(transport=ASGITransport(app=_app(user_role.ADMIN)), base_url="http://test") as client:
        response = await client.post(
            "/api/request-review-waves/wave-2/return",
            json={"note": "location needs correction"},
        )

    assert response.status_code == 200
    assert captured == {"wave_id": "wave-2", "note": "location needs correction", "user": "tester"}
