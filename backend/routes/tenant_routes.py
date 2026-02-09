from fastapi import APIRouter, HTTPException
from fastapi import Depends, UploadFile
from configs.app_dependency import license_required, role_required, status_required, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.account_manager.models.user_meta_model import user_meta_model
from orion.api.interactive.account_manager.models.user_param_model import user_param_model
from orion.api.interactive.resource_manager.resource_manager import ResourceManager
from orion.api.interactive.tenant_manager.models.tenant_param_model import tenant_param_model
from orion.services.mongo_manager.shared_model.db_auth_models import user_role, UserStatus
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantRequest, db_tenant_model, TenantPayload
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.api.interactive.account_manager.models.user_model import user_model
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
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN, user_role.CLIENT_ADMIN, user_role.SP_ADMIN]))], )
async def get_tenant(current_user=Depends(get_current_user)):
    manager = TenantManager.get_instance()
    tenant = await manager._engine.find_one(db_tenant_model, db_tenant_model.id == ObjectId(current_user.tenant_uuid))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "id": str(tenant.id),
        "tenant_type": tenant.tenant_type,
        "profile": tenant.profile or {},
        "subscription": tenant.subscription,
        "verified": tenant.verified,
        "user_quota": tenant.user_quota,
        "status": tenant.status,
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
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN, user_role.GUARD_ADMIN]))], )
async def upload_tenant_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().uploadTenantImage(file, current_user)


@tenant_routes.delete(
    "/api/tenant/image",
    summary="Delete tenant image",
    description="Delete tenant profile image.",
    tags=["Tenant"],
    operation_id="deleteTenantImage",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.CLIENT_ADMIN, user_role.GUARD_ADMIN]))], )
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
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
async def upload_tenant_security_license_document(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().upload_tenant_security_license_document(file, current_user)


@tenant_routes.delete(
    "/api/tenant/files/security-license/{file_id}",
    summary="Delete tenant security license document",
    description="Delete a security license document for the current tenant.",
    tags=["Tenant"],
    operation_id="deleteTenantSecurityLicenseDocument",
    status_code=200,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.GUARD_ADMIN]))], )
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


