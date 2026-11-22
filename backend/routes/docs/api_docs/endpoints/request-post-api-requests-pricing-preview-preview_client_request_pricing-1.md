# Preview request pricing and invoicing

`POST /api/requests/pricing-preview`

Return client charge estimates and invoice settings for a request before saving it.

## At a glance

- **Operation ID:** `previewClientRequestPricing`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`preview_client_request_pricing`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `RequestPricingPreviewPayload`.

```json
{
  "fulfillment_mode": "example-value",
  "client_tenant_id": "507f1f77bcf86cd799439011",
  "site_index": "example-value",
  "site": "example-value",
  "guards_required": 1,
  "requested_start_at": "example-value",
  "requested_end_at": "example-value",
  "invoice_contract_type": "example-value",
  "invoice_cutoff_day": "example-value",
  "invoice_recipient_email": "alex.morgan@example.com"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Pricing and invoicing preview.

```json
{
  "estimated_hours": 80.0,
  "base_rate_per_hour": 32.5,
  "holiday_rate_per_hour": 48.75,
  "travel_allowance": 120.0,
  "subtotal": 2720.0,
  "tax": 353.6,
  "estimated_total": 3073.6,
  "currency": "CAD"
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
curl -X POST 'https://api.example.com/api/requests/pricing-preview' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
