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
    city_code: str = ""
    standard_rate: float = 0.0
    weekend_rate: float = 0.0
    holiday_rate: float = 0.0
    currency: str = "CAD"
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


class TravelPricingPolicy(Model):
    """
    Stores travel pricing and auto-match thresholds by province/city.
    - scope = "guard_travel_default"    → default direct-guard travel policy
    - scope = "provider_travel_default" → default service-provider travel policy

    City rows override the province default row for the same scope, where
    province defaults are stored with an empty city_code.
    """
    scope: str = ""
    region_code: str = ""
    city_code: str = ""
    included_radius_km: float = 10.0
    rate_per_km: float = 0.0
    max_auto_match_radius_km: Optional[float] = None
    manual_review_over_km: Optional[float] = None
    currency: str = "CAD"
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
