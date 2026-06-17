from types import SimpleNamespace

import pytest

from orion.services.mail_manager.mail_manager import mail_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller


class FakeEngine:
    def __init__(self, record):
        self.record = record

    async def find_one(self, *_args, **_kwargs):
        return self.record


@pytest.mark.anyio
async def test_process_app_variables_uses_guardgo_when_app_name_missing(monkeypatch):
    class FakeMongo:
        def get_engine(self):
            return FakeEngine(record=None)

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    subject, body = await mail_manager.get_instance().process_app_variables(
        "Welcome to appname",
        "<p>appname verification</p>",
    )

    assert subject == "Welcome to GuardGo"
    assert body == "<p>GuardGo verification</p>"


@pytest.mark.anyio
async def test_process_app_variables_uses_configured_app_name(monkeypatch):
    class FakeMongo:
        def get_engine(self):
            return FakeEngine(record=SimpleNamespace(value="Custom GuardGo"))

    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: FakeMongo()))

    subject, body = await mail_manager.get_instance().process_app_variables(
        "Welcome to appname",
        "<p>appname verification</p>",
    )

    assert subject == "Welcome to Custom GuardGo"
    assert body == "<p>Custom GuardGo verification</p>"
