# List shifts

`GET /api/shifts`

Return paginated shift instances visible to the current user.

## At a glance

- **Operation ID:** `listRequestShifts`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`list_request_shifts`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |
| `request_id` | `str` | No | `507f1f77bcf86cd799439011` |
| `instance_status` | `str` | No | `example-value` |
| `date_from` | `date | None` | No | `example-value` |
| `date_to` | `date | None` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated shift instances.

```json
{
  "items": [
    {
      "shift_id": "651c4d5e6f7a8b9c0d4e5f6a",
      "request_id": "651b3c4d5e6f7a8b9c0d3e4f",
      "date": "2026-11-10",
      "start_time": "22:00",
      "end_time": "06:00",
      "status": "scheduled",
      "assigned_guard": "Marcus Vance"
    }
  ],
  "total": 1
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
curl -X GET 'https://api.example.com/api/shifts' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
