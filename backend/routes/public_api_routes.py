from fastapi import APIRouter, Depends
from fastapi import Request, HTTPException
from orion.api.interactive.resource_manager.resource_manager import ResourceManager
from orion.api.server.config_manager.config_controller import config_controller
from configs.metadata_constants import (
    COUNTRY_OPTIONS,
    CANADIAN_PROVINCE_OPTIONS,
    CANADIAN_CITIES_BY_PROVINCE_OPTIONS,
    BILLING_REGION_CITY_OPTIONS,
    IDENTITY_DOCUMENT_TYPES,
    SECURITY_LICENSE_TYPE_OPTIONS,
    TRAINING_CERTIFICATE_TYPE_OPTIONS,
    POLICE_CLEARANCE_AUTHORITY_TYPE_OPTIONS,
    TRAINING_ISSUER_OPTIONS_MAP,
    CLIENT_SITE_TYPE_OPTIONS,
    CLIENT_GUARD_TYPE_OPTIONS,
    CLIENT_TYPE_OPTIONS,
)
from orion.services.mongo_manager.shared_model.db_auth_models import PLATFORM_ADMIN_ROLES, TENANT_ADMIN_ROLES, user_role

public_routes = APIRouter(tags=["Public & System Metadata"])


def cookie_required(request: Request):
    if not request.cookies.get("access_token"):
        raise HTTPException(status_code=401, detail="Missing auth cookie")


@public_routes.get(
    "/api/public",
    dependencies=[],
    summary="Get public system configuration",
    description=(
        "Retrieve public platform branding, system identity, contact details, and feature toggles.\n\n"
        "### Workflow\n"
        "- Serves initialization configuration needed by client frontends prior to authentication.\n"
        "- Returns application name, logo URLs, and support coordinates.\n\n"
        "### Input\n"
        "- None (public endpoint).\n\n"
        "### Output\n"
        "- System configuration dictionary with public properties."
    ),
    tags=["Public & System Metadata"],
    operation_id="getPublicConfig",
    response_description="Public configuration values used at frontend startup.",
)
async def get_public_config():
    return await config_controller.getInstance().get_system_info()


@public_routes.get(
    "/api/public/guard-metadata",
    dependencies=[],
    summary="Get guard document dropdown metadata",
    description=(
        "Retrieve standard options and enums required for security guard profile setup and document uploads.\n\n"
        "### Content Provided\n"
        "- List of countries and Canadian provinces.\n"
        "- Major Canadian cities grouped by province.\n"
        "- Accepted government identity document types (Passport, Driver's License, PR Card).\n"
        "- Security license classification codes.\n"
        "- Training certification types and recognized issuing authorities.\n"
        "- Police clearance authority options.\n\n"
        "### Input\n"
        "- None.\n\n"
        "### Output\n"
        "- Dictionary mapping metadata categories to structured choice lists."
    ),
    tags=["Public & System Metadata"],
    operation_id="getGuardMetadata",
    response_description="Guard document dropdown options and metadata dictionaries.",
)
async def get_guard_metadata():
    return {
        "countries": COUNTRY_OPTIONS,
        "canadianProvinces": CANADIAN_PROVINCE_OPTIONS,
        "canadianCitiesByProvince": CANADIAN_CITIES_BY_PROVINCE_OPTIONS,
        "identityDocumentTypes": IDENTITY_DOCUMENT_TYPES,
        "securityLicenseTypes": SECURITY_LICENSE_TYPE_OPTIONS,
        "trainingCertificateTypes": TRAINING_CERTIFICATE_TYPE_OPTIONS,
        "trainingIssuerOptionsMap": TRAINING_ISSUER_OPTIONS_MAP,
        "policeClearanceAuthorityTypes": POLICE_CLEARANCE_AUTHORITY_TYPE_OPTIONS,
        "guardTypeOptions": CLIENT_GUARD_TYPE_OPTIONS,
    }


