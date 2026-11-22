# Restore soft-deleted platform admin user

`POST /api/admin/platform-users/{user_id}/restore`

Reactivate a previously soft-deleted platform administrative user.

### Access
- **Role Required**: `admin`.

### Input
- **Path Parameter**:
  - `user_id` *(string, required)*: Platform user ID.

### Output
- Restored user record with active status.

## At a glance

- **Operation ID:** `restorePlatformUser`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`restore_platform_user`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `user_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Restored user account details.

```json
[
  {
    "id": "651f7a8b9c0d7e8f9a0b1c2d",
    "username": "sarah.compliance",
    "email": "sarah.c@guardgo.ca",
    "role": "compliance_admin",
    "status": "active",
    "invite_pending": false
  }
]
```

## Errors

- `400 Bad Request` — input is invalid or a path identifier has the wrong format.
- `401 Unauthorized` — authentication is missing, expired, or invalid.
- `403 Forbidden` — the authenticated user does not have the required role or status.
- `404 Not Found` — the requested resource does not exist.
- `422 Unprocessable Entity` — FastAPI validation failed before the handler ran.

## cURL

```bash
curl -X POST 'https://api.example.com/api/admin/platform-users/{user_id}/restore' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
