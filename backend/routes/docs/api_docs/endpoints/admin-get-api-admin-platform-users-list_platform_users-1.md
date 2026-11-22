# List platform admin users

`GET /api/admin/platform-users`

Retrieve all internal platform administrative users across all statuses (active, invited, suspended, deleted).

### Access
- **Role Required**: `admin`.

### Output
- Array of user profiles detailing email, full name, role, account status, license grants, and invite state.

## At a glance

- **Operation ID:** `listPlatformUsers`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`list_platform_users`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

This endpoint does not declare a JSON request body.

## Response

List of platform administrative user accounts.

```json
[
  {
    "id": "651f7a8b9c0d7e8f9a0b1c2d",
    "username": "sarah.compliance",
    "email": "sarah.c@guardgo.ca",
    "role": "compliance_admin",
    "status": "active",
    "invite_pending": false
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
curl -X GET 'https://api.example.com/api/admin/platform-users' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
