# List active client tenants for request operations

`GET /api/request-client-tenants`

Return active client tenants that platform users can target when creating or filtering requests.

## At a glance

- **Operation ID:** `listRequestClientTenants`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`list_request_client_tenants`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `keyword` | `str` | No | `example-value` |
| `rows` | `int` | No | `1` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Active client tenants available for request creation.

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
curl -X GET 'https://api.example.com/api/request-client-tenants' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
