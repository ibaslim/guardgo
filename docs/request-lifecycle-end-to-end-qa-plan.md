# Request Lifecycle End-to-End QA Plan

This document is the full QA and UAT plan for the implemented client request lifecycle.

It is now the single authoritative QA document for this feature set. It replaces the older shorter checklist so testing strategy and execution guidance stay in one place.

It is intended for:

- product owners
- QA engineers
- ops reviewers
- client demos
- sign-off before moving to invoicing and reporting

For exact attendance timing checks and strict expected status values, use the companion runbook:

- `docs/attendance-flow-strict-uat-script.md`

Related documents:

- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-broadcast-backend-contract.md`
- `docs/request-shift-operations-backend-contract.md`
- `docs/attendance-flow-strict-uat-script.md`

## Scope

This plan covers the full implemented lifecycle from request creation through shift execution and replacement:

- request draft creation
- request publish
- review queue behavior
- broadcast wave creation
- hybrid acceptance by direct guards and service providers
- reconfirmation after updates
- additional coverage
- request expiry behavior
- schedule creation
- shift generation
- provider rostering
- guard attendance actions
- client arrival confirmation
- no-show and exception handling
- manual replacement reopen workflow
- notification visibility and deep links

It does not cover the future finance phase:

- client invoicing
- payout statements
- settlement close
- financial exports

Those belong to the next phase.

## Test Objectives

The test cycle should answer these questions clearly:

1. Can a client create, publish, and manage a request safely?
2. Does matching produce the right guard and provider offers?
3. Can a single request be fulfilled by both direct guards and service providers?
4. Do request updates and additional coverage create the right downstream behavior?
5. Do schedules and shifts reflect accepted commercial commitments correctly?
6. Can provider-backed shifts be rostered using named provider guards?
7. Do check-in, arrival confirmation, start, and check-out work correctly?
8. Do exceptions create controlled replacement workflows without corrupting the request?
9. Do expired, filled, and closed records remain visible but non-actionable?

## Entry Criteria

Do not begin UAT until all of the following are true:

- backend service starts cleanly
- frontend application loads and login works
- test tenants and users are active
- billing defaults exist for the target province and city
- test sites have valid geo
- one direct guard and one service provider can both match the same request
- provider-owned guards are linked and active

## Test Roles

Use separate browser sessions for each role.

### Platform roles

- `admin`
- `ops_admin`

### Tenant roles

- `client_admin`
- direct `guard_admin`
- `sp_admin`
- provider-owned `guard_admin`

## Test Data Matrix

Prepare at least this data set:

### Client tenant

- one active client tenant
- one site with:
  - province
  - city
  - address
  - latitude
  - longitude

### Direct guard

- one active direct guard
- requested guard type matching the client request
- weekly availability covering test shifts
- travel and operational radius sufficient for the test site

### Service provider

- one active service provider
- regional coverage for the same site
- at least two active provider-owned guards

### Billing setup

For the same province and city:

- direct guard default rates
- service provider default rates
- direct guard margin defaults
- provider commission defaults
- direct guard travel policy
- provider travel policy

## Environment Setup

Recommended startup:

1. `cp env .env` if needed
2. `./run.sh -d`
3. open `http://localhost:8080`
4. keep `http://localhost:8080/docs` available for API checks

Notes:

- notification updates are polling-based, not true realtime push
- allow roughly `30 seconds` for passive notification refresh

## Evidence To Capture

For each failed or disputed case, capture:

- actor role used
- request id
- wave id if applicable
- shift id or slot id if applicable
- exact steps performed
- exact actual result
- screenshot or screen recording
- raw error text if visible

Recommended screenshots for a full UAT pack:

- draft request
- published request
- review queue item
- guard offer detail
- provider offer detail
- accepted and filled request state
- generated shift detail
- rostered provider shift
- checked-in slot
- confirmed shift start
- exception queue item
- replacement reopen result

## Execution Model

Run testing in four packs:

1. `Pack A`: request creation, publish, review, acceptance
2. `Pack B`: request updates, reconfirmation, additional coverage, expiry
3. `Pack C`: schedule, shifts, roster, attendance
4. `Pack D`: exceptions, no-show, replacement, visibility rules

