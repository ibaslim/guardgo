# QA Testing Terms Glossary

This glossary explains the main GuardGo terms in simple words.

Use it whenever a QA guide uses words that sound product-specific, technical, or code-like.

## How To Read This Glossary

- If a term looks like normal business language, read it normally.
- If a term appears in `code style`, it usually matches a status, field, or exact value used in the UI or API.
- If a page uses several unfamiliar terms together, read this glossary first and then return to that page.

## People, Accounts, And Access Terms

### `tenant`

A tenant is one organization or account group inside the platform.

Examples:

- one client company
- one service provider company
- one direct guard account

### `tenant admin`

A tenant admin is the main user who manages that tenant's work in the system.

Examples:

- `client_admin`
- `guard_admin`
- `sp_admin`

### `platform admin`

A platform admin is an internal GuardGo operator, not a client or guard customer.

Examples:

- `admin`
- `ops_admin`
- `compliance_admin`

### `client_admin`

The client-side user who creates staffing requests and confirms guard arrivals.

### `guard_admin`

The guard-side user who accepts direct guard work and performs attendance steps.

### `sp_admin`

The service-provider-side user who accepts provider work and assigns named guards into provider slots.

### `linked guard`

A linked guard is a guard account already attached to a service provider account.

This matters because the provider cannot promise more coverage than the number of usable linked guards it has.

## Request And Broadcast Terms

### `request`

A request is the client's need for security coverage.

It is the top-level business record.

### `fulfillment mode`

Fulfillment mode means who is allowed to cover the request.

Main values:

- `individual_only`
  Only direct guards can receive it.
- `service_provider_only`
  Only service providers can receive it.
- `hybrid`
  Both direct guards and service providers can receive it.

### `candidate`

A candidate is a possible guard or service provider that the system thinks may be able to cover the work.

### `matching`

Matching is the process where the system checks who is a possible fit for the request.

It can consider:

- location
- guard type
- availability
- provider capacity
- existing commitments

### `broadcast`

Broadcast means sending the request offer out to matching candidates.

In this product, that broadcast is in-app, not email-first or SMS-first.

### `wave`

A wave is one round of broadcast for one request.

If the same request needs to be sent again later, that is usually a new wave, not the old wave reopening.

### `offer`

An offer is the candidate-facing work invitation inside a wave.

It is what a guard or provider accepts or declines.

### `assignment`

An assignment is the committed work record created when a guard or provider is involved in a request.

In plain words, this is often the same thing QA calls a job.

### `job`

Job is the simpler QA term for an assignment record.

When the docs say "job detail" or "job list," they usually mean the request assignment record shown to a user.

### `manual assignment`

Manual assignment means a platform user directly chooses who should get the work instead of only relying on the normal broadcast response path.

### `additional coverage`

Additional coverage means the client still wants the same job, but now needs more guard positions than before.

### `reconfirmation`

Reconfirmation means a candidate who already accepted must confirm again because something important changed.

Examples:

- time changed
- location changed
- other important job details changed

### `request revision`

A request revision is the newer version number of the same request after an important update.

### `capacity reopened`

Capacity reopened means the request was once fully staffed, but later became short again.

Example:

- someone cancels
- someone declines reconfirmation
- a provider reduces committed slots

## Schedule, Shift, And Slot Terms

### `schedule`

A schedule is the pattern for when the job should happen.

It answers:

- on what dates
- at what times
- how often

### `implicit schedule`

An implicit schedule is a system-created execution setup when committed work exists but the user did not manually save a normal schedule template yet.

Simple meaning:

- the system creates the execution record automatically so attendance can still happen

### `one_time`

One-time schedule means one shift on one date.

### `date_range`

Date-range schedule means one shift per day across a start date and end date.

### `recurring_weekly`

Recurring weekly means the client chooses certain weekdays, and shifts repeat on those weekdays.

### `shift`

A shift is one actual work instance on the calendar.

Example:

- Tuesday night shift at Site A from 8 PM to 4 AM

### `slot`

A slot is one guard position inside a shift.

If a shift needs 4 guards, then that shift has 4 slots.

### `direct slot`

A direct slot is a shift slot already tied to a direct guard.

### `provider-backed slot`

A provider-backed slot is a shift slot reserved for a service provider's committed coverage.

It still may need a named guard to be rostered into it.

### `roster`

Roster means assigning named guards into provider-backed shift slots.

### `rostered`

