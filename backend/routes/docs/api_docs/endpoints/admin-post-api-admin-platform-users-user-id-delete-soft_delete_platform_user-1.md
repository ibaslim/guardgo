# Soft-delete platform admin user

`POST /api/admin/platform-users/{user_id}/delete`

Mark a platform administrative user as soft-deleted and disable access while retaining audit logs.

### Access
- **Role Required**: `admin`.

### Input
- **Path Parameter**:
  - `user_id` *(string, required)*: Platform user ID.
- **JSON Body (`PlatformAdminStatusReasonRequest`)**:
  - `reason` *(string, required)*: Explanation for deactivating/soft-deleting the user.

### Output
- Deactivated user record showing deleted state.

## At a glance

- **Operation ID:** `softDeletePlatformUser`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`soft_delete_platform_user`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `user_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `PlatformAdminStatusReasonRequest`.

```json
{
  "reason": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Confirmation of soft-deleted user account.

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
curl -X POST 'https://api.example.com/api/admin/platform-users/{user_id}/delete' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
