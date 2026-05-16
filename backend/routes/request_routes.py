from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user, role_required, status_required
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestCreatePayload,
    ClientRequestStatusUpdatePayload,
    ClientRequestUpdatePayload,
    RequestAdditionalCoveragePayload,
    RequestAssignmentCreatePayload,
    RequestAssignmentStatusUpdatePayload,
    RequestPublishPayload,
    RequestPublishUpdatePayload,
    RequestWaveReviewPayload,
)


request_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Client Requests"],
)


@request_routes.get(
    "/api/requests",
    summary="List client requests",
    description="Return paginated requests for the current client tenant.",
    tags=["Client Requests"],
    operation_id="listClientRequests",
    response_description="Paginated client requests.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def list_client_requests(
    page: int = 1,
    rows: int = 20,
    keyword: str = "",
    request_status: str = "",
    fulfillment_mode: str = "",
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_requests(
        current_user=current_user,
        page=page,
        rows=rows,
        keyword=keyword,
        request_status=request_status,
        fulfillment_mode=fulfillment_mode,
    )


@request_routes.post(
    "/api/requests",
    summary="Create client request",
    description="Create a new client request and generate a candidate matching snapshot.",
    tags=["Client Requests"],
    operation_id="createClientRequest",
    response_description="Created client request.",
    status_code=201,
    dependencies=[Depends(role_required([user_role.CLIENT_ADMIN]))],
)
async def create_client_request(payload: ClientRequestCreatePayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().create_request(payload=payload, current_user=current_user)


@request_routes.patch(
    "/api/requests/{request_id}",
    summary="Update request draft",
    description="Update request content while the request is still editable (draft).",
    tags=["Client Requests"],
    operation_id="updateClientRequest",
    response_description="Updated client request draft.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def update_client_request(request_id: str, payload: ClientRequestUpdatePayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().update_request(request_id=request_id, payload=payload, current_user=current_user)


@request_routes.get(
    "/api/requests/{request_id}",
    summary="Get client request",
    description="Return a single client request for the current client tenant.",
    tags=["Client Requests"],
    operation_id="getClientRequest",
    response_description="Client request details.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def get_client_request(request_id: str, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().get_request_by_id(request_id=request_id, current_user=current_user)


@request_routes.get(
    "/api/request-waves/{wave_id}",
    summary="Get request wave",
    description="Return a single request broadcast wave when it is visible to the current user.",
    tags=["Client Requests"],
    operation_id="getClientRequestWave",
    response_description="Request wave details.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def get_client_request_wave(wave_id: str, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().get_request_wave_by_id(wave_id=wave_id, current_user=current_user)


@request_routes.post(
    "/api/requests/{request_id}/publish",
    summary="Publish client request",
    description="Publish a draft client request and create the first broadcast wave.",
    tags=["Client Requests"],
    operation_id="publishClientRequest",
    response_description="Published client request.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def publish_client_request(request_id: str, payload: RequestPublishPayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().publish_request(request_id=request_id, payload=payload, current_user=current_user)


@request_routes.post(
    "/api/requests/{request_id}/publish-update",
    summary="Publish request update",
    description="Apply a material update to a live request and issue a fresh broadcast wave.",
    tags=["Client Requests"],
    operation_id="publishClientRequestUpdate",
    response_description="Updated and republished client request.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def publish_client_request_update(
    request_id: str,
    payload: RequestPublishUpdatePayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().publish_request_update(
        request_id=request_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/requests/{request_id}/additional-coverage",
    summary="Request additional coverage",
    description="Increase open staffing slots for a live request and issue a fresh broadcast wave.",
    tags=["Client Requests"],
    operation_id="requestAdditionalCoverage",
    response_description="Client request with additional coverage issued.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def request_additional_coverage(
    request_id: str,
    payload: RequestAdditionalCoveragePayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().request_additional_coverage(
        request_id=request_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.patch(
    "/api/requests/{request_id}/status",
    summary="Update client request status",
    description="Update request lifecycle state for the current client tenant.",
    tags=["Client Requests"],
    operation_id="updateClientRequestStatus",
    response_description="Updated client request.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def update_client_request_status(request_id: str, payload: ClientRequestStatusUpdatePayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().update_request_status(request_id=request_id, payload=payload, current_user=current_user)


@request_routes.get(
    "/api/requests/{request_id}/waves",
    summary="List request waves",
    description="List broadcast waves for a client request.",
    tags=["Client Requests"],
    operation_id="listClientRequestWaves",
    response_description="Paginated request waves.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def list_client_request_waves(
    request_id: str,
    page: int = 1,
    rows: int = 20,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_request_waves(
        request_id=request_id,
        current_user=current_user,
        page=page,
        rows=rows,
    )


@request_routes.get(
    "/api/request-review-waves",
    summary="List request review waves",
    description="List request broadcast waves that are visible to platform reviewers.",
    tags=["Client Requests"],
    operation_id="listRequestReviewWaves",
    response_description="Paginated request review waves.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
    ]))],
)
async def list_request_review_waves(
    page: int = 1,
    rows: int = 20,
    wave_status: str = "",
    trigger: str = "",
    request_id: str = "",
    client_tenant_id: str = "",
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_review_waves(
        current_user=current_user,
        page=page,
        rows=rows,
        wave_status=wave_status,
        trigger=trigger,
        request_id=request_id,
        client_tenant_id=client_tenant_id,
    )


@request_routes.post(
    "/api/request-review-waves/{wave_id}/approve",
    summary="Approve request wave",
    description="Approve a pending-review request broadcast wave and send offers.",
    tags=["Client Requests"],
    operation_id="approveRequestReviewWave",
    response_description="Approved request wave.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
    ]))],
)
async def approve_request_review_wave(
    wave_id: str,
    payload: RequestWaveReviewPayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().approve_request_wave(
        wave_id=wave_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/request-review-waves/{wave_id}/return",
    summary="Return request wave",
    description="Return a pending-review request broadcast wave back to the client.",
    tags=["Client Requests"],
    operation_id="returnRequestReviewWave",
    response_description="Returned request wave.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
    ]))],
)
async def return_request_review_wave(
    wave_id: str,
    payload: RequestWaveReviewPayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().return_request_wave(
        wave_id=wave_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/requests/{request_id}/assign",
    summary="Assign request candidate",
    description="Create a request assignment from eligible match candidates.",
    tags=["Client Requests"],
    operation_id="assignClientRequest",
    response_description="Created assignment.",
    status_code=201,
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def assign_client_request(request_id: str, payload: RequestAssignmentCreatePayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().create_assignment(request_id=request_id, payload=payload, current_user=current_user)


@request_routes.get(
    "/api/jobs",
    summary="List request jobs",
    description="List request assignments/jobs for the current role scope.",
    tags=["Client Requests"],
    operation_id="listRequestJobs",
    response_description="Paginated assignment jobs.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def list_request_jobs(
    page: int = 1,
    rows: int = 20,
    assignment_status: str = "",
    keyword: str = "",
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_jobs(
        current_user=current_user,
        page=page,
        rows=rows,
        assignment_status=assignment_status,
        keyword=keyword,
    )


@request_routes.get(
    "/api/jobs/{assignment_id}",
    summary="Get request job",
    description="Return a single assignment/job when it is visible to the current user.",
    tags=["Client Requests"],
    operation_id="getRequestJob",
    response_description="Request assignment.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def get_request_job(assignment_id: str, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().get_job_by_id(assignment_id=assignment_id, current_user=current_user)


@request_routes.patch(
    "/api/jobs/{assignment_id}/status",
    summary="Update job status",
    description="Update assignment lifecycle status for accepted/ongoing/completed job flow.",
    tags=["Client Requests"],
    operation_id="updateRequestJobStatus",
    response_description="Updated assignment.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def update_request_job_status(
    assignment_id: str,
    payload: RequestAssignmentStatusUpdatePayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().update_job_status(
        assignment_id=assignment_id,
        payload=payload,
        current_user=current_user,
    )
