from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, constr
from pymongo.errors import DuplicateKeyError

from configs.app_dependency import get_current_user, status_required
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus
from orion.services.mongo_manager.shared_model.db_push_token_model import PushTokenRecord

push_routes = APIRouter(dependencies=[Depends(status_required([UserStatus.ACTIVE]))], tags=["Push"])
Token = constr(pattern=r"^Expo(nent)?PushToken\[[^\]]+\]$", max_length=200)


class TokenBody(BaseModel):
    token: Token


class RegisterBody(TokenBody):
    platform: Literal["android", "ios"]


@push_routes.post("/api/push-tokens", status_code=204)
async def register_push_token(body: RegisterBody, current_user=Depends(get_current_user)):
    collection = mongo_controller.get_instance().get_engine().get_collection(PushTokenRecord)
    now = datetime.utcnow()
    values = {"user_id": str(current_user.id), "tenant_id": getattr(current_user, "tenant_uuid", None),
              "platform": body.platform, "last_seen_at": now}
    try:
        await collection.update_one({"token": body.token}, {"$set": values, "$setOnInsert": {"created_at": now}}, upsert=True)
    except DuplicateKeyError:
        await collection.update_one({"token": body.token}, {"$set": values})
    rows = await collection.find({"user_id": str(current_user.id)}).sort([("last_seen_at", -1), ("_id", -1)]).to_list(length=None)
    if len(rows) > 10:
        await collection.delete_many({"_id": {"$in": [row["_id"] for row in rows[10:]]}, "user_id": str(current_user.id)})
    return Response(status_code=204)


@push_routes.post("/api/push-tokens/revoke", status_code=204)
async def revoke_push_token(body: TokenBody, current_user=Depends(get_current_user)):
    collection = mongo_controller.get_instance().get_engine().get_collection(PushTokenRecord)
    await collection.delete_one({"token": body.token, "user_id": str(current_user.id)})
    return Response(status_code=204)
