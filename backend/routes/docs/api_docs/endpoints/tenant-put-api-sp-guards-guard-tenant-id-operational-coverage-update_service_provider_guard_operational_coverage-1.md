# Update managed guard operational coverage

`PUT /api/sp/guards/{guard_tenant_id}/operational-coverage`

Configure operational dispatch parameters for a managed guard including region, city, maximum travel radius, and weekly availability schedule.

### Access
- **Role Required**: `sp_admin`.

### Input
- **Path Parameter**:
  - `guard_tenant_id` *(string, required)*: Guard tenant ID.
- **JSON Body (`ServiceProviderGuardOperationalCoveragePayload`)**:
  - `operational_region_code` *(string, required)*: Province/state code (e.g. 'ON', 'BC').
  - `operational_city_code` *(string, required)*: Primary operational municipality (e.g. 'TORONTO').
  - `max_travel_radius_km` *(float, required)*: Maximum dispatch radius from base city in km.
  - `weekly_availability` *(object, optional)*: Day-of-week hour windows when guard is available.

### Output
- Updated operational coverage configuration for the guard.

## At a glance

- **Operation ID:** `updateServiceProviderGuardOperationalCoverage`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`update_service_provider_guard_operational_coverage`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ServiceProviderGuardOperationalCoveragePayload`.

```json
{
  "operational_region_code": "example-value",
  "operational_city_code": "example-value",
  "max_travel_radius_km": 1.0,
  "weekly_availability": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated guard operational coverage settings.

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
curl -X PUT 'https://api.example.com/api/sp/guards/{guard_tenant_id}/operational-coverage' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
