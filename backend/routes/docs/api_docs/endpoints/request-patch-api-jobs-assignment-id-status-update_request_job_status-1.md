# Update job status

`PATCH /api/jobs/{assignment_id}/status`

Update assignment lifecycle status for accepted/ongoing/completed job flow.

## At a glance

- **Operation ID:** `updateRequestJobStatus`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`update_request_job_status`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `assignment_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `RequestAssignmentStatusUpdatePayload`.

```json
{
  "assignment_status": "example-value",
  "reason": "example-value",
  "slots_committed": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated assignment.

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
curl -X PATCH 'https://api.example.com/api/jobs/{assignment_id}/status' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
