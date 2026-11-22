# Reject guard status change request

`POST /api/guard-status-requests/{request_id}/reject`

Platform admin rejection of a pending guard status change request.

### Access
- **Role Required**: `admin`.

### Input
- **Path Parameter**:
  - `request_id` *(string, required)*: Status change request ID.
- **JSON Body (`GuardStatusRequestDecisionPayload`)**:
  - `comment` *(string, optional)*: Rejection reason communicated to service provider.

### Output
- Rejected request record.

## At a glance

- **Operation ID:** `rejectGuardStatusRequest`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`reject_guard_status_request`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `request_id` | `str` | Yes | `507f1f77bcf86cd799439011` |

## Request body

The request body is validated by `GuardStatusRequestDecisionPayload`.

```json
{
  "comment": "example-value"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Rejected guard status request confirmation.

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
curl -X POST 'https://api.example.com/api/guard-status-requests/{request_id}/reject' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
