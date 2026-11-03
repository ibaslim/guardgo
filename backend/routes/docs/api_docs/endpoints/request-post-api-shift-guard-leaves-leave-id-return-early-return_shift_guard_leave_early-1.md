# Return guard from leave early

`POST /api/shift-guard-leaves/{leave_id}/return-early`

End an active guard leave early and reconcile future unstaffed replacements.

## At a glance

- **Operation ID:** `returnShiftGuardLeaveEarly`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`return_shift_guard_leave_early`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `leave_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ShiftGuardLeaveReturnPayload`.

```json
{
  "note": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated shift guard leave record.

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
curl -X POST 'https://api.example.com/api/shift-guard-leaves/{leave_id}/return-early' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
