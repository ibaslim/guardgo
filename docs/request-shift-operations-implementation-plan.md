# Request Shift Operations Implementation Plan

This document is the execution plan for implementing the schedule, shift, attendance, and provider-roster layer after the business rules and backend contract are approved.

It is intentionally practical and file-oriented.

Related documents:

- `docs/request-shift-operations-backend-contract.md`
- `docs/request-broadcast-backend-contract.md`
- `docs/request-broadcast-implementation-plan.md`

## Objective

Implement a shift-operations layer that:

- supports one-time, date-range, and recurring weekly schedules
- supports long-term contracts without collapsing them into one assignment lifecycle
- supports service-provider guard rostering after provider-level acceptance
- supports guard check-in, client arrival confirmation, start, checkout, and completion
- supports direct-guard unavailability, no-show, and shift-level replacement
- preserves the current request and broadcast system as the staffing and contract layer

## Delivery Strategy

Recommended implementation order:

1. data model and enum additions
2. schedule generation helpers
3. shift and slot lifecycle manager
4. provider roster APIs
5. attendance APIs
6. replacement and exception flows
7. Angular model and service updates
8. Angular operations UI
9. billing/payroll integration points
10. test suite expansion

This order keeps the core backend state model stable before UI work starts.

## File-By-File Plan

## Backend Shared Models

### [db_request_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_request_model.py)

This remains the best place for the new request-operations records because they are a direct extension of request fulfillment.

Changes:

- add new enums:
  - `RequestScheduleType`
  - `ShiftInstanceStatus`
  - `ShiftCoverageSourceType`
  - `ShiftSlotStatus`
  - `ShiftAttendanceEventType`
- add new records:
  - `RequestScheduleTemplateRecord`
  - `ShiftInstanceRecord`
  - `ShiftSlotRecord`
  - `ShiftAttendanceEventRecord`
- add schedule payloads:
  - `RequestScheduleUpsertPayload`
  - `ShiftListFilters`
  - `ProviderRosterPayload`
  - `BulkRosterPatternPayload`
  - `ShiftSlotCheckInPayload`
  - `ShiftSlotClientConfirmPayload`
  - `ShiftSlotStartPayload`
  - `ShiftSlotCheckOutPayload`
  - `ShiftSlotUnavailablePayload`
  - `ShiftReduceSlotsPayload`
  - `ShiftCancellationPayload`

Implementation note:

- keep the new payloads separate from `ClientRequestCreatePayload` and `ClientRequestUpdatePayload`
- do not overload the request create/update API with recurring schedule shape in one step

## Backend Request Manager

### [request_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/request_manager/request_manager.py)

This file should continue to own request-level acceptance and broadcast orchestration, but not all shift execution rules.

Changes:

- keep request publish, wave, and assignment acceptance flows intact
- after a request reaches accepted staffing, expose integration helpers for shift generation
- add helper methods to:
  - read accepted assignments as recurring capacity commitments
  - determine direct-guard vs provider-backed slot sources
  - trigger replacement waves for uncovered shift slots
  - sync request-level staffing signals from shift-level failures only when needed

Implementation note:

- do not make `update_job_status()` the entry point for attendance
- assignment `started_at` and `completed_at` should remain as coarse legacy compatibility markers until the new shift UI fully replaces them

## New Backend Shift Operations Manager

### Recommended new file

- `backend/orion/api/interactive/request_shift_manager/request_shift_manager.py`

Recommendation:

Create a dedicated manager instead of putting all schedule and attendance logic into `request_manager.py`.

Responsibilities:

- create and update request schedule templates
- generate rolling shift instances
- create shift slots from accepted request assignments
- enforce roster deadlines
- record attendance events
- handle unavailability and no-show state changes
- coordinate replacement flow handoff back to request broadcast logic

Suggested internal helper groups:

### Schedule validation and generation

- validate timezone
- validate one-time, date-range, and recurring weekly inputs
- support overnight windows
- generate UTC shift windows from local schedule definitions
- roll the horizon forward without duplicating shift instances

### Shift slot creation

