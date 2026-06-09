# Request Broadcast Backend Contract

This document converts the agreed business workflow into a backend implementation contract for FastAPI and Mongo/ODMantic.

It is intentionally technical. The client-facing explanation lives in `docs/client-request-broadcast-lifecycle.md`.

## Goals

- support request broadcast waves
- support hybrid fulfillment in one request
- keep old offers visible but non-actionable when the request fills
- allow fresh waves when capacity reopens
- keep request expiry client-controlled and wave expiry system-controlled
- support admin review only when auto-broadcast is unsafe
- minimize unnecessary breakage in the current Angular and FastAPI code

## Current Constraints In The Codebase

The current implementation has four important limitations:

1. `ClientRequestRecord.target_type` assumes a request can only target one channel.
2. `RequestManager._fulfillment_mode_to_target_type()` rejects `hybrid`.
3. `RequestAssignmentStatus` is too small for reconfirmation, expiry, superseded offers, and closed-filled offers.
4. `NotificationManager.create_for_tenant_users()` is too broad because broadcast must notify tenant admins only.

The contract below is designed to resolve those four gaps directly.

## Design Direction

### Recommendation

Keep the current `ClientRequestRecord` and `RequestAssignmentRecord`, but extend them.

Add one new collection:

- `RequestBroadcastWaveRecord`

This is the smallest clean design because:

- the request already stores the matching snapshot
- the assignment already behaves like an offer/job record
- waves need their own audit trail, review state, expiry, and counts

## Request Model Contract

### Keep Existing Core Fields

Keep these existing `ClientRequestRecord` fields:

- `client_tenant_id`
- `created_by_user_id`
- `created_by_username`
- `title`
- `fulfillment_mode`
- `requested_guard_type`
- `guards_required`
- `site_snapshot`
- `special_instructions`
- `requested_start_at`
- `requested_end_at`
- `match_summary`
- `matched_candidates`
- `created_at`
- `updated_at`

### Deprecate Request-Level `target_type`

`target_type` is no longer sufficient once one request can notify:

- individual guards
- service providers
- both at the same time

Recommendation:

- stop using request-level `target_type` as a source of truth
- keep it only as a temporary compatibility field for non-hybrid requests
- rely on `fulfillment_mode` plus `matched_candidates[*].target_type`

### New Request Fields

Add these fields to `ClientRequestRecord`:

| Field | Type | Purpose |
| --- | --- | --- |
| `request_expires_at` | `datetime \| None` | Client-controlled hard expiry for the request |
| `published_at` | `datetime \| None` | First publish timestamp |
| `published_by_user_id` | `str \| None` | Who first published the request |
| `published_by_username` | `str \| None` | Human-readable actor for audit |
| `request_revision` | `int` | Starts at `0` for draft, becomes `1` on first publish, increments on publish update and additional coverage |
| `staffing_status` | `RequestStaffingStatus` | Open, partially filled, filled, expired, or review-driven state |
| `lock_reason` | `RequestLockReason \| None` | Why the request is visible but non-actionable |
| `accepted_slots` | `int` | Current committed accepted slots |
| `open_slots` | `int` | Remaining slots that still need coverage |
| `active_wave_id` | `str \| None` | Current active wave, if any |
| `last_wave_number` | `int` | Monotonic counter for request waves |
| `expired_at` | `datetime \| None` | When request expiry was applied |

### Request Status Strategy

To reduce migration pain, keep `request_status` but narrow its meaning:

| Stored Value | Meaning After Broadcast Implementation |
| --- | --- |
| `draft` | editable draft |
| `submitted` | published/live request before execution starts |
| `in_progress` | work has started |
| `closed` | request completed/closed |
| `cancelled` | request cancelled |

Recommendation:

- stop using `assigned` as an active request status
- treat `submitted` as the stored backend value for user-facing `Published`

### New Request Enums

```python
class RequestStaffingStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    REVIEW_RETURNED = "review_returned"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    EXPIRED = "expired"


class RequestLockReason(str, Enum):
    REVIEW_PENDING = "review_pending"
    FILLED = "filled"
    REQUEST_EXPIRED = "request_expired"
    REQUEST_CANCELLED = "request_cancelled"
    REQUEST_CLOSED = "request_closed"
```

