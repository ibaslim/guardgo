# Get billing location metadata

`GET /api/billing/metadata`

Returns province and city metadata used in billing configuration tables.

## At a glance

- **Operation ID:** `get_billing_location_metadata`
- **Tag / Domain:** `Billing`
- **Source:** `backend/routes/billing_routes.py` (`get_billing_location_metadata`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Successful response.

```json
{
  "provinces": [
    "ON",
    "BC",
    "AB",
    "QC"
  ],
  "citiesByProvince": {
    "ON": [
      "TORONTO",
      "OTTAWA",
      "MISSISSAUGA",
      "HAMILTON"
    ],
    "BC": [
      "VANCOUVER",
      "VICTORIA",
      "SURREY"
    ]
  }
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
curl -X GET 'https://api.example.com/api/billing/metadata' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
