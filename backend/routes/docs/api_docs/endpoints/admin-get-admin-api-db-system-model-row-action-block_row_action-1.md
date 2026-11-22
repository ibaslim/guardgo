# Validate system setting action restriction

`GET /admin/api/db_system_model/row-action`

Internal administration endpoint that guards protected database system records against unauthorized actions.

### Workflow
- Checks the requested action name against restricted operations.
- Disallows deletion of critical system configuration settings (`403 Forbidden`).

### Input
- **Query Parameter**:
  - `name` *(string, required)*: The proposed database table row action.

### Output
- Status message confirming whether the action is permitted.

## At a glance

- **Operation ID:** `blockSystemRowAction`
- **Tag / Domain:** `Platform Administration`
- **Source:** `backend/routes/admin_routes.py` (`block_row_action`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `name` | `str` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Validation result message for the row action.

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
curl -X GET 'https://api.example.com/admin/api/db_system_model/row-action' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
