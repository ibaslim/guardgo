# Google Maps Integration Plan

## Scope

This plan defines where Google Maps APIs should be used for request matching and broadcast eligibility.

## Principles

1. Use Google Maps only where native data quality is insufficient.
2. Keep all persisted distances in kilometers (`km`) as canonical storage.
3. Separate expensive API calls from hot-path request processing via caching.

## APIs to Use

1. Geocoding API
- Convert normalized address payloads to latitude/longitude.
- Use at profile save time for:
  - guard home address
  - service provider operating region anchors
  - client request site address

2. Distance Matrix API
- Use only for route-aware distance checks where straight-line distance is not enough.
- Primary fallback remains Haversine distance when API is unavailable.

## Matching Flow (Recommended)

1. Pre-filter by province/territory.
2. Compute direct distance (Haversine) using stored coordinates.
3. If `GOOGLE_MAPS_DISTANCE_MATRIX_ENABLED=1` and precision mode is needed:
  - compute route distance/time for top candidate subset only.
4. Apply radius and broadcast tier policy.

## Caching Strategy

1. Cache geocode results by normalized address hash.
2. Cache distance matrix responses by origin/destination hash and travel mode.
3. Define TTL to balance freshness and cost.

## Failure/Fallback Behavior

1. If geocode is missing or API fails:
  - mark candidate evaluation as `missing_geo`
  - fallback to province-only mode when allowed.
2. If distance matrix is disabled/unavailable:
  - use Haversine distance only.

## Environment Flags

Add to `.env` (defaults disabled):

```bash
GOOGLE_MAPS_API_KEY=
GOOGLE_MAPS_GEOCODING_ENABLED=0
GOOGLE_MAPS_DISTANCE_MATRIX_ENABLED=0
```

## Audit/Observability

For every match decision, include:

1. `distance_km`
2. `radius_km`
3. `distance_source` (`haversine` | `google_distance_matrix` | `province_fallback`)
4. `reason_code`

## Security and Cost Control

1. Restrict API keys by backend origin and service scope.
2. Apply quotas and rate limiting.
3. Log API usage metrics and error rates.
