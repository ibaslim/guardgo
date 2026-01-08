from fastapi import APIRouter
from fastapi import Depends, UploadFile
from configs.app_dependency import license_required, role_required, status_required, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.account_manager.models.user_meta_model import user_meta_model
from orion.api.interactive.account_manager.models.user_param_model import user_param_model
from orion.api.interactive.resource_manager.resource_manager import ResourceManager
from orion.api.interactive.tenant_manager.models.tenant_param_model import tenant_param_model
from orion.services.mongo_manager.shared_model.db_auth_models import user_role, UserStatus
from orion.services.mongo_manager.shared_model.db_tenant_model import TenantRequest
from orion.api.interactive.tenant_manager.tenant_manager import TenantManager
from orion.api.interactive.account_manager.models.user_model import user_model

tenant_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))], tags=["Orion API"], )


@tenant_routes.post(
    "/api/get/tenant",
    summary="Get tenant for current user",
    description="Retrieve tenant information associated with the current authenticated user.",
    tags=["Tenant"],
    operation_id="getTenantForUser",
    response_description="Tenant information for the current user.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.DEMO, user_role.ADMIN, user_role.MEMBER, user_role.ANALYST]))], )
async def get_tenant(current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().get_tenant(current_user)


@tenant_routes.post(
    "/api/update/tenants",
    summary="Update tenant",
    description="Update tenant configuration and metadata for the current user's tenant.",
    tags=["Tenant"],
    operation_id="updateTenant",
    response_description="Updated tenant information.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.MEMBER, user_role.ADMIN])),
        Depends(status_required([UserStatus.ACTIVE])), Depends(license_required("maintainer")), ], )
async def update_tenant(data: TenantRequest, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().update_tenant(data, current_user)


@tenant_routes.post(
    "/api/users",
    summary="Get all users for tenant",
    description="Retrieve all users associated with the current user's tenant.",
    tags=["Users", "Tenant"],
    operation_id="getAllUsersForTenant",
    response_description="List of users in the tenant.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.MEMBER, user_role.ADMIN]))], )
async def get_tenant_users(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().get_all_users(current_user)


@tenant_routes.post(
    "/api/tenants/get",
    summary="Get all tenants",
    description="Retrieve all tenant records available to the current user.",
    tags=["Tenant"],
    operation_id="getAllTenants",
    response_description="List of all tenants.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def get_all_tenants():
    return await TenantManager.get_instance().get_all_tenant()


@tenant_routes.post(
    "/api/update/user",
    summary="Update user",
    description="Update user profile and access details within the tenant.",
    tags=["Users"],
    operation_id="updateUser",
    response_description="Updated user information.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def update_user(user: tenant_param_model, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().update_user(user, current_user)


@tenant_routes.post(
    "/api/update/current/user",
    summary="Update user",
    description="Update user profile and access details within the tenant.",
    tags=["Users"],
    operation_id="updateUser",
    response_description="Updated user information.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER, user_role.ANALYST]))], )
async def update_user(user: user_meta_model, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().update_current_user(user, current_user)


@tenant_routes.delete(
    "/api/tenant/image",
    summary="Update user",
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def update_user(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_user_icon(current_user)


@tenant_routes.put(
    "/api/tenant/image",
    summary="Upload profile image",
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def upload_profile_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().uploadTenantImage(file, current_user)


@tenant_routes.delete(
    "/api/system/image",
    summary="Update system",
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def update_user(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_system_image(current_user)


@tenant_routes.put(
    "/api/system/image",
    summary="Upload system image",
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def upload_profile_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().update_system_image(file, current_user)


@tenant_routes.delete(
    "/api/user/image",
    summary="Update user",
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER, user_role.ANALYST]))], )
async def update_user(current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().delete_user_image(current_user)


@tenant_routes.put(
    "/api/user/image",
    summary="Upload profile image",
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER, user_role.ANALYST]))], )
async def upload_profile_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await ResourceManager.get_instance().update_user_image(file, current_user)


@tenant_routes.post(
    "/api/delete/user",
    summary="Update user",
    description="Update user profile and access details within the tenant.",
    tags=["Users"],
    operation_id="updateUser",
    response_description="Updated user information.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.ADMIN, user_role.MEMBER]))], )
async def delete_user(user: user_param_model, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().delete_user(user, current_user)


@tenant_routes.post(
    "/api/tenant/create/user",
    summary="Create tenant user",
    description="Create a new company user in the current tenant.",
    tags=["Users", "Tenant"],
    operation_id="createTenantUser",
    response_description="Created tenant user information.",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(role_required([user_role.MEMBER, user_role.ADMIN])),
        Depends(license_required("maintainer")), ], )
async def create_tenant_user(data: user_model, current_user=Depends(get_current_user)):
    return await TenantManager.get_instance().create_tenant_user(data, current_user)




@tenant_routes.post(
    "/api/get/tenant/node",
    status_code=200,
    include_in_schema=False,
    dependencies=[Depends(status_required([UserStatus.ACTIVE])), ], )
async def get_node(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().get_node(current_user)


