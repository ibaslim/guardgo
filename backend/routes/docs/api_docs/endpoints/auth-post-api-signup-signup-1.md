# Register a new tenant & admin account

`POST /api/signup`

Public self-service registration for a new tenant and initial administrator.

### Workflow
- Creates a new tenant organization with specified type (`guard`, `client`, or `service_provider`).
- Creates the initial user account in `pending_activation` status.
- Dispatches an activation verification link to the registered email address.

### Input (`SignupRequest`)
- `username` *(string, required)*: Chosen username for primary account holder.
- `email` *(email, required)*: Valid email address for notifications and email verification.
- `password` *(string, required)*: Initial password meeting strength complexity requirements.
- `tenant_type` *(string, default: client)*: One of `"guard"`, `"client"`, or `"service_provider"`.

### Output
- Confirmation payload including tenant ID, username, and verification dispatch status.

## At a glance

- **Operation ID:** `registerNewTenantUser`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`signup`)
- **Success status:** `201`
- **Authentication:** Authentication is not required (Public endpoint).

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

Tenant creation result and verification email dispatch confirmation.

```json
{
  "message": "User registered successfully. Please verify your email.",
  "tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
  "username": "client_corp",
  "status": "pending_activation"
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
curl -X POST 'https://api.example.com/api/signup' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
