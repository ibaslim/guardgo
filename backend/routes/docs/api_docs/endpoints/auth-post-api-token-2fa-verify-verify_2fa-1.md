# Verify Two-Factor Authentication (2FA) TOTP code

`POST /api/token/2fa/verify`

Verify a 6-digit Time-based One-Time Password (TOTP) code following an initial login challenge.

### Workflow
- Accepts the temporary bearer token issued by `/api/token` in the `Authorization: Bearer <temp_token>` header.
- Validates the submitted 6-digit numeric TOTP token against the user's registered authenticator secret.
- On success, issues a full-access JWT access token and sets the HTTP-only session cookie.

### Input
- **Header**: `Authorization: Bearer <temp_2fa_token>`
- **JSON Body**:
  - `code` *(string, required)*: 6-digit TOTP verification code from authenticator app.

### Output
- `access_token` *(string)*: Activated JWT bearer token with full user privileges.
- `token_type` *(string)*: `"bearer"`.
- `status` *(string)*: Verification status confirmation.

## At a glance

- **Operation ID:** `verifyTwoFactorCode`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`verify_2fa`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `code` | `str` | No | `example-value` |
| `ptoken` | `str` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Full access token upon successful 2FA code verification.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.verified...",
  "token_type": "bearer",
  "status": "verified"
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
curl -X POST 'https://api.example.com/api/token/2fa/verify' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
