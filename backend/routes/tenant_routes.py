
from fastapi import APIRouter, HTTPException
from fastapi import Depends, UploadFile, Path
from configs.app_dependency import license_required, role_required, status_required, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.account_manager.models.user_meta_model import user_meta_model
from orion.api.interactive.account_manager.models.user_param_model import user_param_model
from orion.api.interactive.resource_manager.resource_manager import ResourceManager
from orion.api.interactive.tenant_manager.models.tenant_param_model import tenant_param_model
from orion.api.interactive.tenant_manager.models.service_provider_guard_models import (
    ServiceProviderGuardInviteRequest,
    ServiceProviderGuardOperationalCoveragePayload,
    ServiceProviderGuardStatusRequestPayload,
    GuardStatusRequestDecisionPayload,
    GuardServiceProviderLinkPayload,
    GuardServiceProviderUnlinkPayload,
)
from orion.services.mongo_manager.shared_model.db_auth_models import PLATFORM_ADMIN_ROLES, normalize_role_value, user_role, UserStatus
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantRequest, db_tenant_model, TenantPayload, TenantStatus
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.api.interactive.account_manager.models.user_model import user_model
from orion.api.interactive.activity_manager.activity_manager import ActivityManager
from bson import ObjectId

tenant_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))], tags=["Orion API"], )


# ============================================================================
# TENANT ENDPOINTS (RESTful)
# ============================================================================

@tenant_routes.get(
    "/api/tenant",
    summary="Get current tenant",
    description="Retrieve the complete tenant object including profile and base fields.",
    tags=["Tenant"],
    operation_id="getTenant",
    response_description="Complete tenant data.",
    status_code=200,
    dependencies=[Depends(role_required([
        user_role.ADMIN,
        user_role.OPS_ADMIN,
        user_role.SUPPORT_ADMIN,
        user_role.COMPLIANCE_ADMIN,
        user_role.READ_ONLY_ADMIN,
        user_role.GUARD_ADMIN,
        user_role.CLIENT_ADMIN,
        user_role.SP_ADMIN,
    ]))], )
