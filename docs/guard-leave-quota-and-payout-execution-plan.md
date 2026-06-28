# Guard Leave, Quota, And Payout Execution Plan

## Purpose

This document defines the recommended implementation plan for a real leave-management feature that aligns with:

- operational scheduling
- client request execution
- provider rostering
- payout correctness
- business ownership rules

It is intentionally separate from the current shift-level `Report Unavailable` mechanism.

## What Exists Today

Current shift leave is already implemented, but it is **not** a full leave module.

Current behavior:

- one guard reports leave for one assigned upcoming shift
- only within the final pre-start operational window
- no quota
- no approval workflow
- no paid / unpaid distinction
- no payroll entitlement logic

Current shift leave should be treated as:

- a same-day or near-start attendance exception tool
- not a planned leave / leave balance system

## Business Goal

Build a real leave system with:

- default editable leave quota per guard
- planned leave requests
- approval workflow
- paid vs unpaid leave
- role-correct approval ownership
- rostering / matching impact
- payout impact

## Recommended Product Split

Do **not** merge everything into the existing shift leave flow.

Keep two separate concepts:

### 1. Shift Unavailable

Use for:

- last-minute pre-start problems
- same-day inability to work
- immediate operational exception handling

Key traits:

- shift-specific
- near-start only
- no quota logic
- no entitlement logic

### 2. Planned Leave

Use for:

- future absence
- paid leave
- unpaid leave
- leave balance consumption
- approval workflow
- future roster blocking

Key traits:

- request/approval workflow
- balance-aware
- payroll-aware

## Approval Ownership

### Direct guard

- leave approver: `platform admin` or `ops admin`

### Service-provider-owned guard

- leave approver: `sp_admin`

This matches the actual business ownership model.

## Recommended Domain Model

### Leave policy

Purpose:

- defines the default leave policy for a guard

Suggested fields:

- `guard_tenant_id`
- `ownership_type`
- `service_provider_tenant_id` when applicable
- `annual_paid_leave_days`
- `annual_unpaid_leave_days` optional
- `carry_forward_days`
- `effective_from`
- `effective_to`
- `is_active`
- audit fields

### Leave balance

Purpose:

- tracks remaining entitlement for a guard

Suggested fields:

- `guard_tenant_id`
- `policy_id`
- `period_start`
- `period_end`
- `paid_leave_allocated_days`
- `paid_leave_used_days`
- `paid_leave_remaining_days`
- `unpaid_leave_used_days`
- audit fields

### Leave request

Purpose:

- the actual planned leave workflow record

Suggested fields:

- `guard_tenant_id`
- `ownership_type`
- `service_provider_tenant_id`
- `leave_type`
  - `paid`
  - `unpaid`
- `reason`
- `start_at_utc`
- `end_at_utc`
- `request_status`
  - `pending`
  - `approved`
  - `rejected`
  - `cancelled`
  - `consumed`
- `requested_by_user_id`
- `requested_by_username`
- `approved_by_user_id`
- `approved_by_username`
- `approval_note`
- `balance_days_reserved`
- `balance_days_consumed`
- audit fields

### Leave impact snapshot

Purpose:

- preserve the operational effect of leave at approval time

Suggested fields:

- `leave_request_id`
- `affected_shift_ids`
- `affected_slot_ids`
- `blocked_request_ids`
- `generated_at`

This can be embedded or modeled separately depending on implementation preference.

## Scope Rules

### Planned leave scope

Planned leave should support:

- one day
- multiple days
- partial-day windows
- recurring future schedule overlap resolution only through explicit dates, not recurring leave rules in v1

### Exclusions for v1

Do not add in first pass:

- half-day leave templates
- public holidays
- accrual math by payroll cycle
- carry-forward automation
- leave encashment

## Operational Rules

### Matching impact

Approved planned leave should make the guard unavailable for overlapping future work:

- direct guard matching should exclude the guard
- provider roster picker should exclude provider-owned guards on approved leave

### Existing assigned future shifts

For future shifts overlapping approved leave:

- mark those slots as blocked for roster/assignment
- surface them to the owning operator for replacement planning

Recommended v1 behavior:

- do not auto-open replacement broadcasts
- do notify the responsible operator:
  - platform ops for direct guards
  - service provider admins for SP-owned guards

This keeps behavior consistent with the current controlled replacement posture.

### Same-day urgent cases

