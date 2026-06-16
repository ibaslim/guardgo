# GuardGo Functional Requirements

## 1. Product Summary

GuardGo is a staffing platform for security coverage.

Its main purpose is to connect:

- clients who need guards
- direct guards who can accept work themselves
- service providers who accept work and then roster their own guards
- platform admins who supervise tenant activation, billing rules, request review, and exceptions

The application is split into:

- Angular frontend for user workflows
- FastAPI backend for authentication, profile management, requests, shifts, billing, invoices, and notifications

## 2. User Roles

### Platform roles

- `admin`
  Full platform access, including tenant management, billing configuration, platform users, review approval, and payout analysis.
- `ops_admin`
  Operational access for request review, shift exceptions, and request oversight.
- `support_admin`
  Operational support access to request and shift flows.
- `compliance_admin`
  Access to tenant review and approval-related workflows.
- `read_only_admin`
  Read-focused operational visibility where allowed.

### Tenant roles

- `client_admin`
  Creates and manages staffing requests, confirms arrivals, manages client profile and saved sites.
- `guard_admin`
  Maintains guard profile, accepts offers, and performs attendance actions for assigned shifts.
- `sp_admin`
  Maintains provider profile, accepts provider offers, rosters named guards, and manages provider-owned guard accounts.

## 3. Authentication And Access Requirements

- Users can sign up as `client`, `guard`, or `service_provider`.
- Signup requires a valid username, email, password, and tenant type.
- Duplicate username or email is rejected.
- Email verification is part of the signup flow.
- Users with pending verification cannot log in normally.
- Verification email resend is supported.
- Login supports:
  - normal username/password
  - optional two-factor verification when required by the account
  - demo login when demo credentials are configured
- Password reset supports:
  - request reset link by email
  - open reset link
  - set a new password
  - rejection if the new password matches the old password
- Invite activation supports platform-created or provider-created users who must:
  - open a valid invite link
  - provide username
  - provide full name
  - set password
- Logout clears the session and access cookie.
- Protected dashboard routes are role-gated and status-gated.

## 4. Onboarding And Profile Requirements

### Shared rules

- Every tenant has a profile area under Settings or Onboarding.
- Profile save uses one main tenant update flow.
- Image upload is supported for tenant profile picture and user profile picture.
- Some profile documents are uploaded separately and stored as protected files.
- Profile data is reused in downstream matching, requests, rostering, and approval flows.

### Guard profile requirements

The guard profile must support:

- personal details
- date of birth
- home address
- mobile and landline phone numbers
- profile picture
- identity document details and identity document file upload
- one or more security licenses, including document upload
- one or more police clearances, including document upload
- one or more training certificates, including document upload
- weekly availability
- preferred guard categories
- travel radius and operational location
- emergency or secondary contact

Current guard onboarding behavior:

- saving the profile during onboarding does not allow the guard to force direct activation
- the record moves into pending activation review instead

### Client profile requirements

The client profile must support:

- legal or company identity details
- website
- primary contact
- secondary contact
- billing address
- billing method details
- preferred guard types
- one or more saved sites

Each saved client site supports:

- site name
- site type
- address
- postal code
- country, province, and city
- latitude and longitude
- manager contact
- manager email
- recommended number of guards
- optional Google Maps link

Current client onboarding behavior:

- when the client completes the first onboarding save, the tenant can become active without the manual two-approval flow

### Service provider profile requirements

The service provider profile must support:

- company identity details
- head office address
- profile picture
- security licenses and their documents
- insurance details and insurance document
- operating regions
- city-level operating coverage entries
- city coverage radius
- latitude and longitude for operating cities
- guard categories offered
- emergency or secondary contact

Current provider onboarding behavior:

- the UI saves first-time onboarding as pending activation for later review

### Address quality requirements

- client sites and provider operating regions rely on valid geo coordinates
- client saved sites without coordinates cannot be reused for request creation
- address and coordinate consistency is checked through the Google Maps consistency helper

