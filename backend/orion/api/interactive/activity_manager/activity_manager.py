import threading
from typing import Optional, Dict, Any

from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_activity_log import ActivityLog


class ActivityManager:
    __instance = None
    __lock = threading.Lock()

    @staticmethod
    def get_instance():
        if ActivityManager.__instance is None:
            with ActivityManager.__lock:
                if ActivityManager.__instance is None:
                    ActivityManager.__instance = ActivityManager()
        return ActivityManager.__instance

    def __init__(self):
        self._engine = mongo_controller.get_instance().get_engine()
        if ActivityManager.__instance is not None:
            raise Exception("This class is a singleton!")
        ActivityManager.__instance = self

    async def log_event(
        self,
        module: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: Optional[str] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> ActivityLog:
        log = ActivityLog(
            module=(module or "").strip().lower(),
            entity_type=(entity_type or "").strip().lower(),
            entity_id=str(entity_id or ""),
            action=(action or "").strip().lower(),
            actor_id=actor_id,
            actor_username=actor_username,
            actor_role=(str(actor_role).split(".")[-1].lower() if actor_role is not None else None),
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            metadata=metadata or {},
            severity=severity,
        )
        return await self._engine.save(log)

    async def list_events(
        self,
        module: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        actor_username: Optional[str] = None,
        page: int = 1,
        rows: int = 20,
    ) -> Dict[str, Any]:
        collection = self._engine.get_collection(ActivityLog)

        query: Dict[str, Any] = {}
        if module:
            query["module"] = module.strip().lower()
        if entity_type:
            query["entity_type"] = entity_type.strip().lower()
        if entity_id:
            query["entity_id"] = str(entity_id)
        if action:
            query["action"] = action.strip().lower()
        if actor_username:
            query["actor_username"] = actor_username

        safe_rows = rows if rows and rows > 0 else 20
        safe_page = page if page and page > 0 else 1

        total_items = await collection.count_documents(query)
        total_pages = (total_items + safe_rows - 1) // safe_rows if total_items > 0 else 0
        skip = (safe_page - 1) * safe_rows

        docs = await collection.find(query).sort("created_at", -1).skip(skip).limit(safe_rows).to_list(length=safe_rows)

        items = []
        for doc in docs:
            items.append({
                "id": str(doc.get("_id")),
                "module": doc.get("module"),
                "entity_type": doc.get("entity_type"),
                "entity_id": doc.get("entity_id"),
                "action": doc.get("action"),
                "actor_id": doc.get("actor_id"),
                "actor_username": doc.get("actor_username"),
                "actor_role": doc.get("actor_role"),
                "previous_status": doc.get("previous_status"),
                "new_status": doc.get("new_status"),
                "reason": doc.get("reason"),
                "metadata": doc.get("metadata") or {},
                "severity": doc.get("severity"),
                "created_at": doc.get("created_at"),
            })

        return {
            "items": items,
            "pagination": {
                "page": safe_page,
                "rows": safe_rows,
                "total_items": total_items,
                "total_pages": total_pages,
            },
            "filters": {
                "module": module,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "actor_username": actor_username,
            }
        }
