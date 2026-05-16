# Google Maps Geo Integration Plan

## Purpose

Replace the current mixed geo approach with a single Google Maps based location workflow for:

- client request site
- guard home/base location
- service provider head office
- service provider operating-region city rows

This plan supersedes the temporary URL/manual-coordinate direction. The current partial `geo-location-picker` work should be treated as disposable or transitional.

## Why This Direction

The current product already depends on coordinates for:

- request matching distance checks
- guard operational-radius matching
- service provider operating-region radius matching
- broadcast travel-policy review
- shift check-in geofence validation

Today:

- request site geo is captured
- guard home geo is not properly captured in the profile UI
- provider head office geo is not properly captured in the profile UI
- provider operating-region city geo is not properly captured in the profile UI

That means matching often falls back to province-level logic when precise distance should be used.

Google Maps is the recommended stack here because it gives:

- map rendering
- place search / autocomplete
- place details with geometry
- marker-based pin selection
- one vendor and one auth model for the whole workflow

## Recommended Google Maps Stack

Use the Maps JavaScript API with:

- `maps` library
- `places` library
- `marker` library

Recommended Google pieces:

- `google.maps.importLibrary(...)` based loading
- `PlaceAutocompleteElement`
- `AdvancedMarkerElement`

Official references:

- Load Maps JavaScript API: https://developers.google.com/maps/documentation/javascript/load-maps-js-api
- Place Autocomplete widget: https://developers.google.com/maps/documentation/javascript/place-autocomplete-new
- Places widgets reference: https://developers.google.com/maps/documentation/javascript/reference/3.60/places-widget
- Advanced markers: https://developers.google.com/maps/documentation/javascript/advanced-markers/add-marker
- API key security: https://developers.google.com/maps/api-security-best-practices

## Target UX

Every geo-enabled form should support the same flow:

1. User types a place or address.
2. Google autocomplete suggests a place.
3. User picks the place.
4. Map centers on the place.
5. Marker is placed.
6. Latitude/longitude are saved automatically.
7. Address fields are filled or confirmed.
8. User can drag or re-pin to refine location.

Manual lat/lng editing may remain as an advanced fallback, but should not be the primary path.

## Data Model Rules

### Client Request Site

Keep existing request storage:

- `site_snapshot.site_address.latitude`
- `site_snapshot.site_address.longitude`

No schema redesign needed here.

### Guard

Keep using:

- `profile.home_address.latitude`
- `profile.home_address.longitude`
- `profile.max_travel_radius_km`

No new backend field is required for guard geo. The UI must start populating the existing fields.

### Service Provider Head Office

Keep using:

- `profile.head_office_address.latitude`
- `profile.head_office_address.longitude`

No head-office coverage radius should be added.

### Service Provider Operating Regions

Coverage should remain on operating-region city entries, not on head office.

Each operating-region city entry should store:

- `city_code`
- `city`
- `coverage_radius_km`
- `latitude`
- `longitude`

This is the only required backend schema extension in the provider coverage model.

## Component Architecture

### 1. `GoogleMapsLoaderService`

Create a single loader service that:

- injects the Google Maps JavaScript API script once
- uses `loading=async`
- loads `maps`, `places`, and `marker`
- exposes a promise or observable when the API is ready

Responsibilities:

- avoid duplicate script injection
- centralize API key usage
- centralize API load errors

Suggested location:

- `client/src/app/shared/services/google-maps-loader.service.ts`

### 2. `GoogleMapsLocationPickerComponent`

Create one reusable standalone component for all forms.

Responsibilities:

- render autocomplete input
- render map
- render draggable marker
- emit selected address + lat/lng
- optionally emit normalized place metadata

Suggested API:

- inputs
  - `title`
  - `disabled`
  - `readonly`
  - `countryRestriction`
  - `initialLatitude`
  - `initialLongitude`
  - `initialDisplayAddress`
- outputs
  - `locationChange`
    - `latitude`
    - `longitude`
    - `formattedAddress`
    - `placeId`
    - `addressComponents`

Suggested location:

- `client/src/app/components/google-maps-location-picker/`

### 3. Optional thin `LocationSummary` helper

Use a small helper to map Google address components into existing form fields:

- street
- city
- province
- postal code
- country

Suggested location:

- `client/src/app/shared/helpers/google-maps-address.helper.ts`

## API Key / Config Plan

### Key Strategy

Use one browser-restricted Google Maps API key for the Angular app.

Restrictions:

- HTTP referrer restriction
- only the GuardGo web origins

Minimum enabled APIs:

- Maps JavaScript API
- Places API

Evaluate whether reverse-geocoding-on-pin requires enabling additional Google services during implementation. Do not assume extra APIs without verifying in the Google project console.

### Runtime Config

Do not hardcode the key in the component.

Preferred approach:

- expose a runtime frontend config value from backend or deployment config
- inject it through the existing app config flow if available

Possible paths:

- backend-served public config endpoint
- Angular runtime config object emitted into `index.html`

## Form Integration Plan

### Slice A. Request Form

Replace the current site-location block in:

- `client/src/app/pages/requests/requests.component.html`
- `client/src/app/pages/requests/requests.component.ts`

Behavior:

- autocomplete place search
- map + marker
- drag marker to refine site
- store final:
  - `google_maps_url` optional
  - `latitude`
  - `longitude`

