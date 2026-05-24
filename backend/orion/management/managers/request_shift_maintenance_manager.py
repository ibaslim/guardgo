import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Optional

from bson import ObjectId

from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_notification_model import NotificationRecord
from orion.services.mongo_manager.shared_model.db_request_model import (
    RequestInvoiceTrigger,
    RequestScheduleTemplateRecord,
    RequestStatus,
    ShiftInstanceRecord,
    ShiftInstanceStatus,
    ShiftSlotRecord,
    ShiftSlotStatus,
)


class request_shift_maintenance_manager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance():
        if request_shift_maintenance_manager.__instance is None:
            with request_shift_maintenance_manager.__lock:
                if request_shift_maintenance_manager.__instance is None:
                    request_shift_maintenance_manager.__instance = request_shift_maintenance_manager()
        return request_shift_maintenance_manager.__instance

    def __init__(self):
        if request_shift_maintenance_manager.__instance is not None:
            raise Exception("request_shift_maintenance_manager is a singleton")
        controller = mongo_controller.get_instance()
        if controller is None:
            raise RuntimeError("Mongo controller is not initialized")
        self._engine = controller.get_engine()
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_forever(), name="request_shift_maintenance")

    async def _run_forever(self) -> None:
        while True:
            try:
                await self.run_iteration()
            except Exception as exc:
                print(f"Shift maintenance iteration failed: {exc}")
            await asyncio.sleep(60)

    async def run_iteration(self) -> Dict[str, int]:
        shift_manager = RequestShiftManager.get_instance()
        ensured = await shift_manager.ensure_future_shift_instances_for_active_schedules(limit=200)
        invoice_sync_count = await self._sync_advance_request_invoices(limit=200)
        synced_leave_count = await shift_manager.sync_active_guard_leaves(limit=200)
        synced_exception_count = await self._sync_active_shift_runtime_exceptions(shift_manager)
        roster_reminder_count = await self._send_provider_roster_reminders()
        guard_reminder_count = await self._send_guard_checkin_reminders()
        client_reminder_count = await self._send_client_arrival_confirmation_reminders()

        summary = {
            "created_shift_count": int(ensured.get("created_shift_count") or 0),
            "touched_request_count": int(ensured.get("touched_request_count") or 0),
            "advance_invoice_sync_count": invoice_sync_count,
            "leave_sync_count": synced_leave_count,
            "exception_sync_count": synced_exception_count,
            "provider_roster_reminders": roster_reminder_count,
            "guard_checkin_reminders": guard_reminder_count,
            "client_confirmation_reminders": client_reminder_count,
        }
        if any(summary.values()):
            print(f"Shift maintenance summary: {summary}")
        return summary

    async def _sync_advance_request_invoices(self, limit: int = 200) -> int:
        request_manager = RequestManager.get_instance()
        schedule_collection = self._engine.get_collection(RequestScheduleTemplateRecord)
        schedule_docs = await schedule_collection.find({"active": True}).to_list(length=max(int(limit or 0), 0) or 200)
        system_user = SimpleNamespace(id=None, username="system", role="admin")
        synced_count = 0

        for schedule_doc in schedule_docs:
            request_id = str(schedule_doc.get("request_id") or "").strip()
            if not request_id:
                continue
            try:
                request_record = await request_manager._get_request_or_404(request_id)
            except Exception:
                continue
            if request_record.request_status in {RequestStatus.DRAFT, RequestStatus.CANCELLED, RequestStatus.CLOSED}:
                continue
            if getattr(request_record, "expired_at", None) is not None:
                continue

            invoicing_snapshot = request_record.invoicing_snapshot if isinstance(getattr(request_record, "invoicing_snapshot", None), dict) else {}
            if request_manager._normalize_invoice_contract_type(invoicing_snapshot.get("contract_type")) != "long_term":
                continue

            try:
                result = await request_manager._sync_request_invoice_state(
                    request_record,
                    current_user=system_user,
                    reason=RequestInvoiceTrigger.MONTHLY_ADVANCE,
                )
            except Exception as exc:
                print(f"Advance invoice sync failed for request {request_id}: {exc}")
                continue
            if str(result.get("action") or "") in {"created", "updated"}:
                synced_count += 1

        return synced_count

    async def _sync_active_shift_runtime_exceptions(self, shift_manager: RequestShiftManager) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start = now - timedelta(hours=24)
        window_end = now + timedelta(hours=24)
        shift_collection = self._engine.get_collection(ShiftInstanceRecord)
        shift_docs = await shift_collection.find({
            "shift_end_at_utc": {"$gte": window_start},
            "shift_start_at_utc": {"$lte": window_end},
            "instance_status": {
                "$in": [
                    ShiftInstanceStatus.SCHEDULED.value,
                    ShiftInstanceStatus.PARTIALLY_STAFFED.value,
                    ShiftInstanceStatus.STAFFED.value,
                    ShiftInstanceStatus.IN_PROGRESS.value,
                ]
            },
        }).to_list(length=500)

        synced = 0
        for shift_doc in shift_docs:
            shift_id = str(shift_doc.get("_id") or "").strip()
            if not shift_id:
                continue
            shift_record = await shift_manager._get_shift_or_404(shift_id)
            await shift_manager._sync_shift_runtime_exception_states(shift_record)
            synced += 1
        return synced

    async def _send_provider_roster_reminders(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_collection = self._engine.get_collection(ShiftSlotRecord)
        slot_docs = await slot_collection.find({
            "coverage_source_type": "service_provider",
            "assigned_guard_tenant_id": None,
            "service_provider_tenant_id": {"$ne": None},
            "slot_status": ShiftSlotStatus.RESERVED.value,
            "roster_due_at": {"$lte": now + timedelta(minutes=30)},
        }).to_list(length=300)

        sent = 0
        for slot_doc in slot_docs:
            slot_id = str(slot_doc.get("_id") or "").strip()
            provider_tenant_id = str(slot_doc.get("service_provider_tenant_id") or "").strip()
            shift_id = str(slot_doc.get("shift_instance_id") or "").strip()
            request_id = str(slot_doc.get("request_id") or "").strip()
            if not slot_id or not provider_tenant_id or not shift_id or not request_id:
                continue

            reminder_key = f"provider-roster:{slot_id}"
            if await self._notification_exists(reminder_key=reminder_key, recipient_tenant_id=provider_tenant_id):
                continue

            request_title = await self._request_title(request_id)
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=provider_tenant_id,
                title="Provider guard roster due",
                message=f"{request_title}: an upcoming provider-backed shift slot still needs a named guard rostered.",
                category="warning",
                source_module="requests",
                action_url=f"/dashboard/requests?tab=shifts&shift={shift_id}",
                action_label="Open Shift",
                metadata={
                    "request_id": request_id,
                    "shift_id": shift_id,
                    "slot_id": slot_id,
                    "reminder_key": reminder_key,
                    "reminder_type": "provider_roster_due",
                },
            )
            sent += 1
        return sent

    async def _send_guard_checkin_reminders(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        shift_collection = self._engine.get_collection(ShiftInstanceRecord)
        shift_docs = await shift_collection.find({
            "shift_start_at_utc": {
                "$gte": now - timedelta(minutes=1),
                "$lte": now + timedelta(minutes=5),
            },
            "instance_status": {
                "$in": [
                    ShiftInstanceStatus.SCHEDULED.value,
                    ShiftInstanceStatus.PARTIALLY_STAFFED.value,
                    ShiftInstanceStatus.STAFFED.value,
                ]
            },
        }).to_list(length=300)
        shift_ids = [shift_doc.get("_id") for shift_doc in shift_docs if shift_doc.get("_id") is not None]
        if not shift_ids:
            return 0

        slot_collection = self._engine.get_collection(ShiftSlotRecord)
        slot_docs = await slot_collection.find({
            "shift_instance_id": {"$in": [str(item) for item in shift_ids]},
            "slot_status": {"$in": [ShiftSlotStatus.RESERVED.value, ShiftSlotStatus.ROSTERED.value]},
            "assigned_guard_tenant_id": {"$ne": None},
            "arrived_at": None,
        }).to_list(length=500)

        shift_lookup = {str(shift_doc.get("_id")): shift_doc for shift_doc in shift_docs}
        sent = 0
        for slot_doc in slot_docs:
            slot_id = str(slot_doc.get("_id") or "").strip()
            guard_tenant_id = str(slot_doc.get("assigned_guard_tenant_id") or "").strip()
            shift_id = str(slot_doc.get("shift_instance_id") or "").strip()
            request_id = str(slot_doc.get("request_id") or "").strip()
            if not slot_id or not guard_tenant_id or not shift_id or not request_id:
                continue

            reminder_key = f"guard-checkin:{slot_id}"
            if await self._notification_exists(reminder_key=reminder_key, recipient_tenant_id=guard_tenant_id):
                continue

            shift_doc = shift_lookup.get(shift_id, {})
            request_title = await self._request_title(request_id)
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=guard_tenant_id,
                title="Shift starts in less than 5 minutes",
                message=f"{request_title}: your shift is about to start. Open the shift slot now and complete check-in.",
                category="info",
                source_module="requests",
                action_url=f"/dashboard/requests?tab=shifts&slot={slot_id}",
                action_label="Open Shift Slot",
                metadata={
                    "request_id": request_id,
                    "shift_id": shift_id,
                    "slot_id": slot_id,
                    "reminder_key": reminder_key,
                    "reminder_type": "guard_checkin_due",
                },
            )
            sent += 1
        return sent

    async def _send_client_arrival_confirmation_reminders(self) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        slot_collection = self._engine.get_collection(ShiftSlotRecord)
        slot_docs = await slot_collection.find({
            "slot_status": ShiftSlotStatus.CLIENT_CONFIRMATION_PENDING.value,
            "arrived_at": {"$lte": now - timedelta(minutes=5)},
            "client_confirmed_at": None,
            "started_at": None,
        }).to_list(length=300)

        sent = 0
        for slot_doc in slot_docs:
            slot_id = str(slot_doc.get("_id") or "").strip()
            client_tenant_id = str(slot_doc.get("client_tenant_id") or "").strip()
            shift_id = str(slot_doc.get("shift_instance_id") or "").strip()
            request_id = str(slot_doc.get("request_id") or "").strip()
            if not slot_id or not client_tenant_id or not shift_id or not request_id:
                continue

            reminder_key = f"client-confirm-arrival:{slot_id}"
            if await self._notification_exists(reminder_key=reminder_key, recipient_tenant_id=client_tenant_id):
                continue

            request_title = await self._request_title(request_id)
            await NotificationManager.get_instance().create_for_tenant_admin_users(
                tenant_id=client_tenant_id,
                title="Arrival confirmation pending",
                message=f"{request_title}: a guard checked in and is still waiting for client arrival confirmation.",
                category="warning",
                source_module="requests",
                action_url=f"/dashboard/requests?tab=shifts&slot={slot_id}",
                action_label="Confirm Arrival",
                metadata={
                    "request_id": request_id,
                    "shift_id": shift_id,
                    "slot_id": slot_id,
                    "reminder_key": reminder_key,
                    "reminder_type": "client_arrival_confirmation_due",
                },
            )
            sent += 1
        return sent

    async def _notification_exists(self, *, reminder_key: str, recipient_tenant_id: str) -> bool:
        notification_collection = self._engine.get_collection(NotificationRecord)
        count = await notification_collection.count_documents({
            "recipient_tenant_id": str(recipient_tenant_id),
            "source_module": "requests",
            "metadata.reminder_key": str(reminder_key),
        })
        return bool(count)

    async def _request_title(self, request_id: str) -> str:
        try:
            request_record = await RequestManager.get_instance()._get_request_or_404(str(request_id))
        except Exception:
            return "Scheduled request"
        title = str(getattr(request_record, "title", "") or "").strip()
        return title or "Scheduled request"
