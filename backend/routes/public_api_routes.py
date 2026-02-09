from fastapi import APIRouter, Depends
from fastapi import Request, HTTPException
from orion.api.interactive.resource_manager.resource_manager import ResourceManager
from orion.api.server.config_manager.config_controller import config_controller
from configs.metadata_constants import (
    COUNTRY_OPTIONS,
    CANADIAN_PROVINCE_OPTIONS,
    IDENTITY_DOCUMENT_TYPES,
    SECURITY_LICENSE_TYPE_OPTIONS,
    TRAINING_CERTIFICATE_TYPE_OPTIONS,
    POLICE_CLEARANCE_AUTHORITY_TYPE_OPTIONS,
    TRAINING_ISSUER_OPTIONS_MAP,
)

public_routes = APIRouter(tags=["Public"])


def cookie_required(request: Request):
    if not request.cookies.get("access_token"):
        raise HTTPException(status_code=401, detail="Missing auth cookie")


@public_routes.get(
    "/api/public",
    dependencies=[],
    summary="Get public configuration",
    description="Get public configuration values used for frontend initialization.",
    tags=["Public", "Config"],
    operation_id="getPublicConfig",
    response_description="Public configuration values used at frontend startup.", )
async def get_public_config():
    return await config_controller.getInstance().get_system_info()


@public_routes.get(
    "/api/public/guard-metadata",
    dependencies=[],
    summary="Get guard metadata options",
    description="Get guard document enums and option labels for UI dropdowns.",
    tags=["Public", "Config"],
    operation_id="getGuardMetadata",
    response_description="Guard document metadata.")
async def get_guard_metadata():
    return {
        "countries": COUNTRY_OPTIONS,
        "canadianProvinces": CANADIAN_PROVINCE_OPTIONS,
        "identityDocumentTypes": IDENTITY_DOCUMENT_TYPES,
        "securityLicenseTypes": SECURITY_LICENSE_TYPE_OPTIONS,
        "trainingCertificateTypes": TRAINING_CERTIFICATE_TYPE_OPTIONS,
        "trainingIssuerOptionsMap": TRAINING_ISSUER_OPTIONS_MAP,
        "policeClearanceAuthorityTypes": POLICE_CLEARANCE_AUTHORITY_TYPE_OPTIONS,
    }


@public_routes.get("/api/s/static/tenant/{id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_tenant_resource(id: str):
    return await ResourceManager.get_instance().get_tenant_image(id)


@public_routes.get("/api/s/static/user/{id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_user_resource(id: str):
    return await ResourceManager.get_instance().get_user_image(id)


@public_routes.get("/api/s/static/system/{id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_user_resource():
    return await ResourceManager.get_instance().get_system_image(id)

@public_routes.get("/api/tenant/files/identity/{file_id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_tenant_identity_document(file_id: str, request: Request):
    # Extract user info from cookie to verify ownership
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_identity_document(file_id, current_user)


@public_routes.get("/api/tenant/files/security-license/{file_id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_tenant_security_license_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_security_license_document(file_id, current_user)


@public_routes.get("/api/tenant/files/police-clearance/{file_id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_tenant_police_clearance_document(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_police_clearance_document(file_id, current_user)


@public_routes.get("/api/tenant/files/training-certificate/{file_id}", include_in_schema=False, dependencies=[Depends(cookie_required)])
async def get_tenant_training_certificate(file_id: str, request: Request):
    from configs.token_auth_provider import get_current_user_from_cookie
    current_user = await get_current_user_from_cookie(request)
    return await ResourceManager.get_instance().get_tenant_training_certificate(file_id, current_user)

@public_routes.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    return await ResourceManager.get_instance().get_robots_txt()
