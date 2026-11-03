# User login (OAuth2 Password flow)

`POST /api/token`

Authenticate a user using their username/email and password.

### Workflow
- Validates user credentials against stored argon2/bcrypt password hash.
- Checks user account status (`active`, `pending`, `banned`).
- If Two-Factor Authentication (2FA) is enabled, returns `twofa_required: true` and a short-lived temporary token to submit to `/api/token/2fa/verify`.
- If 2FA is not enabled, issues a standard JWT access token, and sets an `access_token` HTTP-only session cookie.

### Input
- **Form Data (`OAuth2PasswordRequestForm`)**:
  - `username` *(string, required)*: Username or email address.
  - `password` *(string, required)*: Plaintext account password.
  - `scope` *(string, optional)*: Requested OAuth scopes.

### Output
- `access_token` *(string)*: Signed JWT bearer token.
- `token_type` *(string)*: `"bearer"`.
- `twofa_required` *(boolean)*: `true` if 2FA code is needed.
- `user` *(object)*: Basic authenticated user details (id, username, email, role, tenant_uuid).

## At a glance

- **Operation ID:** `loginForAccessToken`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`token`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `OAuth2PasswordRequestForm`.

```json
{
  "username": "example-value",
  "password": "ChangeMe123!",
  "scope": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Access token and authentication session details.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "twofa_required": false,
  "user": {
    "id": "651a2b3c4d5e6f7a8b9c0d1e",
    "username": "guard_admin",
    "email": "guard@example.com",
    "role": "guard_admin",
    "tenant_uuid": "651a2b3c4d5e6f7a8b9c0d2f"
  }
}
```

## Errors

- `400 Bad Request` — input is invalid or a path identifier has the wrong format.
- `401 Unauthorized` — authentication is missing, expired, or invalid.
- `403 Forbidden` — the authenticated user does not have the required role or status.
- `404 Not Found` — the requested resource does not exist.
- `422 Unprocessable Entity` — FastAPI validation failed before the handler ran.

## cURL

```bash
curl -X POST 'https://api.example.com/api/token' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
