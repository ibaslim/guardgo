from datetime import datetime
from typing import Optional, Dict, Any

from odmantic import Model, Field


class NotificationRecord(Model):
    recipient_user_id: str = Field(index=True)
    recipient_tenant_id: Optional[str] = Field(default=None, index=True)
    title: str
    message: str
    category: str = Field(default="info", index=True)
    source_module: Optional[str] = Field(default=None, index=True)
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_read: bool = Field(default=False, index=True)
    read_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
