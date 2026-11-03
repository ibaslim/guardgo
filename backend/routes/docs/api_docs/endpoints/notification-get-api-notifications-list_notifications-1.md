# List notifications

`GET /api/notifications`

Return paginated notifications for the current authenticated user.

## At a glance

- **Operation ID:** `listNotifications`
- **Tag / Domain:** `Notifications`
- **Source:** `backend/routes/notification_routes.py` (`list_notifications`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

| Name | Type | Required | Example |
| --- | --- | --- | --- |
| `page` | `int` | No | `1` |
| `rows` | `int` | No | `1` |
| `status` | `str` | No | `example-value` |

## Request body

This endpoint does not declare a JSON request body.

## Response

Paginated notifications.

```json
{
  "items": [
    {
      "id": "651e6f7a8b9c0d6e7f8a9b0c",
      "title": "Shift Assignment Confirmed",
      "message": "You have been assigned to shift on 2026-11-10 at Metro Square.",
      "read": false,
      "created_at": "2026-11-02T16:00:00Z"
    }
  ],
  "total": 1,
  "unread_count": 3
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
curl -X GET 'https://api.example.com/api/notifications' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