Notes:

- request address fields should stay visible and editable
- picker should update them when a place is selected

### Slice B. Guard Profile

Add Google Maps picker to the Home Address section in:

- `client/src/app/pages/guard-setting/guard-setting.component.html`
- `client/src/app/pages/guard-setting/guard-setting.component.ts`

Behavior:

- select home/base location
- save:
  - `profile.home_address.latitude`
  - `profile.home_address.longitude`

Notes:

- operational radius remains separate
- matching should use home lat/lng + radius

### Slice C. Service Provider Head Office

Add Google Maps picker to Head Office Address in:

- `client/src/app/pages/service-provider-setting/service-provider-setting.component.html`
- `client/src/app/pages/service-provider-setting/service-provider-setting.component.ts`

Behavior:

- select head-office location
- save:
  - `profile.head_office_address.latitude`
  - `profile.head_office_address.longitude`

### Slice D. Service Provider Operating Region Cities

Add Google Maps picker inside each operating city row in:

- `client/src/app/pages/service-provider-setting/service-provider-setting.component.html`
- `client/src/app/pages/service-provider-setting/service-provider-setting.component.ts`

Behavior:

- each city row gets its own map-driven lat/lng
- save per city entry:
  - `latitude`
  - `longitude`
  - `coverage_radius_km`

Required UX shortcut:

- `Use Head Office As Operating Region`

This should:

- create or update an operating-region city entry
- copy province, city, lat, lng from head office
- leave only radius for the user to set or confirm

## Backend Plan

### 1. Extend Provider City Entry Normalization

Update provider normalization in:

- `backend/orion/api/interactive/tenant_manager/tenant_manager.py`

Current method:

- `_validate_and_normalize_provider_operating_regions(...)`

Add support for:

- `latitude`
- `longitude`

Validation rules:

- if one coordinate is present, both are required
- latitude must be `-90..90`
- longitude must be `-180..180`
- keep `coverage_radius_km >= 1`

### 2. Extend Provider Embedded Model

Update provider operating-region embedded structures in:

- `backend/orion/services/mongo_manager/shared_model/db_tenant_model.py`

Add `latitude` and `longitude` to the per-city entry structure actually used in normalized provider profile data.

If a dedicated city-entry embedded model does not yet exist, introduce one.

### 3. Matching Logic

Update provider matching in:

- `backend/orion/api/interactive/request_matching_manager/request_matching_manager.py`

Rules:

- when a provider operating city entry matches the request city, use that entry’s lat/lng
- if city-entry lat/lng are missing, fall back to head-office lat/lng
- if both are missing, preserve current fallback behavior

Matching precedence:

1. matching city-entry lat/lng
2. head-office lat/lng
3. province fallback

### 4. No Request-Side Schema Change

Request geo storage already exists and should remain unchanged.

## Validation Rules

### Request

- city and province required
- lat/lng optional in draft
- lat/lng strongly recommended before publish
- if publish without geo, current review/fallback rules may still apply

### Guard

- address fields required
- lat/lng optional for backward compatibility during rollout
- if missing, matching continues to fall back

### Provider Head Office

- address fields required
- lat/lng optional for backward compatibility

### Provider Operating City Entries

Recommended rollout rule:

- new or edited entries must provide lat/lng
- existing legacy entries without lat/lng remain accepted until touched

This avoids breaking old data immediately.

## Migration Strategy

Do not hard fail old records on deployment.

Migration approach:

- keep legacy providers/guards usable
- when a profile is edited, normalize and require geo for newly edited provider city entries
- add reporting later for missing geo coverage

Admin cleanup report should eventually identify:

- guards missing home geo
- providers missing head-office geo
- provider city entries missing coverage geo

## Testing Plan

### Frontend

Test these flows:

- request site selection by autocomplete
- request site re-pin on map
- guard home location selection
- provider head-office selection
- provider operating-region city selection
- head-office-to-region shortcut
- editing existing data with preloaded marker

### Backend

Add or update tests for:

- provider operating-region normalization with lat/lng
- validation failures for partial coordinates
- provider matching uses city-entry geo before head-office geo
- fallback still works for legacy records without geo

Relevant existing test areas:

- `backend/tests/test_request_matching_manager.py`
- `backend/tests/test_request_manager_matching_preview.py`
- `backend/tests/test_tenant_manager_upsert_edges.py`

## Delivery Slices

### Slice 1. Infrastructure

- Google Maps loader service
- runtime API key config
- reusable location picker component

### Slice 2. Request Form

- replace current site geo UI
- keep existing backend payload

### Slice 3. Guard Profile

- save home lat/lng
- preserve radius logic

### Slice 4. Provider Head Office + Region Cities

- head-office geo
- per-city geo
- head-office shortcut

### Slice 5. Backend Matching / Validation

- provider city-entry geo validation
- matching precedence updates

### Slice 6. QA

- regression on request publish
- guard matching
- provider matching
- travel-policy review behavior

## Recommendation on Current Partial Work

The current temporary geo work should not be expanded further.

Recommended next action:

1. stop wiring more URL/manual geo flows
2. approve this Google Maps plan
3. start with `Slice 1` only

That keeps the final architecture clean and avoids rework.
