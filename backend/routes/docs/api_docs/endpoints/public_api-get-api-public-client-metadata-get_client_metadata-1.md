# Get client profile dropdown metadata

`GET /api/public/client-metadata`

Retrieve standard metadata and choice options for client profile setup and security request forms.

### Content Provided
- Countries, Canadian provinces, and supported cities.
- Billing region choices for pricing calculation.
- Site categories (e.g. Commercial, Residential, Construction, Event, Retail, Industrial).
- Guard service types (e.g. Static Guard, Concierge, Patrolling, Armed/Cash-in-Transit).
- Client organization types (Individual vs Corporate).

### Input
- None.

### Output
- Dictionary containing client option lists for form rendering.

## At a glance

- **Operation ID:** `getClientMetadata`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_client_metadata`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Client profile metadata and form option dictionaries.

```json
{
  "siteTypeOptions": [
    {
      "value": "commercial",
      "label": "Commercial Building"
    },
    {
      "value": "residential",
      "label": "Residential Complex"
    }
  ],
  "guardTypeOptions": [
    {
      "value": "static",
      "label": "Static Guard"
    },
    {
      "value": "patrol",
      "label": "Patrolling Guard"
    }
  ]
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
curl -X GET 'https://api.example.com/api/public/client-metadata' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
