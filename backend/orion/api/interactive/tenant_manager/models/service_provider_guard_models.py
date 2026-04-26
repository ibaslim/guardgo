from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from orion.services.mongo_manager.shared_model.db_tenant_model import GuardStatusAction


class ServiceProviderGuardInviteRequest(BaseModel):
    email: EmailStr


class ServiceProviderGuardStatusRequestPayload(BaseModel):
    action: GuardStatusAction = Field(
        description="Requested action. Use 'activate' or 'deactivate'.",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Required when action is 'deactivate'. Optional for 'activate'.",
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def enforce_reason_for_deactivation(self):
        if self.action == GuardStatusAction.DEACTIVATE and not self.reason:
            raise ValueError("reason is required when action is 'deactivate'")
        return self


class GuardStatusRequestDecisionPayload(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=500)


class GuardServiceProviderLinkPayload(BaseModel):
    service_provider_tenant_id: str
    reason: str = Field(min_length=3, max_length=500)


class GuardServiceProviderUnlinkPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
