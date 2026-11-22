# Preview candidate matching

`POST /api/request-matching/preview`

Run province + radius eligibility matching preview for guards or service providers.

## At a glance

- **Operation ID:** `previewRequestMatching`
- **Tag / Domain:** `Request Matching`
- **Source:** `backend/routes/request_matching_routes.py` (`preview_request_matching`)
- **Success status:** `200`
- **Authentication:** Authentication is required unless this endpoint is explicitly documented as public.

## Parameters

This endpoint does not define ordinary path, query, or form parameters.

## Request body

The request body is validated by `RequestMatchingPreviewPayload`.

```json
{
  "target_type": "example-value",
  "site_address": "example-value",
  "requested_guard_type": "example-value",
  "requested_start_at": "example-value",
  "requested_end_at": "example-value",
  "max_results": 1,
  "fallback_to_province_when_missing_geo": true
}
```

> The exact fields, validation rules, enum values, and generated request example are available in Swagger under **Request body**.

## Response

Reason-coded match candidates with distance and radius in km/mi.

```json
{
  "candidates": [
    {
      "guard_tenant_id": "651a2b3c4d5e6f7a8b9c0d2f",
      "name": "Marcus Vance",
      "distance_km": 8.4,
      "eligible": true,
      "match_score": 96.5,
      "reasons": [
        "VALID_LICENSE",
        "WITHIN_RADIUS",
        "AVAILABLE"
      ]
    }
  ],
  "total_candidates": 1
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
curl -X POST 'https://api.example.com/api/request-matching/preview' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer <access-token>'
```

## Notes

Use the generated OpenAPI schema at `/openapi.json` as the executable contract. Examples in this document are safe illustrative values and must be replaced with real identifiers and credentials.
