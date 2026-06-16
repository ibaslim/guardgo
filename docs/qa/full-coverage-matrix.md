# QA Guide: Full Coverage Matrix

## Why This Document Exists

The other QA guides explain features by business area.

This document does something different:

- lists every meaningful module or feature area found in the current Angular and FastAPI implementation
- tells QA where that feature is already documented
- shows what level of testing is expected
- highlights API-supported or admin-only items that are easy to miss

Use this as the final completeness checklist before sign-off.

## Coverage Levels

- `Deep`
  Full end-to-end and negative-path coverage is expected.
- `Focused`
  Test the module thoroughly, but mostly within its own scope rather than a long cross-module journey.
- `Smoke`
  Confirm load, navigation, and basic sanity only.
- `API / Admin`
  Supported in backend or privileged admin flows, but not a standard routed end-user flow in the current UI.

## Module Inventory

| Module / Feature | Current Surface | Coverage Level | Primary Doc |
| --- | --- | --- | --- |
| Signup | UI | Deep | `docs/qa/authentication-and-access.md` |
| Email verification | UI | Deep | `docs/qa/authentication-and-access.md` |
| Login | UI | Deep | `docs/qa/authentication-and-access.md` |
| Two-factor authentication | UI when enabled | Focused | `docs/qa/authentication-and-access.md` |
| Demo login | UI when configured | Focused | `docs/qa/authentication-and-access.md` |
| Forgot password | UI | Deep | `docs/qa/authentication-and-access.md` |
| Reset password by token | UI | Deep | `docs/qa/authentication-and-access.md` |
| Invite activation | UI | Deep | `docs/qa/authentication-and-access.md` |
| Logout and session refresh | UI | Focused | `docs/qa/authentication-and-access.md` |
| Route guards and role access | UI | Deep | `docs/qa/authentication-and-access.md` |
| Public config bootstrap | App startup | Focused | `docs/qa/api-and-supporting-modules.md` |
| Public role metadata bootstrap | App startup | Focused | `docs/qa/api-and-supporting-modules.md` |
| Guard onboarding and settings | UI | Deep | `docs/qa/onboarding-and-profiles.md` |
| Client onboarding and settings | UI | Deep | `docs/qa/onboarding-and-profiles.md` |
| Service provider onboarding and settings | UI | Deep | `docs/qa/onboarding-and-profiles.md` |
| Tenant profile images | UI | Focused | `docs/qa/onboarding-and-profiles.md` |
| Guard document uploads | UI | Focused | `docs/qa/onboarding-and-profiles.md` |
| Provider insurance upload | UI | Focused | `docs/qa/onboarding-and-profiles.md` |
| Protected document retrieval security | Mixed | Focused | `docs/qa/onboarding-and-profiles.md` |
| Tenant list, filters, sort, detail | UI | Deep | `docs/qa/tenant-and-guard-management.md` |
| Tenant activation approval | UI | Deep | `docs/qa/tenant-and-guard-management.md` |
| Tenant deactivate / ban / reactivate | UI | Deep | `docs/qa/tenant-and-guard-management.md` |
| Tenant activity logs | UI | Focused | `docs/qa/tenant-and-guard-management.md` |
| Platform admin user management | UI | Deep | `docs/qa/tenant-and-guard-management.md` |
| Service provider "My Guards" | UI | Deep | `docs/qa/tenant-and-guard-management.md` |
| Provider guard status request review | UI + role-restricted | Focused | `docs/qa/tenant-and-guard-management.md` |
| Tenant user CRUD (`/api/users`) | Backend-supported, not a clear active routed UI module | API / Admin | `docs/qa/api-and-supporting-modules.md` |
| Current user profile update (`/api/me`) | UI for platform settings, backend for others | Focused | `docs/qa/notifications-dashboard-and-settings.md` and `docs/qa/api-and-supporting-modules.md` |
| Current user image (`/api/me/image`) | Backend-supported, no clear active routed flow | API / Admin | `docs/qa/api-and-supporting-modules.md` |
| Guard-provider link / unlink | Backend-supported | API / Admin | `docs/qa/api-and-supporting-modules.md` |
| Billing defaults | UI | Deep | `docs/qa/billing-and-finance.md` |
| Billing overrides | UI | Deep | `docs/qa/billing-and-finance.md` |
| Margin and commission | UI | Deep | `docs/qa/billing-and-finance.md` |
| Travel policy | UI | Deep | `docs/qa/billing-and-finance.md` |
| Billing activity logs | UI | Focused | `docs/qa/billing-and-finance.md` |
| Request pricing preview | UI | Deep | `docs/qa/billing-and-finance.md` and `docs/qa/requests-shifts-and-coverage.md` |
| Request creation | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request update | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request publish | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request review queue | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request wave history and detail | UI | Focused | `docs/qa/requests-shifts-and-coverage.md` |
| Manual request assignment | UI | Focused | `docs/qa/requests-shifts-and-coverage.md` |
| Request additional coverage | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request status changes | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request soft delete | UI | Focused | `docs/qa/requests-shifts-and-coverage.md` |
| Request matching preview (`/api/request-matching/preview`) | Backend-supported utility | API / Admin | `docs/qa/api-and-supporting-modules.md` |
| Jobs / offers | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Schedule creation and maintenance | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Shift list and shift calendar | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Shift detail and slot detail | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Provider rostering | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Guard attendance flow | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Bulk client arrival confirmation | UI | Focused | `docs/qa/requests-shifts-and-coverage.md` |
| Guard leave | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Leave return reconciliation | UI | Focused | `docs/qa/requests-shifts-and-coverage.md` |
| Shift exception queue | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Replacement coverage reopen | UI | Deep | `docs/qa/requests-shifts-and-coverage.md` |
| Request invoice history | UI | Focused | `docs/qa/billing-and-finance.md` |
| My invoices | UI | Deep | `docs/qa/billing-and-finance.md` |
| Platform payout invoices | UI | Deep | `docs/qa/billing-and-finance.md` |
| Notification bell mini inbox | UI | Focused | `docs/qa/notifications-dashboard-and-settings.md` |
| Notifications page | UI | Deep | `docs/qa/notifications-dashboard-and-settings.md` |
| Dashboard role views | UI | Focused | `docs/qa/notifications-dashboard-and-settings.md` |
| Platform settings | UI | Focused | `docs/qa/notifications-dashboard-and-settings.md` |
| Demo pages: Users, Analytics, Components Demo, Forms | UI | Smoke | `docs/qa/notifications-dashboard-and-settings.md` |

## Modules QA Should Not Accidentally Skip

These are the most commonly missed areas because they are not always top-of-mind during request lifecycle testing:

- public config and role metadata bootstrap
- tenant activity logs
- billing activity logs
- request wave history and review return notes
- manual assignment path
- bulk arrival confirmation
- protected file access checks
- provider expired invite cleanup
- platform payout invoice filters and detail drawer
- notification bell dropdown, not only the full notifications page

## Final Sign-Off Rule

QA sign-off should not be marked complete until every `Deep` and `Focused` item above has:

- at least one positive-path test
- at least one role/permission check where relevant
- at least one meaningful failure or validation check where relevant
