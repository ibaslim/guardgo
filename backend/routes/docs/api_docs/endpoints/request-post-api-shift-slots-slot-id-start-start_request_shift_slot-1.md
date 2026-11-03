# Start shift slot

`POST /api/shift-slots/{slot_id}/start`

Start the shift slot after arrival confirmation, or through platform override.

## At a glance

- **Operation ID:** `startRequestShiftSlot`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`start_request_shift_slot`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `slot_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ShiftSlotStartPayload`.

```json
{
  "note": "example-value",
  "timezone": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated shift slot with attendance events.

```json
{
  "slot_id": "651d5e6f7a8b9c0d5e6f7a8b",
  "status": "in_progress",
  "checked_in_at": "2026-11-10T21:58:32Z",
  "confirmed_by_client": true
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
curl -X POST 'https://api.example.com/api/shift-slots/{slot_id}/start' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
