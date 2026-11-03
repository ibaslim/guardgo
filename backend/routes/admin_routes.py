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
    dependencies=[Depends(status_required([UserStatus.ACTIVE]))],
    tags=["Platform Administration"],
)


@admin_routes.get(
    "/admin/api/db_system_model/row-action",
    summary="Validate system setting action restriction",
    description=(
        "Internal administration endpoint that guards protected database system records against unauthorized actions.\n\n"
        "### Workflow\n"
        "- Checks the requested action name against restricted operations.\n"
        "- Disallows deletion of critical system configuration settings (`403 Forbidden`).\n\n"
        "### Input\n"
        "- **Query Parameter**:\n"
        "  - `name` *(string, required)*: The proposed database table row action.\n\n"
        "### Output\n"
        "- Status message confirming whether the action is permitted."
    ),
    response_description="Validation result message for the row action.",
    operation_id="blockSystemRowAction",
)
async def block_row_action(name: str = Query(..., description="Action name to evaluate")):
    if name == "delete":
        raise HTTPException(status_code=403, detail="Deletion of system settings is not allowed")
    return {"message": f"Action '{name}' is not restricted"}


@admin_routes.post(
    "/admin/api/db_user_account/edit/{id}",
    summary="Admin console user status update & email dispatch",
    description=(
        "Internal handler for the database administration view to modify user account status and send notification emails.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `id` *(string, required)*: User account identifier.\n"
        "- **Request Body / Form**: Form data processed by internal admin manager.\n\n"
        "### Output\n"
        "- `303 See Other` redirect to user account listing page."
    ),
    response_description="Redirects to the admin user list.",
    operation_id="adminEditUserAccountStatus",
)
async def custom_edit_api(id: str, request: Request):
    await auth_manager.edit_userStatus_and_sendMail_from_admin(id, request)
    return RedirectResponse(url="/admin/db_user_account/list", status_code=303)


@admin_routes.post(
    "/admin/api/db_user_account/edit/{id}/",
    summary="Admin console user status update (trailing slash alias)",
    description=(
        "Trailing-slash alias for `/admin/api/db_user_account/edit/{id}` to prevent route resolution mismatches in admin UI.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `id` *(string, required)*: User account identifier.\n\n"
        "### Output\n"
        "- `303 See Other` redirect."
    ),
    response_description="Redirects to the admin user list.",
    operation_id="adminEditUserAccountStatusTrailing",
)
async def custom_edit_api_trailing(id: str, request: Request):
    await auth_manager.edit_userStatus_and_sendMail_from_admin(id, request)
    return RedirectResponse(url="/admin/db_user_account/list", status_code=303)


