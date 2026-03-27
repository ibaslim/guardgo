from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator

from orion.services.mongo_manager.shared_model.db_auth_models import user_role, PLATFORM_ASSIGNABLE_ROLES
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, LicenseName


class PlatformAdminCreateRequest(BaseModel):
    email: EmailStr
    role: user_role

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: user_role) -> user_role:
        if value.value not in PLATFORM_ASSIGNABLE_ROLES:
            allowed = ", ".join(sorted(PLATFORM_ASSIGNABLE_ROLES))
            raise ValueError(f"role must be one of: {allowed}")
        return value


class PlatformAdminUpdateRequest(BaseModel):
    role: Optional[user_role] = None
    status: Optional[UserStatus] = None
    status_reason: Optional[str] = None
    licenses: Optional[List[LicenseName]] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[user_role]) -> Optional[user_role]:
        if value is None:
            return None
        if value.value not in PLATFORM_ASSIGNABLE_ROLES:
            allowed = ", ".join(sorted(PLATFORM_ASSIGNABLE_ROLES))
            raise ValueError(f"role must be one of: {allowed}")
        return value


class PlatformAdminResponse(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    email: str
    role: str
    status: Optional[str] = None
    status_reason: Optional[str] = None
    tenant_uuid: Optional[str] = None
    licenses: List[str] = []
    invite_pending: Optional[bool] = None
    invite_expires_at: Optional[str] = None
    deleted_at: Optional[str] = None


class PlatformAdminStatusReasonRequest(BaseModel):
    reason: str


class PlatformAdminRoleOption(BaseModel):
    value: str
    label: str
