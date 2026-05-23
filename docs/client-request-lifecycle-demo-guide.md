# Client Request Lifecycle Demo Guide

This document is the current end-to-end story for demos.

It explains how a client request moves from creation to staffing, daily execution, exception handling, and completion.

Related documents:

- `docs/client-request-lifecycle-ux-guide.md`
- `docs/client-request-broadcast-lifecycle.md`
- `docs/shift-guard-leave-management.md`
- `docs/request-shift-replacement-mechanism.md`
- `docs/attendance-flow-strict-uat-script.md`

For a strict demo rehearsal with fixed timestamps and expected status values, use:

- `docs/attendance-flow-strict-uat-script.md`

## 1. What The Client Creates

The client creates a `request`.

The request captures:

- title
- site and map location
- guard type
- number of guards needed
- job start and job end
- response cutoff
- optional coverage pattern for long-term work

The request is the commercial / staffing header.

It is not the daily attendance record.

## 2. What Happens When The Client Publishes

When the request is published:

1. the current request revision is frozen for matching
2. an offer round is created
3. matching guards and/or service providers receive in-app offers

The system can support:

- direct individual guards
- service providers
- mixed fulfillment on the same request

## 3. What The Guard Or Service Provider Accepts

Acceptance creates committed work.

At this point:

- `Requests` shows the offer / staffing side
- `Jobs` shows the accepted / in-progress / completed work side
- `Shifts` handles the actual attendance steps

For service providers:

- the provider can accept commercial responsibility first
- then roster a named provider-owned guard onto the actual shift slot

## 4. How The Work Enters Operations

All accepted work is executed through the `Shifts` layer.

That includes:

- long-term scheduled work
- recurring weekly work
- date-range work
- one-time non-scheduled jobs

For non-scheduled one-time jobs, the system creates an implicit one-time shift so the same attendance process still exists.

## 5. What The Guard Sees Operationally

The guard works from the shift slot, not from the raw request.

Daily operational flow:

1. `Check In`
2. `Client Confirms Arrival`
3. `Start Shift`
4. `In Progress`
5. `Check Out`
6. `Completed`

The client request then stays synchronized with that operational state.

## 6. Check-In Rule

Check-in is not open all day.

Current rule:

- check-in opens in the final `2 hours` before scheduled shift start
- check-in is blocked after the shift ends
- geo validation still checks whether the guard is actually at the site

This applies to:

- one-time jobs
- long-term scheduled jobs
- weekend shifts
- overnight shifts

## 7. Client Arrival Approval

Check-in by itself is not enough.

After the guard checks in:

- the client receives an arrival notification
- the client confirms the arrival
- only then can the guard start normally

Platform can still override start when needed, but that is an exceptional path.

## 8. Grace Period Rule

After scheduled shift start, the guard gets a `15 minute` grace period to arrive and check in.

If the guard has not arrived by the end of that grace period:

- the slot becomes `late_risk`
- the guard is treated as no longer eligible for that shift
- the guard receives a warning notification
- the client receives a warning notification
- platform admins receive an escalation notification

The client notification tells them that replacement coverage must now be reviewed / republished for that shift.

## 9. Leave Rule

Leave is now tightly controlled.

Current leave policy:

- only the assigned `guard_admin` can report leave
- leave must be reported before shift start
- leave can only be reported within the final `2 hours` before shift start
- leave is now `one shift at a time`

When leave is reported:

- that shift slot is marked `unavailable`
- client is notified
- platform admins are notified
- provider is also notified if it is a provider-backed guard

The system does not auto-create replacement from leave anymore.

## 10. No-Show Confirmation

If the guard still never arrives after the later no-show cutoff:

- the slot becomes `no_show_confirmed`

That is primarily for audit and operational clarity.

Replacement is still manual at that point.

## 11. Replacement Responsibility

### Direct Guard

Direct-guard replacement is platform-managed.

If replacement must be reopened:

1. platform reviews the failed slot
2. platform reopens replacement coverage
3. a replacement slot / offer round can then be created
4. direct-guard replacement stays review-controlled before offers go out

### Provider-Backed Guard

Provider-backed replacement is provider-first.

Meaning:

- provider is expected to re-roster another linked guard first
- if that still does not solve coverage, platform can reopen replacement manually

## 12. Long-Term Contracts

Long-term work is handled through recurring or date-range shift generation.

Examples:

- Monday to Sunday with Tuesday off:
  - use `Recurring Weekly`
  - select every day except Tuesday

- Daily contract for a month:
  - use `Date Range`

- Weekend-only contract:
  - recurring weekly with Saturday and Sunday selected

Attendance still happens one shift slot at a time.

## 13. Night Shifts

Night shifts are supported.

If a shift end time is earlier than the start time, the system treats it as overnight and carries the end into the next day.

The same lifecycle still applies:

- check in
- confirm
- start
- check out

## 14. Weekend Shifts

Weekend coverage is supported directly by schedule generation.

So:

- Saturday / Sunday one-time jobs work
- recurring weekend schedules work
- weekday-only schedules also work

## 15. Completion

When the guard checks out:

- the slot becomes `completed`
- the shift updates
- the parent accepted job updates
- once the committed request work is fully completed, the client request closes

For clients:

- `Requests` remains the staffing / lifecycle record
- `Jobs` remains the accepted / in-progress / completed work record

## 16. Current Demo Summary

The demo story is now:

1. client creates request
2. client publishes request
3. guard or provider accepts
4. work appears in jobs and shifts
5. guard checks in on site
6. client confirms arrival
7. guard starts work
8. guard completes work
9. request closes when committed work is done

If something goes wrong:

- guard can report leave only in the final 2 hours before start
- missing the 15 minute grace period triggers late-arrival escalation
- client and platform are told to handle replacement manually

That is the current lifecycle the product should demo.

## 17. Recommended Demo Language

For non-technical stakeholders, use the same simple words that now appear in the UI:

- say `offer round` instead of `broadcast wave`
- say `client account` instead of `client tenant`
- say `response cutoff` instead of `request expiry`
- say `plan ongoing shifts` instead of `manage schedule`
- say `coverage issues` instead of `shift exceptions`
