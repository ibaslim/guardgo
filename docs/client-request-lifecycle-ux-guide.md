# Client Request Lifecycle UX Guide

This document explains the product in stakeholder language.

It is intentionally focused on:

- where each user goes in the UI
- what each tab means
- what the normal lifecycle is
- what the system now does to reduce confusion

Related documents:

- `docs/client-request-lifecycle-demo-guide.md`
- `docs/shift-guard-leave-management.md`
- `docs/request-shift-replacement-mechanism.md`

## 1. The Core Mental Model

The easiest way to understand the product is:

- `Requests` = staffing and commercial flow
- `Jobs` = accepted or completed work commitments
- `Shifts` = daily operational execution

In the UI, some role labels are simplified further:

- guards see `Offers` instead of treating every item as a generic request
- `Shifts` is presented as `Attendance`
- platform review language is simplified to `Approvals`
- shift exception language is simplified to `Coverage Issues`
- client-ownership language is simplified to `Client Account`
- broadcast / wave language is simplified to `Offer Round`

That separation is important because the system supports both:

- one-time jobs
- long-term recurring contracts

The request is not the attendance record.

The shift slot is the attendance record.

## 2. What Each User Should Do

### Client Admin

The client mainly works in:

- `Requests` to create, publish, update, cancel, and review staffing
- `Jobs` to see accepted, in-progress, and completed work
- `Shifts` to confirm arrivals and monitor daily execution

### Guard Admin

The guard mainly works in:

- `Requests` to review new offers or reconfirmation requests
- `Jobs` to review accepted and completed work history
- `Shifts` to actually operate the job

For guards, the most important rule is:

- `Shifts` is the operational home for check-in, start, and check-out
- the page now shows a `Next Shift Action` card so the guard does not need to guess where to click next

### Service Provider Admin

The provider mainly works in:

- `Requests` to review offers and request changes
- `Jobs` to review accepted provider work
- `Shifts` to roster named guards and monitor daily execution

The page now also shows a `Next Roster Task` card for provider users when an upcoming provider-backed shift still needs a named guard.

## 3. The Normal Lifecycle

### Step 1: Client Creates A Request

The client fills:

- title
- site and map location
- guard count
- guard type
- job start and end
- response cutoff
- optional long-term coverage pattern

### Step 2: Client Publishes

Publishing creates an offer round.

Matching guards and/or providers receive offers.

### Step 3: Guard Or Provider Accepts

Once accepted:

- the item remains part of the request lifecycle
- the accepted work appears under `Jobs`
- operational execution moves into `Shifts`

For non-scheduled one-time work, the system now creates an implicit one-time shift so the same attendance path still exists.

### Step 4: The Guard Executes The Shift

Daily execution is:

1. `Check In`
2. `Client Confirms Arrival`
3. `Start Shift`
4. `Check Out`
5. `Completed`

For clients, the page now shows `Arrival Confirmations Waiting` when a checked-in guard is waiting for approval.

## 4. What We Simplified In UX

The system now exposes clearer operational guidance:

- a role-aware page guide explains what `Requests`, `Jobs`, and `Shifts` mean
- guards get a visible `Next Shift Action` surface instead of having to discover the operational path manually
- service providers get a visible `Next Roster Task` surface for pending provider-backed coverage
- clients get a visible `Arrival Confirmations Waiting` surface for daily approval work
- request cards and drawers now use plain wording like `Response Cutoff`, `Offer History`, `Client Account`, and `Who Can Cover It`
- the reminder notification opens the exact shift slot, not just the general page

This reduces the main confusion point:

- users no longer need to guess whether an action belongs under `Requests`, `Jobs`, or `Shifts`

## 5. Shift Reminder Behavior

Before an upcoming shift:

- the assigned guard receives a reminder in the final `5 minutes` before shift start
- that reminder deep-links to the actionable shift slot

This is designed to support both:

- one-time jobs
- recurring contract shifts

## 6. Attendance Rules

### Check-In Window

- check-in opens in the final `2 hours` before shift start
- check-in is not meant to be an all-day action

### Grace Period

- after shift start, the guard has `15 minutes` to arrive and check in
- if the guard has not arrived by then, the shift moves to `late_risk`

At that point:

- the guard is no longer eligible for normal attendance on that shift
- the guard is notified
- the client is notified
- platform admins are notified

### Leave

Leave is not open-ended.

Current rule:

- only the assigned guard can submit it
- only before shift start
- only within the final `2 hours` before shift start
- it applies to the specific shift being reported

## 7. Why Shifts Matter Even For One-Time Jobs

Stakeholders often expect only long-term contracts to have attendance.

That is no longer the model.

Even a one-time accepted job still needs:

- on-site arrival proof
- client confirmation
- job start
- job completion

So the system treats operational execution through `Shifts` as the single attendance path for both one-time and long-term work.

## 8. Recommended Demo Story

For demos, use this story:

1. Client creates and publishes a request.
2. Guard receives the offer in `Requests`.
3. Guard accepts and sees the work under `Jobs`.
4. The guard gets a pre-start reminder.
5. The reminder opens the shift slot.
6. Guard checks in.
7. Client confirms arrival.
8. Guard starts and completes the shift.
9. The request and job statuses stay synchronized.

## 9. Current UX Position

The main lifecycle confusion points have now been addressed:

- users are shown their next actionable step near the top of the page
- plain-language labels replace most internal broadcast terminology
- one-time and long-term work now share the same attendance path, so the navigation stays consistent

Remaining work is now mostly visual polish, not a missing navigation model.
