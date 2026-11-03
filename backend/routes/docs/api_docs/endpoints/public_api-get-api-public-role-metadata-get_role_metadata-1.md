# Get role permission group definitions

`GET /api/public/role-metadata`

Retrieve system role categories used by frontend route guards and permission gates.

### Content Provided
- `platformRoles`: Super admin, ops admin, support admin, compliance admin, read-only admin.
- `tenantSettingsRoles`: Tenant administrators permitted to modify organization settings.
- `tenantManagementRoles`: Roles permitted to manage tenant operations.
- `platformUserManagementRoles`: Roles permitted to invite and modify platform staff.

### Input
- None.

### Output
- Mapping of role permission groups to lists of role codes.

## At a glance

- **Operation ID:** `getRoleMetadata`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_role_metadata`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Platform and tenant role groups for UI guards.

```json
{
  "platformRoles": [
    "admin",
    "ops_admin",
    "support_admin",
    "compliance_admin",
    "read_only_admin"
  ],
  "tenantSettingsRoles": [
    "client_admin",
    "guard_admin",
    "sp_admin"
  ]
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
curl -X GET 'https://api.example.com/api/public/role-metadata' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