Sign off each pack before the next one.

## Test Case Matrix

This section is the spreadsheet-style summary of the full QA plan.

Recommended spreadsheet columns if you export this later:

- `ID`
- `Pack`
- `Scenario`
- `Primary Role`
- `Preconditions`
- `Expected Result`
- `Priority`
- `Pass/Fail`
- `Notes`

| ID | Pack | Scenario | Primary Role | Preconditions | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | A | Create draft request | `client_admin` | Active client, valid site | Draft saves, no wave, no notifications | High |
| A2 | A | Publish request without review blockers | `client_admin` | Valid geo, valid travel policy | Live request, first wave, offers sent | High |
| A3 | A | Direct guard accepts | `guard_admin` | Guard offer exists | Accepted slot count increases by 1 | High |
| A4 | A | Service provider accepts remaining slots | `sp_admin` | Provider offer exists | Request becomes filled, old offers close | High |
| A5 | A | Publish request into review queue | `client_admin` | Review-triggering geo or policy case | Wave lands in review queue | High |
| A6 | A | Approve review wave | `admin` or `ops_admin` | Pending review wave exists | Wave activates and broadcasts | High |
| A7 | A | Return review wave | `admin` or `ops_admin` | Pending review wave exists | Returned state, no candidate broadcast | Medium |
| B1 | B | Publish update after acceptance | `client_admin` | Live accepted request | Revision increments, reconfirmation triggered | High |
| B2 | B | Reconfirm accepted coverage | `guard_admin` / `sp_admin` | Reconfirmation job exists | Status returns to accepted | High |
| B3 | B | Decline during reconfirmation | `guard_admin` or `sp_admin` | Reconfirmation job exists | Capacity reopens correctly | High |
| B4 | B | Additional coverage | `client_admin` | Staffed live request | Only extra slot demand is reopened | High |
| B5 | B | Update request expiry while active | `client_admin` | Active request, not expired | Expiry updates with no reconfirmation | Medium |
| B6 | B | Request expires | `client_admin` | Short-expiry request exists | Request becomes visible but read-only | High |
| C1 | C | Create one-time schedule | `client_admin` | Staffed request exists | One shift instance generated | High |
| C2 | C | Create recurring schedule | `client_admin` | Staffed request exists | Multiple shifts generated by pattern | High |
| C3 | C | Validate direct-guard slot generation | `client_admin` or `admin` | Direct guard accepted request exists | Direct guard appears on generated slot | High |
| C4 | C | Validate provider reserved slots | `sp_admin` | Provider accepted request exists | Provider slots appear reserved pre-roster | High |
| C5 | C | Roster provider guards | `sp_admin` | Reserved provider slots exist | Named guards are assigned to slots | High |
| C6 | C | Apply roster pattern to future shifts | `sp_admin` | Multiple future provider shifts exist | Pattern copies to future visible shifts | Medium |
| C7 | C | Guard check-in | `guard_admin` | Assigned shift slot exists | Arrival recorded with geo validation | High |
| C8 | C | Client confirms arrival | `client_admin` | One or more guards checked in | Client confirmation recorded | High |
| C9 | C | Start shift | `guard_admin` | Arrival confirmed or platform override path | Slot becomes in progress | High |
| C10 | C | Check out shift | `guard_admin` | Shift is in progress | Slot completes with actual end time | High |
| D1 | D | Report unavailable before cutoff | `guard_admin` | Future assigned shift before cutoff | Slot becomes unavailable only for that shift | High |
| D2 | D | Late-risk unavailable case | `guard_admin` | Near-start shift after cutoff | Slot reflects late-risk behavior | Medium |
| D3 | D | Grace-period late arrival and later no-show confirmation | System / `admin` | Rostered shift left without check-in | Late-risk escalation occurs after grace, then no-show can confirm later | High |
| D4 | D | View exception queue and detail | `admin` or `ops_admin` | Exception exists | Full request/shift/slot context visible | High |
| D5 | D | Reopen exception for replacement | `admin` or `ops_admin` | Exception slot exists | Manual replacement slot and wave are created when ops reopens it | High |
| D6 | D | Accept replacement offer | `guard_admin` or `sp_admin` | Replacement offer exists | Replacement slot fills correctly | High |
| D7 | D | Filled request visibility rule | Any matched candidate | Request already fully filled | Offer stays visible but non-actionable | Medium |
| D8 | D | Expired request visibility rule | `client_admin` | Request already expired | Request stays visible but non-editable | Medium |
| N1 | N | Offer notification visibility and deep link | `guard_admin` / `sp_admin` | New offer wave exists | Notification appears and opens correct context | High |
| N2 | N | Review-related client visibility | `client_admin` | Review-returned or reviewed request exists | Client sees meaningful review outcome | Medium |
| N3 | N | Shift-related context navigation | `guard_admin` / `client_admin` | Shift or slot context exists | Shift context opens correctly | Medium |

