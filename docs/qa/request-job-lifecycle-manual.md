# Request, Job, Leave, And Finance QA Manual

This is the single primary QA manual for the implemented business flow across:

- `client_admin`
- direct `guard_admin`
- `sp_admin`
- service-provider-owned `guard_admin`
- `platform admin` / `ops_admin`

If QA has time for only one document, use this one.

## What This Manual Covers

- onboarding and profile ownership rules that directly affect request operations
- short-term and long-term request creation
- `individual_only`, `service_provider_only`, and `hybrid` fulfillment
- request review, publish, update, and additional coverage
- direct guard acceptance
- service provider acceptance, partial acceptance, later `Add Coverage`, and rostering
- shift generation, attendance, and execution
- leave requests, leave quota, leave approval, and leave-based availability blocking
- short-term and long-term payout behavior
- client invoices, assignee invoices, hybrid provider payout adjustments, and platform finance reporting
- payout visibility restrictions for service-provider-owned guards
- overview/dashboard sanity checks for all roles

## Core Business Rules

### Fulfillment and pricing

- `individual_only`
  - client pricing uses guard economics
  - only direct guards are targeted
- `service_provider_only`
  - client pricing uses provider economics
  - only service providers are targeted
- `hybrid`
  - client pricing uses guard economics
  - both direct guards and service providers can fulfill the request
  - extra provider compensation is tracked through platform payout adjustments

### Contract and payout behavior

- short-term
  - client billing follows the booked job window
  - assignee payout follows actual attendance hours
- long-term
  - client billing is `weekly advance`
  - first client invoice appears only after full accepted coverage exists
  - later weekly invoices continue automatically while the request and schedule remain active
  - assignee payout remains completed-work based

### Guard ownership rules

- direct guard
  - can manage full personal profile
  - can see own payout and invoices
  - platform approves leave quota and leave requests
- service-provider-owned guard
  - can complete personal onboarding/profile
  - cannot self-manage provider-owned weekly availability
  - cannot self-manage provider-owned operational coverage
  - cannot see payout widgets or invoice pages
  - leave is operationally tracked in platform, but provider remains payout-facing

### Leave rules

- leave is a separate module at `/dashboard/leaves`
- guards can view their own balance and leave history
- guards can request leave but cannot edit quota
- platform manages direct-guard quota and approvals
- service providers manage their own linked guard quota and approvals
- approved leave blocks matching and rostering where the time window overlaps
- approved paid leave for direct guards creates a payout adjustment

## Recommended QA Data Setup

Prepare these users and records before the cycle:

- one active `client_admin`
- one active direct `guard_admin`
- one active `sp_admin`
- at least two active provider-owned guards under that provider
- one active `platform admin` or `ops_admin`
- one client site with valid province, city, latitude, and longitude
- matching billing defaults for that region
- one direct guard with weekly availability covering the target windows
- one service provider with operating regions covering the same site
- at least one provider-owned guard with managed weekly availability and operational coverage already configured
- one long-term request-capable client billing setup

## Role Surfaces To Use During QA

Use these primary surfaces:

- client:
  - `/dashboard/overview`
  - `/dashboard/requests`
  - client settings
- direct guard:
  - `/dashboard/overview`
  - `/dashboard/requests`
  - `/dashboard/my-invoices`
  - `/dashboard/leaves`
- service provider:
  - `/dashboard/overview`
  - `/dashboard/requests`
  - `/dashboard/tenants`
  - `/dashboard/my-invoices`
  - `/dashboard/leaves`
- service-provider-owned guard:
  - `/dashboard/overview`
  - `/dashboard/requests`
  - `/dashboard/leaves`
  - no `My Invoices`
- platform admin:
  - `/dashboard/overview`
  - `/dashboard/requests`
  - `/dashboard/payout-invoices`
  - `/dashboard/leaves`
  - tenant and billing management pages

## How QA Should Use This Manual

For each pack, QA should not stop at one happy-path pass.

Run each pack through these four lenses where applicable:

1. happy path
2. negative path
3. boundary / partial / recovery path
4. wrong-role / wrong-ownership path

Examples:

- not just "provider accepts"
  - also test partial accept, later `Add Coverage`, over-capacity attempt, and wrong-role attempt
- not just "leave approved"
  - also test unpaid leave, overlapping leave, insufficient paid balance, and wrong approver
- not just "invoice exists"
  - also test no premature invoice, no inflated hybrid client billing, and no payout leak to SP-owned guard

