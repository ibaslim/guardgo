from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from configs.app_dependency import get_current_user
from routes import push_routes as routes


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_):
        self.rows.sort(key=lambda row: (row["last_seen_at"], row["_id"]), reverse=True)
        return self

    async def to_list(self, length=None):
        return self.rows


class Collection:
    def __init__(self):
        self.rows = []

    async def update_one(self, query, update, upsert=False):
        row = next((r for r in self.rows if r["token"] == query["token"]), None)
        if row is None and upsert:
            row = {"token": query["token"], "_id": len(self.rows)}
            row.update(update.get("$setOnInsert", {}))
            self.rows.append(row)
        if row is not None:
            row.update(update["$set"])

    def find(self, query):
        return Cursor([r for r in self.rows if r["user_id"] == query["user_id"]])

    async def delete_many(self, query):
        self.rows = [r for r in self.rows if not (r["_id"] in query["_id"]["$in"] and r["user_id"] == query["user_id"])]

    async def delete_one(self, query):
        self.rows = [r for r in self.rows if not all(r.get(k) == v for k, v in query.items())]


@pytest.mark.anyio
async def test_register_rebind_cap_and_revoke(monkeypatch):
    collection = Collection()
    monkeypatch.setattr(routes.mongo_controller, "get_instance", lambda: SimpleNamespace(get_engine=lambda: SimpleNamespace(get_collection=lambda _: collection)))
    user = SimpleNamespace(id="one", tenant_uuid="tenant")
    app = FastAPI()
    # Authentication itself is covered by the existing route tests.
    async def bypass():
        return None
    async def current():
        return user
    app.dependency_overrides[routes.push_routes.dependencies[0].dependency] = bypass
    app.dependency_overrides[get_current_user] = current
    app.include_router(routes.push_routes)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token = "ExponentPushToken[abc]"
        assert (await client.post('/api/push-tokens', json={"token": token, "platform": "ios"})).status_code == 204
        assert (await client.post('/api/push-tokens', json={"token": token, "platform": "android"})).status_code == 204
        assert len(collection.rows) == 1 and collection.rows[0]["platform"] == "android"
        user.id = "two"
        await client.post('/api/push-tokens', json={"token": token, "platform": "ios"})
        assert collection.rows[0]["user_id"] == "two"
        assert (await client.post('/api/push-tokens', json={"token": "bad", "platform": "ios"})).status_code == 422
        user.id = "one"
        assert (await client.post('/api/push-tokens/revoke', json={"token": token})).status_code == 204
        assert len(collection.rows) == 1
        for i in range(11):
            await client.post('/api/push-tokens', json={"token": f"ExpoPushToken[{i}]", "platform": "ios"})
        assert len([r for r in collection.rows if r["user_id"] == "one"]) == 10
        assert (await client.post('/api/push-tokens/revoke', json={"token": "ExpoPushToken[unknown]"})).status_code == 204
        user.id = "two"
        await client.post('/api/push-tokens/revoke', json={"token": token})
        assert all(r["token"] != token for r in collection.rows)