### Matrix Usage Notes

- Use the matrix for daily QA tracking.
- Use the detailed case sections below for exact execution steps.
- Add `Pass/Fail`, defect id, and tester notes in your spreadsheet or directly in a copied markdown table.

## Pack A: Request Creation, Publish, Review, Acceptance

### Case A1: Create draft request

Actor:

- `client_admin`

Steps:

1. Open `Dashboard > Requests`.
2. Create a new request.
3. Use:
   - fulfillment mode: `Hybrid Coverage`
   - matching guard type
   - `guards_required = 3`
   - valid site
   - future request start and end
   - valid request expiry before start
4. Save as draft.

Expected:

- request is listed as draft
- no wave exists
- no candidate notifications exist

Pass criteria:

- request is editable
- no matching-side job offers appear yet

### Case A2: Publish request without review blockers

Actor:

- `client_admin`

Steps:

1. Open the saved draft.
2. Click `Publish Request`.

Expected:

- request becomes live
- first wave is created
- request staffing becomes `open` or `partially_filled`
- no review queue stop occurs

Pass criteria:

- direct guard receives a job offer
- service provider receives a job offer
- notifications appear in polling window

### Case A3: Direct guard accepts

Actor:

- direct `guard_admin`

Steps:

1. Open `Requests > Jobs`.
2. Open the offer detail.
3. Accept the offer.

Expected:

- request accepted slot count increases by `1`
- guard job status becomes `accepted`
- request staffing becomes `partially_filled`

### Case A4: Service provider accepts

Actor:

- `sp_admin`

Steps:

1. Open `Requests > Jobs`.
2. Open provider offer detail.
3. Accept with `2` committed slots.

Expected:

- remaining capacity is committed
- request staffing becomes `filled`
- stale open offers become non-actionable

Pass criteria:

- request detail shows `3/3` fulfilled
- still-open offers are visible but closed

### Case A5: Publish into review queue

Actors:

- `client_admin`
- `admin` or `ops_admin`

Preparation:

- use a request or location/policy combination that should require manual review

Steps:

1. Publish the request.
2. Login as `admin` or `ops_admin`.
3. Open `Requests > Review`.

Expected:

- pending review wave appears
- review reasons and findings are visible

### Case A6: Approve review wave

Actor:

- `admin` or `ops_admin`

Steps:

1. Open the pending review wave.
2. Approve and broadcast.

Expected:

- wave becomes active
- offers are sent to candidates

### Case A7: Return review wave

Actor:

- `admin` or `ops_admin`

Steps:

1. Open another pending review wave.
2. Return it with a note.

Expected:

- request becomes review-returned
- no candidate notifications are sent for that returned wave

## Pack B: Request Updates, Reconfirmation, Additional Coverage, Expiry

### Case B1: Publish update after acceptance

Actors:

- `client_admin`
- direct `guard_admin`
- `sp_admin`

Steps:

1. Open a live accepted request.
2. Use `Publish Update`.
3. Change the time window.

Expected:

- request revision increments
- accepted but not started jobs become `reconfirmation_required`

### Case B2: Reconfirm after update

Actors:

- direct `guard_admin`
- `sp_admin`

Steps:

1. Open reconfirmation job detail.
2. Reconfirm coverage.

Expected:

- status returns to accepted
- request remains staffed

### Case B3: Decline during reconfirmation

Actors:

- one candidate who previously accepted

Steps:

1. Open reconfirmation offer.
2. Decline it.

Expected:

- capacity reopens
- fresh wave can be created if the request still needs staffing