## Minimum Scenario Matrix By Stakeholder

QA should cover these role-specific journeys at least once:

### Client

- create short-term request in all three fulfillment modes
- create long-term recurring request
- publish, update, and request additional coverage
- confirm client invoice behavior
- verify client overview and request detail financial signals

### Direct guard

- complete onboarding and self-managed profile
- accept and decline direct work
- complete attendance flow
- request leave
- receive approved paid leave payout effect
- access `My Invoices`

### Service provider

- complete provider onboarding
- accept provider-only request
- partially accept and later `Add Coverage`
- roster named guards
- manage provider-owned guard leave quota and approvals
- view provider payout invoices

### Service-provider-owned guard

- complete personal onboarding without provider-managed field control
- view own leave and quota
- request leave
- work assigned shifts operationally
- verify no payout or invoice visibility

### Platform admin

- review/publish workflow
- manage direct-guard leave quota and approvals
- inspect finance page
- create, edit, approve, and void provider payout adjustments
- verify overview signals against finance pages

## Must-Run Edge Conditions

These edge cases are mandatory for end-to-end sign-off.

### Ownership and access

- pending service provider cannot use provider-only operational areas
- SP-owned guard cannot self-edit provider-managed weekly availability
- SP-owned guard cannot self-edit provider-managed operational coverage
- SP-owned guard cannot access `My Invoices`
- direct guard can access `My Invoices`
- platform can manage direct-guard leave quota but not provider-owned guard quota
- service provider can manage only their own linked guards' leave quota

### Request pricing and billing

- `hybrid` pricing does not exceed guard-baseline client pricing
- `service_provider_only` pricing still uses provider pricing
- short-term payout changes when actual attendance hours are shorter than planned
- long-term first invoice does not appear before full accepted coverage
- long-term later invoices continue after activation

### Acceptance and coverage recovery

- direct guard decline does not corrupt request counts
- provider partial acceptance leaves request partially fulfilled
- provider later `Add Coverage` works on the same accepted assignment
- provider cannot silently reduce committed slots through that path
- provider roster dropdown remains usable

### Leave and availability

- approved leave blocks direct matching
- approved leave blocks provider roster eligibility
- paid leave consumes quota
- cancelling approved paid leave restores balance
- unpaid leave does not create direct payout
- direct-guard paid leave creates payout adjustment
- provider-owned guard leave does not expose direct platform payout to the guard

### Finance adjustment lifecycle

- draft adjustment does not affect totals
- approved adjustment affects payout and margin
- voided adjustment stays visible in audit history
- voided adjustment no longer affects totals
- platform overview and finance page stay consistent

## Pack 1: Onboarding And Profile Ownership Rules

### Direct guard

Verify:

- direct guard can complete onboarding
- direct guard can edit weekly availability
- direct guard can edit operational region/city/radius
- saved values reopen correctly

### Service-provider-owned guard

Verify:

- service-provider-owned guard can complete onboarding without being blocked by provider-managed fields
- self-view does not allow editing:
  - weekly availability
  - operational region/city
  - operational radius
- service provider can later open that guard and manage those values

### Service provider

Verify:

- provider onboarding saves operating regions and company details correctly
- corporation/company registration number persists after reopen
- pending providers cannot access provider-only operational areas like `My Guards`

Expected:

- profile ownership follows business ownership, not just tenant type

Edge scenarios:

- direct guard saves profile with editable weekly availability and reopens it successfully
- SP-owned guard can finish onboarding without self-filling provider-managed availability/coverage
- service provider can later complete those provider-managed fields before operational use

## Pack 2: Short-Term Request Creation And Pricing

Create three short-term requests with the same site and hours:

1. `individual_only`
2. `service_provider_only`
3. `hybrid`

Verify:

- pricing preview opens
- preview values are stable after save and reopen
- `individual_only` uses guard pricing
- `service_provider_only` uses provider pricing
- `hybrid` uses guard baseline pricing, not provider pricing

Expected:

- `hybrid` must never inflate client charge to provider economics

Edge scenarios:

- save and reopen all three request types and confirm pricing snapshot stability
- verify a hybrid request with provider fulfillment still keeps guard-baseline client pricing

## Pack 3: Long-Term Request Creation And Weekly Advance Billing

Create a long-term recurring request.

Verify:

- recurring schedule saves correctly
- shift generation continues forward automatically
- no first client invoice exists before full accepted coverage
- first client invoice appears after full accepted coverage
- billing cycle is weekly
- charge timing is weekly advance
- later weekly invoices continue automatically while the request and schedule remain active

