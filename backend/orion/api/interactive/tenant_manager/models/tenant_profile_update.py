from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from orion.services.mongo_manager.shared_model.db_tenant_model import (
    GuardProfile,
    ClientProfile,
    ServiceProviderProfile,
    TenantType,
)


class TenantProfileUpdate(BaseModel):
    guard: Optional[GuardProfile] = None
    client: Optional[ClientProfile] = None
    service_provider: Optional[ServiceProviderProfile] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("service_provider")
    @classmethod
    def _noop(cls, v):
        # placeholder to ensure pydantic generates field set info properly
        return v

    @field_validator("guard")
    @classmethod
    def _noop_guard(cls, v):
        return v

    @field_validator("client")
    @classmethod
    def _noop_client(cls, v):
        return v

    def selected_type(self) -> Optional[TenantType]:
        if self.guard is not None:
            return TenantType.GUARD
        if self.client is not None:
            return TenantType.CLIENT
        if self.service_provider is not None:
            return TenantType.SERVICE_PROVIDER
        return None

    def dump_selected(self):
        if self.guard is not None:
            return self.guard.model_dump(exclude_unset=True)
        if self.client is not None:
            return self.client.model_dump(exclude_unset=True)
        if self.service_provider is not None:
            return self.service_provider.model_dump(exclude_unset=True)
        return {}

    @model_validator(mode="after")
    def _ensure_single_type(self):
        count = sum(1 for v in [self.guard, self.client, self.service_provider] if v is not None)
        if count == 0:
            raise ValueError("One of guard, client or service_provider is required")
        if count > 1:
            raise ValueError("Provide only one of guard, client or service_provider")
        return self
