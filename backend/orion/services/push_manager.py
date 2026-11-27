import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from orion.helper_manager.env_handler import env_handler
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_push_token_model import PushTicketRecord, PushTokenRecord

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
MAX_MESSAGES_PER_REQUEST = 100
MAX_RECEIPT_IDS_PER_REQUEST = 1000
REQUEST_TIMEOUT_SECONDS = 10
CHANNEL_JOBS = "job-updates-v1"
CHANNEL_GENERAL = "general-v1"


def _truncate(value, limit):
    value = str(value or "")
    return value if len(value) <= limit else value[:limit - 1] + "…"


def build_message(token, record):
    metadata = record.metadata or {}
    is_job = record.source_module == "requests"
    return {"to": token, "title": _truncate(record.title, 120),
            "body": _truncate(record.message, 600), "sound": "default",
            "priority": "high" if is_job else "default",
            "channelId": CHANNEL_JOBS if is_job else CHANNEL_GENERAL,
            "data": {"v": "1", "notification_id": str(record.id),
                     "source_module": str(record.source_module or ""),
                     "action_url": str(record.action_url or ""),
                     "request_id": str(metadata.get("request_id") or ""),
                     "assignment_id": str(metadata.get("assignment_id") or "")}}


class PushManager:
    def __init__(self):
        env = env_handler.get_instance()
        self.enabled_flag = str(env.env("EXPO_PUSH_ENABLED", "true") or "true").strip().lower() == "true"
        self.access_token = str(env.env("EXPO_ACCESS_TOKEN", "") or "").strip()
        self._task = None

    @property
    def _engine(self):
        return mongo_controller.get_instance().get_engine()

    def _headers(self):
        headers = {"accept": "application/json", "accept-encoding": "gzip, deflate", "content-type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _post(self, client, url, payload):
        for attempt in range(4):
            response = await client.post(url, json=payload, headers=self._headers())
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)
                    continue
            if not response.is_success:
                logger.warning("Expo push HTTP %s: %s", response.status_code, response.text)
                return None
            return response.json()

    async def delete_tokens(self, tokens):
        if tokens:
            await self._engine.get_collection(PushTokenRecord).delete_many({"token": {"$in": list(tokens)}})

    async def delete_tokens_for_user(self, user_id):
        await self._engine.get_collection(PushTokenRecord).delete_many({"user_id": str(user_id)})

    async def _handle_error(self, error, token, notification_id=None):
        if error == "DeviceNotRegistered":
            await self.delete_tokens([token])
        elif error in ("InvalidCredentials", "MismatchSenderId"):
            logger.error("Expo push configuration error %s for notification %s", error, notification_id)
        else:
            logger.warning("Expo push error %s for notification %s", error, notification_id)

    async def send_for_notification(self, record):
        if not self.enabled_flag:
            return
        try:
            tokens = await self._engine.find(PushTokenRecord, PushTokenRecord.user_id == str(record.recipient_user_id))
            if not tokens:
                return
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                for offset in range(0, len(tokens), MAX_MESSAGES_PER_REQUEST):
                    batch = tokens[offset:offset + MAX_MESSAGES_PER_REQUEST]
                    result = await self._post(client, EXPO_PUSH_URL, [build_message(t.token, record) for t in batch])
                    if result is None:
                        break
                    for token, ticket in zip(batch, result.get("data", [])):
                        if ticket.get("status") == "ok" and ticket.get("id"):
                            await self._engine.save(PushTicketRecord(ticket_id=ticket["id"], token=token.token))
                        elif ticket.get("status") == "error":
                            await self._handle_error((ticket.get("details") or {}).get("error"), token.token, str(record.id))
        except Exception:
            logger.exception("Could not send Expo push notification")

    async def check_receipts(self):
        if not self.enabled_flag:
            return
        try:
            tickets = await self._engine.find(PushTicketRecord, PushTicketRecord.created_at <= datetime.utcnow() - timedelta(minutes=15))
            if not tickets:
                return
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                for offset in range(0, len(tickets), MAX_RECEIPT_IDS_PER_REQUEST):
                    batch = tickets[offset:offset + MAX_RECEIPT_IDS_PER_REQUEST]
                    result = await self._post(client, EXPO_RECEIPTS_URL, {"ids": [t.ticket_id for t in batch]})
                    if result is None:
                        break
                    receipts = result.get("data", {})
                    for ticket in batch:
                        receipt = receipts.get(ticket.ticket_id)
                        if receipt is None:
                            continue
                        if receipt.get("status") == "error":
                            await self._handle_error((receipt.get("details") or {}).get("error"), ticket.token)
                        await self._engine.delete(ticket)
        except Exception:
            logger.exception("Could not check Expo push receipts")

    async def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_forever(), name="push_receipts")

    async def _run_forever(self):
        while True:
            await self.check_receipts()
            await asyncio.sleep(900)


async def remove_disabled_user_tokens(user_id):
    try:
        await push_manager.delete_tokens_for_user(str(user_id))
    except Exception:
        logger.exception("Could not remove push tokens for disabled user")


push_manager = PushManager()
