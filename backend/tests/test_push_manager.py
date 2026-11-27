import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from orion.services import push_manager as module
from orion.services.mongo_manager.shared_model.db_push_token_model import PushTicketRecord, PushTokenRecord


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Engine:
    def __init__(self, tokens=(), tickets=()):
        self.tokens = list(tokens)
        self.tickets = list(tickets)
        self.saved = []
        self.deleted = []

    async def find(self, model, *_):
        return self.tokens if model is PushTokenRecord else self.tickets

    async def save(self, record):
        self.saved.append(record)
        return record

    async def delete(self, record):
        self.deleted.append(record)

    def get_collection(self, _model):
        return self

    async def delete_many(self, query):
        self.tokens = [t for t in self.tokens if t.token not in query.get("token", {}).get("$in", [])]


def record(**kwargs):
    return SimpleNamespace(id="n1", recipient_user_id="u1", title="x" * 200, message="y" * 700,
                           source_module=kwargs.get("source_module"), action_url=None,
                           metadata={"request_id": 3, "assignment_id": None})


def setup(monkeypatch, engine, handler, token=""):
    manager = module.PushManager()
    manager.enabled_flag = True
    manager.access_token = token
    monkeypatch.setattr(module.mongo_controller, "get_instance", lambda: SimpleNamespace(get_engine=lambda: engine))
    client = httpx.AsyncClient
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    return manager


def test_message_contract():
    job = module.build_message("token", record(source_module="requests"))
    general = module.build_message("token", record())
    assert (job["channelId"], job["priority"]) == ("job-updates-v1", "high")
    assert (general["channelId"], general["priority"]) == ("general-v1", "default")
    assert all(isinstance(value, str) for value in job["data"].values())
    assert len(job["title"]) == 120 and len(job["body"]) == 600
    assert job["title"].endswith("…")


@pytest.mark.anyio
async def test_batches_headers_and_retry(monkeypatch):
    engine = Engine([SimpleNamespace(token=f"token{i}") for i in range(250)])
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429)
        messages = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"status": "ok", "id": m["to"]} for m in messages]})
    async def no_sleep(_):
        pass
    manager = setup(monkeypatch, engine, handler, "secret")
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    await manager.send_for_notification(record())
    assert [len(json.loads(c.content)) for c in calls] == [100, 100, 100, 50]
    assert calls[0].headers["authorization"] == "Bearer secret"
    assert len(engine.saved) == 250


@pytest.mark.anyio
async def test_ticket_errors_and_disabled(monkeypatch):
    engine = Engine([SimpleNamespace(token="dead"), SimpleNamespace(token="valid")])
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [{"status": "error", "details": {"error": e}} for e in ("DeviceNotRegistered", "InvalidCredentials")]})
    manager = setup(monkeypatch, engine, handler)
    manager.enabled_flag = False
    await manager.send_for_notification(record())
    assert not calls
    manager.enabled_flag = True
    await manager.send_for_notification(record())
    assert [t.token for t in engine.tokens] == ["valid"]
    assert "authorization" not in calls[0].headers


@pytest.mark.anyio
async def test_receipts_and_exception(monkeypatch):
    ticket = PushTicketRecord(ticket_id="ticket", token="dead", created_at=datetime.utcnow() - timedelta(minutes=16))
    engine = Engine([SimpleNamespace(token="dead")], [ticket])
    manager = setup(monkeypatch, engine, lambda _: httpx.Response(200, json={"data": {"ticket": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}}))
    await manager.check_receipts()
    assert not engine.tokens and engine.deleted == [ticket]
    async def fail(*_):
        raise RuntimeError("failure")
    engine.find = fail
    await manager.send_for_notification(record())


@pytest.mark.anyio
async def test_notification_schedules_push_and_skips_seeded(monkeypatch):
    from orion.api.interactive.notification_manager import notification_manager as notifications

    manager = object.__new__(notifications.NotificationManager)
    manager._engine = Engine()
    async def publish(*_):
        pass
    async def fail(_):
        raise RuntimeError("push failed")
    monkeypatch.setattr(notifications.pusher_manager, "publish_notification", publish)
    monkeypatch.setattr(notifications.push_manager, "send_for_notification", fail)
    saved = await manager.create_for_user("u1", "title", "body")
    assert saved.title == "title"
    await asyncio.gather(*list(notifications._background_tasks))
    seeded = await manager.create_for_user("u1", "welcome", "body", metadata={"seeded": True})
    assert seeded.metadata["seeded"] and not notifications._background_tasks