### Match Snapshot Contract

`matched_candidates` should remain the main snapshot source for a wave, but the summary structure should become channel-aware.

Recommended shape:

```json
{
  "total_count": 18,
  "eligible_count": 11,
  "ineligible_count": 7,
  "guard": {
    "total_count": 10,
    "eligible_count": 6,
    "ineligible_count": 4
  },
  "service_provider": {
    "total_count": 8,
    "eligible_count": 5,
    "ineligible_count": 3
  }
}
```

For `hybrid`, the request manager should run matching for both channels and merge the candidate list into one mixed snapshot.

## Broadcast Wave Model Contract

Add a new collection:

```python
class RequestBroadcastWaveRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    request_revision: int = Field(index=True)
    wave_number: int = Field(index=True)
    trigger: RequestWaveTrigger = Field(index=True)
    wave_status: RequestWaveStatus = Field(index=True)
    request_snapshot: Dict[str, Any] = {}
    match_summary_snapshot: Dict[str, Any] = {}
    candidate_snapshots: List[Dict[str, Any]] = []
    review_reason_codes: List[str] = []
    review_findings: List[Dict[str, Any]] = []
    review_note: Optional[str] = None
    reviewed_by_user_id: Optional[str] = Field(default=None, index=True)
    reviewed_by_username: Optional[str] = None
    review_requested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    wave_expires_at: Optional[datetime] = Field(default=None, index=True)
    filled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    open_slots_at_send: int = 0
    offer_count: int = 0
    accepted_slots_at_close: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Wave Enums

```python
class RequestWaveTrigger(str, Enum):
    INITIAL_PUBLISH = "initial_publish"
    PUBLISH_UPDATE = "publish_update"
    ADDITIONAL_COVERAGE = "additional_coverage"
    CAPACITY_REOPENED = "capacity_reopened"


class RequestWaveStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    RETURNED = "returned"
    FILLED = "filled"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"
```

### Why The Wave Stores Candidate Snapshots

Do not rely only on the request record for old wave audit.

The request snapshot will change over time because:

- the request can receive publish updates
- additional coverage creates later revisions
- capacity reopened can create later waves

Store the exact wave candidate snapshot so the platform can always answer:

- who was considered
- who was offered
- why the wave was reviewed
- which revision the wave belonged to

## Assignment / Offer Model Contract

Reuse `RequestAssignmentRecord` as the offer and execution record.

### Keep Existing Fields

Keep:

- `request_id`
- `client_tenant_id`
- `assignee_tenant_id`
- `assignee_tenant_type`
- `candidate_snapshot`
- `assigned_by_user_id`
- `assigned_by_username`
- `note`
- `offered_at`
- `accepted_at`
- `declined_at`
- `started_at`
- `completed_at`
- `cancelled_at`
- `created_at`
- `updated_at`

### Add New Assignment Fields

| Field | Type | Purpose |
| --- | --- | --- |
| `assignment_origin` | `RequestAssignmentOrigin` | Distinguish manual assignment from broadcast offer |
| `broadcast_wave_id` | `str \| None` | Link assignment to the wave that created it |
| `request_revision_at_offer` | `int` | Freeze which request revision the offer belongs to |
| `slots_committed` | `int \| None` | Accepted slot count; `1` for direct guard, client-visible chosen count for provider |
| `response_due_at` | `datetime \| None` | Offer expiry snapshot from the wave |
| `reconfirmation_due_at` | `datetime \| None` | Deadline for reconfirmation responses |
| `lock_reason` | `AssignmentLockReason \| None` | Why the offer is visible but non-actionable |
| `expired_at` | `datetime \| None` | Offer expired |
| `reconfirmation_requested_at` | `datetime \| None` | When the offer entered reconfirmation |
| `reconfirmed_at` | `datetime \| None` | When the candidate reconfirmed |
| `closed_filled_at` | `datetime \| None` | When the offer was closed because request filled |
| `superseded_at` | `datetime \| None` | When the offer was replaced by a newer revision/wave |

### Expanded Assignment Status Enum

```python
class RequestAssignmentStatus(str, Enum):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    RECONFIRMATION_REQUIRED = "reconfirmation_required"
    DECLINED = "declined"
    EXPIRED = "expired"
    CLOSED_FILLED = "closed_filled"
    SUPERSEDED = "superseded"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequestAssignmentOrigin(str, Enum):
    MANUAL = "manual"
    BROADCAST = "broadcast"


