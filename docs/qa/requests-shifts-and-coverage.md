# QA Guide: Requests, Shifts, And Coverage

## What This Feature Does

This is the main operational engine of GuardGo.

It covers:

- client demand creation
- matching and broadcast
- direct-guard jobs
- service-provider jobs
- schedule creation
- shift and slot generation
- attendance execution
- leave, exceptions, and replacement coverage

Important scope split:

- planned leave, leave quota, and leave approvals now belong mainly to `/dashboard/leaves`
- Requests and shift detail now keep the operational same-shift exception and replacement behavior
- approved planned leave affects only overlapping future shifts, not the entire job assignment
- after the leave window ends naturally, later shifts stay with the original guard automatically unless an earlier manual reconciliation decision changed them

If a term here sounds unclear or too technical, use `docs/qa/testing-terms-glossary.md` before continuing.

## Best Companion Docs

Use these together with this guide:

- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-lifecycle-end-to-end-qa-plan.md`
- `docs/attendance-flow-strict-uat-script.md`
- `docs/shift-guard-leave-management.md`
- `docs/request-shift-replacement-mechanism.md`

## Critical Model QA Must Understand First

Before testing, keep these records separate:

- `Request`
  The client's commercial need.
- `Wave`
  One round of offers.
- `Job` or `Assignment`
  One guard or one provider's commitment record.
- `Schedule`
  The coverage pattern.
- `Shift`
  One dated work instance.
- `Slot`
  One guard position inside one shift.

If these are mixed together during testing, root-cause analysis becomes unreliable.

## A. Request Creation And Publish Requirements

### Main features

- create draft
- choose fulfillment mode
- reuse saved site or enter a new site
- set requested time window
- set request expiry
- choose requested guard type
- set quantity needed
- preview pricing
- save and publish

### Happy-path scenarios

Verify:

- client can create a draft request
- platform admin can create a request on behalf of a chosen client account
- saved client site can be reused when it has valid coordinates
- pricing preview returns values before publish
- draft remains editable until published

### Validation checks

Verify:

- publish cannot happen without requested start and end
- publish cannot happen without request expiry
- request expiry cannot be after the requested start
- publish cannot happen without site latitude and longitude
- saved sites missing coordinates are not reusable
- client billing setup is required before request creation can complete

### Fulfillment mode checks

Verify:

- `Direct Guards Only` sends only direct-guard candidates
- `Service Provider Team Only` sends only provider candidates
- `Guards Or Providers` can send both channels at the same time

## B. Matching, Broadcast, And Review

### Main features

- candidate preview
- publish request
- auto-broadcast
- manual review queue
- wave history and wave detail

### Happy-path scenarios

Verify:

- initial publish creates an offer round
- direct guards receive direct-guard offers
- providers receive provider offers
- hybrid requests can be filled by both direct guards and providers
- request history shows the created wave

### Review scenarios

Verify:

- a review-triggering request lands in the approval queue
- platform user can approve and send it
- platform user can send it back to the client with a note
- returned wave does not send offers until corrected and republished
- wave detail clearly shows why review was required

### Visibility rules

Verify:

- filled offers remain visible but non-actionable
- expired waves remain visible but non-actionable
- request detail still shows historical wave information after updates

## C. Direct Guard Jobs vs Service Provider Jobs

This is the most important distinction in the module.

### Direct guard job behavior

Verify:

- direct guard acceptance always fills exactly one slot
- the accepted work is already tied to that guard
- the direct guard appears automatically on direct shift slots
- no roster step is required for direct work

### Service provider job behavior

Verify:

- provider can accept more than one slot
- provider chooses the committed slot count at acceptance time
- provider acceptance increases committed coverage by the chosen slot count
- provider cannot accept beyond available linked-guard capacity
- provider acceptance does not yet assign named guards
- named guard assignment happens later in provider rostering
- if a provider-owned guard later gets approved planned leave, the named guard should be removed only from overlapping future provider-rostered shifts and the provider should re-roster coverage

### Shared job scenarios

Verify:

- decline path requires reason when the UI asks for it
- job detail shows request and wave context
- manual assignment creates the expected assignment when that path is used
- job list and request detail stay aligned on committed coverage totals

## D. Request Maintenance And Re-Broadcast

### Main features

- edit draft
- publish update
- reconfirmation
- additional coverage
- request status changes
- soft delete terminal requests

### Scenarios

Verify:

- non-material edits do not create a fresh wave
- publish update creates a fresh offer round and preserves history
- accepted but not started jobs become `reconfirmation_required` after material updates
- reconfirmed coverage returns to accepted state
- decline during reconfirmation reopens capacity correctly
- additional coverage opens only the extra missing positions
- closing the request behaves correctly when work is already in progress
- soft delete works only for draft, cancelled, or closed requests
- live requests cannot be soft deleted
- platform request list filtering by client account works for platform users

## E. Schedule Rules And Shift Generation

### Main schedule paths

QA must test all four paths:

- no explicit schedule yet
- `one_time`
- `date_range`
- `recurring_weekly`

### No explicit schedule path

Verify:

- committed work can still create an implicit execution shift
- the implicit shift uses the request start and end window
- the implicit shift creates the right slot count

### Explicit schedule path

Verify:

- one-time schedule creates one shift
- date-range schedule creates daily shifts across the range
- recurring weekly schedule creates only the chosen weekdays
- overnight schedules are handled correctly
- request detail shows schedule summary after save
- shift list and shift calendar stay consistent with each other
- future shifts regenerate correctly when the schedule changes

### Direct vs provider slot generation

Use mixed coverage and verify:

- direct accepted work creates direct slots with a named guard already attached
- provider accepted work creates provider-backed reserved slots
- uncovered demand remains as open slots

### Commercial relationship checks

Verify:

- `one_time` behaves as short-term work
- `date_range` behaves as long-term work
- `recurring_weekly` behaves as long-term work
- schedule-driven contract type stays aligned with the coverage pattern

## F. Provider Rostering

### Main features

- open a provider-backed shift
- assign named provider guards to reserved slots
- optionally apply the same roster pattern to future shifts

### Scenarios

Verify:

- provider-backed accepted work creates reserved slots
- roster drawer lists eligible provider guards
- only active guards belonging to that provider can be used
- saving roster changes slot ownership correctly
- roster pattern can copy forward to matching future shifts
- provider cannot roster a guard into another provider's slot
- provider cannot roster ineligible or unavailable guards into the wrong slot

## G. Attendance Execution

### Main features

- guard check in
- client arrival confirmation
- bulk arrival confirmation
- guard start shift
- guard check out

### Core scenarios

Verify:

- check-in records device location
- checked-in slot waits for client confirmation when required
- client can confirm one slot
- client can bulk confirm multiple arrived slots
- start moves the slot to in-progress
- check-out completes the slot
- platform override start path is tested when the role is allowed

### Timing and control rules

Verify:

- check-in too early is rejected
- check-in after shift end is rejected
- start before scheduled start is rejected
- for scheduled work, attendance actions are used instead of generic job-status actions
- one-time scheduled work still follows shift attendance, not free-form job status changes

## H. Leave, Exceptions, And Replacement

### Leave scenarios

Verify:

- only the assigned guard can report leave for their own upcoming shift
- leave is tied to the selected shift, not a broad future range
- leave marks the slot unavailable
- leave notifies the right stakeholders
- shift-level urgent leave stays an exception flow and does not auto-open replacement coverage by itself
- planned leave follows the separate Leaves module rules:
  - direct-guard planned leave opens replacement coverage for overlapping future shifts
  - provider-owned-guard planned leave removes the named guard from overlapping future provider-rostered shifts and returns the slot to provider-managed coverage

### Exception queue scenarios

Verify:

- unavailable slots appear in the exception queue
- late-risk slots appear in the exception queue
- suspected and confirmed no-shows appear correctly
- exception detail shows timeline and context
- exception filtering by status and date works

### Replacement coverage scenarios

Verify:

- platform or ops can reopen an eligible exception
- reopening creates a replacement slot and new offer round
- original issue history stays visible
- replacement offers can be accepted

### Leave return review

Verify:

- active leave can be reviewed for early return
- future replacement items are listed for decision when needed
- original guard can be restored where allowed
- replacement coverage can be kept where manual decision says so

## I. What Good Deep Coverage Looks Like

A full deep QA pass should prove:

- request data is commercially valid before publish
- matching is role-aware and geo-aware
- review-only waves do not skip approval
- direct-guard jobs and provider jobs are tested as different behaviors
- wave history remains traceable after updates and additional coverage
- accepted coverage becomes the right shift slots
- provider work cannot skip rostering
- long-term and short-term schedule behavior stays clear
- on-site attendance follows the real operational order
- leave and no-show do not corrupt the request lifecycle
- replacement coverage creates a traceable second pass, not a hidden overwrite
