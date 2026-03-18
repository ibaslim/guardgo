from typing import Optional
from datetime import datetime

from odmantic import Model, Field


class BillingRate(Model):
    """
    Stores a single province pay rate record.
    - scope = "guard"           → default guard rates
    - scope = <provider_id>     → service-provider-specific rates
    """
    scope: str = ""
    region_code: str = ""
    standard_rate: float = 0.0
    weekend_rate: float = 0.0
    holiday_rate: float = 0.0
    currency: str = "CAD"
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


class BillingRateAudit(Model):
    """Immutable audit record written every time billing rates are saved."""
    scope: str = ""
    region_code: str = ""
    previous_standard_rate: float = 0.0
    previous_weekend_rate: float = 0.0
    previous_holiday_rate: float = 0.0
    new_standard_rate: float = 0.0
    new_weekend_rate: float = 0.0
    new_holiday_rate: float = 0.0
    actor: Optional[str] = None
    actor_role: Optional[str] = None
    created_at: Optional[datetime] = Field(default=None)
