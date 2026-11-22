# Create client request

`POST /api/requests`

Create a new client request and generate a candidate matching snapshot.

## At a glance

- **Operation ID:** `createClientRequest`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`create_client_request`)
- **Success status:** `201`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `ClientRequestCreatePayload`.

```json
{
  "title": "example-value",
  "timezone": "example-value",
  "fulfillment_mode": "example-value",
  "client_tenant_id": "507f1f77bcf86cd799439011",
  "site_index": "example-value",
  "site": "example-value",
  "requested_guard_type": "example-value",
  "guards_required": 1,
  "requested_start_at": "example-value",
  "requested_end_at": "example-value",
  "request_expires_at": "example-value",
  "special_instructions": "example-value",
  "invoice_contract_type": "example-value",
  "invoice_cutoff_day": "example-value",
  "invoice_recipient_email": "alex.morgan@example.com",
  "max_match_results": 1,
  "commit": true
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Created client request.

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
curl -X POST 'https://api.example.com/api/requests' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
