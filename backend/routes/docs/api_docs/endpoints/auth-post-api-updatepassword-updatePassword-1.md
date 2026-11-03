# Reset password with reset token

`POST /api/updatePassword`

Set a new password using a verified password reset token.

### Workflow
- Validates password reset token validity and expiration.
- Hashes new password securely with argon2/bcrypt.
- Invalidates reset token and all existing user sessions.

### Input (`ResetPassword`)
- `token` *(string, required)*: Valid password reset token from reset email.
- `password` *(string, required)*: New plaintext password.

### Output
- Status confirmation of successful password update.

## At a glance

- **Operation ID:** `updateUserPassword`
- **Tag / Domain:** `Authentication & Session`
- **Source:** `backend/routes/auth_routes.py` (`updatePassword`)
- **Success status:** `200`
- **Authentication:** Authentication is not required (Public endpoint).

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `data` | `ResetPassword` | Yes | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Password update confirmation result.

```json
{
  "message": "Password updated successfully"
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
curl -X POST 'https://api.example.com/api/updatePassword' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
