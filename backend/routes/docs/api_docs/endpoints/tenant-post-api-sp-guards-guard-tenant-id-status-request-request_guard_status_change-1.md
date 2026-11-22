# Request guard status change (activation / deactivation)

`POST /api/sp/guards/{guard_tenant_id}/status-request`

Submit a formal status change request to platform compliance admins to activate or deactivate a guard.

### Workflow
- For `action='deactivate'`, a mandatory justification reason must be supplied.
- For `action='activate'`, reason is optional.
- A platform compliance administrator must approve the request before the status changes.

### Access
- **Role Required**: `sp_admin`.

### Input
- **Path Parameter**:
  - `guard_tenant_id` *(string, required)*: Guard tenant ID.
- **JSON Body (`ServiceProviderGuardStatusRequestPayload`)**:
  - `action` *(string, required)*: Either `"activate"` or `"deactivate"`.
  - `reason` *(string, optional/required for deactivate)*: Business reason for the status request.

### Output
- Created guard status change request record with `status: pending`.

## At a glance

- **Operation ID:** `requestGuardStatusChange`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`request_guard_status_change`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `ServiceProviderGuardStatusRequestPayload`.

```json
{
  "action": "example-value",
  "reason": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Created status change request record.

```json
{
  "items": [
    {
      "guard_tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
      "name": "Marcus Vance",
      "email": "marcus.vance@example.com",
      "status": "active",
      "operational_region_code": "ON",
      "operational_city_code": "TORONTO",
      "max_travel_radius_km": 35.0
    }
  ],
  "total": 1,
  "page": 1,
  "rows": 20
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
curl -X POST 'https://api.example.com/api/sp/guards/{guard_tenant_id}/status-request' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