Expected:

- long-term client billing is no longer monthly advance

Edge scenarios:

- recurring weekly pattern across more than one week
- full coverage reached after partial earlier state
- later invoice generation continues without requiring another first-activation step

## Pack 4: Request Publish, Review, Update, And Additional Coverage

Use platform and client roles as appropriate.

Verify:

- draft request can be saved and reopened
- publish succeeds with complete data
- request review queue behaves correctly for platform roles
- publish update recalculates the request finance snapshot correctly
- additional coverage creates the next fulfillment wave where required
- request counts and open slots stay coherent

Edge scenarios:

- publish update after accepted work
- additional coverage on already-active request
- review-required path returned and then republished

## Pack 5: Direct Guard Acceptance

Use a direct guard on an `individual_only` request.

Verify:

- offer opens from Requests page and overview deep links
- accept succeeds
- request accepted/open slot counts update
- guard can later see own payout-side invoice behavior

Also test decline:

- decline succeeds
- decline reason persists where shown

Edge scenarios:

- direct guard cannot accept work outside the expected role path
- decline and later other-guard fill does not corrupt request fulfillment counters

## Pack 6: Service Provider Acceptance, Partial Fulfillment, And Add Coverage

Create a `service_provider_only` request for more guards than the provider currently has available.

Verify:

- provider can partially accept
- request stays partially fulfilled instead of erroring
- accepted provider job shows `Add Coverage` when `open_slots > 0`

Then make another linked guard available.

Verify:

- provider can reopen the same accepted provider job
- `Add Coverage` increases total committed coverage on the same assignment
- request moves from partial toward full coverage
- new reserved provider-backed shift slots appear

Expected:

- provider does not need a second assignment for the same request

Edge scenarios:

- provider with only one linked usable guard against multi-guard request
- provider later gains another available guard and can increase commitment
- provider over-capacity attempt is rejected cleanly

## Pack 7: Provider Rostering And Shift Operations

Use provider-backed accepted work.

Verify:

- roster drawer opens
- provider can select a linked guard from the dropdown
- roster save succeeds
- guards on overlapping approved leave do not appear as selectable roster candidates
- future shifts keep generating for long-term schedules

Then verify execution:

- guard can `Check In`
- client can `Confirm Arrival`
- guard can `Start Shift`
- guard can `Check Out`

Expected:

- scheduled work is executed through shifts and slots, not through one static job record

## Pack 8: Leaves Module, Quota, And Approval Ownership

Use `/dashboard/leaves`.

### Guard self-view

Verify for both direct and provider-owned guards:

- own leave history is visible
- own quota is visible
- used and remaining balance is visible
- leave can be requested
- guard cannot edit quota

### Platform admin

Verify:

- direct-guard leave queue is visible
- direct-guard quota list is visible
- quota can be updated inline or through the quota management surface
- direct-guard leave can be approved/rejected

### Service provider admin

Verify:

- provider-owned guard leave queue is visible
- provider-owned guard quota list is visible
- quota can be updated
- provider-owned guard leave can be approved/rejected

Expected:

- leave module is separate from Requests
- quota ownership follows guard ownership

Edge scenarios:

- existing guard with no prior leave balance falls back correctly
- newly created guard gets default quota automatically
- reviewer can still manage quota even if no leave request exists yet

## Pack 9: Leave Blocking And Leave Payout

### Operational blocking

Approve leave for a future overlapping window.

Verify:

- direct matching excludes the direct guard during the overlap
- provider capacity drops if a linked provider-owned guard is on approved leave
- provider roster drawer excludes overlapping approved-leave guards

### Future shift impact during approved leave

Use future scheduled work that overlaps the approved leave window.

Verify for `direct guard`:

- only the future shifts inside the leave window are affected
- the main assignment/job is not cancelled
- the affected future shift slot moves into replacement coverage handling automatically
- a replacement slot is opened for each affected direct-guard future shift
- shifts after the leave end still remain attached to the original guard without re-accepting the job

Verify for `provider-owned guard`:

- only future provider-rostered shifts inside the leave window are affected
- the named guard is removed from the future provider rostered slot
- the provider slot returns to provider-managed coverage instead of opening direct platform replacement immediately
- shifts after the leave end remain normal for that guard without a manual return action

Edge scenarios:

- approved leave that overlaps one shift affects only that shift
- approved leave that overlaps multiple future days affects each overlapping future shift, not the whole job
- natural leave completion requires no manual "return to schedule" action