@admin_routes.post(
    "/api/public/update",
    summary="Update public configuration settings",
    description=(
        "Update global system-wide configuration parameters including brand identity, contact info, and public feature toggles.\n\n"
        "### Access\n"
        "- **Role Required**: `admin` (Platform Super Admin).\n"
        "- **Status**: `ACTIVE`.\n\n"
        "### Input (`config_data`)\n"
        "- Key-value configuration dictionary specifying updated system parameters.\n\n"
        "### Output\n"
        "- The updated system configuration dictionary."
    ),
    response_description="Updated system configuration object.",
    operation_id="updatePublicConfig",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def update_public_config(param: config_data):
    return await config_controller.getInstance().update_public_config(param)


@admin_routes.post(
    "/api/upload/system",
    summary="Upload platform system logo",
    description=(
        "Upload and store a new branding logo image displayed across the GuardGo platform and transactional emails.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Multipart Form**:\n"
        "  - `file` *(UploadFile, required)*: Image binary (PNG, JPEG, WebP, SVG).\n\n"
        "### Output\n"
        "- File upload metadata including public image resource URL."
    ),
    response_description="Stored logo asset metadata.",
    operation_id="uploadSystemLogo",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def upload_system_image(file: UploadFile, current_user=Depends(get_current_user)):
    return await config_controller.getInstance().uploadSystemResource(file, current_user)


@admin_routes.get(
    "/api/admin/platform-roles",
    summary="Get assignable platform admin roles",
    description=(
        "List all platform administrative roles that can be assigned to platform personnel.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Output\n"
        "- Array of role objects with `value` and user-friendly `label` "
        "(e.g., Ops Admin, Support Admin, Compliance Admin, Read Only Admin)."
    ),
    response_description="List of assignable platform administrator roles.",
    operation_id="getPlatformRoles",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
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
    description=(
        "Retrieve all internal platform administrative users across all statuses (active, invited, suspended, deleted).\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Output\n"
        "- Array of user profiles detailing email, full name, role, account status, license grants, and invite state."
    ),
    response_description="List of platform administrative user accounts.",
    operation_id="listPlatformUsers",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def list_platform_users(current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().list_platform_admin_users(current_user)


@admin_routes.post(
    "/api/admin/platform-users",
    summary="Invite new platform admin user",
    description=(
        "Create and invite a new internal platform administrative team member.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input (`PlatformAdminCreateRequest`)\n"
        "- `email` *(email, required)*: Work email of the platform administrator.\n"
        "- `role` *(user_role, required)*: Assignable platform role (`ops_admin`, `support_admin`, `compliance_admin`, `read_only_admin`).\n\n"
        "### Output\n"
        "- Created user record with pending invitation token details."
    ),
    response_description="Created platform user record with invitation state.",
    operation_id="createPlatformUser",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def create_platform_user(data: PlatformAdminCreateRequest, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().create_platform_admin_user(data, current_user)


@admin_routes.put(
    "/api/admin/platform-users/{user_id}",
    summary="Update platform admin user details & permissions",
    description=(
        "Modify role, account status, reason for status modification, and license permissions for a platform user.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `user_id` *(string, required)*: Unique identifier of platform user.\n"
        "- **JSON Body (`PlatformAdminUpdateRequest`)**:\n"
        "  - `role` *(user_role, optional)*: Updated administrative role.\n"
        "  - `status` *(UserStatus, optional)*: Updated status (`active`, `pending`, `suspended`, `banned`).\n"
        "  - `status_reason` *(string, optional)*: Audit explanation for status change.\n"
        "  - `licenses` *(list of strings, optional)*: Module license grants.\n\n"
        "### Output\n"
        "- Updated platform administrator user record."
    ),
    response_description="Updated platform user profile.",
    operation_id="updatePlatformUser",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def update_platform_user(user_id: str, data: PlatformAdminUpdateRequest, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().update_platform_admin_user(user_id, data, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/resend-invite",
    summary="Resend invitation email to platform admin user",
    description=(
        "Generate a fresh invitation token and resend the onboarding email to a pending platform user.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `user_id` *(string, required)*: Platform user ID.\n\n"
        "### Output\n"
        "- Confirmation payload indicating fresh invite token generation and dispatch."
    ),
    response_description="Confirmation of resent invitation email.",
    operation_id="resendPlatformUserInvite",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def resend_platform_user_invite(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().resend_platform_admin_invite(user_id, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/delete",
    summary="Soft-delete platform admin user",
    description=(
        "Mark a platform administrative user as soft-deleted and disable access while retaining audit logs.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `user_id` *(string, required)*: Platform user ID.\n"
        "- **JSON Body (`PlatformAdminStatusReasonRequest`)**:\n"
        "  - `reason` *(string, required)*: Explanation for deactivating/soft-deleting the user.\n\n"
        "### Output\n"
        "- Deactivated user record showing deleted state."
    ),
    response_description="Confirmation of soft-deleted user account.",
    operation_id="softDeletePlatformUser",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def soft_delete_platform_user(
    user_id: str,
    data: PlatformAdminStatusReasonRequest,
    current_user=Depends(get_current_user),
):
    return await AccountManager.get_instance().soft_delete_platform_admin_user(user_id, data, current_user)


@admin_routes.post(
    "/api/admin/platform-users/{user_id}/restore",
    summary="Restore soft-deleted platform admin user",
    description=(
        "Reactivate a previously soft-deleted platform administrative user.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `user_id` *(string, required)*: Platform user ID.\n\n"
        "### Output\n"
        "- Restored user record with active status."
    ),
    response_description="Restored user account details.",
    operation_id="restorePlatformUser",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def restore_platform_user(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().restore_platform_admin_user(user_id, current_user)


@admin_routes.delete(
    "/api/admin/platform-users/{user_id}/permanent",
    summary="Permanently purge platform admin user",
    description=(
        "Permanently delete a soft-deleted platform user record and associated credentials from the database.\n\n"
        "### Access\n"
        "- **Role Required**: `admin`.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `user_id` *(string, required)*: Platform user ID.\n\n"
        "### Output\n"
        "- `{\"detail\": \"User permanently deleted\"}`"
    ),
    response_description="Confirmation of permanent user deletion.",
    operation_id="permanentlyDeletePlatformUser",
    dependencies=[Depends(role_required([user_role.ADMIN]))],
)
async def permanently_delete_platform_user(user_id: str, current_user=Depends(get_current_user)):
    return await AccountManager.get_instance().permanently_delete_platform_admin_user(user_id, current_user)
