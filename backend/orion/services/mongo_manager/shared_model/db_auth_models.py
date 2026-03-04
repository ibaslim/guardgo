import re
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Set

import pyotp
from odmantic import Model, Field
from passlib.context import CryptContext
from fastapi import HTTPException
from pydantic import field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class user_role(str, Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    OPS_ADMIN = "ops_admin"
    SUPPORT_ADMIN = "support_admin"
    COMPLIANCE_ADMIN = "compliance_admin"
    READ_ONLY_ADMIN = "read_only_admin"
    GUARD_ADMIN = "guard_admin"
    CLIENT_ADMIN = "client_admin"
    SP_ADMIN = "sp_admin"


PLATFORM_ADMIN_ROLES: Set[str] = {
    user_role.ADMIN.value,
    user_role.SUPER_ADMIN.value,
    user_role.OPS_ADMIN.value,
    user_role.SUPPORT_ADMIN.value,
    user_role.COMPLIANCE_ADMIN.value,
    user_role.READ_ONLY_ADMIN.value,
}


PLATFORM_ASSIGNABLE_ROLES: Set[str] = {
    user_role.OPS_ADMIN.value,
    user_role.SUPPORT_ADMIN.value,
    user_role.COMPLIANCE_ADMIN.value,
    user_role.READ_ONLY_ADMIN.value,
}


TENANT_ADMIN_ROLES: Set[str] = {
    user_role.GUARD_ADMIN.value,
    user_role.CLIENT_ADMIN.value,
    user_role.SP_ADMIN.value,
}


ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    user_role.ADMIN.value: {"*"},
    user_role.SUPER_ADMIN.value: {"*"},
    user_role.OPS_ADMIN.value: {
        "tenant:read", "tenant:write", "tenant:status", "platform_admin:read"
    },
    user_role.SUPPORT_ADMIN.value: {
        "tenant:read", "user:read", "user:status", "platform_admin:read"
    },
    user_role.COMPLIANCE_ADMIN.value: {
        "tenant:read", "tenant:verify", "documents:read", "platform_admin:read"
    },
    user_role.READ_ONLY_ADMIN.value: {
        "tenant:read", "user:read", "platform_admin:read"
    },
    user_role.GUARD_ADMIN.value: set(),
    user_role.CLIENT_ADMIN.value: set(),
    user_role.SP_ADMIN.value: set(),
}


def normalize_role_value(role: str | user_role | None) -> str:
    if role is None:
        return ""
    if isinstance(role, user_role):
        return role.value
    return str(role)


def is_super_admin_role(role: str | user_role | None) -> bool:
    return normalize_role_value(role) in {user_role.SUPER_ADMIN.value, user_role.ADMIN.value}


def is_platform_admin_role(role: str | user_role | None) -> bool:
    return normalize_role_value(role) in PLATFORM_ADMIN_ROLES


def is_tenant_admin_role(role: str | user_role | None) -> bool:
    return normalize_role_value(role) in TENANT_ADMIN_ROLES


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    DELETED = "deleted"
    DISABLE = "disable"


class LicenseName(str, Enum):
    FREE = "free"
    ONSIT_BASIC = "osint_basic"
    ONSIT_ADVANCED = "osint_advanced"
    PENTESTER = "pentester"
    MAINTAINER = "maintainer"
    ENTERPRISE = "enterprise"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


class db_user_account(Model):
    username: str = Field(unique=True)
    full_name: str = Field(default="")
    password: str
    email: str = Field(default="")
    role: user_role = Field(default=user_role.CLIENT_ADMIN)
    status: Optional[UserStatus] = Field(default=None)
    status_reason: Optional[str] = Field(default=None)
    status_changed_at: Optional[datetime] = Field(default=None)
    status_changed_by: Optional[str] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None)
    deleted_by: Optional[str] = Field(default=None)

    tenant_uuid: str = Field(default="")
    verification_token: Optional[str] = Field(default=None)
    verification_expiry: Optional[datetime] = Field(default=None)
    invite_pending: bool = Field(default=False)

    twofa_enabled: bool = Field(default=False)
    twofa_secret: Optional[str] = Field(default=None)

    account_verify_at: Optional[datetime] = Field(default=None)
    subscription: bool = Field(default=False)
    preferences: Optional[Dict[str, Any]] = {}
    current_session_id: Optional[str] = Field(default=None)
    licenses: List[LicenseName] = Field(default=[LicenseName.FREE])

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(str(password))

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str, info: FieldValidationInfo) -> str:
        value = value.strip()
        role = info.data.get("role")
        username_pattern = r"^[A-Za-z][A-Za-z0-9_-]{7,19}$"
        # Allow legacy short admin usernames like "admin" to keep existing accounts working
        if value == "admin" or role in [user_role.ADMIN, user_role.SUPER_ADMIN]:
            return value
        if role not in [user_role.ADMIN, user_role.SUPER_ADMIN]:
            if not re.match(username_pattern, value):
                raise ValueError("Username must be 8-20 characters, start with letter")
            if any(op in value for op in ["$", "{", "}"]):
                raise ValueError("Invalid characters in username")
        return value

    @field_validator("password", mode="before")
    @classmethod
    def validate_and_hash_password(cls, value: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError("Password is required")

        password = str(value)

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("Password must contain at least one special character")

        if password.startswith("$2b$"):
            return password

        return pwd_context.hash(password)

    @model_validator(mode="before")
    def validate_licenses(cls, values):
        licenses = values.get("licenses")

        if licenses is not None:
            if not licenses:
                raise HTTPException(status_code=400, detail="At least one license is required")

            if LicenseName.FREE in licenses and len(licenses) > 1:
                raise HTTPException(status_code=400, detail="Free license cannot be combined with other licenses")

            if LicenseName.ONSIT_BASIC in licenses and LicenseName.ONSIT_ADVANCED in licenses:
                raise HTTPException(status_code=400, detail="osint_basic and osint_advanced cannot both be assigned")

            if LicenseName.ENTERPRISE in licenses:
                allowed_combo = {LicenseName.ENTERPRISE, LicenseName.MAINTAINER}
                if not set(licenses).issubset(allowed_combo):
                    raise HTTPException(
                        status_code=400,
                        detail="Enterprise license can only be combined with Maintainer")

        return values

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def is_admin(self) -> bool:
        return is_platform_admin_role(self.role)

    def is_tenant_admin(self) -> bool:
        return is_tenant_admin_role(self.role)

    def verify_2fa(self, code: str) -> bool:
        if not self.twofa_enabled or not self.twofa_secret:
            return False
        return pyotp.TOTP(self.twofa_secret).verify(code, valid_window=1)

    def provisioning_uri(self, issuer: str = "MyApp") -> Optional[str]:
        if not self.twofa_secret:
            return None
        return pyotp.totp.TOTP(self.twofa_secret).provisioning_uri(
            name=self.username, issuer_name=issuer, )