## 5. Tenant Management Requirements

### Platform tenant management

Platform users must be able to:

- list tenants in a paginated table
- search by keyword
- filter by tenant type
- filter by tenant status
- sort the table
- open tenant detail
- see tenant profile in read-only detail mode
- review tenant activity logs

### Tenant statuses

Supported statuses include:

- onboarding
- pending activation
- active
- inactive
- banned

Platform users with the right role must be able to:

- approve activation
- deactivate tenants
- ban tenants
- reactivate previously inactive or banned tenants through approval flow

Approval rules:

- activation approval requires two distinct approvers
- duplicate approval by the same approver does not count twice

### Platform users

An `admin` must be able to manage platform admin accounts:

- list users
- view role options
- create user by sending invite
- resend invite
- change role or status
- soft delete
- restore
- permanently delete a previously soft-deleted user

### Service-provider guard administration

An `sp_admin` must be able to:

- list guards owned or managed by the provider
- invite a guard by email
- see pending invite state and expiry
- delete expired pending invites
- request activation or deactivation of a provider-owned guard

Guard status request rules:

- deactivation request requires a reason
- platform-side approval or rejection is required before the request is finalized

## 6. Billing And Travel Policy Requirements

Billing configuration is a platform-admin feature.

The platform must support:

- guard default pay rates by province and city
- guard-specific override pay rates
- service-provider default pay rates by province and city
- service-provider-specific override pay rates
- guard margin defaults
- provider commission defaults
- guard travel policies
- provider travel policies
- sync individual override tables from current defaults
- activity logs for billing-related changes

Travel policy data influences request broadcast behavior.

Travel policy outcomes include:

- candidate is safe to auto-broadcast
- candidate requires manual review
- candidate is outside policy and held back

The system must reject invalid travel policy thresholds, such as a manual review band that is lower than the auto-match limit.

## 7. Request And Matching Requirements

### Request creation

Authorized roles must be able to:

- create draft staffing requests
- edit draft requests
- preview pricing before saving
- save without publishing

Request fields include:

- job title
- fulfillment mode:
  - direct guards only
  - service providers only
  - hybrid
- site details
- requested guard type
- number of guards required
- requested start and end window
- request expiry
- special instructions
- invoice contract type
- invoice cutoff day for long-term work
- invoice recipient email

Platform users can create a request on behalf of a selected client tenant.

Request creation depends on valid client billing data.

### Matching preview

The platform can preview match candidates for guards or service providers.

Matching logic considers:

- active status
- tenant type
- guard ownership rules
- province and city coverage
- geo coordinates and distance
- guard weekly availability
- guard type preference or category fit
- provider capacity from linked guards
- overlapping committed work

### Request publish and review

Publishing a request requires:

- requested start and end times
- site latitude and longitude
- valid commercial and policy context

Publishing creates an offer round, called a request wave.

A wave can be:

- sent immediately
- held for platform review
- returned to the client for changes

Review-triggering situations include travel policy or matching-policy findings.

### Request lifecycle

Request lifecycle states include:

- draft
- submitted
- assigned
- in progress
- cancelled
- closed

Staffing states include:

- pending review
- review returned
- open
- partially filled
- filled
- expired

### Request updates

The system must support:

- publish update for a live request
- reconfirmation flow for already accepted assignees
- additional coverage on a live request
- request status update
- soft delete for terminal requests only

Soft delete rules:

- draft, cancelled, or closed requests can be removed from dashboard listings
- live requests cannot be soft deleted

## 8. Jobs, Offers, And Assignment Requirements

Requests create assignment records for guards or providers.

Assignment statuses include:

- offered
- accepted
- reconfirmation required
- in progress
- completed
- declined
- expired
- filled elsewhere
- cancelled

The application must support:

