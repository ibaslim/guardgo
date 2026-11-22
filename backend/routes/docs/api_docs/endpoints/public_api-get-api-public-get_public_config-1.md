# Get public system configuration

`GET /api/public`

Retrieve public platform branding, system identity, contact details, and feature toggles.

### Workflow
- Serves initialization configuration needed by client frontends prior to authentication.
- Returns application name, logo URLs, and support coordinates.

### Input
- None (public endpoint).

### Output
- System configuration dictionary with public properties.

## At a glance

- **Operation ID:** `getPublicConfig`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_public_config`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Public configuration values used at frontend startup.

```json
{
  "name": "GuardGo Security Platform",
  "version": "1.0.0",
  "logo_url": "/api/s/static/system/logo-main",
  "support_email": "support@guardgo.ca",
  "maintenance_mode": false
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
curl -X GET 'https://api.example.com/api/public' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
