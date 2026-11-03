# Save guard pay rates

`PUT /api/billing/guards/{guard_id}`

Upsert pay rates by province and city for a specific guard (admin only).

## At a glance

- **Operation ID:** `save_guard_override_rates`
- **Tag / Domain:** `Billing`
- **Source:** `backend/routes/billing_routes.py` (`save_guard_override_rates`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_id` | `str` | No | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `List[Dict[str, Any]]`.

```json
{
  "example_field": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Successful response.

```json
[
  {
    "region_code": "ON",
    "city_code": "TORONTO",
    "standard_rate": 28.5,
    "weekend_rate": 32.0,
    "holiday_rate": 42.75,
    "currency": "CAD"
  }
]
```

## Errors

- `400 Bad Request` — input is invalid or a path identifier has the wrong format.
- `401 Unauthorized` — authentication is missing, expired, or invalid.
- `403 Forbidden` — the authenticated user does not have the required role or status.
- `404 Not Found` — the requested resource does not exist.
- `422 Unprocessable Entity` — FastAPI validation failed before the handler ran.

## cURL

```bash
curl -X PUT 'https://api.example.com/api/billing/guards/{guard_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
