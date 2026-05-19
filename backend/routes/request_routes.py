from datetime import date

from fastapi import APIRouter, Depends

from configs.app_dependency import get_current_user, role_required, status_required
from orion.api.interactive.request_manager.request_manager import RequestManager
from orion.api.interactive.request_shift_manager.request_shift_manager import RequestShiftManager
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role
from orion.services.mongo_manager.shared_model.db_request_model import (
    ClientRequestCreatePayload,
    ClientRequestSoftDeletePayload,
    ClientRequestStatusUpdatePayload,
    ClientRequestUpdatePayload,
    ProviderRosterPayload,
    RequestScheduleUpsertPayload,
    RequestAdditionalCoveragePayload,
    RequestAssignmentCreatePayload,
    RequestAssignmentStatusUpdatePayload,
    RequestPublishPayload,
    RequestPublishUpdatePayload,
    ShiftSlotCheckInPayload,
    ShiftSlotCheckOutPayload,
    ShiftSlotClientConfirmPayload,
    ShiftSlotReopenPayload,
    ShiftSlotStartPayload,
    ShiftSlotUnavailablePayload,
    RequestWaveReviewPayload,
)


request_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Client Requests"],
)


@request_routes.get(
    "/api/requests",
    summary="List client requests",
    description="Return paginated requests in the current role scope.",
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
    client_tenant_id: str = "",
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_requests(
        current_user=current_user,
        page=page,
        rows=rows,
        keyword=keyword,
        request_status=request_status,
        fulfillment_mode=fulfillment_mode,
        client_tenant_id=client_tenant_id,
    )


@request_routes.post(
    "/api/requests",
    summary="Create client request",
    description="Create a new client request and generate a candidate matching snapshot.",
    tags=["Client Requests"],
    operation_id="createClientRequest",
    response_description="Created client request.",
    status_code=201,
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def create_client_request(payload: ClientRequestCreatePayload, current_user=Depends(get_current_user)):
    return await RequestManager.get_instance().create_request(payload=payload, current_user=current_user)


@request_routes.get(
    "/api/request-client-tenants",
    summary="List active client tenants for request operations",
    description="Return active client tenants that platform users can target when creating or filtering requests.",
    tags=["Client Requests"],
    operation_id="listRequestClientTenants",
    response_description="Active client tenants available for request creation.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
    ]))],
)
async def list_request_client_tenants(
    keyword: str = "",
    rows: int = 100,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().list_request_client_tenants(
        current_user=current_user,
        keyword=keyword,
        rows=rows,
    )


@request_routes.get(
    "/api/request-client-tenants/{tenant_id}",
    summary="Get active client tenant snapshot for request creation",
    description="Return the client profile snapshot, including saved sites, for a platform-targeted request.",
    tags=["Client Requests"],
    operation_id="getRequestClientTenantSnapshot",
    response_description="Client tenant snapshot.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
    ]))],
)
async def get_request_client_tenant_snapshot(
    tenant_id: str,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().get_request_client_tenant_snapshot(
        tenant_id=tenant_id,
        current_user=current_user,
    )


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
    "/api/requests/{request_id}/schedule",
    summary="Get request schedule",
    description="Return the configured schedule template for a request.",
    tags=["Client Requests"],
    operation_id="getRequestSchedule",
    response_description="Request schedule.",
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
async def get_request_schedule(request_id: str, current_user=Depends(get_current_user)):
    return await RequestShiftManager.get_instance().get_request_schedule(request_id=request_id, current_user=current_user)


@request_routes.post(
    "/api/requests/{request_id}/schedule",
    summary="Create or replace request schedule",
    description="Create or replace the schedule template for a request and regenerate future shift instances.",
    tags=["Client Requests"],
    operation_id="upsertRequestSchedule",
    response_description="Updated request schedule.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def create_request_schedule(
    request_id: str,
    payload: RequestScheduleUpsertPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().upsert_request_schedule(
        request_id=request_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.patch(
    "/api/requests/{request_id}/schedule",
    summary="Update request schedule",
    description="Update the schedule template for a request and regenerate future shift instances.",
    tags=["Client Requests"],
    operation_id="updateRequestSchedule",
    response_description="Updated request schedule.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def update_request_schedule(
    request_id: str,
    payload: RequestScheduleUpsertPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().upsert_request_schedule(
        request_id=request_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.get(
    "/api/shifts",
    summary="List shifts",
    description="Return paginated shift instances visible to the current user.",
    tags=["Client Requests"],
    operation_id="listRequestShifts",
    response_description="Paginated shift instances.",
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
async def list_request_shifts(
    page: int = 1,
    rows: int = 20,
    request_id: str = "",
    instance_status: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().list_shifts(
        current_user=current_user,
        page=page,
        rows=rows,
        request_id=request_id,
        instance_status=instance_status,
        date_from=date_from,
        date_to=date_to,
    )


@request_routes.get(
    "/api/shift-exceptions",
    summary="List shift exceptions",
    description="Return shift-slot exceptions for platform review, including unavailable and no-show cases.",
    tags=["Client Requests"],
    operation_id="listShiftExceptions",
    response_description="Paginated shift-slot exceptions.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
    ]))],
)
async def list_shift_exceptions(
    page: int = 1,
    rows: int = 20,
    exception_status: str = "",
    request_id: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().list_shift_exceptions(
        current_user=current_user,
        page=page,
        rows=rows,
        exception_status=exception_status,
        request_id=request_id,
        date_from=date_from,
        date_to=date_to,
    )


@request_routes.get(
    "/api/shifts/{shift_id}",
    summary="Get shift",
    description="Return one shift instance when it is visible to the current user.",
    tags=["Client Requests"],
    operation_id="getRequestShift",
    response_description="Shift instance details.",
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
async def get_request_shift(shift_id: str, current_user=Depends(get_current_user)):
    return await RequestShiftManager.get_instance().get_shift_by_id(shift_id=shift_id, current_user=current_user)


@request_routes.get(
    "/api/shift-slots/{slot_id}",
    summary="Get shift slot",
    description="Return one shift slot when it is visible to the current user.",
    tags=["Client Requests"],
    operation_id="getRequestShiftSlot",
    response_description="Shift slot details.",
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
async def get_request_shift_slot(slot_id: str, current_user=Depends(get_current_user)):
    return await RequestShiftManager.get_instance().get_shift_slot_by_id(slot_id=slot_id, current_user=current_user)


@request_routes.post(
    "/api/shifts/{shift_id}/roster",
    summary="Roster provider guards for a shift",
    description="Assign named active service-provider guards to provider-backed shift slots.",
    tags=["Client Requests"],
    operation_id="rosterRequestShift",
    response_description="Updated shift with rostered slots.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.SP_ADMIN,
    ]))],
)
async def roster_request_shift(
    shift_id: str,
    payload: ProviderRosterPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().roster_shift(
        shift_id=shift_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/report-unavailable",
    summary="Report shift slot unavailable",
    description="Report that an assigned guard cannot cover the shift slot before start time.",
    tags=["Client Requests"],
    operation_id="reportRequestShiftSlotUnavailable",
    response_description="Updated shift slot with exception events.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.GUARD_ADMIN,
    ]))],
)
async def report_request_shift_slot_unavailable(
    slot_id: str,
    payload: ShiftSlotUnavailablePayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().report_shift_slot_unavailable(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/reopen",
    summary="Reopen shift slot for replacement",
    description="Create a replacement slot and broadcast wave for an exception shift slot.",
    tags=["Client Requests"],
    operation_id="reopenRequestShiftSlot",
    response_description="Replacement slot and wave context.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
    ]))],
)
async def reopen_request_shift_slot(
    slot_id: str,
    payload: ShiftSlotReopenPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().reopen_shift_slot(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/check-in",
    summary="Check in to a shift slot",
    description="Submit guard arrival with location proof for a shift slot.",
    tags=["Client Requests"],
    operation_id="checkInRequestShiftSlot",
    response_description="Updated shift slot with attendance events.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.GUARD_ADMIN,
    ]))],
)
async def check_in_request_shift_slot(
    slot_id: str,
    payload: ShiftSlotCheckInPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().check_in_shift_slot(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/client-confirm",
    summary="Confirm shift slot arrival",
    description="Confirm that a guard is physically present and ready to start the shift.",
    tags=["Client Requests"],
    operation_id="confirmRequestShiftSlotArrival",
    response_description="Updated shift slot with attendance events.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.CLIENT_ADMIN,
    ]))],
)
async def confirm_request_shift_slot_arrival(
    slot_id: str,
    payload: ShiftSlotClientConfirmPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().confirm_shift_slot_arrival(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/start",
    summary="Start shift slot",
    description="Start the shift slot after arrival confirmation, or through platform override.",
    tags=["Client Requests"],
    operation_id="startRequestShiftSlot",
    response_description="Updated shift slot with attendance events.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.GUARD_ADMIN,
    ]))],
)
async def start_request_shift_slot(
    slot_id: str,
    payload: ShiftSlotStartPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().start_shift_slot(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


@request_routes.post(
    "/api/shift-slots/{slot_id}/check-out",
    summary="Check out from a shift slot",
    description="Check out and complete the shift slot using actual end time.",
    tags=["Client Requests"],
    operation_id="checkOutRequestShiftSlot",
    response_description="Updated shift slot with attendance events.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.GUARD_ADMIN,
    ]))],
)
async def check_out_request_shift_slot(
    slot_id: str,
    payload: ShiftSlotCheckOutPayload,
    current_user=Depends(get_current_user),
):
    return await RequestShiftManager.get_instance().check_out_shift_slot(
        slot_id=slot_id,
        payload=payload,
        current_user=current_user,
    )


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


@request_routes.post(
    "/api/requests/{request_id}/soft-delete",
    summary="Soft delete client request",
    description="Remove a client request from dashboard listings without permanently deleting its underlying record.",
    tags=["Client Requests"],
    operation_id="softDeleteClientRequest",
    response_description="Soft-deleted client request.",
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
    ]))],
)
async def soft_delete_client_request(
    request_id: str,
    payload: ClientRequestSoftDeletePayload,
    current_user=Depends(get_current_user),
):
    return await RequestManager.get_instance().soft_delete_request(
        request_id=request_id,
        payload=payload,
        current_user=current_user,
    )


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
