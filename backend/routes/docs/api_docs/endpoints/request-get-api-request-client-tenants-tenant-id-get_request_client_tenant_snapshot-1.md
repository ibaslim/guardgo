# Get active client tenant snapshot for request creation

`GET /api/request-client-tenants/{tenant_id}`

Return the client profile snapshot, including saved sites, for a platform-targeted request.

## At a glance

- **Operation ID:** `getRequestClientTenantSnapshot`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`get_request_client_tenant_snapshot`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Client tenant snapshot.

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
curl -X GET 'https://api.example.com/api/request-client-tenants/{tenant_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
