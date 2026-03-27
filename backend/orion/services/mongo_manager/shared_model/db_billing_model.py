from typing import Optional
from datetime import datetime

from odmantic import Model


class BillingRate(Model):
    """
    Stores a single province pay rate record.
    - scope = "guard_default"         → default guard rates
    - scope = "provider_default"      → default service-provider rates
    - scope = "guard:<tenant_id>"     → guard-specific override rates
    - scope = "provider:<tenant_id>"  → service-provider-specific override rates

    Legacy scopes are still read for compatibility during transition.
    """
    scope: str = ""
    region_code: str = ""
    standard_rate: float = 0.0
    weekend_rate: float = 0.0
    holiday_rate: float = 0.0
    currency: str = "CAD"
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
