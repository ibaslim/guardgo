# Get assignee invoice

`GET /api/my-invoices/{invoice_id}`

Return a single guard or service-provider invoice detail derived from the request invoice share for that assignee.

## At a glance

- **Operation ID:** `getMyInvoiceById`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`get_my_invoice`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `invoice_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Assignee invoice detail.

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
curl -X GET 'https://api.example.com/api/my-invoices/{invoice_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
