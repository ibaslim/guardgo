# Update current tenant

`PUT /api/tenant`

Update the complete tenant object (profile + base fields).

## At a glance

- **Operation ID:** `updateTenant`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`update_tenant`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `TenantPayload`.

```json
{
  "id": "507f1f77bcf86cd799439011",
  "tenant_type": "example-value",
  "profile": "example-value",
  "subscription": true,
  "verified": true,
  "user_quota": 1,
  "status": "example-value",
  "approvals_required": 1,
  "approval_actors": "example-value",
  "licenses": "example-value",
  "iocs": "example-value",
  "created_at": "example-value",
  "updated_at": "example-value",
  "verified_date": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated tenant data.

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
curl -X PUT 'https://api.example.com/api/tenant' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
