# GuardGo Documentation Map

This folder now has two kinds of documents:

- product and functional requirement guides for understanding what the application does
- QA guides for end-to-end test execution

## Best Starting Points

- `docs/application-functional-requirements.md`
  Use this to understand the full feature set, roles, and business flows.
- `docs/qa/README.md`
  Use this to plan the QA cycle, environments, test data, and execution order.
- `docs/qa/testing-terms-glossary.md`
  Use this when QA readers need plain-language explanations of GuardGo-specific terms and status words.

## Request / Shift Deep-Dive Docs

These are the main deep-dive documents for the most complex part of the product:

- `docs/client-request-broadcast-lifecycle.md`
  Main plain-language explanation of the client request -> broadcast -> job -> schedule -> shift flow.
- `docs/request-lifecycle-end-to-end-qa-plan.md`
  Full UAT and execution plan for the request lifecycle.
- `docs/attendance-flow-strict-uat-script.md`
  Strict attendance-step verification.
- `docs/request-shift-replacement-mechanism.md`
  Replacement reopening and refill behavior.
- `docs/shift-guard-leave-management.md`
  Shift-level leave and return handling.

Use them together with the new QA guides under `docs/qa/`.

## Feature Areas Covered In The New Docs

- authentication, verification, invite activation, password reset, login, logout, and route access
- onboarding and profile completion for guards, clients, and service providers
- tenant management, activation approvals, and service-provider guard administration
- billing setup, travel policy configuration, and finance views
- staffing request creation, matching, review, job offers, shifts, attendance, leave, exceptions, and replacement coverage
- notifications, dashboard behavior, and platform settings

## Important QA Scope Notes

These surfaces exist in the frontend but should not be treated as core business workflows for sign-off:

- `Dashboard > Users`
  Current page shows static sample data.
- `Dashboard > Analytics`
  Current page shows static sample data.
- `Dashboard > Components Demo`
  Internal UI showcase.
- `Dashboard > Forms`
  Internal form showcase.

There is also older legacy code in `client/src/app/pages/tenant/` that is not part of the active routed workflow.
