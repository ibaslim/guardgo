# List guard status change requests

`GET /api/guard-status-requests`

Retrieve all pending, approved, or rejected guard status change requests submitted by service providers.

### Access
- **Role Required**: `admin`.

### Input
- **Query Parameters**:
  - `page` *(integer, default: 1)*: Page number.
  - `rows` *(integer, default: 20)*: Page size.

### Output
- Paginated list of guard status change request records with requester and target guard metadata.

## At a glance

- **Operation ID:** `listGuardStatusRequests`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`list_guard_status_requests`)
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

Paginated list of guard status change requests.

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
curl -X GET 'https://api.example.com/api/guard-status-requests' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
