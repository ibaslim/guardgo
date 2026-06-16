# QA Guide: API And Supporting Modules

## Why This Document Exists

Not every implemented feature is obvious from the main navigation.

Some modules are:

- startup or support modules
- admin-only
- backend-supported but not exposed as a normal end-user routed page

If QA ignores them, the product can still have serious gaps even when the main business flows pass.

## A. Application Bootstrap Dependencies

### Public configuration

The frontend depends on public config at startup.

Verify:

- the app loads without a broken shell
- login page branding and app name load
- role-based pages still work after a fresh browser session

Good failure checks:

- if public config fails to load, the app should fail gracefully rather than white-screen

### Role metadata

The frontend also depends on role metadata for navigation and access decisions.

Verify:

- expected role-based menu items appear
- hidden items do not show for lower-privilege users
- direct URL access is still blocked even if a menu link is hidden

## B. Current User And Account Support APIs

### `/api/me`

This endpoint is used heavily by the app session model.

Verify:

- session data refreshes after login
- role and tenant context look correct
- platform settings update is reflected after save

### `/api/me/image`

This is backend-supported user profile image handling.

Current note:

- there is no clear major routed UI flow dedicated to this in the current app

Recommended QA:

- test through API or any available internal flow if the release scope includes avatar handling
- otherwise classify as backend-support coverage

## C. Tenant User CRUD

Backend routes exist for:

- list tenant users
- create tenant user
- update tenant user
- delete tenant user

Current note:

- the routed `Dashboard > Users` page looks like static sample data, not an active tenant-user management module

Recommended QA approach:

- do not assume the feature is absent
- confirm with product whether tenant-user CRUD is in current release scope
- if it is in scope, test these endpoints at API level because the current page does not represent the real workflow

## D. Request Matching Preview Utility

The backend supports candidate matching preview.

It checks:

- target type
- province and city scope
- distance eligibility
- weekly availability
- guard type fit
- provider capacity
- provider city-entry coordinates

Current note:

- this is more of an operational or support utility than a standard end-user page

Recommended QA:

- test at API level or through any admin utility path if exposed in the release branch
- cover both guard and provider target types
- include missing-geo and outside-availability cases

## E. Guard-Service Provider Linking

Backend routes exist to:

- link a guard to a service provider
- unlink a guard from a service provider

Current note:

- this is not a visible mainstream routed UI flow in the current app

Recommended QA:

- confirm whether this is handled by an admin operation outside the standard web UI
- if in release scope, test by API and then verify downstream effects:
  - guard ownership label changes
  - guard disappears from direct matching when provider-owned
  - provider capacity calculations use the linked guard

## F. Protected Resource Access

Protected file endpoints exist for:

- tenant image
- user image
- system image
- identity files
- security license files
- police clearance files
- training certificate files
- insurance files

Verify:

- an authenticated owner or allowed actor can open the file
- an unauthorized tenant cannot open another tenant's protected file by direct URL
- deleted files stop resolving correctly

## G. Activity Log Modules

### Tenant activity logs

Verify:

- tenant status changes appear in tenant activity logs
- filters by module, entity, or actor work where exposed

### Billing activity logs

Verify:

- billing updates create visible entries
- context-specific billing log drawers show the correct scope

## H. Admin/System Support Endpoints

These exist but may not be part of the standard QA release pack unless product includes them:

- update public configuration
- upload system logo or system image
- delete system image

Recommended QA:

- cover them only if platform branding or admin console support is in current release scope
- otherwise mark them as admin-support items outside normal end-user sign-off

## I. How To Use This Document In Practice

When a feature is not clearly available from the routed UI:

1. Check whether product intends to release it now.
2. If yes, include API-level or admin-level coverage.
3. If no, mark it explicitly as out of release scope so QA does not silently miss it.
