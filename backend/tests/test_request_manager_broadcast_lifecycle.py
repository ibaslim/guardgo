from types import SimpleNamespace

import pytest
from bson import ObjectId

from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_request_model import (
    RequestLockReason,
    RequestStaffingStatus,
    RequestStatus,
)


class FakeEngine:
    def __init__(self):
        self.saved = []

    async def save(self, model):
        self.saved.append(model)
        return model


def _make_request_record(**overrides):
    base = {
        "id": ObjectId(),
        "request_expires_at": None,
        "request_status": RequestStatus.SUBMITTED,
        "staffing_status": RequestStaffingStatus.OPEN,
        "lock_reason": None,
        "expired_at": None,
        "active_wave_id": None,
        "guards_required": 2,
        "accepted_slots": 0,
        "open_slots": 2,
        "updated_at": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.anyio
async def test_sync_request_runtime_state_preserves_pending_review():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()
    manager._get_assignments_for_request = lambda _request_id: []
    manager._close_open_offers_for_request = lambda *_args, **_kwargs: 0

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.PENDING_REVIEW,
        lock_reason=RequestLockReason.REVIEW_PENDING,
    )

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.PENDING_REVIEW
    assert updated.lock_reason == RequestLockReason.REVIEW_PENDING


@pytest.mark.anyio
async def test_sync_request_runtime_state_preserves_review_returned_without_active_wave():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.REVIEW_RETURNED,
        lock_reason=None,
        active_wave_id=None,
    )

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.REVIEW_RETURNED
    assert updated.lock_reason is None


@pytest.mark.anyio
async def test_sync_request_runtime_state_reopens_review_returned_request_once_new_wave_is_active():
    manager = object.__new__(RequestManager)
    manager._engine = FakeEngine()

    async def _get_assignments(_request_id):
        return []

    async def _close_open_offers(*_args, **_kwargs):
        return 0

    manager._get_assignments_for_request = _get_assignments
    manager._close_open_offers_for_request = _close_open_offers

    record = _make_request_record(
        staffing_status=RequestStaffingStatus.REVIEW_RETURNED,
        lock_reason=None,
        active_wave_id="wave-1",
    )

    updated = await manager._sync_request_runtime_state(record)

    assert updated.staffing_status == RequestStaffingStatus.OPEN
    assert updated.lock_reason is None
