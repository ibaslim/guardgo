# Get user invitation context

`GET /api/invite/context/{token}`

Validate an invite token and retrieve invitation metadata for onboarding.

### Workflow
- Verifies the invitation token created by platform or tenant admins.
- Returns invited email, assigned role, and tenant details so frontend displays onboarding form.

### Input
- **Path Parameter**:
  - `token` *(string, required)*: Cryptographic invite token.

### Output
- `{"valid": true, "email": "...", "role": "...", "tenant_name": "..."}`

## At a glance

- **Operation ID:** `getInviteContext`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`inviteContext`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `token` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Invitation validity and profile context for user onboarding.

```json
{
  "valid": true,
  "email": "invitee@example.com",
  "role": "guard_admin",
  "tenant_name": "Apex Security Services"
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
curl -X GET 'https://api.example.com/api/invite/context/{token}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
