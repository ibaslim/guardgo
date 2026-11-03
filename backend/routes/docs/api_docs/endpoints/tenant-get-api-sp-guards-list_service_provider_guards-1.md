# List guards owned by service provider

`GET /api/sp/guards`

Retrieve paginated security guards employed by or associated with the caller's service provider company.

### Access
- **Role Required**: `sp_admin`.

### Input
- **Query Parameters**:
  - `page` *(integer, default: 1)*: Page number.
  - `rows` *(integer, default: 20)*: Page size.

### Output
- Paginated list of guard records with profile details, license status, and operational coverage.

## At a glance

- **Operation ID:** `listServiceProviderGuards`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`list_service_provider_guards`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated list of service provider guards.

```json
{
  "items": [
    {
      "guard_tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
      "name": "Marcus Vance",
      "email": "marcus.vance@example.com",
      "status": "active",
      "operational_region_code": "ON",
      "operational_city_code": "TORONTO",
      "max_travel_radius_km": 35.0
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
curl -X GET 'https://api.example.com/api/sp/guards' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