- map accepted direct-guard assignments into recurring reserved slots
- map accepted provider assignments into provider-owned reserved slots
- create `open` shift slots for uncovered capacity

### Roster enforcement

- compute `roster_due_at`
- detect unrostered provider slots
- raise `client_action_required` on affected shift instances

### Attendance enforcement

- validate geofence check-in
- require client confirmation before shift start
- support `admin` and `ops_admin` start override
- capture actual start/end times

### Exception handling

- unavailability before cutoff
- late risk after cutoff
- no-show suspected and confirmed timers
- replacement-required slot handling

## Backend Routes

### [request_routes.py](/home/ibsalim/Projects/guardgo/backend/routes/request_routes.py)

Add schedule and shift routes here because they are part of request fulfillment.

Recommended endpoints:

- `POST /api/requests/{request_id}/schedule`
- `GET /api/requests/{request_id}/schedule`
- `PATCH /api/requests/{request_id}/schedule`
- `GET /api/shifts`
- `GET /api/shifts/{shift_id}`
- `POST /api/shifts/{shift_id}/cancel`
- `POST /api/shifts/{shift_id}/reduce-slots`
- `GET /api/shift-slots/{slot_id}`
- `POST /api/shift-slots/{slot_id}/check-in`
- `POST /api/shift-slots/{slot_id}/client-confirm`
- `POST /api/shift-slots/{slot_id}/start`
- `POST /api/shift-slots/{slot_id}/check-out`
- `POST /api/shift-slots/{slot_id}/report-unavailable`
- `POST /api/shift-slots/{slot_id}/replace`

Implementation note:

- keep role gates narrow
- direct guard and provider guard actions should only work on visible or owned shift slots

## Backend Tenant Manager And Routes

### [tenant_routes.py](/home/ibsalim/Projects/guardgo/backend/routes/tenant_routes.py)
### [tenant_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/tenant_manager/tenant_manager.py)

The owned service-provider guard list already exists here.

Changes:

- reuse `/api/sp/guards` for roster selection sources
- add helper support if needed for:
  - filtering only active and verified guards
  - returning simplified roster-ready summaries

Recommendation:

- do not create a second provider-guard directory
- extend the current list shape only if the roster UI needs lighter payloads

## Backend Notifications

### [notification_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/notification_manager/notification_manager.py)

Changes:

- add shift-specific notification helpers
- notify:
  - direct guards about upcoming shifts, unavailability outcomes, and no-show consequences
  - service provider admins about roster deadlines and replacement pressure
  - client admins about arrival confirmations and missing coverage decisions
  - platform admins and ops admins about uncovered or disputed shifts

Implementation note:

- keep notifications in-app first
- reuse request/job deep-link style for shift and slot detail links

## Backend Billing Integration

### [billing_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/billing_manager/billing_manager.py)

Changes for this phase should stay limited.

Recommended additions:

- helper to compute scheduled duration from shift instance
- helper to compute actual duration from slot start/end timestamps
- helper to flag suspicious variance for later review

Implementation note:

- do not attempt full invoice generation in the same phase
- first make actual time data trustworthy and queryable

## Backend Activity Logging

### likely current manager

- `backend/orion/api/interactive/activity_manager/activity_manager.py`

Changes:

- log high-signal shift operations:
  - schedule created or updated
  - future shift cancelled or reduced
  - provider roster pattern applied
  - guard marked unavailable
  - no-show confirmed
  - replacement reopened
  - ops override applied

Implementation note:

- use shift identifiers and request identifiers in metadata
- this matters for disputes later

## Frontend Shared Models

### [client-request.model.ts](/home/ibsalim/Projects/guardgo/client/src/app/shared/model/request/client-request.model.ts)

Changes:

- add schedule types and payloads
- add shift instance and shift slot interfaces
- add attendance event interfaces
- add roster payload types
- add exception and filter types for shift lists

Implementation note:

- keep request-level types and shift-level types distinct
- do not overload `RequestAssignmentItem` with shift attendance state

## Frontend Services

### [request.service.ts](/home/ibsalim/Projects/guardgo/client/src/app/shared/services/request.service.ts)

