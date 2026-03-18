from typing import Optional
from datetime import datetime

from odmantic import Model


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
