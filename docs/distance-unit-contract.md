# Distance Unit Contract (Phase 0)

## Objective

Prevent unit confusion for radius, distance filtering, and notifications across guard, service provider, and client request workflows.

## Canonical Storage Rule

All persisted distance values are stored in kilometers.

- Guard: `max_travel_radius_km`
- Service provider operating region: `coverage_radius_km`
- Matching calculations: canonical `distance_km`

Miles are a display/input preference only.

## Conversion Formula

- `km = mi * 1.60934`
- `mi = km / 1.60934`

## Precision Rule

- Storage precision: 2 decimals in km.
- Display precision: 1 decimal for km and mi.

## API Contract Rule

When returning distance-aware responses, include explicit unit-safe fields where practical:

- `distance_km`
- `distance_mi`
- `radius_km`
- `radius_mi`

Do not return ambiguous values without unit suffix or field naming.

## Fallback Rule (Missing Geodata)

If precise distance cannot be computed (missing coordinates), mark the decision as unverified and use province-level fallback matching.

Suggested reason code values:

- `within_radius`
- `outside_radius`
- `province_mismatch`
- `missing_geo`

## UI Rule

- Every distance label must show unit suffix (`km` or `mi`).
- Prefer dual-display where confusion is possible (for example: `12.0 km (7.5 mi)`).
- User preference controls primary display unit.

## Google Maps Rule

- Google Maps APIs should be used only for features that need geocoding or route-aware distance accuracy.
- Google Maps usage must still output and persist canonical kilometer fields.
- See the implementation blueprint in `docs/google-maps-integration-plan.md`.
