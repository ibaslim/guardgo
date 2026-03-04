from fastapi import APIRouter, HTTPException, Query, Request, Depends, UploadFile
from fastapi.responses import RedirectResponse

from configs.app_dependency import status_required, role_required, get_current_user
from orion.api.interactive.account_manager.account_manager import AccountManager
from orion.api.interactive.account_manager.models.platform_admin_model import (
    PlatformAdminCreateRequest,
    PlatformAdminUpdateRequest,
    PlatformAdminStatusReasonRequest,
)
from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.api.server.config_manager.config_controller import config_controller
from orion.api.server.config_manager.model.config_data import config_data
from orion.services.mongo_manager.shared_model.db_auth_models import UserStatus, user_role, PLATFORM_ASSIGNABLE_ROLES

admin_routes = APIRouter(
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))], tags=["Orion API"], )


@admin_routes.get("/admin/api/db_system_model/row-action")
async def block_row_action(name: str = Query(...)):
    if name == "delete":
        raise HTTPException(status_code=403, detail="Deletion of system settings is not allowed")
    return {"message": f"Action '{name}' is not restricted"}


@admin_routes.post("/admin/api/db_user_account/edit/{id}")
async def custom_edit_api(id: str, request: Request):
    await auth_manager.edit_userStatus_and_sendMail_from_admin(id, request)
    return RedirectResponse(url="/admin/db_user_account/list", status_code=303)


@admin_routes.post("/admin/api/db_user_account/edit/{id}/")
async def custom_edit_api_trailing(id: str, request: Request):
    await auth_manager.edit_userStatus_and_sendMail_from_admin(id, request)
    return RedirectResponse(url="/admin/db_user_account/list", status_code=303)


@admin_routes.post(
    "/api/public/update", summary="Update public configuration", dependencies=[Depends(
        role_required(
            [user_role.ADMIN])), ], )
async def update_public_config(param: config_data):
    return await config_controller.getInstance().update_public_config(param)


@admin_routes.post(
    "/api/upload/system", summary="Upload system logo", dependencies=[Depends(role_required([user_role.ADMIN]))], )
async def upload_system_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await config_controller.getInstance().uploadSystemResource(file, current_user)


@admin_routes.get(
    "/api/admin/platform-roles",
    summary="Get platform admin role options",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def get_platform_roles(_current_user=Depends(get_current_user)):
    labels = {
        user_role.OPS_ADMIN.value: "Ops Admin",
        user_role.SUPPORT_ADMIN.value: "Support Admin",
        user_role.COMPLIANCE_ADMIN.value: "Compliance Admin",
        user_role.READ_ONLY_ADMIN.value: "Read Only Admin",
    }
    return [
        {"value": role, "label": labels.get(role, role)}
        for role in sorted(PLATFORM_ASSIGNABLE_ROLES)
    ]


@admin_routes.get(
    "/api/admin/platform-users",
    summary="List platform admin users",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def list_platform_users(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().list_platform_admin_users(current_user)


@admin_routes.post(
    "/api/admin/platform-users",
    summary="Create platform admin user",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def create_platform_user(data: PlatformAdminCreateRequest, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().create_platform_admin_user(data, current_user)


@admin_routes.put(
    "/api/admin/platform-users/{user_id}",
    summary="Update platform admin user",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def update_platform_user(user_id: str, data: PlatformAdminUpdateRequest, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().update_platform_admin_user(user_id, data, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/resend-invite",
    summary="Resend platform admin invite",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def resend_platform_user_invite(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().resend_platform_admin_invite(user_id, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/delete",
    summary="Soft delete platform admin user",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def soft_delete_platform_user(
    user_id: str,
    data: PlatformAdminStatusReasonRequest,
    current_user=Depends(get_current_user),
):
    return await AccountManager.get_instance().soft_delete_platform_admin_user(user_id, data, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/restore",
    summary="Restore soft-deleted platform admin user",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def restore_platform_user(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().restore_platform_admin_user(user_id, current_user)


@admin_routes.delete(
    "/api/admin/platform-users/{user_id}/permanent",
    summary="Permanently delete soft-deleted platform admin user",
    dependencies=[Depends(role_required([user_role.SUPER_ADMIN]))], )
async def permanently_delete_platform_user(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().permanently_delete_platform_admin_user(user_id, current_user)
