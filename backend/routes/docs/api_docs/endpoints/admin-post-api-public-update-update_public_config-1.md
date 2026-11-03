# Update public configuration settings

`POST /api/public/update`

Update global system-wide configuration parameters including brand identity, contact info, and public feature toggles.

### Access
- **Role Required**: `admin` (Platform Super Admin).
- **Status**: `ACTIVE`.

### Input (`config_data`)
- Key-value configuration dictionary specifying updated system parameters.

### Output
- The updated system configuration dictionary.

## At a glance

- **Operation ID:** `updatePublicConfig`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`update_public_config`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `param` | `config_data` | Yes | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Updated system configuration object.

```json
{
  "message": "Operation completed successfully",
  "status": "success"
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
curl -X POST 'https://api.example.com/api/public/update' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