class AssignmentLockReason(str, Enum):
    FILLED = "filled"
    WAVE_EXPIRED = "wave_expired"
    REQUEST_EXPIRED = "request_expired"
    SUPERSEDED = "superseded"
    REQUEST_CANCELLED = "request_cancelled"
```

### Slot Rules

- direct guard acceptance must commit exactly `1` slot
- service provider acceptance must provide `slots_committed >= 1`
- service provider acceptance must not exceed current `open_slots`
- the request is `filled` when total accepted committed slots equals `guards_required`

## Notification Contract

### New Notification Helper

Add a new helper to `NotificationManager`:

```python
async def create_for_tenant_admin_users(...)
```

Behavior:

- send only to active users
- send only to tenant admin roles
- do not send to every tenant user

Recommended allowed roles:

- `guard_admin`
- `client_admin`
- `sp_admin`

### Broadcast Notification Metadata

Use metadata like this for broadcast-created offers:

```json
{
  "request_id": "REQ_ID",
  "assignment_id": "ASSIGNMENT_ID",
  "broadcast_wave_id": "WAVE_ID",
  "request_revision": 2,
  "wave_number": 3,
  "assignment_origin": "broadcast"
}
```

Recommended `source_module`:

- keep `requests` if you want minimum UI churn
- use `request_broadcast` if you want a clearer future split

## Review Reason Contract

### Review Reason Codes

```python
class BroadcastReviewReasonCode(str, Enum):
    MISSING_GEO = "missing_geo"
    DISTANCE_UNVERIFIED = "distance_unverified"
    TRAVEL_POLICY_MISSING = "travel_policy_missing"
    AMBIGUOUS_LOCATION = "ambiguous_location"
    MANUAL_REVIEW_DISTANCE = "manual_review_distance"
