# Log out and destroy session

`POST /api/logout`

Terminate the active user session and remove authentication credentials.

### Workflow
- Invalidates the session entry in the session cache/store.
- Deletes the `access_token` HTTP-only cookie on the client.

### Input
- **Cookie / Header**: Caller's current session identifier.

### Output
- `{"detail": "Logged out"}`

## At a glance

- **Operation ID:** `logoutUser`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`logout`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

Logout confirmation message.

```json
{
  "detail": "Logged out"
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
curl -X POST 'https://api.example.com/api/logout' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
