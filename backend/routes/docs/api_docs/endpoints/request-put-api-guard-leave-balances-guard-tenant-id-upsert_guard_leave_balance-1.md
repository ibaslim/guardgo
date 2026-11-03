# Update guard leave quota

`PUT /api/guard-leave-balances/{guard_tenant_id}`

Update the leave quota policy for a direct or provider-owned guard tenant.

## At a glance

- **Operation ID:** `upsertGuardLeaveBalance`
- **Tag / Domain:** `Client Requests`
- **Source:** `backend/routes/request_routes.py` (`upsert_guard_leave_balance`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `guard_tenant_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `GuardLeavePolicyUpsertPayload`.

```json
{
  "annual_paid_leave_days": 1.0,
  "annual_unpaid_leave_days": 1.0,
  "carry_forward_days": 1.0,
  "effective_from": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Updated leave policy and balance snapshot.

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
curl -X PUT 'https://api.example.com/api/guard-leave-balances/{guard_tenant_id}' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
