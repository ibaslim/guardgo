# Get system brand asset image

`GET /api/s/static/system/{id}`

Stream platform brand logos, icons, and system graphics by asset ID.

### Access
- Requires valid session cookie (`access_token`).

### Input
- **Path Parameter**:
  - `id` *(string, required)*: System asset identifier.

### Output
- Binary image stream.

## At a glance

- **Operation ID:** `getSystemImageResource`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_system_resource`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Binary image file response.

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
curl -X GET 'https://api.example.com/api/s/static/system/{id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