@public_routes.get(
    "/api/public/client-metadata",
    dependencies=[],
    summary="Get client profile dropdown metadata",
    description=(
        "Retrieve standard metadata and choice options for client profile setup and security request forms.\n\n"
        "### Content Provided\n"
        "- Countries, Canadian provinces, and supported cities.\n"
        "- Billing region choices for pricing calculation.\n"
        "- Site categories (e.g. Commercial, Residential, Construction, Event, Retail, Industrial).\n"
        "- Guard service types (e.g. Static Guard, Concierge, Patrolling, Armed/Cash-in-Transit).\n"
        "- Client organization types (Individual vs Corporate).\n\n"
        "### Input\n"
        "- None.\n\n"
        "### Output\n"
        "- Dictionary containing client option lists for form rendering."
    ),
    tags=["Public & System Metadata"],
    operation_id="getClientMetadata",
    response_description="Client profile metadata and form option dictionaries.",
)
async def get_client_metadata():
    return {
        "countries": COUNTRY_OPTIONS,
        "canadianProvinces": CANADIAN_PROVINCE_OPTIONS,
        "canadianCitiesByProvince": CANADIAN_CITIES_BY_PROVINCE_OPTIONS,
        "billingLocationOptions": BILLING_REGION_CITY_OPTIONS,
        "siteTypeOptions": CLIENT_SITE_TYPE_OPTIONS,
        "guardTypeOptions": CLIENT_GUARD_TYPE_OPTIONS,
        "clientTypeOptions": CLIENT_TYPE_OPTIONS,
    }


@public_routes.get(
    "/api/public/role-metadata",
    dependencies=[],
    summary="Get role permission group definitions",
    description=(
        "Retrieve system role categories used by frontend route guards and permission gates.\n\n"
        "### Content Provided\n"
        "- `platformRoles`: Super admin, ops admin, support admin, compliance admin, read-only admin.\n"
        "- `tenantSettingsRoles`: Tenant administrators permitted to modify organization settings.\n"
        "- `tenantManagementRoles`: Roles permitted to manage tenant operations.\n"
        "- `platformUserManagementRoles`: Roles permitted to invite and modify platform staff.\n\n"
        "### Input\n"
        "- None.\n\n"
        "### Output\n"
        "- Mapping of role permission groups to lists of role codes."
    ),
    tags=["Public & System Metadata"],
    operation_id="getRoleMetadata",
    response_description="Platform and tenant role groups for UI guards.",
)
async def get_role_metadata():
    management_roles = sorted([user_role.ADMIN.value, user_role.COMPLIANCE_ADMIN.value])
    platform_user_management_roles = [user_role.ADMIN.value]
    return {
        "platformRoles": sorted(list(PLATFORM_ADMIN_ROLES)),
        "tenantSettingsRoles": sorted(list(TENANT_ADMIN_ROLES)),
        "tenantManagementRoles": management_roles,
        "platformUserManagementRoles": platform_user_management_roles,
    }


