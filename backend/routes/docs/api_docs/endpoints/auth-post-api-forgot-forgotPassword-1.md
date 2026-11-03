# Request password reset email

`POST /api/forgot`

Initiate self-service password recovery for a registered user account.

### Workflow
- Looks up account by registered email address.
- If account exists and is eligible, generates a secure, time-limited reset token.
- Dispatches password reset email containing link to password reset UI.

### Input (`ForgotPasswordRequest`)
- `email` *(string, required)*: Registered user email address.

### Output
- Standard confirmation message confirming instructions have been dispatched.

## At a glance

- **Operation ID:** `requestPasswordReset`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`forgotPassword`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Confirmation of password reset request dispatch.

```json
{
  "message": "If the email is registered, password reset instructions have been sent."
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
curl -X POST 'https://api.example.com/api/forgot' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
