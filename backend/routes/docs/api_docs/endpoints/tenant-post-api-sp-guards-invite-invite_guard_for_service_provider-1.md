# Invite guard under service provider

`POST /api/sp/guards/invite`

Send an onboarding invitation to a licensed security guard to join the service provider's managed guard roster.

### Workflow
- Creates a pending guard tenant linked to the caller's service provider.
- Generates an invite token and sends an onboarding email to the guard.

### Access
- **Role Required**: `sp_admin` (Service Provider Administrator).

### Input (`ServiceProviderGuardInviteRequest`)
- `email` *(email, required)*: Guard's email address.

### Output
- Created guard invite record with expiration timestamp and pending activation status.

## At a glance

- **Operation ID:** `inviteGuardForServiceProvider`
- **Tag / Domain:** `Service Provider Guards`
- **Source:** `backend/routes/tenant_routes.py` (`invite_guard_for_service_provider`)
- **Success status:** `201`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `ServiceProviderGuardInviteRequest`.

```json
{
  "email": "alex.morgan@example.com"
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Created guard invitation details.

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
curl -X POST 'https://api.example.com/api/sp/guards/invite' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
