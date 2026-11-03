# Unlink guard from service provider

`POST /api/guards/{guard_tenant_id}/unlink-service-provider`

Detach a guard from a service provider company, returning the guard to independent status.

### Access
- **Role Required**: `admin`.

### Input
- **Path Parameter**:
  - `guard_tenant_id` *(string, required)*: Guard tenant ID.
- **JSON Body (`GuardServiceProviderUnlinkPayload`)**:
  - `reason` *(string, required, min 3 chars)*: Audit explanation for unlinking.

### Output
- Updated guard tenant record with nullified service provider association.

## At a glance

- **Operation ID:** `unlinkGuardFromServiceProvider`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`unlink_guard_from_service_provider`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `GuardServiceProviderUnlinkPayload`.

```json
{
  "reason": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated guard tenant record without provider association.

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
curl -X POST 'https://api.example.com/api/guards/{guard_tenant_id}/unlink-service-provider' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