```

### Review Table

| Outcome | Criteria |
| --- | --- |
| `auto_broadcast` | request is valid, site geo is usable, distance can be evaluated reliably, travel policy resolves, and no review threshold is crossed |
| `pending_review` | missing or invalid geo, failed geocoding, unreliable distance, missing travel policy, ambiguous location data, or distance beyond `manual_review_over_km` |
| `validation_error` | expired request, invalid time range, expiry after shift start, expiry not in future, or illegal slot reduction |

Requests in `pending_review` must not notify candidates until a platform reviewer approves the wave.

## Travel Policy Contract Change

The current billing code rejects travel policies when:

- `manual_review_over_km < max_auto_match_radius_km`

That validation does not fit the agreed review behavior.

### Recommended Rule

Use this relationship instead:

- `manual_review_over_km <= max_auto_match_radius_km`

Recommended meaning:

- `distance_km <= manual_review_over_km`
  - safe for auto-broadcast
- `manual_review_over_km < distance_km <= max_auto_match_radius_km`
  - send to admin review before broadcast
- `distance_km > max_auto_match_radius_km`
  - candidate is not auto-targetable for that wave

This lets travel policy act as a real broadcast control layer when the candidate operational radius is larger than the billing safety radius.

## API Contract

### Request Read Endpoints

### `GET /api/requests`

Keep the route. Extend the response item.

New response fields:

- `request_expires_at`
- `published_at`
- `request_revision`
- `staffing_status`
- `lock_reason`
- `accepted_slots`
- `open_slots`
- `active_wave_id`
- `last_wave_number`

### `GET /api/requests/{request_id}`

Keep the route. Extend the payload with the same fields as the list item, plus current wave and staffing summary if useful.

### `GET /api/requests/{request_id}/waves`

New route.

Purpose:

- list all waves for a request
- allow the client and platform admins to inspect history

Roles:

- `admin`
- `ops_admin`
- `support_admin`
- `compliance_admin`
- `read_only_admin`
- owning `client_admin`

### `GET /api/request-waves`

New route.

Primary use:

- platform review queue
- audit view for waves

Suggested filters:

- `wave_status`
- `trigger`
- `client_tenant_id`
- `request_id`

Roles:

- `admin`
- `ops_admin`
- optionally other read-only platform roles

### Request Write Endpoints

### `POST /api/requests`

Recommended behavior:

- create a draft request
- do not auto-publish by default

Compatibility option:

- keep existing `commit` field for a short transition period
- if `commit=true`, internally create the draft and then run publish

Add to payload:

```json
{
  "request_expires_at": "2026-05-16T18:00:00Z"
}
```

Validation:

- `request_expires_at` may be optional for draft creation
- it becomes required before publish

### `PATCH /api/requests/{request_id}`

Keep the route, but split behavior by request state.

Allowed behavior:

- draft request: full editable payload
- active published request: only normal-update fields

Allowed active fields:

- `title`
- `request_expires_at`

If the client tries to change material fields on a live request through this endpoint, return `409` with guidance to use:

- `POST /api/requests/{id}/publish`
- `POST /api/requests/{id}/publish-update`
- `POST /api/requests/{id}/additional-coverage`

### `POST /api/requests/{request_id}/publish`

New route.

Purpose:

- first publish from draft
- calculate a fresh matching snapshot
- create wave `1`
- either activate the wave or send it to review

Payload:

```json
{
  "max_match_results": 25
}
```

Roles:

- owning `client_admin`
- recommended override: `admin`

### `POST /api/requests/{request_id}/publish-update`

New route.

Purpose:

- apply a material change to a live request
- increment `request_revision`
- create a fresh wave
- put accepted not-started assignments into `reconfirmation_required`

Payload:

```json
{
  "requested_start_at": "2026-05-16T20:00:00Z",
  "requested_end_at": "2026-05-16T23:00:00Z",
  "site": { "...": "..." },
  "requested_guard_type": "armed",
  "special_instructions": "Updated details",
  "request_expires_at": "2026-05-16T19:00:00Z",
  "max_match_results": 25
}
```

Rules:

- closes older open offers as `superseded`
- existing accepted but not started assignments move to `reconfirmation_required`
- existing in-progress work cannot be silently changed

### `POST /api/requests/{request_id}/additional-coverage`

New route.

Purpose:

- keep the same live job
- increase staffing need
- create a fresh wave only for the extra open slots

Payload:

```json
{
  "additional_slots": 2,
  "request_expires_at": "2026-05-16T19:00:00Z",
  "max_match_results": 25
}
```

Rules:

- increments `guards_required`
- increments `request_revision`
- keeps existing accepted work intact
- does not trigger reconfirmation

### `PATCH /api/requests/{request_id}/status`

Keep this route, but narrow its purpose.

Recommended supported transitions:

- `draft -> cancelled`
- `submitted -> cancelled`
- `submitted -> closed`
- `in_progress -> cancelled`
- `in_progress -> closed`

Do not use this route for:

- publish
- publish update
- additional coverage
- review approval

### Wave Review Endpoints

### `POST /api/request-waves/{wave_id}/approve`

New route.

Purpose:

- approve a wave in review
- create the offers
- notify tenant admins

Payload:

```json
{
  "note": "Approved after distance review"
}
```

Roles:

- `admin`
- `ops_admin`

### `POST /api/request-waves/{wave_id}/return`

New route.

Purpose:

- return a pending-review wave to the client without notifying candidates

Payload:

```json
{
  "note": "Missing usable location coordinates"
}
```

Roles:

- `admin`
- `ops_admin`

### Job / Offer Endpoints

### `GET /api/jobs`

Keep the route.

Recommended new filters:

- `request_id`
- `broadcast_wave_id`
- `assignment_origin`

Recommended new response fields:

- `assignment_origin`
- `broadcast_wave_id`
- `request_revision_at_offer`
- `slots_committed`
- `response_due_at`
- `reconfirmation_due_at`
- `lock_reason`
- `expired_at`
- `closed_filled_at`
- `superseded_at`

### `PATCH /api/jobs/{assignment_id}/status`

Keep the route for minimum churn, but expand the payload.

New payload shape:

```json
{
  "assignment_status": "accepted",
  "reason": null,
  "slots_committed": 2
}
```

Rules:

- direct guard acceptance:
  - `slots_committed` omitted or `1`
- service provider acceptance:
  - `slots_committed` required
  - must be `>= 1`
  - must be `<= current open slots`
- decline and cancel:
  - `reason` required
- reconfirmation:
  - accept from `reconfirmation_required` returns to `accepted`
  - decline from `reconfirmation_required` opens capacity again

Allowed tenant-side transitions:

| From | To |
| --- | --- |
| `offered` | `accepted`, `declined` |
| `reconfirmation_required` | `accepted`, `declined` |
| `accepted` | `in_progress`, `cancelled` |
| `in_progress` | `completed`, `cancelled` |

System-side transitions:

| From | To |
| --- | --- |
| `offered` | `expired`, `closed_filled`, `superseded` |
| `accepted` | `reconfirmation_required` |

## Permission Matrix

Recommended role behavior:

| Action | Client Admin | Admin | Ops Admin |
| --- | --- | --- | --- |
| create draft | yes | optional override | no |
| normal update | yes | optional override | no |
| publish request | yes | optional override | no |
| publish update | yes | optional override | no |
| additional coverage | yes | optional override | no |
| approve review wave | no | yes | yes |
| return review wave | no | yes | yes |
| accept/decline tenant offer | matched tenant admin only | override only if needed | no |

This is the recommended assumption because it preserves client ownership while still allowing super-admin intervention.

## Key Implementation Rules

### Fresh Wave Instead Of Reopening Old Offers

When capacity reopens:

- do not reopen old offers
- create a new wave
- allow previously declined candidates to receive the new wave

### Keep Closed Offers Visible

When a request fills:

- keep old offers visible
- mark them non-actionable using `closed_filled`
- store `lock_reason=filled`

### Expired Requests Stay Read-Only

When `request_expires_at` passes:

- set `staffing_status=expired`
- close open offers as non-actionable
- keep accepted work intact
- block all edits

### No Duplicate Actionable Offer For Same Tenant

For the same request:

- one tenant must not have more than one actionable open offer at the same time

This applies across waves as well.

## Migration Notes Against Current Code

### Request Model

Current file:

- `backend/orion/services/mongo_manager/shared_model/db_request_model.py`

Changes needed:

- add the new request fields and enums
- expand `RequestAssignmentStatus`
- add `RequestBroadcastWaveRecord`
- add `request_expires_at` to create and update payloads

### Request Manager

Current file:

- `backend/orion/api/interactive/request_manager/request_manager.py`

Changes needed:

- enable `hybrid`
- stop treating `target_type` as the main request selector
- split publish logic from generic status updates
- add wave creation and review handling
- recalculate `accepted_slots` and `open_slots`
- stop auto-progressing request status to `assigned`
- create fresh waves on capacity reopen

### Notification Manager

Current file:

- `backend/orion/api/interactive/notification_manager/notification_manager.py`

Changes needed:

- add `create_for_tenant_admin_users()`
- filter for active users only

### Request Routes

Current file:

- `backend/routes/request_routes.py`

Changes needed:

- add publish endpoint
- add publish update endpoint
- add additional coverage endpoint
- add request waves read endpoint
- add review approve/return endpoints
- extend job status payload support

## Recommended First Implementation Order

1. Extend enums and models in `db_request_model.py`.
2. Add `RequestBroadcastWaveRecord`.
3. Add notification helper for tenant admins only.
4. Refactor `RequestManager` to separate:
   - draft save
   - publish
   - publish update
   - additional coverage
   - review approve/return
5. Extend `GET /api/requests` and `GET /api/jobs` response serializers.
6. Add the new routes.
7. Update Angular models and request service.
8. Update the request page to use the new commands.

## Summary

The recommended backend contract is:

- keep `ClientRequestRecord`
- keep `RequestAssignmentRecord`
- add `RequestBroadcastWaveRecord`
- use `submitted` as the stored live request status
- move staffing truth into `staffing_status`
- move offer truth into expanded `assignment_status`
- use explicit publish commands instead of overloading generic status updates

This gives the platform a wave-based broadcast system without losing the current request and job foundations already present in the project.
