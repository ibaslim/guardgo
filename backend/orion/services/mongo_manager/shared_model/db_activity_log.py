from datetime import datetime
from typing import Optional, Dict, Any

from odmantic import Model, Field


class ActivityLog(Model):
    module: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_id: str = Field(index=True)
    action: str = Field(index=True)

    actor_id: Optional[str] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None

    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    reason: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None
    severity: str = Field(default="info")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