### Direct guard paid leave payout

Use approved paid leave for a direct guard over scheduled work.

Verify:

- payout invoice still exists even if there is no completed attendance for that leave-only window
- leave payout appears as a payout adjustment
- platform payout reporting includes that adjustment

### Provider-owned guard leave payout

Verify:

- leave remains operationally tracked
- provider-owned guard still sees no direct platform payout amount for that leave

Edge scenarios:

- approved paid leave with no attendance still creates direct-guard payout result
- approved unpaid leave creates no payout increase

## Pack 10: Short-Term Payout Accuracy

Create a short-term request and complete it with actual attendance.

Run at least these variants:

1. full scheduled duration worked
2. shorter worked duration than planned without approved leave

Verify:

- client charge remains commercially tied to the booked job window
- assignee payout follows actual attendance hours
- shorter worked duration reduces payout where no approved paid leave applies

Expected:

- short-term payout is not locked to the original estimated invoice amount

Edge scenarios:

- shorter actual duration than planned
- leave-adjusted case versus non-leave early-exit case

## Pack 11: SP-Owned Guard Payout Visibility

Log in as a provider-owned `guard_admin`.

Verify:

- no payout widgets on `/dashboard/overview`
- no `My Invoices` link
- direct `/dashboard/my-invoices` access is blocked
- no direct payout amount surfaces in request/job views
- leave can still be requested and viewed operationally

Expected:

- provider-owned guard is not payout-facing in the platform

Edge scenarios:

- direct URL attempt to `/dashboard/my-invoices`
- request/job drawer paths still avoid payout leakage

## Pack 12: Hybrid Provider Adjustment And Platform Finance

Create a `hybrid` request and let a service provider cover some or all of it.

As platform admin:

- open `/dashboard/payout-invoices`
- create a provider payout adjustment draft
- confirm the draft does not yet affect payout totals
- approve the draft
- optionally edit another draft before approval
- optionally void an approved adjustment

Verify:

- draft adjustments are saved with `Draft` status
- approved adjustments move to `Approved`
- only approved adjustments change provider payout and platform margin
- client invoice does not change
- voided adjustments remain visible in the audit trail
- voided adjustments no longer affect payout totals
- finance summary shows:
  - provider adjustment totals
  - draft counts
  - approved counts
  - voided counts

Expected:

- provider uplift for hybrid work is tracked in-system with audit state

Edge scenarios:

- edit a draft before approval
- approve one draft and void another approved record
- verify finance totals move only on approval and reverse on void

## Pack 13: Dashboard / Overview Sanity

For each role, verify `/dashboard/overview`:

- page loads
- visible buttons work
- links open the correct request/job/shift/invoice surfaces
- numbers look plausible relative to the underlying Requests, Leaves, and Finance pages

Key checks:

- client overview spend/billing signals are not zero when issued billing exists
- provider overview reflects operational offers and provider payout context
- direct guard overview shows payout context
- provider-owned guard overview shows no payout context
- platform overview shows revenue, payout, margin, and provider adjustment pressure

Edge scenarios:

- overview links still open the right details after data changes
- finance adjustment counts in overview stay aligned with payout-invoices page

## Evidence Checklist

Capture on any failure or suspicious behavior:

- role
- tenant type
- request id
- wave id
- assignment id
- shift id
- slot id
- leave id
- invoice id
- exact steps
- expected result
- actual result
- screenshot or recording
- visible error text
- relevant API payload or response when available

## Final Sign-Off Checklist

Do not sign off until all are true:

- short-term pricing is correct for all fulfillment modes
- hybrid uses guard-baseline client pricing
- long-term first invoice waits for full coverage
- long-term invoices are weekly advance
- direct guard acceptance works
- provider partial acceptance and later `Add Coverage` work
- provider rostering works
- leaves module works for guards, providers, and platform reviewers
- leave quota ownership is correct
- approved leave blocks matching and rostering
- short-term payout follows attendance
- direct guard paid leave produces payout adjustment behavior
- provider-owned guard sees no payout surfaces
- hybrid provider adjustment lifecycle works through draft, approve, and void
- platform finance and platform overview reflect the adjustment lifecycle correctly

## Optional Execution Tracker

QA can mark each scenario with:

- `P` = passed
- `F` = failed
- `N/A` = not applicable in this environment
- `Blocked` = cannot execute because prerequisite data or environment is missing

Suggested tracking columns:

- scenario
- stakeholder
- environment
- evidence link
- status
- notes
