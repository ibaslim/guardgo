# QA Guide: Billing And Finance

## What This Feature Does

This area controls the commercial rules used by pricing, invoices, and payout analysis.

It is mainly a platform-admin workflow.

## A. Billing Configurations

### Main tabs

- Guard Billing
- Service Provider Billing
- Margin & Commission
- Travel Policy

### Guard billing scenarios

Verify:

- default guard rates load
- province rows expand and collapse
- province default can be applied down to city rows
- changes save correctly
- activity logs open for default guard rates

### Guard override scenarios

Verify:

- a specific guard can be selected
- override rates load for that guard
- override values save correctly
- sync from defaults copies current default values into the guard override table

### Service provider billing scenarios

Verify:

- provider default rates load and save
- a specific provider can be selected
- provider override rates load and save
- sync from defaults copies current default values into the provider override table

### Margin and commission scenarios

Verify:

- guard margin defaults load and save
- provider commission defaults load and save
- activity logs open for both areas

### Travel policy scenarios

Verify for both guards and providers:

- travel policy rows load
- changes save
- no-change save behavior is sensible
- invalid threshold combinations are rejected
- auto-broadcast threshold, manual-review threshold, and outside-policy behavior are understood by QA before request testing

Travel policy is critical because it affects whether a request wave:

- sends automatically
- waits for manual review
- holds candidates back entirely

## B. Pricing Preview

Pricing preview is available during request creation and request update.

Verify:

- preview works only when the request has enough billing and location data
- client rate, guard rate, provider rate, and estimated totals look populated
- invoice settings preview matches the selected contract type
- changing schedule type changes the expected contract type when schedule-driven behavior applies
- preview still behaves correctly for platform-created requests on behalf of a client tenant

## C. Request Invoice History

Inside request detail, verify:

- invoice history appears for the request
- invoice status is visible
- invoice detail opens
- line items and amounts look consistent with the request window or schedule
- revised invoice behavior is visible when a request changed after earlier invoice generation

## D. My Invoices

This page is for:

- direct guards
- service providers

Verify:

- invoice list loads
- summary cards update
- invoice detail drawer opens
- line items are visible
- payout amount, hours, and rate are readable

Important expectation:

- these are payout-side invoices only, not the client charge view

## E. Platform Payout Analysis

This page is for platform roles.

Verify:

- invoice list loads
- keyword filter works
- assignee type filter works
- summary metrics update
- invoice detail drawer opens
- linked payout context is visible
- both guard and service-provider assignee types are covered

Key metrics to check:

- invoice count
- total client revenue
- total payout
- total platform earning
- total hours
- total guard payout
- total provider payout

## Finance Limitation To Remember

Current request screens explicitly describe payment capture as mocked.

QA should validate:

- saved commercial data
- calculations
- invoice records
- status transitions

QA should not expect:

- real external card charging
- real bank settlement

## F. Billing Activity Logs

Verify:

- activity log drawer opens from each billing area that offers it
- the log context matches the selected entity:
  - guard defaults
  - guard override
  - provider defaults
  - provider override
  - guard margins
  - provider commissions
- recent save actions appear after refresh