Rostered means a named provider guard has already been assigned into that provider-backed slot.

### `reserved`

Reserved means the slot is committed for someone, but work has not started yet.

For provider slots, it can also mean the provider accepted the slot but has not yet named the exact guard.

### `open slot`

An open slot is still unfilled coverage demand.

No one has committed to that slot yet.

## Billing And Commercial Terms

### `pricing preview`

Pricing preview is the estimated commercial result shown before final save or publish.

It helps QA confirm the system can calculate expected pricing.

### `short_term`

Short-term means the work is treated like a one-off or per-job commercial arrangement.

### `long_term`

Long-term means the work is treated like repeating or ongoing coverage.

### `invoice cutoff day`

Invoice cutoff day is the day of the month used for long-term invoicing.

### `payout invoice`

A payout invoice is the money-side record for what a guard or service provider is expected to be paid.

It is not the same as the client's charge view.

### `travel policy`

Travel policy is the set of rules that helps decide whether a candidate is safe to auto-broadcast, should go to review, or should be held back.

### `operational radius`

Operational radius means how far a guard or provider normally says they can serve jobs.

### `override`

Override means a custom commercial rule for one specific guard or one specific provider instead of using the default setup.

## Review, Visibility, And Control Terms

### `actionable`

Actionable means the user can still do something on that item.

Example:

- accept
- decline
- confirm
- start

### `non-actionable`

Non-actionable means the record is still visible, but the user can no longer act on it.

### `manual review`

Manual review means the system paused the request for a platform user to inspect it before offers are sent.

### `soft delete`

Soft delete means the item is hidden from normal active lists without fully erasing its historical record.

### `override start`

Override start means a platform user is allowed to start the shift flow in an exceptional operational case.

## Common Request Status Words

### `draft`

Saved, but not yet published to candidates.

### `submitted`

The request is live in the system beyond draft stage.

### `assigned`

Coverage has been committed to the request.

### `in_progress`

The work has started.

### `cancelled`

The request was stopped before normal completion.

### `closed`

The request finished and is no longer an active work item.

## Common Staffing Status Words

### `pending_review`

The request is waiting for platform review before broadcast can proceed.

### `review_returned`

The request was sent back to the client for correction instead of being released.

### `open`

The request still has open staffing demand.

### `partially_filled`

Some required positions are covered, but not all.

### `filled`

All required positions are covered.

### `expired`

The request or offer deadline passed, so it is no longer active for new action.

## Common Shift And Slot Status Words

### `scheduled`

The shift exists on the calendar and is waiting for execution.

### `partially_staffed`

Some shift slots are covered, but not all.

### `staffed`

All needed shift slots are covered.

### `reserved`

The slot is committed but not yet actively being worked.

### `rostered`

The provider has placed a named guard into that provider-backed slot.

### `arrival_pending`

The system is waiting for the arrival step to happen.

### `client_confirmation_pending`

The guard checked in, but the client still needs to confirm arrival.

### `completed`

The work step or slot finished successfully.

### `late_risk`

The slot is at risk because the assigned guard may be too late for normal service.

### `no_show_suspected`

The guard still has not appeared and the system is treating it as a likely no-show.

### `no_show_confirmed`

The no-show cutoff passed and the system now treats it as a confirmed no-show.

### `replacement_required`

The slot needs replacement coverage because the original coverage failed.

## Timing And Location Terms

### `cutoff`

Cutoff means the last allowed time for a certain action.

Examples:

- request response cutoff
- unavailable cutoff
- no-show cutoff

### `geofence`

Geofence means a location boundary used to check whether the guard is close enough to the site during attendance.

### `geo`

Geo is short for geographic location data, mainly latitude and longitude.

### `overnight`

Overnight means the shift starts on one day and ends on the next day.

## Exception And Recovery Terms

### `exception queue`

The exception queue is the list of shift problems that need operational attention.

Examples:

- unavailable guard
- late-risk slot
- no-show
- replacement-needed slot

### `replacement wave`

A replacement wave is a new offer round created to refill a failed or reopened shift slot.

### `leave return reconciliation`

This means deciding what to do when the original guard comes back after a leave-related replacement process already started.

## Final Reminder For QA

When a term still feels unclear, translate it back into one of these simple questions:

- who is doing the action?
- what record is being changed?
- is this commercial planning, candidate response, or live execution?
- is the item still actionable, or only visible for history?

That usually makes the workflow understandable again.