async def get_tenant(current_user=Depends(get_current_user)):
    manager = TenantManager.get_instance()
    role_value = normalize_role_value(getattr(current_user, "role", ""))
    tenant_uuid = str(getattr(current_user, "tenant_uuid", "") or "").strip()

    if not tenant_uuid and role_value in PLATFORM_ADMIN_ROLES:
        return {
            "id": "",
            "tenant_type": None,
            "profile": {},
            "ownership_type": None,
            "service_provider_tenant_id": None,
            "service_provider": None,
            "subscription": False,
            "verified": False,
            "user_quota": 0,
            "status": "",
            "approvals_required": 0,
            "approvals_done": 0,
            "approvals_remaining": 0,
            "licenses": [],
            "iocs": [],
            "created_at": None,
            "updated_at": None,
            "verified_date": None,
        }

    try:
        tenant_object_id = ObjectId(tenant_uuid)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tenant association")

    tenant = await manager._engine.find_one(db_tenant_model, db_tenant_model.id == tenant_object_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    provider_summary = await manager._provider_summary(getattr(tenant, "service_provider_tenant_id", None))
    return {
        "id": str(tenant.id),
        "tenant_type": tenant.tenant_type,
        "profile": tenant.profile or {},
        "ownership_type": getattr(tenant, "ownership_type", None),
        "service_provider_tenant_id": getattr(tenant, "service_provider_tenant_id", None),
        "service_provider": provider_summary,
        "subscription": tenant.subscription,
        "verified": tenant.verified,
        "user_quota": tenant.user_quota,
        "status": TenantManager.get_instance()._normalized_status_value(tenant.status),
        "approvals_required": int(getattr(tenant, "approvals_required", 2) or 2),
        "approvals_done": len(list(dict.fromkeys(getattr(tenant, "approval_actors", []) or []))),
        "approvals_remaining": max(int(getattr(tenant, "approvals_required", 2) or 2) - len(list(dict.fromkeys(getattr(tenant, "approval_actors", []) or []))), 0),
        "licenses": tenant.licenses,
        "iocs": tenant.iocs,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
        "verified_date": tenant.verified_date,
    }


@tenant_routes.post(
    "/api/tenant",
    summary="Create new tenant",
    description="Create a new tenant with complete data (profile + base fields).",
    tags=["Tenant"],
    operation_id="createTenant",
    response_description="Created tenant data.",
    status_code=201,
    dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def create_tenant(data: TenantPayload, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().upsert_tenant(data, current_user, is_update=False)


@tenant_routes.put(
    "/api/tenant",
    summary="Update current tenant",
    description="Update the complete tenant object (profile + base fields).",
    tags=["Tenant"],
    operation_id="updateTenant",
    response_description="Updated tenant data.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN, user_role.CLIENT_ADMIN, user_role.SP_ADMIN]))], )
async def update_tenant(data: TenantPayload, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().upsert_tenant(data, current_user, is_update=True)


@tenant_routes.get(
    "/api/tenants",
    summary="Get all tenants",
    description="Retrieve all tenant records (admin only).",
    tags=["Tenant"],
    operation_id="getAllTenants",
    response_description="List of all tenants.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def get_all_tenants():
    return await TenantManager.get_instance().get_all_tenant()


@tenant_routes.get(
    "/api/tenants/datatable",
    summary="Get tenants datatable",
    description="Get tenants with pagination, filters, keyword search, and sorting.",
    tags=["Tenant"],
    operation_id="getTenantsDatatable",
    response_description="Paginated tenant rows.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def get_tenants_datatable(
        page: int = 1,
        rows: int = 10,
        tenant_type: str | None = None,
        tenant_status: str | None = None,
        keyword: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"):
    return await TenantManager.get_instance().get_tenants_datatable(
        page=page,
        rows=rows,
        tenant_type=tenant_type,
        tenant_status=tenant_status,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@tenant_routes.get(
    "/api/tenants/{tenant_id}",
    summary="Get tenant by id",
    description="Retrieve the complete tenant object by tenant id (admin only).",
    tags=["Tenant"],
    operation_id="getTenantById",
    response_description="Complete tenant data.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def get_tenant_by_id(
    tenant_id: str = Path(..., description="Tenant ObjectId as string")
):
    return await TenantManager.get_instance().get_tenant_by_id(tenant_id)


@tenant_routes.patch(
    "/api/tenants/{tenant_id}/approve",
    summary="Approve tenant activation",
    description="Record an approval. Tenant activates only after required approvals are reached.",
    tags=["Tenant"],
    operation_id="approveTenant",
    response_description="Updated tenant status.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def approve_tenant(tenant_id: str, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().approve_tenant_activation(tenant_id, current_user=current_user)


@tenant_routes.patch(
    "/api/tenants/{tenant_id}/verify",
    summary="Verify tenant (legacy alias)",
    description="Legacy alias for approve tenant activation.",
    tags=["Tenant"],
    operation_id="verifyTenant",
    response_description="Updated tenant status.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def verify_tenant(tenant_id: str, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().approve_tenant_activation(tenant_id, current_user=current_user)


@tenant_routes.patch(
    "/api/tenants/{tenant_id}/deactivate",
    summary="Deactivate tenant",
    description="Set tenant status to inactive.",
    tags=["Tenant"],
    operation_id="deactivateTenant",
    response_description="Updated tenant status.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def deactivate_tenant(tenant_id: str, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().set_tenant_status(tenant_id, TenantStatus.INACTIVE, current_user=current_user)


@tenant_routes.patch(
    "/api/tenants/{tenant_id}/ban",
    summary="Ban tenant",
    description="Set tenant status to banned.",
    tags=["Tenant"],
    operation_id="banTenant",
    response_description="Updated tenant status.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def ban_tenant(tenant_id: str, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().set_tenant_status(tenant_id, TenantStatus.BANNED, current_user=current_user)


@tenant_routes.get(
    "/api/activity",
    summary="Get activity logs",
    description="Retrieve activity logs with module/entity filters.",
    tags=["Activity"],
    operation_id="getActivityLogs",
    response_description="Paginated activity logs.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.COMPLIANCE_ADMIN]))], )
async def get_activity_logs(
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    actor_username: str | None = None,
    page: int = 1,
    rows: int = 20,
):
    return await ActivityManager.get_instance().list_events(
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_username=actor_username,
        page=page,
        rows=rows,
    )


# ============================================================================
# USER ENDPOINTS (RESTful)
# ============================================================================

@tenant_routes.get(
    "/api/users",
    summary="Get all users in tenant",
    description="Retrieve all users associated with the current tenant.",
    tags=["Users"],
    operation_id="getUsers",
    response_description="List of users in the tenant.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.CLIENT_ADMIN, user_role.ADMIN]))], )
async def get_users(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().get_all_users(current_user)


@tenant_routes.post(
    "/api/users",
    summary="Create user in tenant",
    description="Create a new user in the current tenant.",
    tags=["Users"],
    operation_id="createUser",
    response_description="Created user information.",
    status_code=201,
    dependencies=[Depends(role_required([user_role.CLIENT_ADMIN, user_role.ADMIN])),
        Depends(license_required("maintainer")), ], )
async def create_user(data: user_model, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().create_tenant_user(data, current_user)


@tenant_routes.put(
    "/api/users/{user_id}",
    summary="Update user",
    description="Update specific user by ID.",
    tags=["Users"],
    operation_id="updateUser",
    response_description="Updated user information.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN]))], )
async def update_user_by_id(user_id: str, user: tenant_param_model, current_user=Depends(get_current_user)):
    user.user_id = user_id
    return await AccountManager.get_instance().update_user(user, current_user)


@tenant_routes.delete(
    "/api/users/{user_id}",
    summary="Delete user",
    description="Delete specific user by ID.",
    tags=["Users"],
    operation_id="deleteUser",
    response_description="Deletion confirmation.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN]))], )
async def delete_user_by_id(user_id: str, current_user=Depends(get_current_user)):
    user_param = user_param_model(user_id=user_id)
    return await AccountManager.get_instance().delete_user(user_param, current_user)


# ============================================================================
# CURRENT USER ENDPOINTS (RESTful)
# ============================================================================

@tenant_routes.get(
    "/api/me",
    summary="Get current user info",
    description="Get current authenticated user information with tenant details.",
    tags=["User Profile"],
    operation_id="getCurrentUser",
    response_description="Current user information.",
    status_code=200, )
async def get_current_user_info(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().get_node(current_user)


@tenant_routes.put(
    "/api/me",
    summary="Update current user",
    description="Update current authenticated user profile.",
    tags=["User Profile"],
    operation_id="updateCurrentUser",
    response_description="Updated user information.",
    status_code=200, )
async def update_current_user(user: user_meta_model, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().update_current_user(user, current_user)


# ============================================================================
# IMAGE UPLOAD ENDPOINTS
# ============================================================================

@tenant_routes.put(
    "/api/tenant/image",
    summary="Upload tenant image",
    description="Upload or update tenant profile image.",
    tags=["Tenant"],
    operation_id="uploadTenantImage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN, user_role.GUARD_ADMIN, user_role.SP_ADMIN]))], )
async def upload_tenant_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().uploadTenantImage(file, current_user)


@tenant_routes.delete(
    "/api/tenant/image",
    summary="Delete tenant image",
    description="Delete tenant profile image.",
    tags=["Tenant"],
    operation_id="deleteTenantImage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN, user_role.GUARD_ADMIN, user_role.SP_ADMIN]))], )
async def delete_tenant_image(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_image(current_user)


# ============================================================================
# IDENTITY DOCUMENT UPLOAD ENDPOINTS
# ============================================================================

@tenant_routes.post(
    "/api/tenant/files/identity",
    summary="Upload tenant identity document",
    description="Upload identity documents for the current tenant profile.",
    tags=["Tenant"],
    operation_id="uploadTenantIdentityDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def upload_tenant_identity_document(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_identity_document(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/identity/{file_id}",
    summary="Delete tenant identity document",
    description="Delete an identity document for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantIdentityDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def delete_tenant_identity_document(file_id: str, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_identity_document(file_id, current_user)


@tenant_routes.post(
    "/api/tenant/files/security-license",
    summary="Upload tenant security license document",
    description="Upload security license documents for the current tenant profile.",
    tags=["Tenant"],
    operation_id="uploadTenantSecurityLicenseDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN, user_role.SP_ADMIN]))], )
async def upload_tenant_security_license_document(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_security_license_document(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/security-license/{file_id}",
    summary="Delete tenant security license document",
    description="Delete a security license document for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantSecurityLicenseDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN, user_role.SP_ADMIN]))], )
async def delete_tenant_security_license_document(file_id: str, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_security_license_document(file_id, current_user)


@tenant_routes.post(
    "/api/tenant/files/police-clearance",
    summary="Upload tenant police clearance document",
    description="Upload police clearance documents for the current tenant profile.",
    tags=["Tenant"],
    operation_id="uploadTenantPoliceClearanceDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def upload_tenant_police_clearance_document(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_police_clearance_document(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/police-clearance/{file_id}",
    summary="Delete tenant police clearance document",
    description="Delete a police clearance document for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantPoliceClearanceDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def delete_tenant_police_clearance_document(file_id: str, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_police_clearance_document(file_id, current_user)


@tenant_routes.post(
    "/api/tenant/files/training-certificate",
    summary="Upload tenant training certificate",
    description="Upload training certificates for the current tenant profile.",
    tags=["Tenant"],
    operation_id="uploadTenantTrainingCertificate",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def upload_tenant_training_certificate(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_training_certificate(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/training-certificate/{file_id}",
    summary="Delete tenant training certificate",
    description="Delete a training certificate for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantTrainingCertificate",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def delete_tenant_training_certificate(file_id: str, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_training_certificate(file_id, current_user)


@tenant_routes.post(
    "/api/tenant/files/insurance",
    summary="Upload tenant insurance document",
    description="Upload insurance documents for the current tenant profile.",
    tags=["Tenant"],
    operation_id="uploadTenantInsuranceDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.SP_ADMIN]))], )
async def upload_tenant_insurance_document(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_insurance_document(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/insurance/{file_id}",
    summary="Delete tenant insurance document",
    description="Delete an insurance document for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantInsuranceDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.SP_ADMIN]))], )
async def delete_tenant_insurance_document(file_id: str, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_tenant_insurance_document(file_id, current_user)


@tenant_routes.put(
    "/api/me/image",
    summary="Upload user profile image",
    description="Upload or update current user profile image.",
    tags=["User Profile"],
    operation_id="uploadUserImage",
    status_code=200, )
async def upload_user_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().update_user_image(file, current_user)


@tenant_routes.delete(
    "/api/me/image",
    summary="Delete user profile image",
    description="Delete current user profile image.",
    tags=["User Profile"],
    operation_id="deleteUserImage",
    status_code=200, )
async def delete_user_image(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_user_image(current_user)


@tenant_routes.put(
    "/api/system/image",
    summary="Upload system image",
    description="Upload system-level image (admin only).",
    tags=["System"],
    operation_id="uploadSystemImage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def upload_system_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().update_system_image(file, current_user)


@tenant_routes.delete(
    "/api/system/image",
    summary="Delete system image",
    description="Delete system-level image (admin only).",
    tags=["System"],
    operation_id="deleteSystemImage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def delete_system_image(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_system_image(current_user)


@tenant_routes.post(
    "/api/sp/guards/invite",
    summary="Invite guard under service provider",
    status_code=201,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def invite_guard_for_service_provider(
    data: ServiceProviderGuardInviteRequest,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().invite_guard_for_service_provider(data, current_user)


@tenant_routes.get(
    "/api/sp/guards",
    summary="List guards owned by service provider",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def list_service_provider_guards(
    page: int = 1,
    rows: int = 20,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().list_service_provider_guards(current_user, page=page, rows=rows)


@tenant_routes.get(
    "/api/sp/guards/{guard_tenant_id}",
    summary="Get service provider guard details",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def get_service_provider_guard_details(
    guard_tenant_id: str,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().get_service_provider_guard(guard_tenant_id, current_user)


@tenant_routes.put(
    "/api/sp/guards/{guard_tenant_id}/operational-coverage",
    summary="Update managed guard operational coverage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def update_service_provider_guard_operational_coverage(
    guard_tenant_id: str,
    payload: ServiceProviderGuardOperationalCoveragePayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().update_service_provider_guard_operational_coverage(
        guard_tenant_id,
        payload,
        current_user,
    )


@tenant_routes.delete(
    "/api/sp/guards/pending/{guard_tenant_id}",
    summary="Delete expired pending guard invite",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def delete_expired_pending_guard_invite(
    guard_tenant_id: str,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().delete_expired_pending_guard_invite(guard_tenant_id, current_user)


@tenant_routes.post(
    "/api/sp/guards/{guard_tenant_id}/status-request",
    summary="Request guard status change",
    description="For action='deactivate', request body must include a non-empty reason. For action='activate', reason is optional.",
    status_code=200,
    dependencies=[Depends(role_required([user_role.SP_ADMIN]))],
)
async def request_guard_status_change(
    guard_tenant_id: str,
    payload: ServiceProviderGuardStatusRequestPayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().request_guard_status_change(guard_tenant_id, payload, current_user)


@tenant_routes.get(
    "/api/guard-status-requests",
    summary="List guard status change requests",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def list_guard_status_requests(page: int = 1, rows: int = 20):
    return await TenantManager.get_instance().list_guard_status_requests(page=page, rows=rows)


@tenant_routes.post(
    "/api/guard-status-requests/{request_id}/approve",
    summary="Approve guard status change request",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def approve_guard_status_request(
    request_id: str,
    payload: GuardStatusRequestDecisionPayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().approve_guard_status_request(request_id, payload, current_user)


@tenant_routes.post(
    "/api/guard-status-requests/{request_id}/reject",
    summary="Reject guard status change request",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def reject_guard_status_request(
    request_id: str,
    payload: GuardStatusRequestDecisionPayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().reject_guard_status_request(request_id, payload, current_user)


@tenant_routes.post(
    "/api/guards/{guard_tenant_id}/link-service-provider",
    summary="Link guard to service provider",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def link_guard_to_service_provider(
    guard_tenant_id: str,
    payload: GuardServiceProviderLinkPayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().link_guard_to_service_provider(guard_tenant_id, payload, current_user)


@tenant_routes.post(
    "/api/guards/{guard_tenant_id}/unlink-service-provider",
    summary="Unlink guard from service provider",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def unlink_guard_from_service_provider(
    guard_tenant_id: str,
    payload: GuardServiceProviderUnlinkPayload,
    current_user=Depends(get_current_user),
):
    return await TenantManager.get_instance().unlink_guard_from_service_provider(guard_tenant_id, payload, current_user)
