# Roster provider guards for a shift

`POST /api/shifts/{shift_id}/roster`

Assign named active service-provider guards to provider-backed shift slots.

## At a glance

- **Operation ID:** `rosterRequestShift`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`roster_request_shift`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `shift_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ProviderRosterPayload`.

```json
{
  "assignments": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated shift with rostered slots.

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
curl -X POST 'https://api.example.com/api/shifts/{shift_id}/roster' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
