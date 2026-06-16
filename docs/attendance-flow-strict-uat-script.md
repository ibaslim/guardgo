# Attendance Flow Strict UAT Script

This is the practical operator runbook for testing attendance end to end.

Use this when you want a strict click-by-click test, not the broader QA matrix.

Related documents:

- `docs/request-lifecycle-end-to-end-qa-plan.md`
- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-shift-replacement-mechanism.md`

## 1. Test Rules

Use these fixed assumptions unless you intentionally change them:

- city / site example: Vancouver
- local timezone for the request schedule: `America/Vancouver`
- default attendance rules:
  - check-in opens `2 hours` before shift start
  - late grace period = `15 minutes`
  - no-show cutoff = `30 minutes`
- all times below are Vancouver local time

Use separate browser sessions for:

- `client_admin`
- direct `guard_admin`
- `sp_admin`
- provider-owned `guard_admin`
- `admin` or `ops_admin`

## 2. Core Status Reference

Use these exact values when validating screens or API responses.

### Request

- before send: `draft`
- after send: usually `submitted`
- after first started shift: `in_progress`
- after all committed work is fully completed: `closed`

### Request staffing

- before any acceptance: `open`
- after some acceptance but not full coverage: `partially_filled`
- after all required slots are accepted: `filled`

### Job

- before response: `offered`
- after acceptance: `accepted`
- after shift start: `in_progress`
- after final eligible completion sync: `completed`

### Shift slot

- direct accepted slot before check-in: `reserved`
- provider slot before named guard: `reserved`
- provider slot after named guard: `rostered`
- after valid check-in: `client_confirmation_pending`
- after shift start: `in_progress`
- after check-out: `completed`
- leave in allowed window: `unavailable`
- missed grace period: `late_risk`
- missed no-show cutoff: `no_show_confirmed`

## 3. Fixture A: Direct Guard One-Time Job

Create this request exactly:

- title: `UAT A1 Direct One-Time Attendance`
- coverage mode: `Direct Guards Only`
- guards required: `1`
- guard type: any type your direct guard matches
- site: valid Vancouver site with coordinates
- job start: `Monday, June 15, 2026 10:00 AM`
- job end: `Monday, June 15, 2026 6:00 PM`
- response cutoff: `Monday, June 15, 2026 9:30 AM`
- no repeating schedule in the form

### A1. Client sends the request

Actor:

- `client_admin`

Steps:

1. Open `Requests`.
2. Click `Create Job Request`.
3. Enter the fixture above.
4. Click `Send Request`.

Expected:

- request appears under `Requests`
- `request_status = submitted`
- `staffing_status = open`
- `accepted_slots = 0`
- `open_slots = 1`

### A2. Guard accepts the offer

Actor:

- direct `guard_admin`

Steps:

1. Open `Offers`.
2. Open `UAT A1 Direct One-Time Attendance`.
3. Click `Accept`.

Expected:

- offer disappears from the guard's `Offers`
- job appears under `Jobs`
- `assignment_status = accepted`
- request now shows:
  - `request_status = submitted`
  - `staffing_status = filled`
  - `accepted_slots = 1`
  - `open_slots = 0`
- a one-time attendance shift exists in `Attendance`
- the direct guard slot exists with:
  - `slot_status = reserved`
  - `assigned_guard_tenant_id = direct guard tenant id`

### A3. Check-in window boundary

Actor:

- direct `guard_admin`

Target shift:

- `Monday, June 15, 2026 10:00 AM`

Exact timing checks:

- at `7:59 AM`: check-in must still be unavailable
- at `8:00 AM`: check-in becomes available

Steps:

1. Open `Jobs`.
2. Open the accepted job.
3. Click `Open Attendance Steps`.
4. Open the slot.

Expected:

- before `8:00 AM`, normal `Check In` is not available
- from `8:00 AM` onward, `Check In` is available

### A3b. Guard reminder before shift start

Actor:

- direct `guard_admin`

Execution time:

- `Monday, June 15, 2026 9:55 AM`

Expected:

- a pre-start reminder notification is visible for the guard
- the reminder wording clearly indicates the upcoming shift is about to start
- opening the reminder should take the guard directly to the correct attendance context
- from there, the guard should be able to reach the same slot used for:
  - `Check In`
  - `Start Shift`
  - `Check Out`

### A4. Guard checks in

Actor:

- direct `guard_admin`

Execution time:

- `Monday, June 15, 2026 9:56 AM`

Steps:

1. Open the slot.
2. Click `Check In`.
3. Provide valid on-site coordinates within the distance limit.

Expected:

- `arrived_at` is populated
- `geo_check_passed = true`
- `slot_status = client_confirmation_pending`
- client receives arrival task / notification
- guard cannot normally start yet

### A5. Client confirms arrival

Actor:

- `client_admin`

Execution time:

- `Monday, June 15, 2026 9:57 AM`

Steps:

1. Open `Attendance`.
2. Use `Arrival Confirmation Waiting` or open the shift directly.
3. Open the slot.
4. Click `Confirm Arrival`.

Expected:

- `client_confirmed_at` is populated
- `slot_status` still remains `client_confirmation_pending`
- guard receives arrival-confirmed notification
- guard can now start the shift once the start window opens

### A6. Guard starts the shift

Actor:

- direct `guard_admin`

Execution time:

- `Monday, June 15, 2026 10:00 AM`

Steps:

1. Open the same slot.
2. Click `Start Shift`.

Expected:

- `started_at` is populated
- `actual_start_at` is populated
- `slot_status = in_progress`
- parent job becomes `assignment_status = in_progress`
- parent request becomes `request_status = in_progress`

### A7. Guard checks out and completes

Actor:

- direct `guard_admin`

Execution time:

- `Monday, June 15, 2026 6:05 PM`

Steps:

1. Open the same slot.
2. Click `Check Out`.

Expected:

- `checked_out_at`, `actual_end_at`, and `completed_at` are populated
- `slot_status = completed`
- parent job becomes `assignment_status = completed`
- parent request becomes `request_status = closed`

## 4. Fixture B: Recurring Weekly Contract With Tuesday Off

Create this request exactly:

- title: `UAT B1 Recurring Weekly Attendance`
- coverage mode: `Direct Guards Only`
- guards required: `1`
- site: valid Vancouver site
- first shift start: `Monday, June 15, 2026 9:00 AM`
- first shift end: `Monday, June 15, 2026 5:00 PM`
- response cutoff: `Sunday, June 14, 2026 8:00 PM`
- repeating pattern:
  - start date: `2026-06-15`
  - end date: `2026-06-21`
  - weekdays selected: `Mon Wed Thu Fri Sat Sun`
  - `Tue` deliberately not selected

### B1. Send and accept

Actors:

- `client_admin`
- direct `guard_admin`

Expected after acceptance:

- request staffing should be `filled`
- accepted job exists
- generated shifts exist on:
  - `Monday, June 15, 2026`
  - `Wednesday, June 17, 2026`
  - `Thursday, June 18, 2026`
  - `Friday, June 19, 2026`
  - `Saturday, June 20, 2026`
  - `Sunday, June 21, 2026`
- no shift exists on:
  - `Tuesday, June 16, 2026`

### B2. Verify Tuesday off

Actor:

- `client_admin` or direct `guard_admin`

Steps:

1. Open `Attendance`.
2. Open calendar for June 2026.
3. Inspect `Tuesday, June 16, 2026`.

Expected:

- no shift card exists on that day

### B3. Verify weekend generation

Actor:

- `client_admin` or direct `guard_admin`

Steps:

1. Inspect `Saturday, June 20, 2026`.

Expected:

- a shift exists
- it can be opened normally

### B4. Verify mid-contract completion does not close the whole contract

Actor:

- direct `guard_admin`

Test date:

- `Wednesday, June 17, 2026`

Steps:

1. Complete the full attendance flow for the Wednesday shift:
   - `Check In`
   - `Client Confirms Arrival`
   - `Start Shift`
   - `Check Out`

Expected after Wednesday checkout:

- that slot is `completed`
- parent job remains `in_progress`
- parent request remains `in_progress`
- later shifts for `June 18, 19, 20, 21` still remain available

### B5. Verify final contract completion

Actor:

- direct `guard_admin`

Final test date:

- `Sunday, June 21, 2026`

Steps:

1. Complete the final remaining shift.

Expected after final checkout:

- last slot becomes `completed`
- parent job becomes `completed`
- parent request becomes `closed`

## 5. Fixture C: Overnight Shift

Create this request exactly:

- title: `UAT C1 Overnight Attendance`
- coverage mode: `Direct Guards Only`
- guards required: `1`
- site: valid Vancouver site
- job start: `Friday, June 19, 2026 9:00 PM`
- job end: `Saturday, June 20, 2026 5:00 AM`
- response cutoff: `Friday, June 19, 2026 7:30 PM`

### C1. Verify overnight lifecycle

Actors:

- `client_admin`
- direct `guard_admin`

Checkpoints:

- check-in opens at `Friday, June 19, 2026 7:00 PM`
- reminder should arrive around `8:55 PM`
- guard starts at `9:00 PM`
- guard checks out at or after `5:00 AM` on `Saturday, June 20, 2026`

Expected:

- same attendance flow works across midnight
- shift remains a single operational slot
- final completion occurs after the overnight slot is checked out

## 6. Fixture D: Provider-Backed Attendance

Create this request exactly:

- title: `UAT D1 Provider Attendance`
- coverage mode: `Service Provider Team Only`
- guards required: `2`
- site: valid Vancouver site
- job start: `Saturday, June 20, 2026 9:00 AM`
- job end: `Saturday, June 20, 2026 5:00 PM`
- response cutoff: `Saturday, June 20, 2026 7:30 AM`

### D1. Provider accepts commercial coverage

Actor:

- `sp_admin`

Steps:

1. Open the provider offer.
2. Accept `2` positions.

Expected:

- provider job appears under `Jobs`
- request staffing becomes `filled`
- shift is generated with `2` provider-backed slots
- both slots initially show:
  - `slot_status = reserved`
  - no `assigned_guard_tenant_id` yet

### D2. Provider rosters named guards

Actor:

- `sp_admin`

Steps:

1. Open `Attendance`.
2. Open the provider shift.
3. Use rostering.
4. assign provider guard A to slot 1
5. assign provider guard B to slot 2

Expected:

- both slots become `slot_status = rostered`
- each slot now has a named `assigned_guard_tenant_id`
- provider users see `Next Roster Task` clear or move to the next pending item

### D3. Provider-owned guards execute attendance

Actors:

- provider-owned `guard_admin` A
- provider-owned `guard_admin` B
- `client_admin`

Expected:

- each named provider guard independently performs:
  - `Check In`
  - wait for client confirmation
  - `Start Shift`
  - `Check Out`
- bulk or individual client confirmation works
- both slots complete independently

## 7. Fixture E: Guard Leave Window

Use the recurring contract from Fixture B.

Target slot:

- `Wednesday, June 17, 2026 9:00 AM`

### E1. Leave too early must fail

Actor:

- assigned `guard_admin`

Test time:

- `Wednesday, June 17, 2026 6:59 AM`

Expected:

- normal guard leave action is not available yet

### E2. Leave inside the allowed window

Actor:

- assigned `guard_admin`

Test time:

- `Wednesday, June 17, 2026 7:30 AM`

Steps:

1. Open the slot.
2. Use the leave action.

Expected:

- `slot_status = unavailable`
- leave event is recorded
- client is notified
- platform admins are notified
- if provider-backed, provider is also notified
- normal attendance path does not continue for that slot

## 8. Fixture F: Late Arrival And No-Show

Use a direct-guard or provider-owned rostered slot.

Target slot:

- `Saturday, June 20, 2026 9:00 AM`

### F1. Miss the grace period

Actor:

- no user action

Steps:

1. Do not check in.
2. Inspect the slot after `9:16 AM`.

Expected:

- `slot_status = late_risk`
- guard can no longer normally continue with check-in/start
- guard receives warning notification
- client receives warning notification
- platform admins receive warning notification

### F2. Confirm no-show

Actor:

- no user action

Steps:

1. Continue to do nothing.
2. Inspect again after `9:31 AM`.

Expected:

- `slot_status = no_show_confirmed`
- issue appears in `Coverage Issues`

## 9. Fixture G: Manual Replacement

Use the no-show case from Fixture F.

### G1. Platform reopens coverage

Actor:

- `admin` or `ops_admin`

Steps:

1. Open `Coverage Issues`.
2. Open the affected issue.
3. Click `Start Replacement Coverage`.
4. submit the replacement action.

Expected:

- replacement slot is created
- replacement offer round is created
- original failed slot history stays intact

### G2. Replacement is accepted

Actor:

- another eligible `guard_admin` or `sp_admin`

Steps:

1. Open the replacement offer.
2. Accept it.

Expected:

- replacement slot fills correctly
- attendance for the replacement still follows the same normal path:
  - `Check In`
  - `Client Confirms Arrival`
  - `Start Shift`
  - `Check Out`

## 10. Quick Failure Guide

If a step fails, capture these exact fields:

- request id
- job id
- shift id
- slot id
- current visible status
- exact timestamp when tested
- role used
- button clicked
- error text

This script is strict by design.

If the UI result differs from the expected values here, treat that as a real UAT defect until proven otherwise.

## 11. Simple Navigation Expectations

These are also part of UAT. If users cannot find the next action quickly, treat that as a UX defect.

### Guard

- `Offers` should show items that still need accept / decline
- `Jobs` should show accepted, active, and completed work
- `Attendance` should show the dated shift the guard must act on
- a guard should be able to reach the next attendance action from either:
  - `Jobs -> Open Attendance Steps`
  - `Attendance`
  - the pre-start reminder notification

### Client

- `Requests` should remain the staffing / lifecycle area
- `Attendance` should expose `Arrival Confirmation Waiting` clearly
- client should not have to search through old requests to confirm arrival for the current shift

### Service Provider

- `Offers` should show provider staffing offers
- `Jobs` should show accepted provider work
- `Attendance` should show provider-backed shifts
- `Next Roster Task` should clearly point to any slot that still needs a named guard

### Platform

- `Review` should show controlled approval items
- `Coverage Issues` should show late, no-show, leave, and replacement recovery work
- platform should be able to reopen replacement without losing the original attendance history
