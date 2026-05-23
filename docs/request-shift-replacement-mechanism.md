# Request Shift Replacement Mechanism

This document explains how replacement coverage works after the current leave / late-arrival policy change.

Related documents:

- `docs/client-request-lifecycle-demo-guide.md`
- `docs/shift-guard-leave-management.md`

## Main Principle

Replacement is now a `manual escalation workflow`, not an automatic background recovery workflow.

That is true for both:

- guard-reported leave
- missed arrival after grace period

## Current Trigger Cases

Replacement may be needed when:

1. the assigned guard reports leave in the allowed pre-start window
2. the guard misses the `15 minute` arrival grace period
3. the slot later settles into `no_show_confirmed`
4. platform manually decides that the slot must be reopened for replacement

## What The System Does Automatically

The system now does these things automatically:

- marks the slot `unavailable` when a valid leave is reported
- marks the slot `late_risk` after the guard misses the 15 minute grace period
- marks the slot `no_show_confirmed` after the later no-show cutoff
- notifies the guard, client, and platform admins when the guard misses the grace period without valid leave

The system does **not** automatically:

- create a replacement slot
- create a replacement wave
- broadcast replacement offers

## Client Notification Rule

When the guard misses the grace period without valid leave:

- the client is notified that the guard did not arrive in time
- the client is told to review and republish / request replacement coverage for that shift

In practice, this is an operational instruction and escalation signal.

## Platform Responsibility

Platform admins remain the operational owners for direct-guard recovery.

If replacement must be reopened:

1. platform reviews the failed slot
2. platform reopens the slot for replacement
3. a replacement slot is created
4. a replacement wave is created
5. for direct-guard replacement, that wave remains `pending_review` until platform releases it

So `direct guard replacement` is still platform-managed, but it is now intentionally manual instead of automatic.

## Provider-Backed Slots

Provider-backed slots remain provider-first operationally.

Current meaning:

- if the assigned guard belongs to a service provider, the provider is also notified
- provider ops should try to re-roster another linked guard first
- if that is not enough, platform can still reopen replacement coverage manually

## Attendance Failure Timeline

For an assigned shift slot:

1. `2 hours before start`
   - guard can report leave
   - guard can check in once physically arriving

2. `shift start to +15 minutes`
   - grace period

3. `after +15 minutes with no arrival`
   - slot becomes `late_risk`
   - guard is treated as no longer eligible for the shift
   - guard, client, and platform admins are notified

4. `after later no-show cutoff`
   - slot becomes `no_show_confirmed`
   - this preserves audit state
   - replacement is still manual

## Manual Replacement Path

When ops decides to reopen coverage:

1. original failed slot is treated as the exception slot
2. platform reopens it
3. replacement slot is created
4. replacement wave is created
5. candidates can then receive offers after review

This keeps the system auditable while avoiding silent automatic replacement behavior.

## Current Summary

Today:

- no automatic replacement after leave
- no automatic replacement after late arrival / no-show
- client and platform are explicitly notified instead
- direct-guard replacement still stays under platform control
- provider-backed recovery still starts with provider action first
