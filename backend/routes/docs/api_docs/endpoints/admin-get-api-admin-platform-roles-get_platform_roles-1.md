# Get assignable platform admin roles

`GET /api/admin/platform-roles`

List all platform administrative roles that can be assigned to platform personnel.

### Access
- **Role Required**: `admin`.

### Output
- Array of role objects with `value` and user-friendly `label` (e.g., Ops Admin, Support Admin, Compliance Admin, Read Only Admin).

## At a glance

- **Operation ID:** `getPlatformRoles`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`get_platform_roles`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

List of assignable platform administrator roles.

```json
[
  {
    "value": "ops_admin",
    "label": "Ops Admin"
  },
  {
    "value": "support_admin",
    "label": "Support Admin"
  },
  {
    "value": "compliance_admin",
    "label": "Compliance Admin"
  },
  {
    "value": "read_only_admin",
    "label": "Read Only Admin"
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
curl -X GET 'https://api.example.com/api/admin/platform-roles' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
