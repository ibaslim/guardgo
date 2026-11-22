# Download tenant government identity document

`GET /api/tenant/files/identity/{file_id}`

Stream encrypted government identification document (passport, driver license) for authorized profile inspection.

### Access
- Verifies ownership or compliance admin privilege via session cookie.

### Input
- **Path Parameter**:
  - `file_id` *(string, required)*: Stored identity document ID.

### Output
- Binary document stream (PDF, JPEG, PNG).

## At a glance

- **Operation ID:** `getTenantIdentityDocument`
- **Tag / Domain:** `Public & System Metadata`
- **Source:** `backend/routes/public_api_routes.py` (`get_tenant_identity_document`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `file_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Identity document binary stream.

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
curl -X GET 'https://api.example.com/api/tenant/files/identity/{file_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
