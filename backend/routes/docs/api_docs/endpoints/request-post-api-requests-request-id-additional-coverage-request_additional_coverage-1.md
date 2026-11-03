# Request additional coverage

`POST /api/requests/{request_id}/additional-coverage`

Increase open staffing slots for a live request and issue a fresh broadcast wave.

## At a glance

- **Operation ID:** `requestAdditionalCoverage`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`request_additional_coverage`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `request_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `RequestAdditionalCoveragePayload`.

```json
{
  "additional_slots": 1,
  "request_expires_at": "example-value",
  "max_match_results": 1
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Client request with additional coverage issued.

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
curl -X POST 'https://api.example.com/api/requests/{request_id}/additional-coverage' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
