# Create provider payout adjustment

`POST /api/payout-invoices/{invoice_id}/adjustments`

Apply a platform-tracked payout adjustment to a service-provider payout invoice.

## At a glance

- **Operation ID:** `createPlatformPayoutAdjustment`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`create_platform_payout_adjustment`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `invoice_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `RequestPayoutAdjustmentCreatePayload`.

```json
{
  "amount": 1.0,
  "reason": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated platform payout invoice detail.

```json
{
  "items": [
    {
      "invoice_id": "INV-2026-00841",
      "invoice_number": "GG-841",
      "subtotal": 1200.0,
      "tax": 156.0,
      "total": 1356.0,
      "currency": "CAD",
      "status": "approved",
      "due_date": "2026-11-25"
    }
  ],
  "total": 1
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
curl -X POST 'https://api.example.com/api/payout-invoices/{invoice_id}/adjustments' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
