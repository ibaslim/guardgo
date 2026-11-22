# Refresh active session token

`POST /api/token/refresh`

Generate a renewed JWT access token using the caller's active bearer token or session cookie.

### Workflow
- Extracts caller's current token from `Authorization` header or HTTP-only `access_token` cookie.
- Validates session activity in Redis/database.
- Extends session lifetime and issues a freshly signed JWT token.

### Input
- **Header / Cookie**: `Authorization: Bearer <token>` or `access_token` cookie.

### Output
- `access_token` *(string)*: Refreshed JWT access token.
- `token_type` *(string)*: `"bearer"`.

## At a glance

- **Operation ID:** `refreshAccessToken`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`refresh_token`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Renewed access token with extended session validity.

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.refreshed...",
  "token_type": "bearer"
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
curl -X POST 'https://api.example.com/api/token/refresh' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
