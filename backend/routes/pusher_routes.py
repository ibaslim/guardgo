from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request

from configs.app_dependency import get_current_user, status_required
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus
from orion.services.pusher_manager import pusher_manager


pusher_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Pusher"],
)


@pusher_routes.get("/api/pusher/channel", summary="Get current user's private Pusher channel")
async def get_pusher_channel(current_user=Depends(get_current_user)):
    user_id = str(getattr(current_user, "id", "") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user is unavailable")
    return {"channel_name": f"private-user-{user_id}"}


@pusher_routes.post("/api/pusher/auth", summary="Authorize a private Pusher channel")
async def authorize_pusher_channel(request: Request, current_user=Depends(get_current_user)):
    if not pusher_manager.enabled:
        raise HTTPException(status_code=503, detail="Pusher is not configured")

    # Pusher JS sends URL-encoded socket_id and channel_name fields by default.
    form_values = parse_qs((await request.body()).decode("utf-8", errors="replace"))
    socket_id = (form_values.get("socket_id") or [""])[0].strip()
    channel_name = (form_values.get("channel_name") or [""])[0].strip()
    user_id = str(getattr(current_user, "id", "") or "").strip()

    if not socket_id or not channel_name:
        raise HTTPException(status_code=400, detail="socket_id and channel_name are required")
    if not user_id or channel_name != f"private-user-{user_id}":
        raise HTTPException(status_code=403, detail="Not authorized for this Pusher channel")

    return await pusher_manager.authenticate_channel(channel_name, socket_id)
