# QA Handbook

`docs/qa/request-job-lifecycle-manual.md` is the main QA runbook.

If QA follows only one document for the current implemented system, use that manual.

## Use This Folder Like This

### Primary document

1. [request-job-lifecycle-manual.md](./request-job-lifecycle-manual.md)

This is the preferred end-to-end manual for:

- request creation and pricing
- guard and provider acceptance
- provider `Add Coverage`
- provider rostering
- shift execution
- leaves and leave quota
- invoices and payout behavior
- hybrid provider adjustments
- platform finance and overview sanity

### Supporting documents

Use these only when the main manual needs deeper module detail:

- [testing-terms-glossary.md](./testing-terms-glossary.md)
- [authentication-and-access.md](./authentication-and-access.md)
- [onboarding-and-profiles.md](./onboarding-and-profiles.md)
- [tenant-and-guard-management.md](./tenant-and-guard-management.md)
- [billing-and-finance.md](./billing-and-finance.md)
- [requests-shifts-and-coverage.md](./requests-shifts-and-coverage.md)
- [notifications-dashboard-and-settings.md](./notifications-dashboard-and-settings.md)
- [api-and-supporting-modules.md](./api-and-supporting-modules.md)
- [full-coverage-matrix.md](./full-coverage-matrix.md)

## What Was Removed

The old focused hybrid-adjustment QA runbook was removed because it duplicated the main lifecycle manual and drifted from the implemented behavior.

The current rule is simple:

- one primary QA manual
- several supporting references
- no competing end-to-end scripts for the same feature set

## Suggested Reading Order

1. [request-job-lifecycle-manual.md](./request-job-lifecycle-manual.md)
2. [testing-terms-glossary.md](./testing-terms-glossary.md)
3. [full-coverage-matrix.md](./full-coverage-matrix.md)

Then read only the supporting module docs needed for the specific regression or release area.

## Evidence Rule

When a scenario fails, always capture:

- role
- tenant type
- page or route
- request / assignment / shift / slot / leave / invoice id
- exact expected result
- exact actual result
- screenshot or recording
- visible error text
- API payload or response when available