Changes:

- add schedule CRUD methods
- add shift list/detail methods
- add shift-slot attendance methods
- add provider roster methods
- add shift cancel/reduce methods

Recommended methods:

- `upsertRequestSchedule()`
- `getRequestSchedule()`
- `listShifts()`
- `getShift()`
- `getShiftSlot()`
- `submitShiftCheckIn()`
- `submitShiftClientConfirm()`
- `submitShiftStart()`
- `submitShiftCheckOut()`
- `reportShiftUnavailability()`
- `submitProviderRoster()`
- `applyProviderRosterPattern()`
- `cancelShift()`
- `reduceShiftSlots()`

## Frontend Request Page

### [requests.component.ts](/home/ibsalim/Projects/guardgo/client/src/app/pages/requests/requests.component.ts)
### [requests.component.html](/home/ibsalim/Projects/guardgo/client/src/app/pages/requests/requests.component.html)

Do not try to cram every operations surface into the existing request page immediately.

Recommended first-step changes:

- allow schedule creation from request detail
- show whether a request has a schedule template
- show high-level shift counts in request detail
- deep-link from request to shift operations pages

Implementation note:

- keep the request page request-centric
- move detailed shift execution into dedicated pages or drawers

## Recommended New Frontend Pages

### Client-facing

- `client/src/app/pages/request-schedule/request-schedule.component.ts`
- `client/src/app/pages/request-shifts/request-shifts.component.ts`

Purpose:

- schedule setup and editing
- future shift management
- bulk arrival confirmation
- future shift cancel/reduce flows

### Guard-facing

- `client/src/app/pages/my-shifts/my-shifts.component.ts`

Purpose:

- upcoming shifts
- check-in, start, check-out
- unavailable reporting

### Service-provider-facing

- `client/src/app/pages/provider-roster/provider-roster.component.ts`

Purpose:

- accepted contract roster view
- bulk roster pattern application
- day-level exception editing
- roster deadline handling

### Platform-facing

- `client/src/app/pages/shift-operations/shift-operations.component.ts`

Purpose:

- uncovered shifts
- no-show queue
- roster-failed queue
- override and replacement actions

## Routing

### [app.routes.ts](/home/ibsalim/Projects/guardgo/client/src/app/app.routes.ts)

Changes:

- add routes for:
  - request schedule
  - request shifts
  - my shifts
  - provider roster
  - shift operations

Recommendation:

- guard and provider routes should default to shift-focused pages once this phase lands

## Data Migration And Backfill

Recommendation:

- do not backfill every historical request
- support new schedule-aware flow for newly scheduled requests first
- optionally backfill one-time schedules for current active requests later

If minimal backfill is needed:

- create a one-time schedule template for active requests with a valid request window
- generate one shift instance
- link existing accepted assignments as initial recurring sources

## Test Plan

### Backend tests to add

- schedule validation tests
- recurring horizon generation tests
- overnight shift generation tests
- direct guard unavailable flow tests
- provider roster deadline tests
- geofence check-in tests
- client bulk confirmation tests
- no-show suspected/confirmed tests
- shift reduction and cancellation tests
- replacement wave handoff tests

Likely locations:

- `backend/tests/test_request_shift_manager.py`
- `backend/tests/test_request_shift_routes.py`
- extend `backend/tests/test_request_manager_broadcast_lifecycle.py`

### Frontend tests to add later

- schedule form state tests
- shift list and detail rendering tests
- provider roster action tests
- guard attendance action tests
- client bulk confirmation behavior tests

## Recommended Delivery Slices

### Slice 1

- schedule template model
- shift instance generation
- request-to-schedule linkage

### Slice 2

- shift slot generation from accepted assignments
- direct guard shift visibility
- provider roster board foundations

### Slice 3

- check-in, client confirm, start, check-out
- attendance event logging

### Slice 4

- unavailable, no-show, replacement-required flows
- admin and ops exception queues

### Slice 5

- actual-time billing hooks
- polish, deep-linking, and notification coverage

This sequence keeps the hardest operational logic behind stable models and basic shift visibility first.
