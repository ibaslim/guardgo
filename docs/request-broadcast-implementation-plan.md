# Request Broadcast Implementation Plan

This document is the execution plan for implementing the client request broadcast system after the business rules and backend contract are approved.

It is intentionally practical and file-oriented.

Related documents:

- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-broadcast-backend-contract.md`

## Objective

Implement a wave-based broadcast engine for client requests that:

- supports `individual guards` and `service providers` on the same request
- creates in-app tenant-admin-only offers
- supports admin review before broadcast when auto-broadcast is unsafe
- keeps offers visible after fill or expiry but makes them non-actionable
- creates fresh waves when capacity reopens
- supports reconfirmation after material request updates

## Delivery Strategy

Recommended implementation order:

1. data model and enum expansion
2. migration/backfill for existing records
3. notification and billing helpers
4. request manager refactor
5. API route additions
6. Angular model/service updates
7. Angular request page update
8. test suite expansion

This order keeps the backend state model stable before UI work starts.

## File-By-File Plan

## Backend Shared Models

### [db_request_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_request_model.py)

This is the primary schema change file.

Changes:

- expand `RequestAssignmentStatus`
  - add `reconfirmation_required`
  - add `expired`
  - add `closed_filled`
  - add `superseded`
- add new enums:
  - `RequestStaffingStatus`
  - `RequestLockReason`
  - `RequestWaveTrigger`
  - `RequestWaveStatus`
  - `RequestAssignmentOrigin`
  - `AssignmentLockReason`
  - `BroadcastReviewReasonCode`
- extend `ClientRequestRecord` with:
  - `request_expires_at`
  - `published_at`
  - `published_by_user_id`
  - `published_by_username`
  - `request_revision`
  - `staffing_status`
  - `lock_reason`
  - `accepted_slots`
  - `open_slots`
  - `active_wave_id`
  - `last_wave_number`
  - `expired_at`
- extend `RequestAssignmentRecord` with:
  - `assignment_origin`
  - `broadcast_wave_id`
  - `request_revision_at_offer`
  - `slots_committed`
  - `response_due_at`
  - `reconfirmation_due_at`
  - `lock_reason`
  - `expired_at`
  - `reconfirmation_requested_at`
  - `reconfirmed_at`
  - `closed_filled_at`
  - `superseded_at`
- add new model:
  - `RequestBroadcastWaveRecord`
- extend payloads:
  - add `request_expires_at` to create and update payloads
  - add `slots_committed` to `RequestAssignmentStatusUpdatePayload`
- add new payloads:
  - `RequestPublishPayload`
  - `RequestPublishUpdatePayload`
  - `RequestAdditionalCoveragePayload`
  - `RequestWaveReviewPayload`

Implementation note:

- keep `target_type` for compatibility, but stop treating it as the main source of truth for hybrid requests

## Backend Billing

### [billing_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/billing_manager/billing_manager.py)

Changes:

- reverse the travel-policy validation relationship so:
  - `manual_review_over_km <= max_auto_match_radius_km`
- add a small helper for broadcast safety evaluation, for example:
  - `evaluate_broadcast_distance(distance_km, policy)`
- return structured outcome values such as:
  - `auto_broadcast`
  - `pending_review`
  - `outside_policy`

Implementation note:

- this helper should not replace operational matching
- it should sit on top of matching and determine broadcast safety only

### [db_billing_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_billing_model.py)

Changes:

- likely no schema changes needed
- keep model as-is unless we later decide to store more review metadata

## Backend Notifications

### [notification_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/notification_manager/notification_manager.py)

Changes:

- add `create_for_tenant_admin_users()`
- add a helper to resolve active tenant-admin user ids only
- restrict to:
  - `guard_admin`
  - `client_admin`
  - `sp_admin`
- exclude inactive, blocked, deleted, and disabled users

Implementation note:

- existing `create_for_tenant_users()` should stay for other modules
- broadcast flow should use the new tenant-admin-only method

### [db_notification_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_notification_model.py)

Changes:

- no schema change required
- continue using `metadata` for wave and offer context

## Backend Request Manager

### [request_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/request_manager/request_manager.py)

This will be the largest refactor.

The current manager mixes:

- draft save
- submit
- manual assignment
- job execution

The new implementation should split these concerns into focused helpers.

Recommended internal helper groups:

### Request construction and validation

- validate `request_expires_at`
- enforce active-request update rules
- detect update type:
  - normal update
  - publish update
  - additional coverage

### Matching snapshot

- keep current matching preview behavior for one channel
- add a hybrid aggregator that:
  - runs guard matching
  - runs service-provider matching
  - merges both result sets
  - builds channel-aware `match_summary`

### Travel/review evaluation

- evaluate request site geo quality
- resolve the correct travel policy scope:
  - guard travel default for guard candidates
  - provider travel default for provider candidates
- determine:
  - auto-broadcast
  - pending review
  - validation error

### Publish pipeline

- `create_request()` should become draft-first
- add explicit `publish_request()`
- on publish:
  - refresh snapshot
  - set `request_status=submitted`
  - set `staffing_status=open` or `pending_review`
  - set `request_revision=1`
  - set `published_at`
  - create wave `1`

### Publish update pipeline

- apply material changes
- increment request revision
- refresh snapshot
- move accepted not-started assignments to `reconfirmation_required`
- close older open offers as `superseded`
- create fresh wave or hold for review

### Additional coverage pipeline

- increase `guards_required`
- increment request revision
- preserve existing accepted work
- create wave only for newly opened slots

### Wave creation and activation

- create `RequestBroadcastWaveRecord`
- if no review needed:
  - set wave `active`
  - create assignment offers
  - send notifications
- if review needed:
  - set wave `pending_review`
  - do not create tenant-facing offers yet

### Offer creation

- create `RequestAssignmentRecord` with:
  - `assignment_origin=broadcast`
  - `broadcast_wave_id`
  - `request_revision_at_offer`
  - `response_due_at`
- ensure one tenant cannot have more than one actionable open offer for the same request at the same time

### Staffing reconciliation

- compute accepted slots across assignments
- compute open slots
- set `staffing_status`:
  - `open`
  - `partially_filled`
  - `filled`
- when filled:
  - close remaining open offers as `closed_filled`
  - close current wave as `filled`

### Capacity reopened handling

- when accepted capacity drops:
  - move request from `filled` to `partially_filled`
  - create fresh wave if request is still active and not expired
- do not reopen older offers

### Request expiry handling

- if `request_expires_at` passes:
  - set `staffing_status=expired`
  - set `lock_reason=request_expired`
  - close open offers
  - keep accepted work intact

### Reconfirmation handling

- on publish update:
  - accepted not-started assignments go to `reconfirmation_required`
- on reconfirm acceptance:
  - restore `accepted`
- on reconfirm decline or reconfirm timeout:
  - free the slot
  - evaluate capacity reopened logic

### Serializer updates

- extend request serializer with new request fields
- extend assignment serializer with new offer fields
- add wave serializer

### Legacy behavior to remove or replace

- stop auto-progressing request status to `assigned`
- stop using generic `update_request_status()` as the publish mechanism
- stop rejecting hybrid in `_fulfillment_mode_to_target_type()`

## Backend Routes

### [request_routes.py](/home/ibsalim/Projects/guardgo/backend/routes/request_routes.py)

Changes:

- keep existing routes:
  - `GET /api/requests`
  - `POST /api/requests`
  - `PATCH /api/requests/{id}`
  - `GET /api/requests/{id}`
  - `PATCH /api/requests/{id}/status`
  - `GET /api/jobs`
  - `PATCH /api/jobs/{id}/status`
- add new routes:
  - `POST /api/requests/{id}/publish`
  - `POST /api/requests/{id}/publish-update`
  - `POST /api/requests/{id}/additional-coverage`
  - `GET /api/requests/{id}/waves`
  - `GET /api/request-waves`
  - `POST /api/request-waves/{id}/approve`
  - `POST /api/request-waves/{id}/return`

Role guidance:

- `client_admin`
  - create draft
  - normal update
  - publish
  - publish update
  - additional coverage
- `admin`
  - same as client override if needed
  - can approve or return review waves
- `ops_admin`
  - review approve/return only

Implementation note:

- keep `PATCH /status` only for cancel and close flows

### [notification_routes.py](/home/ibsalim/Projects/guardgo/backend/routes/notification_routes.py)

Changes:

- no route changes required

## Backend Migrations

### New migration script

Add a new script under:

- `/home/ibsalim/Projects/guardgo/backend/migrations/scripts/`

Recommended name:

- `migrate_request_broadcast_phase1.py`

Purpose:

- backfill existing requests
- backfill existing assignments
- seed default values for new fields

Recommended backfill rules:

### Existing requests

- if `request_status=draft`
  - `request_revision=0`
  - `staffing_status=open`
  - `open_slots=guards_required`
- if `request_status in {submitted, assigned}`
  - convert to `request_status=submitted`
  - derive accepted/open slots from assignments
  - set `staffing_status=open`, `partially_filled`, or `filled`
- if `request_status=in_progress`
  - keep `in_progress`
  - derive staffing counters
- if `request_status=closed`
  - set `lock_reason=request_closed`
- if `request_status=cancelled`
  - set `lock_reason=request_cancelled`

### Existing assignments

- default `assignment_origin=manual`
- set `request_revision_at_offer=0` for historical records
- for guard assignments:
  - accepted/in-progress/completed -> `slots_committed=1`
- for provider assignments:
  - if one clear provider assignment represents the request, set `slots_committed=guards_required`
  - if historical data is ambiguous, flag for manual review in migration logs

### Existing waves

- no historical waves need to be synthesized in v1
- `last_wave_number=0`
- `active_wave_id=null`

Implementation note:

- the project currently runs important migration scripts directly from `backend/main.py`
- to stay consistent with the repo, this migration should be wired there as well unless we decide to centralize on the generic migration manager later

### [main.py](/home/ibsalim/Projects/guardgo/backend/main.py)

Changes:

- call the new request broadcast migration during startup

## Frontend Models And Services

### [client-request.model.ts](/home/ibsalim/Projects/guardgo/client/src/app/shared/model/request/client-request.model.ts)

Changes:

- update `ClientRequestStatus`
  - remove UI dependence on `assigned`
  - keep compatibility if backend still emits it during transition
- add request fields:
  - `request_expires_at`
  - `published_at`
  - `request_revision`
  - `staffing_status`
  - `lock_reason`
  - `accepted_slots`
  - `open_slots`
  - `active_wave_id`
  - `last_wave_number`
- expand `RequestAssignmentStatus`
  - `reconfirmation_required`
  - `expired`
  - `closed_filled`
  - `superseded`
- add assignment fields:
  - `assignment_origin`
  - `broadcast_wave_id`
  - `request_revision_at_offer`
  - `slots_committed`
  - `response_due_at`
  - `reconfirmation_due_at`
  - `lock_reason`
- add wave models:
  - `RequestBroadcastWaveItem`
  - `RequestWaveListResponse`
- add payload models:
  - `RequestPublishPayload`
  - `RequestPublishUpdatePayload`
  - `RequestAdditionalCoveragePayload`
  - `RequestWaveReviewPayload`

### [request.service.ts](/home/ibsalim/Projects/guardgo/client/src/app/shared/services/request.service.ts)

Changes:

- keep existing methods where still valid
- add:
  - `publishRequest()`
  - `publishRequestUpdate()`
  - `requestAdditionalCoverage()`
  - `listRequestWaves()`
  - `listReviewWaves()`
  - `approveWave()`
  - `returnWave()`
- extend `updateJobStatus()` to optionally send `slots_committed`
- stop relying on `updateRequestStatus(..., 'submitted')` as publish behavior

## Frontend Request Page

### [requests.component.ts](/home/ibsalim/Projects/guardgo/client/src/app/pages/requests/requests.component.ts)

This file will need a substantial workflow update.

Changes:

- replace `Commit` action with:
  - `Publish Request`
- add actions for live requests:
  - `Publish Update`
  - `Request Additional Coverage`
- add request expiry field handling
- distinguish:
  - draft save
  - publish
  - publish update
  - additional coverage
- remove UI assumptions that only drafts can ever change
- add staffing-state-aware request actions
- show `accepted_slots` and `open_slots`
- show review state for platform roles
- add provider slot input on offer acceptance
- support `reconfirmation_required` in job actions
- keep manual assignment as fallback, but only where still allowed

Recommended internal cleanup:

- split large methods into:
  - request form mapping
  - publish action handlers
  - status banner helpers
  - job action helpers

### [requests.component.html](/home/ibsalim/Projects/guardgo/client/src/app/pages/requests/requests.component.html)

Changes:

- replace draft-era wording:
  - `Commit`
  - `Edit Request Draft`
- add client-visible status badges for:
  - `pending_review`
  - `partially_filled`
  - `filled`
  - `expired`
- show request expiry and open slots
- show banners when offers are visible but locked
  - filled
  - expired
  - superseded
- add UI for:
  - publish request
  - publish update
  - additional coverage
  - platform review actions
- remove the “hybrid planned later” warning
- update jobs section to support:
  - `reconfirmation_required`
  - `expired`
  - `closed_filled`
  - `superseded`

Recommended UX scope for v1:

- keep all of this inside the existing requests page
- add a platform-only review panel instead of a separate route first

## Tests

## Backend Route Tests

### [test_request_routes.py](/home/ibsalim/Projects/guardgo/backend/tests/test_request_routes.py)

Update and extend:

- keep existing route-forwarding tests where still valid
- replace publish-through-status assumptions
- add tests for:
  - `POST /requests/{id}/publish`
  - `POST /requests/{id}/publish-update`
  - `POST /requests/{id}/additional-coverage`
  - `GET /requests/{id}/waves`
  - `GET /request-waves`
  - `POST /request-waves/{id}/approve`
  - `POST /request-waves/{id}/return`
- extend job status payload test to include `slots_committed`

## Backend Manager Tests

### New file recommended

- `/home/ibsalim/Projects/guardgo/backend/tests/test_request_broadcast_manager.py`

Add focused manager tests for:

- first publish creates wave `1`
- publish update increments revision and supersedes older offers
- additional coverage opens only extra slots
- hybrid matching merges guard and provider pools
- accepted slots and open slots recalculate correctly
- request becomes filled and closes open offers
- capacity reopened creates a fresh wave
- decline in wave `1` does not block wave `2`
- expired request closes unfilled portion only
- pending review blocks candidate notifications
- approve review creates offers and notifications
- return review does not create offers
- reconfirmation required flow
- provider slot acceptance respects open-slot limit

### [test_request_manager_matching_preview.py](/home/ibsalim/Projects/guardgo/backend/tests/test_request_manager_matching_preview.py)

Extend:

- add hybrid preview aggregation test
- keep existing requested-window forwarding test

### [test_billing_manager_travel_policy.py](/home/ibsalim/Projects/guardgo/backend/tests/test_billing_manager_travel_policy.py)

Extend:

- add test for new threshold rule:
  - `manual_review_over_km <= max_auto_match_radius_km`
- add tests for broadcast safety evaluator outcomes:
  - auto-broadcast
  - pending review
  - outside policy

### New notification manager test file recommended

- `/home/ibsalim/Projects/guardgo/backend/tests/test_notification_manager.py`

Add tests for:

- tenant-admin-only notification targeting
- active user filtering
- deduping duplicate recipients

## Suggested Implementation Phases

### Phase 1: Models and Migration

- update `db_request_model.py`
- add migration script
- wire migration in `main.py`

Deliverable:

- project starts with new fields present and legacy data backfilled

### Phase 2: Helpers

- update `billing_manager.py`
- update `notification_manager.py`

Deliverable:

- travel-policy review logic and tenant-admin notification targeting are ready

### Phase 3: Request Manager Core

- refactor `request_manager.py`
- add wave lifecycle
- add slot reconciliation
- add review pipeline

Deliverable:

- backend logic supports draft, publish, review, waves, offers, expiry, and hybrid fill

### Phase 4: Routes

- update `request_routes.py`

Deliverable:

- API exposes explicit commands instead of hidden status overloading

### Phase 5: Angular Models and Services

- update `client-request.model.ts`
- update `request.service.ts`

Deliverable:

- client API layer understands new request, wave, and assignment contracts

### Phase 6: Angular Page

- update `requests.component.ts`
- update `requests.component.html`

Deliverable:

- users can publish requests, review statuses, accept offers, reconfirm, and request more coverage

### Phase 7: Tests

- update and add backend tests

Deliverable:

- coverage for wave creation, review, fill, expiry, and hybrid slot logic

## Verification Checklist

After implementation, verify these end-to-end behaviors:

### Request Creation And Publish

- client saves draft
- client publishes request
- request creates wave `1`
- tenant admins receive in-app offers only

### Review Flow

- request with missing geo enters `pending_review`
- no offers are created before approval
- admin approval sends offers
- admin return sends request back without offers

### Hybrid Fill

- one guard accepts `1` slot
- one provider accepts `2` slots
- request becomes filled at the correct total

### Filled Offer Closing

- open offers remain visible after fill
- open offers become non-actionable

### Capacity Reopened

- accepted capacity drops
- fresh wave is created
- previously declined tenant can receive later wave

### Expiry

- wave expires before request expiry
- request can still create a later wave if still active
- request expiry locks the request
- accepted assignments remain valid after request expiry

### Publish Update

- material update creates new revision
- accepted not-started assignments enter reconfirmation
- stale offers become superseded

## Remaining Details To Confirm Before Coding

These are the only material items I still consider open enough to confirm before implementation begins.

### 1. Request expiry input precision

Current frontend request form uses `date` inputs, not precise datetimes.

Need final choice:

- `date only`
- `full datetime`

Recommendation:

- use `datetime` for `request_expires_at`
- otherwise wave expiry, reconfirmation, and start-time comparisons stay too coarse

### 2. Wave expiry algorithm

We agreed wave expiry is system-controlled, but the exact formula is still open.

Need final rule, for example:

- `min(request_expires_at, requested_start_at - 2h)`
- or tiered by request lead time

### 3. Reconfirmation deadline algorithm

We agreed reconfirmation is required, but not the exact timeout.

Need final rule, for example:

- fixed `2 hours`
- or `min(request_expires_at, requested_start_at - 1h)`

### 4. Provider slot reduction UX

We agreed a provider can later reduce committed slots, which reopens capacity.

Need final choice:

- allow slot reduction through the existing job status endpoint
- or add a dedicated `adjust committed slots` action

Recommendation:

- use a dedicated action later if needed
- for first implementation, keep slot changes under platform-assisted flow unless you want self-service reduction immediately

## Recommended Next Move

Once the four remaining details above are confirmed, implementation should start in this order:

1. `db_request_model.py`
2. migration script
3. `billing_manager.py`
4. `notification_manager.py`
5. `request_manager.py`
6. `request_routes.py`
7. Angular models and service
8. Angular request page
9. backend tests

## Summary

The plan is to evolve the existing request and job system rather than replace it.

That means:

- keep request records
- keep assignment records
- add wave records
- split publish behavior into explicit commands
- add staffing counters and review state
- keep UI history visible even when offers are no longer actionable

This is the safest path because it builds on the current code instead of fighting it.
