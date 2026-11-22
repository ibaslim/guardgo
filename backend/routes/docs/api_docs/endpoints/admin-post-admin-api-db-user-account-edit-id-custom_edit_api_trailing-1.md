# Admin console user status update (trailing slash alias)

`POST /admin/api/db_user_account/edit/{id}/`

Trailing-slash alias for `/admin/api/db_user_account/edit/{id}` to prevent route resolution mismatches in admin UI.

### Input
- **Path Parameter**:
  - `id` *(string, required)*: User account identifier.

### Output
- `303 See Other` redirect.

## At a glance

- **Operation ID:** `adminEditUserAccountStatusTrailing`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`custom_edit_api_trailing`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Redirects to the admin user list.

```json
{
  "message": "Operation completed successfully",
  "status": "success"
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
curl -X POST 'https://api.example.com/admin/api/db_user_account/edit/{id}/' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
