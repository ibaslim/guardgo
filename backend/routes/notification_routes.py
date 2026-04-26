from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user, status_required
from orion.api.interactive.notification_manager.notification_manager import NotificationManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus


notification_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Notifications"],
)


@notification_routes.get(
    "/api/notifications/latest",
    summary="Get latest notifications",
    description="Return the latest notifications for the current authenticated user.",
    tags=["Notifications"],
    operation_id="getLatestNotifications",
    response_description="Latest notifications and unread count.",
)
async def get_latest_notifications(limit: int = 5, current_user=Depends(get_current_user)):
    return await NotificationManager.get_instance().list_latest(current_user=current_user, limit=limit)


@notification_routes.get(
    "/api/notifications/unread-count",
    summary="Get unread notification count",
    description="Return unread notification count for the current authenticated user.",
    tags=["Notifications"],
    operation_id="getUnreadNotificationCount",
    response_description="Unread notification count.",
)
async def get_unread_notification_count(current_user=Depends(get_current_user)):
    return await NotificationManager.get_instance().get_unread_count(current_user=current_user)


@notification_routes.get(
    "/api/notifications",
    summary="List notifications",
    description="Return paginated notifications for the current authenticated user.",
    tags=["Notifications"],
    operation_id="listNotifications",
    response_description="Paginated notifications.",
)
async def list_notifications(page: int = 1, rows: int = 20, status: str = "all", current_user=Depends(get_current_user)):
    return await NotificationManager.get_instance().list_notifications(
        current_user=current_user,
        page=page,
        rows=rows,
        status=status,
    )


@notification_routes.patch(
    "/api/notifications/read-all",
    summary="Mark all notifications read",
    description="Mark every unread notification as read for the current authenticated user.",
    tags=["Notifications"],
    operation_id="markAllNotificationsRead",
    response_description="Updated unread count.",
)
async def mark_all_notifications_read(current_user=Depends(get_current_user)):
    return await NotificationManager.get_instance().mark_all_read(current_user=current_user)


@notification_routes.patch(
    "/api/notifications/{notification_id}/read",
    summary="Mark notification read",
    description="Mark a single notification as read for the current authenticated user.",
    tags=["Notifications"],
    operation_id="markNotificationRead",
    response_description="Updated notification record.",
)
async def mark_notification_read(notification_id: str, current_user=Depends(get_current_user)):
    return await NotificationManager.get_instance().mark_read(notification_id=notification_id, current_user=current_user)