@public_routes.get(
    "/api/s/static/tenant/{id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Get tenant profile photo or logo",
    description=(
        "Stream stored tenant profile image, organization logo, or photo asset.\n\n"
        "### Access\n"
        "- Requires valid session cookie (`access_token`).\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `id` *(string, required)*: Tenant UUID or image resource identifier.\n\n"
        "### Output\n"
        "- Binary image stream (JPEG, PNG, WebP) with appropriate `Content-Type` header."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantImageResource",
    response_description="Binary image file response.",
)
async def get_tenant_resource(id: str):
    return await ResourceManager.get_instance().get_tenant_image(id)


@public_routes.get(
    "/api/s/static/user/{id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Get user profile avatar image",
    description=(
        "Stream user profile avatar or headshot graphic.\n\n"
        "### Access\n"
        "- Requires valid session cookie (`access_token`).\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `id` *(string, required)*: User ID or avatar asset identifier.\n\n"
        "### Output\n"
        "- Binary image stream with appropriate `Content-Type` header."
    ),
    tags=["Public & System Metadata"],
    operation_id="getUserAvatarResource",
    response_description="Binary image file response.",
)
async def get_user_resource(id: str):
    return await ResourceManager.get_instance().get_user_image(id)


@public_routes.get(
    "/api/s/static/system/{id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Get system brand asset image",
    description=(
        "Stream platform brand logos, icons, and system graphics by asset ID.\n\n"
        "### Access\n"
        "- Requires valid session cookie (`access_token`).\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `id` *(string, required)*: System asset identifier.\n\n"
        "### Output\n"
        "- Binary image stream."
    ),
    tags=["Public & System Metadata"],
    operation_id="getSystemImageResource",
    response_description="Binary image file response.",
)
async def get_system_resource(id: str):
    return await ResourceManager.get_instance().get_system_image(id)


@public_routes.get(
    "/api/tenant/files/identity/{file_id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Download tenant government identity document",
    description=(
        "Stream encrypted government identification document (passport, driver license) for authorized profile inspection.\n\n"
        "### Access\n"
        "- Verifies ownership or compliance admin privilege via session cookie.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `file_id` *(string, required)*: Stored identity document ID.\n\n"
        "### Output\n"
        "- Binary document stream (PDF, JPEG, PNG)."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantIdentityDocument",
    response_description="Identity document binary stream.",
)
async def get_tenant_identity_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_identity_document(file_id, current_user)


@public_routes.get(
    "/api/tenant/files/security-license/{file_id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Download security license document",
    description=(
        "Stream verified provincial security guard license document.\n\n"
        "### Access\n"
        "- Verifies ownership or compliance admin privilege via session cookie.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `file_id` *(string, required)*: Security license document ID.\n\n"
        "### Output\n"
        "- Binary document stream (PDF, JPEG, PNG)."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantSecurityLicenseDocument",
    response_description="Security license document binary stream.",
)
async def get_tenant_security_license_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_security_license_document(file_id, current_user)


@public_routes.get(
    "/api/tenant/files/police-clearance/{file_id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Download police clearance background check document",
    description=(
        "Stream official police clearance or criminal background check record for a guard tenant.\n\n"
        "### Access\n"
        "- Verifies ownership or compliance admin privilege via session cookie.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `file_id` *(string, required)*: Police clearance document ID.\n\n"
        "### Output\n"
        "- Binary document stream (PDF, JPEG, PNG)."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantPoliceClearanceDocument",
    response_description="Police clearance document binary stream.",
)
async def get_tenant_police_clearance_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_police_clearance_document(file_id, current_user)


@public_routes.get(
    "/api/tenant/files/training-certificate/{file_id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Download training certification document",
    description=(
        "Stream specialized security or emergency training certificate (First Aid, CPR, Baton, etc.).\n\n"
        "### Access\n"
        "- Verifies ownership or compliance admin privilege via session cookie.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `file_id` *(string, required)*: Training certificate document ID.\n\n"
        "### Output\n"
        "- Binary document stream (PDF, JPEG, PNG)."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantTrainingCertificateDocument",
    response_description="Training certificate binary stream.",
)
async def get_tenant_training_certificate(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_training_certificate(file_id, current_user)


@public_routes.get(
    "/api/tenant/files/insurance/{file_id}",
    include_in_schema=True,
    dependencies=[Depends(cookie_required)],
    summary="Download commercial general liability insurance document",
    description=(
        "Stream commercial general liability insurance certificate for a service provider tenant.\n\n"
        "### Access\n"
        "- Verifies ownership or compliance admin privilege via session cookie.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `file_id` *(string, required)*: Insurance document ID.\n\n"
        "### Output\n"
        "- Binary document stream (PDF, JPEG, PNG)."
    ),
    tags=["Public & System Metadata"],
    operation_id="getTenantInsuranceDocument",
    response_description="Insurance certificate binary stream.",
)
async def get_tenant_insurance_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_insurance_document(file_id, current_user)


@public_routes.get(
    "/robots.txt",
    include_in_schema=False,
    summary="Get robots.txt",
    description="Serves robots exclusion standard file.",
)
async def robots_txt():
    return await ResourceManager.get_instance().get_robots_txt()