### Case B4: Additional coverage

Actor:

- `client_admin`

Steps:

1. Open a staffed request.
2. Use `Request Additional Coverage`.
3. Increase required slots by `1`.

Expected:

- existing accepted work remains unchanged
- only extra demand is reopened
- fresh wave is created for the added slot

### Case B5: Expiry update while request is still active

Actor:

- `client_admin`

Steps:

1. Open active request.
2. Update only request expiry.

Expected:

- expiry updates successfully
- no reconfirmation is triggered
- no old waves are reopened just because expiry changed

### Case B6: Request expires

Actor:

- `client_admin`

Steps:

1. Use a request with near expiry.
2. Let `request_expires_at` pass.

Expected:

- request remains visible
- request becomes read-only
- no further edit action is allowed
- already accepted work remains valid

## Pack C: Schedule, Shifts, Roster, Attendance

### Case C1: Create one-time schedule

Actor:

- `client_admin`

Steps:

1. Open a staffed request.
2. Create a `one_time` schedule with timezone.

Expected:

- one shift is generated
- shift appears in `Requests > Shifts`

### Case C2: Create recurring weekly schedule

Actor:

- `client_admin`

Steps:

1. Open another staffed request.
2. Create `recurring_weekly` schedule.
3. Use several recurrence days and future horizon.

Expected:

- multiple shifts appear
- shift dates align with local timezone pattern

### Case C3: Verify direct-guard slot generation

Actor:

- `client_admin` or `admin`

Steps:

1. Open a shift detail from a request with direct guard acceptance.

Expected:

- direct guard appears already attached to the appropriate slot

### Case C4: Verify provider-backed reserved slots

Actor:

- `sp_admin`

Steps:

1. Open a shift from a request where provider accepted slots.

Expected:

- provider-backed slots appear as reserved until named guards are rostered

### Case C5: Roster provider guards

Actor:

- `sp_admin`

Steps:

1. Open roster drawer.
2. Assign named provider-owned guards to reserved slots.

Expected:

- slots become rostered
- selected guards are shown on the shift

### Case C6: Apply roster pattern

Actor:

- `sp_admin`

Steps:

1. On the same roster action, apply the same guard pattern to future visible shifts.

Expected:

- future provider-backed shifts receive equivalent slot-to-guard mapping where possible

### Case C7: Guard check-in

Actor:

- direct `guard_admin` or provider-owned `guard_admin`

Steps:

1. Open shift slot detail.
2. Click `Check In`.
3. Use browser location or manual coordinates.

Expected:

- arrival is recorded
- geofence validation is applied
- slot advances to arrival/client-confirmation stage

### Case C8: Client confirms arrival

Actor:

- `client_admin`

Steps:

1. Open the shift.
2. Confirm arrival for one slot.
3. If multiple guards are present, use bulk confirm.

Expected:

- client confirmation event is recorded
- slot is ready to start

### Case C9: Start shift

Actor:

- `guard_admin`

Steps:

1. Open confirmed shift slot.
2. Start shift.

Expected:

- slot becomes `in_progress`
- actual start time is recorded

### Case C10: Check out

Actor:

- `guard_admin`

Steps:

1. Open in-progress shift slot.
2. Check out.

Expected:

- slot completes
- actual end time is recorded
- shift completion counters update

## Pack D: Exceptions, No-Show, Replacement, Visibility Rules

### Case D1: Report unavailable before cutoff

Actor:

- assigned `guard_admin`

Steps:

1. Open a future shift before the unavailable deadline.
2. Use `Report Unavailable`.

Expected:

- slot becomes unavailable
- only that shift slot is affected

### Case D2: Late risk after cutoff but before start

Actor:

- assigned `guard_admin`

Steps:

1. Report unavailable after cutoff but before shift start if the UI/path allows it in the current implementation.

Expected:

- slot reflects late-risk behavior rather than normal early unavailability

### Case D3: No-show suspected and confirmed

Actor:

- none initially

Steps:

1. Leave a rostered shift slot without check-in.
2. Read the shift after start plus grace.
3. Read again after no-show cutoff.

Expected:

- first transition: `no_show_suspected`
- second transition: `no_show_confirmed`
- item appears in `Shift Exceptions`

