# Update platform admin user details & permissions

`PUT /api/admin/platform-users/{user_id}`

Modify role, account status, reason for status modification, and license permissions for a platform user.

### Access
- **Role Required**: `admin`.

### Input
- **Path Parameter**:
  - `user_id` *(string, required)*: Unique identifier of platform user.
- **JSON Body (`PlatformAdminUpdateRequest`)**:
  - `role` *(user_role, optional)*: Updated administrative role.
  - `status` *(UserStatus, optional)*: Updated status (`active`, `pending`, `suspended`, `banned`).
  - `status_reason` *(string, optional)*: Audit explanation for status change.
  - `licenses` *(list of strings, optional)*: Module license grants.

### Output
- Updated platform administrator user record.

## At a glance

- **Operation ID:** `updatePlatformUser`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`update_platform_user`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `user_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `PlatformAdminUpdateRequest`.

```json
{
  "role": "example-value",
  "status": "example-value",
  "status_reason": "example-value",
  "licenses": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated platform user profile.

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
curl -X PUT 'https://api.example.com/api/admin/platform-users/{user_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
