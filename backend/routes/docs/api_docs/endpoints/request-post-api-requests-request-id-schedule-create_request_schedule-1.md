# Create or replace request schedule

`POST /api/requests/{request_id}/schedule`

Create or replace the schedule template for a request and regenerate future shift instances.

## At a glance

- **Operation ID:** `upsertRequestSchedule`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`create_request_schedule`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `request_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `RequestScheduleUpsertPayload`.

```json
{
  "timezone": "example-value",
  "schedule_type": "example-value",
  "start_date": "example-value",
  "end_date": "example-value",
  "start_time_local": "example-value",
  "end_time_local": "example-value",
  "recurrence_days": "example-value",
  "generation_horizon_days": 1,
  "roster_due_offset_minutes": 1,
  "unavailable_cutoff_minutes": 1,
  "late_grace_minutes": 1,
  "no_show_cutoff_minutes": 1,
  "checkin_geofence_meters": 1,
  "active": true
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated request schedule.

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
curl -X POST 'https://api.example.com/api/requests/{request_id}/schedule' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