- guard accepting an offer
- provider accepting an offer
- decline with reason
- reconfirmation after request changes
- view request and wave context from the job detail

Provider acceptance must respect provider-linked guard capacity.

## 9. Schedule, Shift, And Attendance Requirements

### Request scheduling

The platform must support request schedule setup with:

- one-time schedule
- date-range schedule
- recurring weekly schedule

Schedule settings include:

- timezone
- date window
- start and end local times
- recurrence weekdays
- generation horizon
- roster due offset
- unavailable cutoff
- late grace
- no-show cutoff
- check-in geofence distance

Schedule save regenerates future shifts.

### Shifts and slots

The system must support:

- list shifts
- list shift exceptions
- open shift detail
- open shift slot detail
- see shift and slot statuses

Provider-backed accepted coverage creates reserved slots that still need named guard rostering.

### Provider rostering

An `sp_admin` must be able to:

- open a shift
- assign named provider guards to rosterable provider slots
- optionally apply the same roster pattern to future shifts of the same request

### Attendance flow

The main attendance flow is:

1. guard checks in
2. client confirms arrival
3. guard starts shift
4. guard checks out

Platform admins can override start in some operational cases.

Time-based rules exist for:

- check-in opening window
- start timing
- no-show escalation

Generic job status actions must not replace scheduled shift attendance actions.

## 10. Leave, Exception, And Replacement Requirements

### Guard leave

Current leave behavior is shift-focused.

The system supports:

- record pre-start leave for an assigned guard
- keep leave tied to the specific upcoming shift
- notify client and platform ops
- allow early return review
- reconcile future replacement ownership when the original guard returns

Important rule:

- leave does not auto-open replacement coverage anymore

### Shift exceptions

The platform must track exceptions such as:

- unavailable
- late risk
- suspected no-show
- confirmed no-show
- replacement required

Platform or ops users must be able to:

- view exception queue
- open exception detail
- reopen eligible exception slots for replacement coverage

Reopening creates:

- a replacement slot
- a fresh offer round
- preserved history for the original issue

## 11. Invoice And Finance Requirements

### Request invoice history

Request detail must show client-side invoice history for that request.

### My invoices

Guards and service providers must be able to:

- list their payout-side invoices
- open invoice detail
- review line items, planned hours, committed positions, and expected payment

Current invoice behavior:

- scheduled long-term coverage is grouped into weekly payout invoices
- short-term work remains per job

### Platform payout analysis

Platform users must be able to:

- list payout invoices across guards and service providers
- filter by keyword and assignee type
- open invoice detail
- see summary metrics such as:
  - invoice count
  - client revenue
  - payout total
  - platform earning
  - total hours
  - guard payout
  - provider payout
  - platform margin percent

### Finance limitations

Current request UI states that payment capture is mocked.

That means QA should validate:

- pricing and invoice record behavior
- status and amount calculations

but should not expect a real external payment gateway settlement flow in the current build.

## 12. Notifications, Dashboard, And Settings Requirements

### Notifications

Users must be able to:

- open latest notifications from the bell
- view paginated notification history
- filter by all, unread, or read
- mark one notification as read
- mark all notifications as read
- follow action links into the related record

### Dashboard

The dashboard is role-aware.

Examples:

- platform sees operational demand, shifts, and recent jobs
- client sees request and arrival follow-up items
- guard sees next shift action and offers
- service provider sees rostering work, offers, and invoices

### Platform settings

Platform users can update:

- username
- full name

### Tenant settings

Tenant admins use Settings to maintain the tenant profile that matches their tenant type.

## 13. Current QA Exclusions Or Low-Risk Placeholder Areas

These pages currently look like demo or showcase surfaces, not production business flows:

- `Dashboard > Users`
- `Dashboard > Analytics`
- `Dashboard > Components Demo`
- `Dashboard > Forms`

They can be smoke-tested for page load and navigation, but they should not be treated as core functional requirements for business sign-off.
