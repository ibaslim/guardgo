# QA Guide: Tenant And Guard Management

## What This Feature Does

This area lets the platform supervise tenant lifecycle and lets service providers manage their own linked guard accounts.

## A. Platform Tenant Management

### Main features

- tenant list
- keyword search
- type filter
- status filter
- sorting
- tenant detail drawer
- activity logs
- approval and status actions

### Happy-path scenarios

Verify:

- tenant table loads
- search finds the expected tenant
- type and status filters work together
- sorting changes row order
- opening a tenant shows the correct profile
- activity log drawer loads for the selected tenant

### Status and approval scenarios

Verify:

- a pending tenant can be approved
- two different approvers are needed before activation is complete
- the same approver cannot count twice
- inactive tenants can be reactivated through approval path
- banned tenants can be reactivated through approval path
- deactivate changes the status to inactive
- ban changes the status to banned

### Role checks

Verify:

- tenant management is available only to allowed platform roles
- tenant admins cannot access the platform tenant table

## B. Tenant Activity Logs

This is easy to miss because it sits inside tenant detail rather than as a major navigation item.

Verify:

- activity log drawer opens from tenant detail
- tenant status changes appear in the log
- relevant actor information is visible
- pagination works when enough log entries exist
## C. Platform Admin User Management

### Main features

- list platform users
- create by invite
- resend invite
- edit role and status
- soft delete
- restore
- permanent delete after soft delete

### Scenarios

Verify:

- role list loads
- creating a user sends an invite and adds the user to the list
- invite-pending state is visible
- resend invite works
- edit saves changes
- delete reason is required
- soft-deleted user can be restored
- permanently deleted user disappears from the list

## D. Service Provider "My Guards" Area

### Main features

- list provider guards
- invite guard by email
- view invite state
- request guard activation
- request guard deactivation
- delete expired invite

### Happy-path scenarios

Verify:

- guard invite succeeds for a valid email
- invited guard appears in the list with pending invite state
- provider can open guard detail
- expired invite can be deleted
- activation request can be submitted
- deactivation request can be submitted with a reason

### Validation checks

Verify:

- blank invite email is rejected
- deactivation request without reason is rejected

## E. Platform Review Of Guard Status Requests

Verify:

- pending provider guard status requests can be approved by an allowed platform role
- pending provider guard status requests can be rejected by an allowed platform role
- approval or rejection changes the visible request state

## F. Admin-Only Or API-Backed Tenant Management Items

These items exist in backend support but are not obvious from the normal routed UI:

- tenant user CRUD
- guard link to service provider
- guard unlink from service provider

Use `docs/qa/api-and-supporting-modules.md` for those checks if they are in release scope.

## Evidence To Capture

For tenant and guard admin issues, capture:

- acting role
- tenant id
- guard tenant id when relevant
- previous status
- new status
- whether the action came from platform side or provider side
