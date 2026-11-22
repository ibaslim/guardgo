# Delete expired pending guard invite

`DELETE /api/sp/guards/pending/{guard_tenant_id}`

Remove an unaccepted or expired guard invitation and purge pending tenant records.

### Access
- **Role Required**: `sp_admin`.

### Input
- **Path Parameter**:
  - `guard_tenant_id` *(string, required)*: Pending guard tenant ID.

### Output
- Deletion confirmation message.

## At a glance

- **Operation ID:** `deleteExpiredPendingGuardInvite`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`delete_expired_pending_guard_invite`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Confirmation of pending guard invitation deletion.

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
curl -X DELETE 'https://api.example.com/api/sp/guards/pending/{guard_tenant_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
