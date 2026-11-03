# Update request draft

`PATCH /api/requests/{request_id}`

Update request content while the request is still editable (draft).

## At a glance

- **Operation ID:** `updateClientRequest`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`update_client_request`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `request_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ClientRequestUpdatePayload`.

```json
{
  "title": "example-value",
  "timezone": "example-value",
  "fulfillment_mode": "example-value",
  "site": "example-value",
  "requested_guard_type": "example-value",
  "guards_required": "example-value",
  "requested_start_at": "example-value",
  "requested_end_at": "example-value",
  "request_expires_at": "example-value",
  "special_instructions": "example-value",
  "invoice_contract_type": "example-value",
  "invoice_cutoff_day": "example-value",
  "invoice_recipient_email": "alex.morgan@example.com",
  "max_match_results": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated client request draft.

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
curl -X PATCH 'https://api.example.com/api/requests/{request_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
