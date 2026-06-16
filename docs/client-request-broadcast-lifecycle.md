# Client Request to Job and Schedule Lifecycle

This is the main plain-language guide for the most important GuardGo workflow.

It explains how a client request turns into:

- a broadcast wave
- accepted work
- jobs for direct guards or service providers
- schedules
- shifts
- shift slots
- attendance activity

Use this document before deep QA so the testing team does not mix up request records, offers, jobs, and shifts.

If a term in this document feels too product-specific, read `docs/qa/testing-terms-glossary.md` first and then return here.

## Why This Matters

In this product, one business need can pass through several stages:

1. the client asks for coverage
2. the platform finds matching guards or providers
3. offers are broadcast
4. candidates accept
5. the accepted work becomes scheduled execution
6. the execution is tracked through shifts and attendance

If QA treats these stages as the same thing, important defects get missed.

## The Six Records QA Must Keep Separate

- `Client Request`
  The client's commercial demand for coverage.
- `Broadcast Wave`
  One round of offers sent for the request at a specific moment.
- `Assignment` or `Job`
  One guard or one service provider's work record for that request.
- `Schedule Template`
  The coverage pattern for the request, such as one day, daily range, or recurring weekdays.
- `Shift`
  One dated work instance created from the schedule.
- `Shift Slot`
  One guard position inside one shift.

Simple way to remember this:

- the request asks for coverage
- the wave asks candidates to respond
- the job records who committed
- the schedule defines when work should happen
- the shift is the calendar item
- the slot is the actual guard position being worked

## Main Actors

- `client_admin`
  Creates the request, publishes it, updates it, adds coverage, and confirms arrivals.
- `guard_admin`
  Accepts direct-guard work and performs attendance for assigned direct slots.
- `sp_admin`
  Accepts provider work, commits slot count, and rosters named provider guards into provider-backed slots.
- `admin`
  Reviews blocked waves, oversees requests, can manually assign, and can handle operational exceptions.
- `ops_admin`
  Shares review and exception responsibilities with an operations focus.

## One-Page Lifecycle Map

1. Client saves a draft request.
2. Client publishes the request.
3. The platform validates timing, geo, billing, and matching context.
4. The request either:
   - auto-broadcasts, or
   - goes to review, or
   - is blocked with a validation error
5. One broadcast wave sends in-app offers to matching tenant admins.
6. Direct guards or service providers accept or decline.
7. Accepted work increases committed coverage.
8. The request becomes `open`, `partially_filled`, or `filled`.
9. The request either:
   - uses a saved schedule, or
   - uses an implicit one-time execution path based on the request window
10. Shifts and slots are created for execution.
11. Direct guards work named direct slots.
12. Service providers roster named guards into provider-backed slots.
13. Attendance is tracked through check-in, client confirmation, start, and check-out.
14. If coverage breaks, the platform handles reconfirmation, additional coverage, or replacement waves.

## Request Creation Requirements

The request is the source record. If it is wrong, every later stage is wrong too.

### Core fields

The client request captures:

- title
- fulfillment mode
- site details
- requested guard type
- guards required
- requested start and end
- request expiry
- special instructions
- invoicing choices

### Publish-time requirements

The system does not allow a request to publish unless the important business data is present.

QA should verify that publish is blocked when any of these are missing or invalid:

- requested start time
- requested end time
- request expiry
- site latitude
- site longitude
- valid client billing setup
- a valid future request expiry before the requested start

### Fulfillment mode requirements

The client chooses who is allowed to cover the work:

- `Direct Guards Only`
  Only direct guard candidates can receive the work.
- `Service Provider Team Only`
  Only service providers can receive the work.
- `Guards Or Providers`
  Both channels can receive the same request at the same time.

This choice controls who can be matched, who gets offers, and what the later job model looks like.

## Broadcast Requirements

Broadcast is the offer stage.

### Core rules

- Broadcast is `in-app only`.
- Broadcast notifications go to `tenant admins only`.
- A wave uses the request's saved match snapshot at the time the wave is created.
- One request can be fulfilled by direct guards, service providers, or both, depending on fulfillment mode.
- One candidate tenant gets at most one actionable offer per wave.
- Old offers stay visible for history even when they are no longer actionable.

### Review rules

Publishing does not always send offers immediately.

