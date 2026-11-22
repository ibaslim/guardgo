# Get guard document dropdown metadata

`GET /api/public/guard-metadata`

Retrieve standard options and enums required for security guard profile setup and document uploads.

### Content Provided
- List of countries and Canadian provinces.
- Major Canadian cities grouped by province.
- Accepted government identity document types (Passport, Driver's License, PR Card).
- Security license classification codes.
- Training certification types and recognized issuing authorities.
- Police clearance authority options.

### Input
- None.

### Output
- Dictionary mapping metadata categories to structured choice lists.

## At a glance

- **Operation ID:** `getGuardMetadata`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_guard_metadata`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Guard document dropdown options and metadata dictionaries.

```json
{
  "countries": [
    "Canada"
  ],
  "canadianProvinces": [
    {
      "code": "ON",
      "name": "Ontario"
    },
    {
      "code": "BC",
      "name": "British Columbia"
    }
  ],
  "identityDocumentTypes": [
    {
      "code": "PASSPORT",
      "label": "Passport"
    },
    {
      "code": "DRIVERS_LICENSE",
      "label": "Driver's License"
    }
  ],
  "securityLicenseTypes": [
    {
      "code": "ONTARIO_SECURITY_GUARD",
      "label": "Ontario Security Guard License"
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
curl -X GET 'https://api.example.com/api/public/guard-metadata' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
