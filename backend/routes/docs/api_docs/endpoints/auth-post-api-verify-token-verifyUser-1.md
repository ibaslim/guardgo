# Verify email and activate account

`POST /api/verify/{token}`

Complete self-service email verification using the one-time token received via email.

### Workflow
- Validates token authenticity, signature, and expiration.
- Updates user account status from `pending_activation` to `active`.
- Marks tenant email as verified.

### Input
- **Path Parameter**:
  - `token` *(string, required)*: Cryptographic one-time email verification token.

### Output
- Verification success status and updated account state.

## At a glance

- **Operation ID:** `verifyUserEmailToken`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`verifyUser`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `token` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Verification confirmation and activation result.

```json
{
  "message": "Email verified successfully. Account is now active."
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
curl -X POST 'https://api.example.com/api/verify/{token}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
