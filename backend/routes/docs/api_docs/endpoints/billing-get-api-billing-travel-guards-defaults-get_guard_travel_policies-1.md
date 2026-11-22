# Get guard travel policy defaults

`GET /api/billing/travel/guards/defaults`

Returns travel pricing and auto-match defaults by province and city for direct guards (admin only).

## At a glance

- **Operation ID:** `get_guard_travel_policies`
- **Tag / Domain:** `Billing`
- **Source:** `backend/routes/billing_routes.py` (`get_guard_travel_policies`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

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
curl -X GET 'https://api.example.com/api/billing/travel/guards/defaults' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
