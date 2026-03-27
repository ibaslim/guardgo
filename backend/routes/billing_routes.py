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
    description="Returns default pay rates by province for guards (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_guard_rates():
    return await BillingManager.get_instance().get_guard_rates()


@billing_routes.put(
    "/api/billing/guards",
    summary="Save guard default pay rates",
    description="Upsert default pay rates by province for guards (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_guard_rates(
    payload: List[Dict[str, Any]],
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_guard_rates(payload, current_user)


@billing_routes.get(
    "/api/billing/margins/guards/defaults",
    summary="Get guard margin defaults",
    description="Returns default guard margin values by province (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_guard_margin_rates():
    return await BillingManager.get_instance().get_guard_margin_rates()


@billing_routes.put(
    "/api/billing/margins/guards/defaults",
    summary="Save guard margin defaults",
    description="Upsert default guard margin values by province (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_guard_margin_rates(
    payload: List[Dict[str, Any]],
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_guard_margin_rates(payload, current_user)


@billing_routes.get(
    "/api/billing/guards/list",
    summary="List active guards",
    description="Returns name + id for each active guard (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def list_active_guards():
    return await BillingManager.get_instance().list_active_guards()


@billing_routes.get(
    "/api/billing/guards/{guard_id}",
    summary="Get guard pay rates",
    description="Returns pay rates by province for a specific guard (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_guard_override_rates(
    guard_id: str = Path(..., description="Guard tenant ObjectId"),
):
    return await BillingManager.get_instance().get_guard_override_rates(guard_id)


@billing_routes.put(
    "/api/billing/guards/{guard_id}",
    summary="Save guard pay rates",
    description="Upsert pay rates by province for a specific guard (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_guard_override_rates(
    payload: List[Dict[str, Any]],
    guard_id: str = Path(..., description="Guard tenant ObjectId"),
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_guard_override_rates(
        guard_id, payload, current_user
    )


@billing_routes.post(
    "/api/billing/guards/{guard_id}/sync-defaults",
    summary="Sync guard rates from defaults",
    description="Copy current guard default rates into a specific guard override matrix (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def sync_guard_override_rates_from_defaults(
    guard_id: str = Path(..., description="Guard tenant ObjectId"),
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().sync_guard_override_with_defaults(
        guard_id, current_user
    )


@billing_routes.get(
    "/api/billing/providers/defaults",
    summary="Get service provider default pay rates",
    description="Returns default pay rates by province for service providers (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_provider_default_rates():
    return await BillingManager.get_instance().get_provider_default_rates()


@billing_routes.put(
    "/api/billing/providers/defaults",
    summary="Save service provider default pay rates",
    description="Upsert default pay rates by province for service providers (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_provider_default_rates(
    payload: List[Dict[str, Any]],
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_provider_default_rates(payload, current_user)


@billing_routes.get(
    "/api/billing/commissions/providers/defaults",
    summary="Get provider commission defaults",
    description="Returns default provider commission values by province (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_provider_commission_rates():
    return await BillingManager.get_instance().get_provider_commission_rates()


@billing_routes.put(
    "/api/billing/commissions/providers/defaults",
    summary="Save provider commission defaults",
    description="Upsert default provider commission values by province (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_provider_commission_rates(
    payload: List[Dict[str, Any]],
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_provider_commission_rates(payload, current_user)


@billing_routes.get(
    "/api/billing/providers/list",
    summary="List active service providers",
    description="Returns name + id for each active service provider (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def list_active_providers():
    return await BillingManager.get_instance().list_active_providers()


@billing_routes.get(
    "/api/billing/providers/{provider_id}",
    summary="Get provider pay rates",
    description="Returns pay rates by province for a specific service provider (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def get_provider_rates(
    provider_id: str = Path(..., description="Service provider tenant ObjectId"),
):
    return await BillingManager.get_instance().get_provider_rates(provider_id)


@billing_routes.put(
    "/api/billing/providers/{provider_id}",
    summary="Save provider pay rates",
    description="Upsert pay rates by province for a specific service provider (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def save_provider_rates(
    payload: List[Dict[str, Any]],
    provider_id: str = Path(..., description="Service provider tenant ObjectId"),
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().save_provider_rates(
        provider_id, payload, current_user
    )


@billing_routes.post(
    "/api/billing/providers/{provider_id}/sync-defaults",
    summary="Sync provider rates from defaults",
    description="Copy current service provider default rates into a specific provider override matrix (admin only).",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def sync_provider_override_rates_from_defaults(
    provider_id: str = Path(..., description="Service provider tenant ObjectId"),
    current_user=Depends(get_current_user),
):
    return await BillingManager.get_instance().sync_provider_override_with_defaults(
        provider_id, current_user
    )
