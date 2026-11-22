# Publish request update

`POST /api/requests/{request_id}/publish-update`

Apply a material update to a live request and issue a fresh broadcast wave.

## At a glance

- **Operation ID:** `publishClientRequestUpdate`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`publish_client_request_update`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `request_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `RequestPublishUpdatePayload`.

```json
{
  "timezone": "example-value",
  "fulfillment_mode": "example-value",
  "site": "example-value",
  "requested_guard_type": "example-value",
  "requested_start_at": "example-value",
  "requested_end_at": "example-value",
  "request_expires_at": "example-value",
  "special_instructions": "example-value",
  "invoice_contract_type": "example-value",
  "invoice_cutoff_day": "example-value",
  "invoice_recipient_email": "alex.morgan@example.com",
  "max_match_results": 1
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated and republished client request.

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
curl -X POST 'https://api.example.com/api/requests/{request_id}/publish-update' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
