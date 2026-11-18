from types import SimpleNamespace

import pytest

from migrations.scripts.migrate_tenant_pending_activation import migrate_tenant_pending_activation
from orion.services.mongo_manager.mongo_controller import mongo_controller


@pytest.mark.anyio
async def test_migration_preserves_service_provider_guard_invites(monkeypatch):
    documents = [
        {"tenant_type": "guard", "ownership_type": "service_provider", "status": "pending_verification"},
        {"tenant_type": "guard", "ownership_type": None, "status": "pending_verification"},
        {"tenant_type": "client", "status": "pending_verification"},
    ]

    class Collection:
        async def update_many(self, query, update):
            if query.get("status") != "pending_verification":
                return
            for doc in documents:
                excluded = any(all(doc.get(key) == value for key, value in condition.items())
                               for condition in query.get("$nor", []))
                if doc.get("status") == query["status"] and not excluded:
                    doc.update(update["$set"])

    engine = SimpleNamespace(get_collection=lambda _model: Collection())
    monkeypatch.setattr(mongo_controller, "get_instance", staticmethod(lambda: SimpleNamespace(get_engine=lambda: engine)))

    await migrate_tenant_pending_activation()

    assert [doc["status"] for doc in documents] == ["pending_verification", "pending_activation", "pending_activation"]
