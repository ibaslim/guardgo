# Report guard leave range

`POST /api/shift-guard-leaves`

Record a future guard leave window and apply it across scheduled shift slots.

## At a glance

- **Operation ID:** `reportShiftGuardLeave`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`report_shift_guard_leave`)
- **Success status:** `201`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `ShiftGuardLeaveCreatePayload`.

```json
{
  "guard_tenant_id": "507f1f77bcf86cd799439011",
  "start_at_utc": "example-value",
  "end_at_utc": "example-value",
  "reason": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Created shift guard leave record.

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
curl -X POST 'https://api.example.com/api/shift-guard-leaves' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
