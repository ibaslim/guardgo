import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_notification_model import NotificationRecord
from orion.services.mongo_manager.shared_model.db_auth_models import (
    TENANT_ADMIN_ROLES,
    UserStatus,
    db_user_account,
    normalize_role_value,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantStatus


class NotificationManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance() -> "NotificationManager":
        if NotificationManager.__instance is None:
            with NotificationManager.__lock:
                if NotificationManager.__instance is None:
                    NotificationManager.__instance = NotificationManager()
        return NotificationManager.__instance

    def __init__(self):
        if NotificationManager.__instance is not None:
            raise Exception("NotificationManager is a singleton")
        self._engine = mongo_controller.get_instance().get_engine()

    @staticmethod
    def _user_id(current_user) -> str:
        return str(getattr(current_user, "id", "") or "")

    @staticmethod
    def _tenant_id(current_user) -> str:
        return str(getattr(current_user, "tenant_uuid", "") or "")

    @staticmethod
    def _is_tenant_admin_role(role_value: str) -> bool:
        return role_value in {"guard_admin", "client_admin", "sp_admin"}

    @staticmethod
    def _normalized_status_value(status_value: Any) -> str:
        return str(getattr(status_value, "value", status_value) or "").strip().lower()

    async def _active_tenant_user_ids(self, tenant_id: str, *, admin_only: bool = False) -> List[str]:
        users = await self._engine.find(db_user_account, db_user_account.tenant_uuid == str(tenant_id))
        user_ids: List[str] = []
        for user in users:
            user_id = getattr(user, "id", None)
            if user_id is None:
                continue

            role_value = normalize_role_value(getattr(user, "role", ""))
            status_value = self._normalized_status_value(getattr(user, "status", ""))
            if admin_only and role_value not in TENANT_ADMIN_ROLES:
                continue
            if status_value != UserStatus.ACTIVE.value:
                continue

            user_ids.append(str(user_id))
        return user_ids

    async def _active_tenant_admin_user_ids(self, tenant_id: str) -> List[str]:
        return await self._active_tenant_user_ids(tenant_id, admin_only=True)

    async def _ensure_active_tenant_for_current_user(self, current_user) -> None:
        role_value = normalize_role_value(getattr(current_user, "role", ""))
        if not self._is_tenant_admin_role(role_value):
            return
        tenant_id = self._tenant_id(current_user)
        if not tenant_id:
            raise HTTPException(status_code=403, detail="Invalid tenant association")
        try:
            tenant = await self._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(tenant_id))
        except Exception:
            tenant = None
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            raise HTTPException(status_code=403, detail="Tenant is not active for this action")

    @staticmethod
    def _serialize(record: NotificationRecord | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(record, dict):
            record_id = str(record.get("_id") or record.get("id") or "")
            return {
                "id": record_id,
                "title": record.get("title") or "",
                "message": record.get("message") or "",
                "category": record.get("category") or "info",
                "source_module": record.get("source_module"),
                "action_url": record.get("action_url"),
                "action_label": record.get("action_label"),
                "metadata": record.get("metadata") or {},
                "is_read": bool(record.get("is_read", False)),
                "read_at": record.get("read_at"),
                "created_at": record.get("created_at"),
            }

        return {
            "id": str(record.id),
            "title": record.title,
            "message": record.message,
            "category": record.category,
            "source_module": record.source_module,
            "action_url": record.action_url,
            "action_label": record.action_label,
            "metadata": record.metadata or {},
            "is_read": bool(record.is_read),
            "read_at": record.read_at,
            "created_at": record.created_at,
        }

    async def _ensure_default_notification(self, current_user) -> None:
        recipient_user_id = self._user_id(current_user)
        if not recipient_user_id:
            return

        existing = await self._engine.find_one(
            NotificationRecord,
            NotificationRecord.recipient_user_id == recipient_user_id,
        )
        if existing:
            return

        await self.create_for_user(
            recipient_user_id=recipient_user_id,
            recipient_tenant_id=self._tenant_id(current_user) or None,
            title="Welcome to GuardGo",
            message="Your notification center is ready. Important account, tenant, and workflow updates will appear here.",
            category="info",
            source_module="notifications",
            action_url="/dashboard/notifications",
            action_label="Open Notifications",
            metadata={"seeded": True},
        )

    async def create_for_user(
        self,
        recipient_user_id: str,
        title: str,
        message: str,
        category: str = "info",
        source_module: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        recipient_tenant_id: Optional[str] = None,
    ) -> NotificationRecord:
        record = NotificationRecord(
            recipient_user_id=str(recipient_user_id),
            recipient_tenant_id=recipient_tenant_id,
            title=(title or "").strip(),
            message=(message or "").strip(),
            category=(category or "info").strip().lower(),
            source_module=(source_module or "").strip().lower() or None,
            action_url=(action_url or "").strip() or None,
            action_label=(action_label or "").strip() or None,
            metadata=metadata or {},
        )
        return await self._engine.save(record)

    async def create_for_users(
        self,
        recipient_user_ids: List[str],
        title: str,
        message: str,
        category: str = "info",
        source_module: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        recipient_tenant_id: Optional[str] = None,
    ) -> int:
        saved_count = 0
        seen = set()
        for recipient_user_id in recipient_user_ids:
            normalized = str(recipient_user_id or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            await self.create_for_user(
                recipient_user_id=normalized,
                recipient_tenant_id=recipient_tenant_id,
                title=title,
                message=message,
                category=category,
                source_module=source_module,
                action_url=action_url,
                action_label=action_label,
                metadata=metadata,
            )
            saved_count += 1
        return saved_count

    async def create_for_tenant_users(
        self,
        tenant_id: str,
        title: str,
        message: str,
        category: str = "info",
        source_module: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        users = await self._engine.find(db_user_account, db_user_account.tenant_uuid == str(tenant_id))
        user_ids = [str(user.id) for user in users if getattr(user, "id", None) is not None]
        return await self.create_for_users(
            recipient_user_ids=user_ids,
            recipient_tenant_id=str(tenant_id),
            title=title,
            message=message,
            category=category,
            source_module=source_module,
            action_url=action_url,
            action_label=action_label,
            metadata=metadata,
        )

    async def create_for_tenant_admin_users(
        self,
        tenant_id: str,
        title: str,
        message: str,
        category: str = "info",
        source_module: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        user_ids = await self._active_tenant_admin_user_ids(str(tenant_id))
        if not user_ids:
            # Guard and provider tenants can still have valid active users even when
            # legacy bootstrap data does not expose an active tenant-admin account.
            user_ids = await self._active_tenant_user_ids(str(tenant_id), admin_only=False)
        return await self.create_for_users(
            recipient_user_ids=user_ids,
            recipient_tenant_id=str(tenant_id),
            title=title,
            message=message,
            category=category,
            source_module=source_module,
            action_url=action_url,
            action_label=action_label,
            metadata=metadata,
        )

    async def list_latest(self, current_user, limit: int = 5) -> Dict[str, Any]:
        await self._ensure_active_tenant_for_current_user(current_user)
        await self._ensure_default_notification(current_user)
        safe_limit = max(1, min(int(limit or 5), 20))
        recipient_user_id = self._user_id(current_user)
        collection = self._engine.get_collection(NotificationRecord)
        docs = await collection.find({"recipient_user_id": recipient_user_id}).sort("created_at", -1).limit(safe_limit).to_list(length=safe_limit)
        items = [self._serialize(doc) for doc in docs]
        unread_count = await collection.count_documents({"recipient_user_id": recipient_user_id, "is_read": False})
        return {"items": items, "unread_count": unread_count}

    async def list_notifications(self, current_user, page: int = 1, rows: int = 20, status: str = "all") -> Dict[str, Any]:
        await self._ensure_active_tenant_for_current_user(current_user)
        await self._ensure_default_notification(current_user)
        recipient_user_id = self._user_id(current_user)
        safe_page = page if page and page > 0 else 1
        safe_rows = rows if rows and rows > 0 else 20
        normalized_status = str(status or "all").strip().lower()

        query: Dict[str, Any] = {"recipient_user_id": recipient_user_id}
        if normalized_status == "unread":
            query["is_read"] = False
        elif normalized_status == "read":
            query["is_read"] = True

        collection = self._engine.get_collection(NotificationRecord)
        total_items = await collection.count_documents(query)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        skip = (safe_page - 1) * safe_rows

        docs = await collection.find(query).sort("created_at", -1).skip(skip).limit(safe_rows).to_list(length=safe_rows)
        items = [self._serialize(doc) for doc in docs]

        unread_count = await collection.count_documents({"recipient_user_id": recipient_user_id, "is_read": False})
        return {
            "items": items,
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "status": normalized_status,
            },
            "unread_count": unread_count,
        }

    async def get_unread_count(self, current_user) -> Dict[str, Any]:
        await self._ensure_active_tenant_for_current_user(current_user)
        await self._ensure_default_notification(current_user)
        recipient_user_id = self._user_id(current_user)
        collection = self._engine.get_collection(NotificationRecord)
        unread_count = await collection.count_documents({"recipient_user_id": recipient_user_id, "is_read": False})
        return {"unread_count": unread_count}

    async def mark_read(self, notification_id: str, current_user) -> Dict[str, Any]:
        await self._ensure_active_tenant_for_current_user(current_user)
        recipient_user_id = self._user_id(current_user)
        try:
            object_id = ObjectId(notification_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid notification id")

        record = await self._engine.find_one(NotificationRecord, NotificationRecord.id == object_id)
        if not record or record.recipient_user_id != recipient_user_id:
            raise HTTPException(status_code=404, detail="Notification not found")

        if not record.is_read:
            record.is_read = True
            record.read_at = datetime.utcnow()
            await self._engine.save(record)

        return {
            "message": "Notification marked as read",
            "item": self._serialize(record),
        }

    async def mark_all_read(self, current_user) -> Dict[str, Any]:
        await self._ensure_active_tenant_for_current_user(current_user)
        recipient_user_id = self._user_id(current_user)
        collection = self._engine.get_collection(NotificationRecord)
        await collection.update_many(
            {"recipient_user_id": recipient_user_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}},
        )
        unread_count = await collection.count_documents({"recipient_user_id": recipient_user_id, "is_read": False})
        return {
            "message": "All notifications marked as read",
            "unread_count": unread_count,
        }
