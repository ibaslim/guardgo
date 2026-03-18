from typing import List, Dict, Any

from fastapi import APIRouter, Depends, Path

from configs.app_dependency import status_required, role_required, get_current_user
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.api.interactive.billing_manager.billing_manager import BillingManager

billing_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Billing"],
)


@billing_routes.get(
    "/api/billing/guards",
    summary="Get guard default pay rates",
    description="Returns default pay rates by province for guards (super-admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))],
)
async def get_guard_rates():
    return await BillingManager.get_instance().get_guard_rates()


@billing_routes.put(
    "/api/billing/guards",
    summary="Save guard default pay rates",
    description="Upsert default pay rates by province for guards (super-admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))],
)
async def save_guard_rates(
    payload: List[Dict[str, Any]],
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_guard_rates(payload, current_user)


@billing_routes.get(
    "/api/billing/providers/list",
    summary="List active service providers",
    description="Returns name + id for each active service provider (super-admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))],
)
async def list_active_providers():
    return await BillingManager.get_instance().list_active_providers()


@billing_routes.get(
    "/api/billing/providers/{provider_id}",
    summary="Get provider pay rates",
    description="Returns pay rates by province for a specific service provider (super-admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))],
)
async def get_provider_rates(
    provider_id: str = Path(..., description="Service provider tenant ObjectId"),
):
    return await BillingManager.get_instance().get_provider_rates(provider_id)


@billing_routes.put(
    "/api/billing/providers/{provider_id}",
    summary="Save provider pay rates",
    description="Upsert pay rates by province for a specific service provider (super-admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))],
)
async def save_provider_rates(
    payload: List[Dict[str, Any]],
    provider_id: str = Path(..., description="Service provider tenant ObjectId"),
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_provider_rates(
        provider_id, payload, current_user
    )