The request can go to manual review when the platform cannot safely auto-broadcast, for example:

- site geo is missing or unreliable
- distance cannot be trusted
- travel policy is missing
- location data is ambiguous
- the request crosses the manual review travel threshold

When this happens:

- the request staffing state becomes `pending_review`
- no candidate receives an actionable offer yet
- `admin` or `ops_admin` must either approve and broadcast or return the item to the client

### Request expiry vs wave expiry

These are different things.

- `Request expiry`
  Chosen by the client. It is the deadline for the request itself.
- `Wave expiry`
  Calculated by the system. It is the deadline for one offer round.

Important rule:

- a request can stay active while one old wave has already expired
- a new wave can still be created later if the request is still valid and has open slots

## Acceptance Rules

The biggest QA risk in this module is treating direct-guard work and provider work as if they behave the same way.

They do not.

| Topic | Direct guard job | Service provider job |
| --- | --- | --- |
| Who accepts | `guard_admin` | `sp_admin` |
| What acceptance means | One named guard commits to work | One provider commits capacity |
| Slot impact | Always fills `1` slot | Fills the committed slot count |
| Named guard known at acceptance time | Yes | No, not yet |
| Extra step before execution | No roster step | Provider must roster named guards into provider-backed slots |
| Common QA mistake | forgetting it is already guard-specific | forgetting acceptance is not the same as named-guard assignment |

### Direct guard job rules

- A direct guard acceptance always commits exactly `1` slot.
- The accepted job is already tied to that guard tenant.
- When shifts are created, the direct guard appears on the direct slot automatically.
- There is no provider roster step for direct work.

### Service provider job rules

- A service provider can accept more than one slot.
- The provider chooses how many slots it is committing.
- The provider cannot accept more slots than its available linked-guard capacity for the request window.
- Acceptance means the provider organization committed the coverage.
- Acceptance does not yet mean named guards have been chosen.
- Named provider guards are assigned later through rostering.

## Request Staffing States

The request has a business lifecycle and a staffing lifecycle.

### Request status

The main request status can move through:

- `draft`
- `submitted`
- `assigned`
- `in_progress`
- `cancelled`
- `closed`

### Staffing status

The staffing status tells QA what is happening commercially:

- `pending_review`
- `review_returned`
- `open`
- `partially_filled`
- `filled`
- `expired`

Example:

- a request can be `submitted` and `partially_filled`
- a request can be `submitted` and `filled`
- a request can be `in_progress` while some shift slots are already underway

## Schedule Requirements

The next major branch is whether the request uses explicit schedule setup or relies on the request window itself.

### Path 1: No explicit schedule yet

The system still needs execution records when committed work exists.

If a request has committed work but no saved schedule template:

- the system can create an implicit one-time schedule
- one execution shift is created from the request start and end
- one or more slots are created inside that shift
- attendance can still be tracked normally

This path is important for one-off jobs that are accepted before a user creates a full schedule setup.

QA should prove:

- committed work still becomes an execution shift
- the created shift uses the request window
- the direct or provider slots match the committed coverage

### Path 2: `one_time` schedule

This means:

- one shift instance
- one coverage date
- start and end local times
- overnight work is allowed

Commercial meaning:

- this is the short-term schedule pattern

### Path 3: `date_range` schedule

This means:

- one shift per day across a start and end date range
- same local time window each day
- future shifts are generated across the defined range

Commercial meaning:

- this is treated as a long-term schedule pattern

### Path 4: `recurring_weekly` schedule

This means:

- the client chooses weekdays such as Monday, Wednesday, and Friday
- the system creates future shifts only on those days
- the generation horizon controls how far ahead the shifts are created
- overnight recurring work is supported

Commercial meaning:

- this is treated as a long-term schedule pattern

### Shared schedule rules

For explicit schedule setup, QA should verify:

- timezone is required
- local start and end times are respected
- overnight windows are handled correctly
- future shifts regenerate when the schedule changes
- shift list and shift calendar stay aligned

## Short-Term vs Long-Term Rules

This area must be very clear for QA because the request form, schedule logic, and invoicing all touch it.

### Client-side meaning

- `short_term`
  Charge per job.
- `long_term`
  Advance monthly invoicing with a monthly cutoff day.

