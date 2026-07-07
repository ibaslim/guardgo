import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from configs import config
from configs import exception_handlers
from orion.helper_manager.env_handler import env_handler
from orion.services.mail_manager.mail_manager import mail_manager


def _make_request(body: dict | None = None):
    payload = json.dumps(body or {}).encode("utf-8")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/fail",
        "query_string": b"x=1",
        "headers": [
            (b"content-type", b"application/json"),
            (b"host", b"guardgo.org"),
            (b"user-agent", b"pytest"),
        ],
        "client": ("127.0.0.1", 12345),
        "scheme": "https",
        "server": ("guardgo.org", 443),
    }

    state = {"sent": False}

    async def receive():
        if not state["sent"]:
            state["sent"] = True
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.anyio
async def test_global_exception_handler_sends_500_alert_email(monkeypatch):
    sent = {}

    class FakeEnv:
        def env(self, key, default=None):
            if key == "ERROR_ALERT_RECIPIENTS":
                return "alerts@guardgo.org"
            if key == "ACCOUNTS_MAIL":
                return "support@guardgo.org"
            return default

    class FakeMail:
        async def send_verification_mail_list(self, to_list, subject, body):
            sent["to_list"] = to_list
            sent["subject"] = subject
            sent["body"] = body

    monkeypatch.setattr(config, "DEBUG", False)
    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))
    monkeypatch.setattr(mail_manager, "get_instance", staticmethod(lambda: FakeMail()))

    request = _make_request({"username": "alice", "password": "secret-pass"})
    await exception_handlers.global_exception_handler(request, RuntimeError("boom"))

    assert sent["to_list"] == ["alerts@guardgo.org"]
    assert "[GuardGo][PROD] 500 Error" in sent["subject"]
    assert "/api/fail" in sent["body"]
    assert "secret-pass" not in sent["body"]


@pytest.mark.anyio
async def test_global_exception_handler_skips_alert_for_4xx(monkeypatch):
    called = {"value": False}

    class FakeEnv:
        def env(self, _key, default=None):
            return default

    class FakeMail:
        async def send_verification_mail_list(self, to_list, subject, body):
            called["value"] = True

    monkeypatch.setattr(config, "DEBUG", False)
    monkeypatch.setattr(env_handler, "get_instance", staticmethod(lambda: FakeEnv()))
    monkeypatch.setattr(mail_manager, "get_instance", staticmethod(lambda: FakeMail()))

    request = _make_request({"foo": "bar"})
    await exception_handlers.global_exception_handler(request, HTTPException(status_code=400, detail="bad request"))

    assert called["value"] is False
