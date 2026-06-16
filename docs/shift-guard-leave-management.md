# Shift Guard Leave Management

This document describes the current leave rule for shift execution.

Related documents:

- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-shift-replacement-mechanism.md`

## Current Rule

Leave is now a `shift-specific`, `day-of / near-start` action.

It is no longer treated as a planned multi-day future range for automatic coverage planning.

## Who Can Report Leave

Only the assigned `guard_admin` can report leave, and only for that guard's own upcoming shift.

Current non-allowed actors:

- `sp_admin`
- platform admins acting on behalf of the guard
- client admins

## Timing Rule

Leave can only be reported:

- before the shift starts
- within the final `2 hours` before the scheduled shift start time

If the guard tries earlier than that window, the request is rejected.

## Scope Rule

Leave is now `one shift at a time`.

Even though the API payload still carries `start_at_utc` and `end_at_utc`, the backend resolves the selected assigned shift and stores leave against that actual shift window.

Practical meaning:

- one leave report = one upcoming assigned shift
- the system does not use one leave request to pre-mark multiple future dates anymore

## What Happens When Leave Is Reported

When a valid leave report is submitted:

1. the assigned shift slot is marked `unavailable`
2. a `leave_reported` attendance event is recorded
3. the client is notified to review the shift and request / republish replacement coverage manually
4. platform admins are notified for operational follow-up
5. if the slot is provider-backed, the service provider is also notified

Important:

- the system does **not** auto-open replacement anymore
- the system does **not** auto-create a replacement wave from leave anymore

## Relationship To Check-In

The same `2-hour` pre-start rule is also the check-in opening window.

That means:

- guard cannot check in hours or days early
- guard can report leave only in the same late pre-start operational window

## Early Return

If a leave record is still active and the shift has not started yet, it can still be ended early.

If no replacement has been manually opened yet:

- the original slot is restored

If a replacement was manually opened later by ops:

- open future replacement work can still be cancelled and restored through the existing return / reconciliation flow

## What Leave No Longer Means

Leave is no longer used for:

- multi-day planned absence
- pre-marking many future shifts
- automatic replacement planning
- provider/platform filing leave on behalf of a guard

## Operational Summary

Current leave is a controlled last-window attendance exception:

- `who`: assigned guard only
- `when`: within 2 hours before start
- `scope`: one shift
- `effect`: mark unavailable and notify client / ops
- `replacement`: manual follow-up, not automatic
