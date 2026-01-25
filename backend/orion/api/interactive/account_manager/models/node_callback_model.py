from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from orion.services.mongo_manager.shared_model.db_auth_models import LicenseName, UserStatus, user_role


class UserDataModel(BaseModel):
    email: str
    twofa_enabled: bool
    username: str
    role: user_role
    status: UserStatus
    subscription: bool
    verificationDate: Optional[datetime]
    license: List[LicenseName]
    image: Optional[str] = None


class TenantDataModel(BaseModel):
    id: str
    name: str
    phone: str
    country: str
    city: str
    postal_code: str
    tax_id: str
    has_onboarding: bool
    is_default: bool
    user_id: str
    licenses: list[str]
    assigned_quota: str
    quota_exceeded: bool
    image: Optional[str] = None
    tenant_type: Optional[str] = None
    status: Optional[str] = None


class NodeCallbackModel(BaseModel):
    user: UserDataModel
    tenant: TenantDataModel
