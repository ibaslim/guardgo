from fastapi import APIRouter, Depends

from configs.app_dependency import role_required, status_required, get_current_user
from orion.api.interactive.request_matching_manager.models.request_matching_models import (
    RequestMatchingPreviewPayload,
)
from orion.api.interactive.request_matching_manager.request_matching_manager import RequestMatchingManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role


request_matching_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Request Matching"],
)


@request_matching_routes.post(
    "/api/request-matching/preview",
    summary="Preview candidate matching",
    description="Run province + radius eligibility matching preview for guards or service providers.",
    tags=["Request Matching"],
    operation_id="previewRequestMatching",
    response_description="Reason-coded match candidates with distance and radius in km/mi.",
    status_code=200,
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def preview_request_matching(payload: RequestMatchingPreviewPayload, current_user=Depends(get_current_user)):
    _ = current_user
    return await RequestMatchingManager.get_instance().preview_matches(payload)
