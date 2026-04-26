# Request Fulfillment Phases

This document locks the Phase 0 business rules and the Phase 1 data-contract changes for request fulfillment.

## Phase 0 Rules

- Service-provider-owned guards are excluded from direct client matching for individual guard fulfillment.
- Individual guard eligibility must consider weekly availability.
- Travel pricing must be configured by city with region fallback and must remain separate from raw eligibility checks.
- Request notifications/offers must move to wave-based dispatch instead of notifying every eligible candidate at once.
- Service providers accept requests at tenant level first and staff their own guards afterward.

## Fulfillment Modes

Requests are moving to an explicit `fulfillment_mode` model:

- `individual_only`
  - Only platform-owned guards are eligible.
- `service_provider_only`
  - Only service provider tenants are eligible.
- `hybrid`
  - Both channels are eligible, but they must remain separate candidate pools and require slot-based fulfillment orchestration.

## Sequential Delivery Constraint

`hybrid` is intentionally a later phase. The platform must first support:

1. explicit fulfillment mode on requests
2. separate guard/provider eligibility pipelines
3. weekly availability filtering for individual guards
4. travel pricing configuration by location
5. slot-aware offers/assignments

Until slot-aware hybrid orchestration is implemented, request creation and editing should only allow:

- `individual_only`
- `service_provider_only`

## Compatibility Guidance

The current request system still uses `target_type` and single-assignee assignment flows. During the transition:

- `individual_only` maps to legacy `target_type = guard`
- `service_provider_only` maps to legacy `target_type = service_provider`
- `hybrid` remains documented but unavailable for request creation/update until the later phases land

