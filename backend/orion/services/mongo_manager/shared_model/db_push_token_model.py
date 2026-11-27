from datetime import datetime
from typing import Optional

from odmantic import Field, Model


class PushTokenRecord(Model):
    token: str = Field(unique=True)
    user_id: str = Field(index=True)
    tenant_id: Optional[str] = Field(default=None, index=True)
    platform: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class PushTicketRecord(Model):
    ticket_id: str = Field(unique=True)
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
