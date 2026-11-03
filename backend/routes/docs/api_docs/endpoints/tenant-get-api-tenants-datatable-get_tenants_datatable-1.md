# Get tenants datatable

`GET /api/tenants/datatable`

Get tenants with pagination, filters, keyword search, and sorting.

## At a glance

- **Operation ID:** `getTenantsDatatable`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`get_tenants_datatable`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |
| `tenant_type` | `str | None` | No | `example-value` |
| `tenant_status` | `str | None` | No | `example-value` |
| `keyword` | `str | None` | No | `example-value` |
| `sort_by` | `str` | No | `example-value` |
| `sort_order` | `str` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated tenant rows.

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
curl -X GET 'https://api.example.com/api/tenants/datatable' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
