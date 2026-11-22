# List client requests

`GET /api/requests`

Return paginated requests in the current role scope.

## At a glance

- **Operation ID:** `listClientRequests`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`list_client_requests`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |
| `keyword` | `str` | No | `example-value` |
| `request_status` | `str` | No | `example-value` |
| `fulfillment_mode` | `str` | No | `example-value` |
| `client_tenant_id` | `str` | No | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated client requests.

```json
{
  "items": [
    {
      "id": "651b3c4d5e6f7a8b9c0d3e4f",
      "title": "Commercial Plaza Overnight Security",
      "status": "published",
      "fulfillment_mode": "auto_match",
      "site": {
        "name": "Metro Square",
        "city": "Toronto",
        "province": "ON"
      },
      "start_date": "2026-11-10",
      "end_date": "2026-11-20",
      "estimated_total": 4800.0
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
curl -X GET 'https://api.example.com/api/requests' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
