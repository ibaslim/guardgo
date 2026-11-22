from fastapi import APIRouter, Depends, Body, Response, Request, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from starlette.responses import JSONResponse

from orion.api.interactive.auth_manager.auth_manager import auth_manager
from orion.helper_manager.env_handler import env_handler
from orion.services.session_manager.session_manager import session_manager
from orion.api.interactive.signup_manager.model.signup_request_model import SignupRequest
from orion.api.interactive.signup_manager.signup_manager import SignupManager
from orion.api.interactive.auth_manager.models.forgot_password_request import (
    ForgotPasswordRequest,
    ResetPassword,
    InviteActivationRequest,
)

auth_router = APIRouter(tags=["Authentication & Session"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

ACCESS_COOKIE = "access_token"
COOKIE_MAX_AGE = 30 * 60  # 30 minutes


def set_access_cookie(resp: Response, token: str) -> None:
    is_debug = env_handler.get_instance().env("PRODUCTION", "0") != "1"
    resp.set_cookie(
        key=ACCESS_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not is_debug,
        path="/",
        max_age=COOKIE_MAX_AGE,
    )


def token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    parts = auth.split(" ", 1)
    bearer = parts[1] if len(parts) == 2 and parts[0] == "Bearer" else None
    return bearer or request.cookies.get(ACCESS_COOKIE)


@auth_router.post(
    "/api/token",
    summary="User login (OAuth2 Password flow)",
    description=(
        "Authenticate a user using their username/email and password.\n\n"
        "### Workflow\n"
        "- Validates user credentials against stored argon2/bcrypt password hash.\n"
        "- Checks user account status (`active`, `pending`, `banned`).\n"
        "- If Two-Factor Authentication (2FA) is enabled, returns `twofa_required: true` "
        "and a short-lived temporary token to submit to `/api/token/2fa/verify`.\n"
        "- If 2FA is not enabled, issues a standard JWT access token, and sets an `access_token` HTTP-only session cookie.\n\n"
        "### Input\n"
        "- **Form Data (`OAuth2PasswordRequestForm`)**:\n"
        "  - `username` *(string, required)*: Username or email address.\n"
        "  - `password` *(string, required)*: Plaintext account password.\n"
        "  - `scope` *(string, optional)*: Requested OAuth scopes.\n\n"
        "### Output\n"
        "- `access_token` *(string)*: Signed JWT bearer token.\n"
        "- `token_type` *(string)*: `\"bearer\"`.\n"
        "- `twofa_required` *(boolean)*: `true` if 2FA code is needed.\n"
        "- `user` *(object)*: Basic authenticated user details (id, username, email, role, tenant_uuid)."
    ),
    response_description="Access token and authentication session details.",
    operation_id="loginForAccessToken",
)
async def token(form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None):
    result = await auth_manager.login(form_data.username, form_data.password)
    access_token = result.get("access_token")
    twofa_required = result.get("twofa_required")

    if access_token and not twofa_required:
        set_access_cookie(response, access_token)

    return result


@auth_router.post(
    "/api/token/demo",
    summary="Demo environment quick login",
    description=(
        "Authenticate using pre-configured demonstration credentials defined in the application environment.\n\n"
        "### Purpose\n"
        "- Fast automated or manual access for local development, staging, or testing.\n"
        "- Reads `DEMO_USERNAME` and `DEMO_PASSWORD` from server configuration.\n\n"
        "### Input\n"
        "- None (credentials are sourced from server environment).\n\n"
        "### Output\n"
        "- Standard login dictionary containing `access_token`, `token_type`, and session cookie."
    ),
    response_description="Demo user access token and session cookie.",
    operation_id="loginDemoUser",
)
async def token_demo(response: Response = None):
    DEMO_USERNAME = env_handler.get_instance().env("DEMO_USERNAME")
    DEMO_PASSWORD = env_handler.get_instance().env("DEMO_PASSWORD")

    result = await auth_manager.login(DEMO_USERNAME, DEMO_PASSWORD, True)
    access_token = result.get("access_token")
    twofa_required = result.get("twofa_required")

    if access_token and not twofa_required:
        set_access_cookie(response, access_token)

    return result


@auth_router.post(
    "/api/token/2fa/verify",
    summary="Verify Two-Factor Authentication (2FA) TOTP code",
    description=(
        "Verify a 6-digit Time-based One-Time Password (TOTP) code following an initial login challenge.\n\n"
        "### Workflow\n"
        "- Accepts the temporary bearer token issued by `/api/token` in the `Authorization: Bearer <temp_token>` header.\n"
        "- Validates the submitted 6-digit numeric TOTP token against the user's registered authenticator secret.\n"
        "- On success, issues a full-access JWT access token and sets the HTTP-only session cookie.\n\n"
        "### Input\n"
        "- **Header**: `Authorization: Bearer <temp_2fa_token>`\n"
        "- **JSON Body**:\n"
        "  - `code` *(string, required)*: 6-digit TOTP verification code from authenticator app.\n\n"
        "### Output\n"
        "- `access_token` *(string)*: Activated JWT bearer token with full user privileges.\n"
        "- `token_type` *(string)*: `\"bearer\"`.\n"
        "- `status` *(string)*: Verification status confirmation."
    ),
    response_description="Full access token upon successful 2FA code verification.",
    operation_id="verifyTwoFactorCode",
)
async def verify_2fa(
    code: str = Body(..., embed=True, description="6-digit TOTP verification code"),
    ptoken: str = Depends(oauth2_scheme),
    response: Response = None,
):
    result = await session_manager.get_instance().verify_2fa_and_issue(ptoken, code)
    access_token = result.get("access_token")
    if access_token:
        set_access_cookie(response, access_token)
    return result


@auth_router.post(
    "/api/token/refresh",
    summary="Refresh active session token",
    description=(
        "Generate a renewed JWT access token using the caller's active bearer token or session cookie.\n\n"
        "### Workflow\n"
        "- Extracts caller's current token from `Authorization` header or HTTP-only `access_token` cookie.\n"
        "- Validates session activity in Redis/database.\n"
        "- Extends session lifetime and issues a freshly signed JWT token.\n\n"
        "### Input\n"
        "- **Header / Cookie**: `Authorization: Bearer <token>` or `access_token` cookie.\n\n"
        "### Output\n"
        "- `access_token` *(string)*: Refreshed JWT access token.\n"
        "- `token_type` *(string)*: `\"bearer\"`."
    ),
    response_description="Renewed access token with extended session validity.",
    operation_id="refreshAccessToken",
)
async def refresh_token(request: Request, response: Response = None):
    token = token_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    result = await session_manager.get_instance().refresh_token(token)
    access_token = result.get("access_token")
    if access_token:
        set_access_cookie(response, access_token)
    return result


@auth_router.post(
    "/api/logout",
    summary="Log out and destroy session",
    description=(
        "Terminate the active user session and remove authentication credentials.\n\n"
        "### Workflow\n"
        "- Invalidates the session entry in the session cache/store.\n"
        "- Deletes the `access_token` HTTP-only cookie on the client.\n\n"
        "### Input\n"
        "- **Cookie / Header**: Caller's current session identifier.\n\n"
        "### Output\n"
        "- `{\"detail\": \"Logged out\"}`"
    ),
    response_description="Logout confirmation message.",
    operation_id="logoutUser",
)
async def logout(request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    session_manager.logout_user(ptoken=token)
    resp = JSONResponse(content={"detail": "Logged out"})
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    return resp


@auth_router.post(
    "/api/signup",
    summary="Register a new tenant & admin account",
    description=(
        "Public self-service registration for a new tenant and initial administrator.\n\n"
        "### Workflow\n"
        "- Creates a new tenant organization with specified type (`guard`, `client`, or `service_provider`).\n"
        "- Creates the initial user account in `pending_activation` status.\n"
        "- Dispatches an activation verification link to the registered email address.\n\n"
        "### Input (`SignupRequest`)\n"
        "- `username` *(string, required)*: Chosen username for primary account holder.\n"
        "- `email` *(email, required)*: Valid email address for notifications and email verification.\n"
        "- `password` *(string, required)*: Initial password meeting strength complexity requirements.\n"
        "- `tenant_type` *(string, default: client)*: One of `\"guard\"`, `\"client\"`, or `\"service_provider\"`.\n\n"
        "### Output\n"
        "- Confirmation payload including tenant ID, username, and verification dispatch status."
    ),
    response_description="Tenant creation result and verification email dispatch confirmation.",
    operation_id="registerNewTenantUser",
    status_code=201,
)
async def signup(data: SignupRequest):
    return await SignupManager.signup_user(data)


@auth_router.post(
    "/api/signup/verificaion",
    summary="Resend registration verification email",
    description=(
        "Resend the activation and email verification message to a newly registered tenant.\n\n"
        "### Workflow\n"
        "- Locates user by registered email.\n"
        "- Generates a fresh verification token.\n"
        "- Sends verification email via the platform notification manager.\n\n"
        "### Input (`SignupRequest`)\n"
        "- `email` *(email, required)*: The registered account email address.\n\n"
        "### Output\n"
        "- Status confirmation of the email resend request."
    ),
    response_description="Status confirmation of verification email dispatch.",
    operation_id="resendRegistrationVerification",
)
async def resend_verification_email(data: SignupRequest):
    return await SignupManager.resend_verification_email(data)


@auth_router.post(
    "/api/verify/{token}",
    summary="Verify email and activate account",
    description=(
        "Complete self-service email verification using the one-time token received via email.\n\n"
        "### Workflow\n"
        "- Validates token authenticity, signature, and expiration.\n"
        "- Updates user account status from `pending_activation` to `active`.\n"
        "- Marks tenant email as verified.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `token` *(string, required)*: Cryptographic one-time email verification token.\n\n"
        "### Output\n"
        "- Verification success status and updated account state."
    ),
    response_description="Verification confirmation and activation result.",
    operation_id="verifyUserEmailToken",
)
async def verifyUser(token: str):
    return await auth_manager.verify_user(token)


@auth_router.post(
    "/api/forgot",
    summary="Request password reset email",
    description=(
        "Initiate self-service password recovery for a registered user account.\n\n"
        "### Workflow\n"
        "- Looks up account by registered email address.\n"
        "- If account exists and is eligible, generates a secure, time-limited reset token.\n"
        "- Dispatches password reset email containing link to password reset UI.\n\n"
        "### Input (`ForgotPasswordRequest`)\n"
        "- `email` *(string, required)*: Registered user email address.\n\n"
        "### Output\n"
        "- Standard confirmation message confirming instructions have been dispatched."
    ),
    response_description="Confirmation of password reset request dispatch.",
    operation_id="requestPasswordReset",
)
async def forgotPassword(request: ForgotPasswordRequest):
    return await auth_manager.forgot_password(request.email)


@auth_router.post(
    "/api/updatePassword",
    summary="Reset password with reset token",
    description=(
        "Set a new password using a verified password reset token.\n\n"
        "### Workflow\n"
        "- Validates password reset token validity and expiration.\n"
        "- Hashes new password securely with argon2/bcrypt.\n"
        "- Invalidates reset token and all existing user sessions.\n\n"
        "### Input (`ResetPassword`)\n"
        "- `token` *(string, required)*: Valid password reset token from reset email.\n"
        "- `password` *(string, required)*: New plaintext password.\n\n"
        "### Output\n"
        "- Status confirmation of successful password update."
    ),
    response_description="Password update confirmation result.",
    operation_id="updateUserPassword",
)
async def updatePassword(data: ResetPassword):
    return await auth_manager.update_password(data.token, data.password)


@auth_router.get(
    "/api/reset/context/{token}",
    summary="Get password reset token context",
    description=(
        "Inspect and validate a password reset token before rendering the reset form.\n\n"
        "### Workflow\n"
        "- Validates token format, signature, and expiration.\n"
        "- Returns masked email and status so frontend can present user context.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `token` *(string, required)*: One-time password reset token.\n\n"
        "### Output\n"
        "- `{\"valid\": true, \"email\": \"user@example.com\", \"expires_at\": \"...\"}`"
    ),
    response_description="Password reset token validity and context information.",
    operation_id="getPasswordResetContext",
)
async def resetPasswordContext(token: str):
    return await auth_manager.get_password_reset_context(token)


@auth_router.get(
    "/api/invite/context/{token}",
    summary="Get user invitation context",
    description=(
        "Validate an invite token and retrieve invitation metadata for onboarding.\n\n"
        "### Workflow\n"
        "- Verifies the invitation token created by platform or tenant admins.\n"
        "- Returns invited email, assigned role, and tenant details so frontend displays onboarding form.\n\n"
        "### Input\n"
        "- **Path Parameter**:\n"
        "  - `token` *(string, required)*: Cryptographic invite token.\n\n"
        "### Output\n"
        "- `{\"valid\": true, \"email\": \"...\", \"role\": \"...\", \"tenant_name\": \"...\"}`"
    ),
    response_description="Invitation validity and profile context for user onboarding.",
    operation_id="getInviteContext",
)
async def inviteContext(token: str):
    return await auth_manager.get_invite_context(token)


@auth_router.post(
    "/api/invite/activate",
    summary="Activate invited user account",
    description=(
        "Complete account setup for an invited user by setting their username, display name, and password.\n\n"
        "### Workflow\n"
        "- Validates invitation token.\n"
        "- Configures user credentials, sets status to `active`, and initializes tenant membership.\n\n"
        "### Input (`InviteActivationRequest`)\n"
        "- `token` *(string, required)*: Invite token.\n"
        "- `username` *(string, required)*: Chosen username.\n"
        "- `full_name` *(string, required)*: User full display name.\n"
        "- `password` *(string, required)*: Chosen account password.\n\n"
        "### Output\n"
        "- Confirmation payload with activated user profile and initial login guidance."
    ),
    response_description="Activation confirmation for invited user account.",
    operation_id="activateInvitedUser",
)
async def activateInvite(data: InviteActivationRequest):
    return await auth_manager.activate_invited_user(
        token=data.token,
        password=data.password,
        username=data.username,
        full_name=data.full_name,
    )
