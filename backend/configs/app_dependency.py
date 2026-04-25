from typing import Optional
from fastapi import Depends, HTTPException, status
from bson import ObjectId
from fastapi.security import OAuth2PasswordBearer
from orion.helper_manager.env_handler import env_handler
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_auth_models import (
    user_role,
    UserStatus,
    normalize_role_value,
    is_platform_admin_role,
    is_tenant_admin_role,
)
from orion.services.mongo_manager.shared_model.db_tenant_model import db_tenant_model, TenantStatus
from orion.services.session_manager.session_manager import session_manager
from orion.constants import constant

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/token", auto_error=False)


async def get_current_role(token: str = Depends(oauth2_scheme)):
    role = await session_manager.get_instance().get_current_role(token)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not found")

    return role


async def get_current_status(token: str = Depends(oauth2_scheme)):
    user_status = await session_manager.get_instance().get_current_status(token)
    if user_status is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role not found")

    return user_status


def role_required(required_roles: list[user_role]):
    def _matches(required: user_role, actual_role_value: str) -> bool:
        required_value = normalize_role_value(required)
        return actual_role_value == required_value

    async def verify_role(role: user_role = Depends(get_current_role)):
        actual_role_value = normalize_role_value(role)
        if not any(_matches(required_role, actual_role_value) for required_role in required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")
        return role

    return verify_role


async def get_current_user(token: str = Depends(oauth2_scheme)):
    session_mgr = session_manager.get_instance()
    return await session_mgr.get_current_user(token)


def status_required(status_required: list[UserStatus], bypass_roles: Optional[list[user_role]] = None):
    async def verify_status(user_status: UserStatus = Depends(get_current_status),
            role: user_role = Depends(get_current_role), ):
        if bypass_roles and role in bypass_roles:
            return user_status

        if user_status not in status_required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")
        return user_status

    return verify_status


def tenant_status_required(allowed_statuses: list[TenantStatus], bypass_roles: Optional[list[user_role]] = None):
    async def verify_tenant_status(
        current_user=Depends(get_current_user),
        role: user_role = Depends(get_current_role),
    ):
        if bypass_roles and role in bypass_roles:
            return True

        if is_platform_admin_role(role):
            return True

        if not is_tenant_admin_role(role):
            return True

        tenant_uuid = str(getattr(current_user, "tenant_uuid", "") or "").strip()
        if not tenant_uuid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid tenant association")

        try:
            tenant = await mongo_controller.get_instance().get_engine().find_one(
                db_tenant_model,
                db_tenant_model.id == ObjectId(tenant_uuid),
            )
        except Exception:
            tenant = None

        if not tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found")

        allowed_values = {str(getattr(s, "value", s)).strip().lower() for s in (allowed_statuses or [])}
        tenant_value = str(getattr(tenant.status, "value", tenant.status)).strip().lower()
        if tenant_value == TenantStatus.PENDING_VERIFICATION.value:
            tenant_value = TenantStatus.PENDING_ACTIVATION.value

        if tenant_value not in allowed_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is not active for this action")

        return True

    return verify_tenant_status


def license_required(feature: str, bypass_roles: Optional[list[user_role]] = None):
    async def checker(user=Depends(get_current_user), role: user_role = Depends(get_current_role)):
        if bypass_roles and role in bypass_roles:
            return True
        permissions = get_user_permissions(user)
        if feature.startswith("module:"):
            module_name = feature.split(":", 1)[1]
            if permissions["modules"] == "all" or module_name in permissions["modules"]:
                return True
            raise HTTPException(
                403, f"No license for module: {module_name}")
        if not permissions.get(feature, False):
            raise HTTPException(
                403, f"License required: {feature}")
        return True

    return checker


def get_user_permissions(user):
    final = {"modules": set(), "cti_graph": False, "mapping": False, "scanning": False, "maintainer": False}

    for lic in user.licenses:
        rules = constant.license_rules.get(lic, {})
        if rules.get("modules") == "all":
            final["modules"] = "all"
        elif final["modules"] != "all":
            final["modules"].update(rules.get("modules", []))

        final["cti_graph"] |= rules.get("cti_graph", False)
        final["mapping"] |= rules.get("mapping", False)
        final["scanning"] |= rules.get("scanning", False)
        final["maintainer"] |= rules.get("maintainer", False)

    return final
