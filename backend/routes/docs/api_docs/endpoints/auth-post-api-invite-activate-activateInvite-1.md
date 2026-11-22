# Activate invited user account

`POST /api/invite/activate`

Complete account setup for an invited user by setting their username, display name, and password.

### Workflow
- Validates invitation token.
- Configures user credentials, sets status to `active`, and initializes tenant membership.

### Input (`InviteActivationRequest`)
- `token` *(string, required)*: Invite token.
- `username` *(string, required)*: Chosen username.
- `full_name` *(string, required)*: User full display name.
- `password` *(string, required)*: Chosen account password.

### Output
- Confirmation payload with activated user profile and initial login guidance.

## At a glance

- **Operation ID:** `activateInvitedUser`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`activateInvite`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `InviteActivationRequest`.

```json
{
  "token": "507f1f77bcf86cd799439011",
  "password": "ChangeMe123!",
  "username": "example-value",
  "full_name": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Activation confirmation for invited user account.

```json
{
  "message": "Account activated successfully. You can now log in."
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
curl -X POST 'https://api.example.com/api/invite/activate' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
