# Resend registration verification email

`POST /api/signup/verificaion`

Resend the activation and email verification message to a newly registered tenant.

### Workflow
- Locates user by registered email.
- Generates a fresh verification token.
- Sends verification email via the platform notification manager.

### Input (`SignupRequest`)
- `email` *(email, required)*: The registered account email address.

### Output
- Status confirmation of the email resend request.

## At a glance

- **Operation ID:** `resendRegistrationVerification`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`resend_verification_email`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `SignupRequest`.

```json
{
  "username": "example-value",
  "email": "alex.morgan@example.com",
  "password": "ChangeMe123!",
  "tenant_type": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Status confirmation of verification email dispatch.

```json
{
  "message": "Verification email resent successfully"
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
curl -X POST 'https://api.example.com/api/signup/verificaion' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
