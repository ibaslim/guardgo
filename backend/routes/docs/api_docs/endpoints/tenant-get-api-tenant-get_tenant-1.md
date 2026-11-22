# Get current tenant

`GET /api/tenant`

Retrieve the complete tenant object including profile and base fields.

## At a glance

- **Operation ID:** `getTenant`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`get_tenant`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Complete tenant data.

```json
{
  "id": "651a2b3c4d5e6f7a8b9c0d2f",
  "tenant_type": "guard",
  "status": "active",
  "verified": true,
  "profile": {
    "first_name": "Marcus",
    "last_name": "Vance",
    "phone": "+1-416-555-0199",
    "address": {
      "city": "Toronto",
      "province": "ON",
      "postal_code": "M5V 2T6"
    }
  },
  "approvals_required": 2,
  "approvals_done": 2,
  "approvals_remaining": 0
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
curl -X GET 'https://api.example.com/api/tenant' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