Planned leave should not replace the current urgent flow.

Use cases:

- future known absence -> planned leave
- urgent same-day absence -> shift unavailable / report leave on shift

## Payout Rules

This is the most important finance rule set.

### Base rule

Payout should be built from:

- actual worked attendance hours
- plus approved paid-leave payout where applicable

### If guard leaves early without approved leave

Payout:

- pay only actual worked hours

### If leave is approved and paid

Payout:

- actual worked hours
- plus paid leave compensation adjustment, if any leave time is entitled and not worked

### If leave is approved and unpaid

Payout:

- actual worked hours only

## Ownership Rule For SP-Owned Guards

This must remain strict.

### Direct guards

Platform may calculate and expose direct payout impacts.

### SP-owned guards

Platform should **not** expose or pay the guard’s private cut directly.

Correct model:

- platform tracks operational leave approval
- service provider remains payout-facing
- service provider handles the guard’s internal payroll / leave compensation

Optional future capability:

- platform may support provider-facing commercial adjustments related to approved leave
- but not direct platform payout visibility to the SP-owned guard

## Short-Term Payout Recommendation

This should be fixed as part of the leave/payout track.

### Current problem

Short-term assignee payout appears estimate-based.

### Recommended correction

Short-term payout should become:

- attendance-realized worked hours
- plus paid-leave adjustment if approved

This aligns short-term with long-term payout logic.

## Frontend Modules

### New leave module pages

Recommended new pages:

- `Leave Requests`
- `Leave Approvals`
- `Leave Policies`

### Role views

#### Direct guard

- submit planned leave
- view own leave balance
- view leave history

#### SP-owned guard

- submit planned leave
- view leave history
- optional view of balance only if product wants guard transparency
- no payout visibility

#### Platform admin / ops admin

- approve direct-guard leave
- manage direct-guard leave policies/balances
- view leave-related operational conflicts

#### Service provider admin

- approve SP-owned guard leave
- manage provider-owned guard leave balances/policies
- view overlap with rostered future shifts

## Suggested API Surface

### Policies / balances

- `GET /leave/policies`
- `PUT /leave/policies/{guardId}`
- `GET /leave/balances/{guardId}`

### Leave requests

- `POST /leave/requests`
- `GET /leave/requests`
- `GET /leave/requests/{id}`
- `POST /leave/requests/{id}/approve`
- `POST /leave/requests/{id}/reject`
- `POST /leave/requests/{id}/cancel`

### Operational impact

- `GET /leave/requests/{id}/impact`

### Payout integration

This should likely reuse the payout-adjustment infrastructure rather than invent a second payout mutation path.

Suggested internal shape:

- approved paid leave creates a typed payout adjustment record
- reason category should distinguish:
  - `hybrid_provider_adjustment`
  - `paid_leave_adjustment`

## Implementation Order

### Phase A: Leave foundation

- data models
- CRUD for leave request
- approval workflow
- balance/policy storage

### Phase B: Operational integration

- block future matching / rostering
- show affected future shifts
- notify responsible operators

### Phase C: Payout integration

- make short-term payout attendance-based
- add paid-leave payout adjustment handling
- keep SP-owned guard payout visibility rules unchanged

### Phase D: Admin maturity

- reporting
- leave summaries
- adjustment history tied to leave

## Migration Strategy

No destructive migration is required for current shift leave.

Recommended approach:

- keep existing shift leave records untouched
- introduce new leave models alongside them
- do not reinterpret historical shift leave as planned leave

## QA Focus Areas

### Planned leave workflow

- direct guard submits leave
- platform approves/rejects
- SP-owned guard submits leave
- service provider approves/rejects

### Quota handling

- default quota exists
- quota can be edited
- approved paid leave reduces remaining balance correctly

### Operational effect

- overlapping future shifts become visible as impacted
- roster selection excludes guards on approved leave
- matching excludes direct guards on approved leave

### Payout effect

- unapproved early exit pays worked hours only
- approved unpaid leave pays worked hours only
- approved paid leave creates correct payout adjustment
- SP-owned guard still does not see payout/cut directly

## Recommended Decision

The most business-aligned next build is:

1. planned leave + quota + approval
2. operational overlap handling
3. short-term payout accuracy correction
4. paid-leave payout integration
5. later, richer finance operations like adjustment edit/void approval lifecycle

That order gives the cleanest outcome with the least architectural debt.
