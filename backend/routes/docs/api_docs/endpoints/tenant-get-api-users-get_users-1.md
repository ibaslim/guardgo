# Get all users in tenant

`GET /api/users`

Retrieve all users associated with the current tenant.

## At a glance

- **Operation ID:** `getUsers`
- **Tag / Domain:** `Users`
- **Source:** `backend/routes/tenant_routes.py` (`get_users`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

List of users in the tenant.

```json
[
  {
    "id": "651a2b3c4d5e6f7a8b9c0d1e",
    "username": "guard_mvance",
    "email": "marcus.vance@example.com",
    "role": "guard_admin",
    "status": "active"
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
curl -X GET 'https://api.example.com/api/users' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
