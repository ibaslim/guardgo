# Get all tenants

`GET /api/tenants`

Retrieve all tenant records (admin only).

## At a glance

- **Operation ID:** `getAllTenants`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`get_all_tenants`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

List of all tenants.

```json
{
  "items": [
    {
      "id": "651a2b3c4d5e6f7a8b9c0d2f",
      "name": "Marcus Vance",
      "tenant_type": "guard",
      "status": "active",
      "verified": true
    }
  ],
  "total": 1,
  "page": 1,
  "rows": 20
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
curl -X GET 'https://api.example.com/api/tenants' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