### Case D4: Exception queue visibility

Actor:

- `admin` or `ops_admin`

Steps:

1. Open `Requests > Shift Exceptions`.
2. Open the exception detail.

Expected:

- shift, slot, request, and timeline context are visible

### Case D5: Reopen for replacement

Actor:

- `admin` or `ops_admin`

Steps:

1. Open exception detail.
2. Use `Reopen For Replacement`.

Expected:

- replacement slot is created
- replacement wave is created
- replacement offers become available

### Case D6: Accept replacement

Actors:

- another `guard_admin` or `sp_admin`

Steps:

1. Open replacement offer.
2. Accept it.

Expected:

- replacement slot fills
- original request history remains intact
- replacement remains auditable as a shift-level correction

### Case D7: Filled request visibility rule

Actor:

- any previously matched candidate

Steps:

1. Open an old offer from a request that is already fully filled.

Expected:

- record stays visible
- response actions are disabled
- UI explains that vacancies are already filled

### Case D8: Expired request visibility rule

Actor:

- `client_admin`

Steps:

1. Open an expired request.

Expected:

- request remains visible
- no edit or publish actions remain available

## Notification Validation

### Case N1: Offer notification

Actors:

- direct `guard_admin`
- `sp_admin`

Expected:

- notification appears after wave activation
- clicking notification opens the correct job or request context

### Case N2: Review-related notification

Actor:

- `client_admin`

Expected:

- client sees meaningful review outcome or returned state

### Case N3: Shift-related context

Actors:

- guard and client

Expected:

- shift or slot context opens correctly when navigated through current UI entry points

## Quick Sequential Smoke Run

If you need one realistic full-flow test in the shortest possible sequence, use this order:

1. Create draft request
2. Publish request
3. Guard accepts
4. Service provider accepts remaining slots
5. Publish update
6. Reconfirm accepted coverage
7. Add additional coverage
8. Create recurring schedule
9. Roster provider guards
10. Guard checks in
11. Client confirms arrival
12. Guard starts shift
13. Guard checks out
14. Trigger unavailable or no-show
15. Reopen replacement
16. Accept replacement
17. Validate expiry behavior on a separate short-expiry request

## Defect Logging Format

Use this minimum structure:

- title
- environment
- actor role
- request id
- related wave id or shift id
- reproduction steps
- expected result
- actual result
- severity
- attachments

## Non-Functional Checks

These are lighter but still required:

### UX checks

- page tabs update correctly
- drawers open and close predictably
- non-actionable records clearly communicate why they are locked
- bulk-confirm flow is understandable

### Performance checks

- request list loads without obvious lag
- jobs list updates within the polling interval
- shift list and calendar remain usable with multiple generated shifts

### Data integrity checks

- no duplicate offers in one wave for the same tenant
- accepted slot counts match visible staffing
- completed shifts preserve actual times after refresh
- replacement history does not overwrite original slot history

## Pass / Fail Criteria

### High-severity failure examples

- publish does not create wave
- review-needed request auto-broadcasts without approval
- hybrid acceptance breaks slot counts
- accepted request does not generate shifts
- guard can start shift without required confirmation path
- no-show never enters exception queue
- grace-period miss does not notify guard, client, and platform admins
- replacement reopen does not create a replacement offer
- expired request is still editable

### Overall pass criteria

The request lifecycle is QA-ready when:

- all critical path cases pass
- no high-severity defects remain open
- medium-severity defects have acceptable workaround or approved deferment
- product owner signs off on the behavior

## Suggested Execution Order For A Real UAT Session

If you want the shortest realistic full-flow run:

1. A1
2. A2
3. A3
4. A4
5. B1
6. B2
7. B4
8. C2
9. C5
10. C7
11. C8
12. C9
13. C10
14. D1 or D3
15. D5
16. D6
17. B6

## Sign-Off Section

Use this at the end of the session.

### Session details

- environment:
- build/date:
- test lead:
- observers:

### Result summary

- total cases executed:
- passed:
- failed:
- blocked:

### Decision

- approved for next phase:
- approved with conditions:
- not approved:

### Notes

- key defects:
- business clarifications discovered:
- follow-up actions:
