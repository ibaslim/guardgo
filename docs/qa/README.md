# QA Guide Index

This folder is the plain-language QA handbook for GuardGo.

It is written for:

- QA engineers
- product owners
- operations reviewers
- non-technical stakeholders who need feature awareness before a full end-to-end cycle

## Recommended Reading Order

1. `docs/application-functional-requirements.md`
2. `docs/qa/testing-terms-glossary.md`
3. `docs/qa/full-coverage-matrix.md`
4. `docs/client-request-broadcast-lifecycle.md`
5. `docs/qa/authentication-and-access.md`
6. `docs/qa/onboarding-and-profiles.md`
7. `docs/qa/tenant-and-guard-management.md`
8. `docs/qa/billing-and-finance.md`
9. `docs/qa/requests-shifts-and-coverage.md`
10. `docs/qa/notifications-dashboard-and-settings.md`
11. `docs/qa/api-and-supporting-modules.md`

## Read This First If Terms Feel Unclear

Use `docs/qa/testing-terms-glossary.md` whenever you see product words like:

- tenant
- wave
- assignment
- roster
- slot
- reconfirmation
- geofence
- short-term or long-term

That glossary translates those words into plain QA language.

## Best Companion Docs For Deep Request Testing

Use these when you are testing the request lifecycle in detail:

- `docs/qa/testing-terms-glossary.md`
- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-lifecycle-end-to-end-qa-plan.md`
- `docs/attendance-flow-strict-uat-script.md`
- `docs/shift-guard-leave-management.md`
- `docs/request-shift-replacement-mechanism.md`

## Suggested QA Execution Order

### Pack 1: Access and onboarding

- signup
- email verification
- login and logout
- forgot password and reset password
- invite activation
- first-time onboarding for each tenant type

### Pack 2: Tenant administration

- tenant list and filtering
- tenant approvals
- tenant status actions
- provider guard invite and status request flows
- platform admin user management
- tenant activity logs

### Pack 3: Billing setup

- default rates
- overrides
- margin and commission
- travel policies
- billing activity logs

### Pack 4: Request lifecycle

- create request
- pricing preview
- publish
- review queue
- offer acceptance
- request update
- additional coverage
- request status changes

### Pack 5: Shift execution

- schedule setup
- shift generation
- provider rostering
- check in
- arrival confirmation
- start
- check out
- leave
- exception queue
- replacement coverage

### Pack 6: Finance and notifications

- request invoice history
- my invoices
- platform payout invoices
- notifications and deep links
- dashboard refresh and role views

### Pack 7: Supporting and API-backed modules

- public config bootstrap
- role metadata bootstrap
- protected file access checks
- tenant user CRUD scope check
- request matching preview utility
- guard-provider link and unlink scope check

## Environment And Data Checklist

Before the QA cycle starts, prepare:

- one active `client_admin`
- one active direct `guard_admin`
- one active `sp_admin`
- at least two active provider-owned guards
- billing defaults for the same province and city that the client site uses
- client sites with valid latitude and longitude
- provider operating regions with valid city-level coordinates
- at least one guard and one provider who both match the same request area

## Evidence To Capture

Capture this whenever a scenario fails or looks suspicious:

- user role
- tenant type
- page or flow name
- request id, wave id, shift id, slot id, or invoice id when available
- exact steps
- actual result
- expected result
- screenshot or short recording
- raw error text

## Important Scope Notes

Treat these pages as low-priority smoke test surfaces, not core sign-off features:

- `Dashboard > Users`
- `Dashboard > Analytics`
- `Dashboard > Components Demo`
- `Dashboard > Forms`

## Final Completeness Rule

Do not assume the feature set is fully covered just because the main request flow passed.

Use:

- `docs/qa/full-coverage-matrix.md`
  to confirm every module has a coverage owner
- `docs/qa/api-and-supporting-modules.md`
  to catch backend-supported or admin-only modules that are easy to miss
