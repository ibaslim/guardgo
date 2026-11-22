# Delete tenant security license document

`DELETE /api/tenant/files/security-license/{file_id}`

Delete a security license document for the current tenant.

## At a glance

- **Operation ID:** `deleteTenantSecurityLicenseDocument`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`delete_tenant_security_license_document`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `file_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Successful response.

```json
{
  "detail": "Resource deleted successfully"
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
curl -X DELETE 'https://api.example.com/api/tenant/files/security-license/{file_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
