# Demo environment quick login

`POST /api/token/demo`

Authenticate using pre-configured demonstration credentials defined in the application environment.

### Purpose
- Fast automated or manual access for local development, staging, or testing.
- Reads `DEMO_USERNAME` and `DEMO_PASSWORD` from server configuration.

### Input
- None (credentials are sourced from server environment).

### Output
- Standard login dictionary containing `access_token`, `token_type`, and session cookie.

## At a glance

- **Operation ID:** `loginDemoUser`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`token_demo`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Demo user access token and session cookie.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.demo...",
  "token_type": "bearer",
  "twofa_required": false
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
curl -X POST 'https://api.example.com/api/token/demo' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