### Schedule-driven behavior

When schedule setup is active, the contract type follows the coverage pattern:

- `one_time` schedule => `short_term`
- `date_range` schedule => `long_term`
- `recurring_weekly` schedule => `long_term`

So QA should not expect a repeating schedule to remain short-term once the schedule is driving the request.

### Payout-side behavior

For assignee-side invoices:

- scheduled long-term coverage is grouped into weekly payout invoices
- short-term work remains per job

## How Shifts and Slots Are Built

Each shift has a required slot count based on the request.

Inside each shift:

- direct-guard commitments create direct slots
- provider commitments create provider-backed slots
- any remaining uncovered demand stays as open slots

Example:

- request needs `4` guards
- `1` direct guard accepted
- `1` service provider accepted `2` slots
- no one accepted the last slot yet

Then each generated shift should show:

- `1` direct slot already tied to the direct guard
- `2` provider-backed reserved slots
- `1` open slot

## Provider Rostering Requirements

Provider-backed execution is not complete at provider acceptance time.

The provider still must roster named guards.

QA should verify:

- only provider-backed slots can be rostered
- only the owning service provider can roster its slots
- only active guards can be rostered
- the guard must belong to that service provider
- rostered slots show the named guard after save
- the roster pattern can optionally be copied to future matching shifts

## Execution and Attendance Rules

For scheduled work, the execution truth is the shift slot, not the high-level request job.

### Main attendance order

1. guard checks in
2. client confirms arrival
3. guard starts shift
4. guard checks out

### Important execution rules

- scheduled request jobs must use shift attendance actions instead of generic job-status start actions
- client confirmation can be done one by one or in bulk
- platform start override exists for some operational cases
- site geo is required for normal check-in validation
- time windows still matter for early check-in, start, and no-show logic

## Update and Re-Broadcast Rules

Not every request change means the same thing.

### Normal update

Use for changes that do not materially change the job.

Typical examples:

- title change
- request expiry change while still active

Expected effect:

- no fresh wave
- no reconfirmation

### Publish update

Use when already accepted candidates must review a meaningful change.

Typical examples:

- start time changed
- end time changed
- location changed
- guard type changed
- fulfillment mode changed
- important instructions changed

Expected effect:

- request revision increases
- old open offers are superseded
- accepted but not started assignments become `reconfirmation_required`
- a fresh wave can be created

### Additional coverage

Use when the job is still the same but the client needs more positions.

Expected effect:

- existing accepted coverage stays intact
- only the extra missing positions reopen
- no reconfirmation is triggered just because demand increased

### Capacity reopened

This is the system recovery path.

Typical triggers:

- a candidate declines during reconfirmation
- a provider reduces committed slots
- accepted coverage is cancelled before work starts

Expected effect:

- the request becomes short again
- the system creates a fresh wave
- old historical offers are not reopened

## Minimum Deep-Coverage QA Scenarios

At minimum, QA should test all of these:

1. `Direct guard only`, one-off request, no explicit schedule at first
   Prove the accepted work still becomes an execution shift and slot.
2. `Hybrid` request with one direct guard and one provider
   Prove slot math is correct and the request can be filled by both channels together.
3. Provider acceptance above available linked-guard capacity
   Prove the over-commit attempt is rejected.
4. `one_time` schedule
   Prove one shift is created and it behaves as short-term work.
5. `date_range` schedule
   Prove daily shifts are created and the request is treated as long-term.
6. `recurring_weekly` overnight schedule
   Prove selected weekdays and overnight timing are respected.
7. Provider rostering on provider-backed slots
   Prove named guards must still be assigned after provider acceptance.
8. Publish update after acceptance
   Prove reconfirmation is triggered.
9. Additional coverage after partial or full staffing
   Prove only extra demand reopens.
10. Filled request later losing capacity
   Prove a fresh wave is created rather than reopening old offers.

## Final QA Reminder

The safest way to test this module is to think in this order:

1. Was the request valid?
2. Was the correct audience broadcast?
3. Did acceptance create the right committed coverage?
4. Did that coverage become the right shift slots?
5. Did provider work get rostered before execution?
6. Did attendance happen on shift slots, not by bypassing the schedule?

If those six questions are answered clearly, the client request to job schedule lifecycle is being tested correctly.
