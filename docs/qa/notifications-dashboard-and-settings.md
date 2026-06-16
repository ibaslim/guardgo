# QA Guide: Notifications, Dashboard, And Settings

## What This Feature Does

This area gives users day-to-day visibility into what needs attention and lets them perform light account maintenance.

## A. Dashboard

### What to expect

The dashboard is not the same for every role.

Typical examples:

- platform users see requests needing staffing attention, upcoming shift workload, and recent job activity
- service providers see offers awaiting response, roster work, and payout invoices
- guards see offers awaiting response, upcoming assignments, and payout invoices
- clients see request workload and arrival confirmation follow-up

### Core checks

Verify:

- the page loads after login
- the correct role-specific sections appear
- summary cards and list sections link into the correct tab of the Requests or Invoices page
- focused operational widgets open the next task quickly

## B. Notifications

### Main features

- bell unread count
- latest notifications
- full inbox page
- all, unread, and read filters
- mark one as read
- mark all as read
- open linked record from notification

### Scenarios

Verify:

- unread count increases when a new event occurs
- opening an unread notification marks it read
- mark all read clears the unread count
- action links open the correct destination
- notification list pagination works
- the bell dropdown and the full inbox stay consistent with each other

Good events to use during QA:

- new request offer
- review returned
- shift attendance change
- leave or exception event

## C. Platform Settings

This page is for platform roles only.

Verify:

- full name loads from session
- username loads from session
- valid update saves successfully
- invalid username format is rejected
- tenant users cannot access this page

## D. Tenant Settings Access

Verify:

- client admins open the client settings view
- guard admins open the guard settings view
- service providers open the provider settings view
- the right form appears after page refresh

## E. Platform And Current-User Settings Support

Verify:

- session refresh after saving settings updates the visible username or full name
- avatar or user-display areas do not show stale account data after profile changes

If current release scope includes direct current-user image handling or system branding, also use:

- `docs/qa/api-and-supporting-modules.md`

## F. Smoke-Only Pages

These pages currently look like showcase or placeholder screens:

- `Dashboard > Users`
- `Dashboard > Analytics`
- `Dashboard > Components Demo`
- `Dashboard > Forms`

Recommended QA treatment:

- confirm page load
- confirm navigation does not crash
- do not block product sign-off on their sample data content
