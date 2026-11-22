# List shift exceptions

`GET /api/shift-exceptions`

Return shift-slot exceptions for platform review, including unavailable and no-show cases.

## At a glance

- **Operation ID:** `listShiftExceptions`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`list_shift_exceptions`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |
| `exception_status` | `str` | No | `example-value` |
| `request_id` | `str` | No | `507f1f77bcf86cd799439011` |
| `date_from` | `date | None` | No | `example-value` |
| `date_to` | `date | None` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated shift-slot exceptions.

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
curl -X GET 'https://api.example.com/api/shift-exceptions' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
