# Get password reset token context

`GET /api/reset/context/{token}`

Inspect and validate a password reset token before rendering the reset form.

### Workflow
- Validates token format, signature, and expiration.
- Returns masked email and status so frontend can present user context.

### Input
- **Path Parameter**:
  - `token` *(string, required)*: One-time password reset token.

### Output
- `{"valid": true, "email": "user@example.com", "expires_at": "..."}`

## At a glance

- **Operation ID:** `getPasswordResetContext`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`resetPasswordContext`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `token` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Password reset token validity and context information.

```json
{
  "valid": true,
  "email": "user@example.com",
  "expires_at": "2026-11-03T12:00:00Z"
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
curl -X GET 'https://api.example.com/api/reset/context/{token}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
