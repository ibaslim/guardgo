# Approve tenant activation

`PATCH /api/tenants/{tenant_id}/approve`

Record an approval. Tenant activates only after required approvals are reached.

## At a glance

- **Operation ID:** `approveTenant`
- **Tag / Domain:** `Tenant`
- **Source:** `backend/routes/tenant_routes.py` (`approve_tenant`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Updated tenant status.

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
curl -X PATCH 'https://api.example.com/api/tenants/{tenant_id}/approve' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
