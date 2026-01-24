from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str
    tenant_type: Optional[str] = "client"  # guard | client | service_provider

    @field_validator("tenant_type")
    @classmethod
    def validate_tenant_type(cls, value: Optional[str]):
        if value is None:
            return "client"
        allowed = {"guard", "client", "service_provider"}
        if value not in allowed:
            raise ValueError(f"tenant_type must be one of: {', '.join(sorted(allowed))}")
        return value
