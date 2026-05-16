# Client Request and Broadcast Lifecycle

This document explains how a client request moves from draft to broadcast, how candidates receive offers, when platform admins must review a request, and what happens when a request changes over time.

The goal is to keep the workflow easy to understand for clients, platform admins, guards, and service providers.

## Purpose

The platform should allow a client to create a request for guards, publish it, notify matching candidates, collect acceptances, and keep the whole process auditable and controlled.

This lifecycle also supports mixed fulfillment:

- individual guards can accept a request
- service providers can accept the same request at the same time
- the request is considered filled when the required number of guard slots is covered

## Core Rules

- Broadcast is `in-app only`.
- Broadcast notifications go to `tenant admins only`.
- A request uses saved `matched_candidates` when a broadcast wave is created.
- One request can be fulfilled by both `individual guards` and `service providers`.
- A direct guard acceptance fills `1` slot.
- A service provider acceptance fills the number of slots the provider commits to at acceptance time.
- When all required slots are filled, remaining open offers stay visible but become non-actionable.
- If capacity opens again later, the system creates a `fresh broadcast wave`. It does not reopen old offers.
- A candidate who declined in an earlier wave can still receive a later wave for the same request.
- Request details remain viewable even when the request is no longer actionable.

## Main Terms

- `Client Request`: the main staffing request created by the client.
- `Broadcast Wave`: one notification run for a request at a specific point in time.
- `Offer`: the actionable item sent to a candidate tenant for a specific wave.
- `Accepted Assignment`: an offer that has been accepted and now counts toward staffing.
- `Request Expiry`: the deadline chosen by the client for the request itself.
- `Wave Expiry`: the deadline calculated by the system for one broadcast wave.
- `Open Slots`: the number of remaining guard positions that still need coverage.
- `Reconfirmation Required`: the state used when an already accepted assignment must confirm again after a material request change.

## Main Actors

- `Client Tenant Admin`
  - creates and manages the request
  - publishes the request
  - can request more coverage later
  - can update allowed fields while the request is still active

- `Platform Admin`
  - can review requests that cannot be safely auto-broadcast
  - can approve and release a blocked wave
  - can return a request to the client for correction

- `Ops Admin`
  - shares the same review visibility for broadcast review cases
  - focuses on operational checks such as distance and location safety

- `Guard Tenant Admin`
  - receives offers for individual guard participation
  - reviews request details and accepts or declines

- `Service Provider Tenant Admin`
  - receives offers for service-provider participation
  - reviews request details and accepts or declines
  - chooses how many slots the provider can cover when accepting

## Request Lifecycle

### 1. Draft

The client creates a request in draft mode.

In draft mode, the client can prepare:

- title
- site details
- requested guard type
- requested time window
- number of guards needed
- special instructions
- request expiry

No candidate is notified at this stage.

### 2. Publish Request

When the client is ready, the request is published.

Publishing does two things:

1. freezes the current request revision for broadcast purposes
2. creates the first broadcast wave if the request is safe to auto-broadcast

If the request requires platform review, it moves into review instead of sending notifications immediately.

### 3. Broadcast Wave

Each wave uses the saved match snapshot from the request.

The wave sends in-app offers to:

- matching individual guard tenants
- matching service provider tenants

Only `tenant admins` receive the notification.

Each candidate tenant receives at most one actionable offer per wave.

### 4. Candidate Response

The candidate opens the request details from the offer and then decides whether to respond.

Possible outcomes:

- `accept`
- `decline`
- `ignore until offer expires`

Acceptances are wave-specific. A decline in one wave does not block future waves for the same request.

### 5. Partial Fill or Full Fill

As acceptances come in, the system tracks open slots.

- if some slots are filled, the request becomes `partially filled`
- if all slots are filled, the request becomes `filled`

When the request becomes fully filled:

- remaining open offers stay visible
- those offers become non-actionable
- candidates can still open the detail view
- the detail page shows that all slots have already been filled

### 6. In Progress and Completion

Once work begins, the request moves into execution.

Later, when the committed work is completed, the request can be closed as completed.

## Hybrid Fulfillment Rules

One request can be fulfilled by both channels at the same time.

Example:

- client needs `4` guards
- `2` direct guards accept
- one service provider accepts `2` slots

The request is now fully filled.

Rules:

- direct guard acceptance always fills exactly `1` slot
- service provider acceptance fills the chosen committed slot count
- the first accepted slots win
- once the request reaches full capacity, remaining open offers are closed

## Visibility vs Actionability

The platform should separate whether a request can be seen from whether it can still be acted on.

This means:

- a request can stay visible after it is filled
- a request can stay visible after it expires
- an offer can stay visible after it is closed
- action buttons appear only when the current state allows action

Examples:

- `filled`: visible, but open offers cannot be accepted
- `expired`: visible, but the client cannot edit the request
- `wave expired`: visible, but that wave no longer accepts responses

## Update Types

Not every client change should be treated the same way.

### Normal Update

Use a normal update when the job itself has not materially changed.

Recommended fields:

- `title`
- `request_expires_at` while the request is still active

Effect:

- no new broadcast wave
- no reconfirmation
- no reopening of old offers

### Publish Update

Use this when the live job changed in a way that candidates must be told again.

Recommended triggers:

- start time changes
- end time changes
- site or location changes
- requested guard type changes
- fulfillment mode changes
- special instructions change in a candidate-meaningful way

Effect:

- creates a new request revision
- creates a fresh broadcast wave
- closes older open offers from the earlier wave
- moves already accepted but not started assignments to `reconfirmation required`

### Request Additional Coverage

Use this when the job is still the same, but the client needs more guard capacity.

Trigger:

- only `guards_required` increases

Effect:

- existing accepted assignments stay intact
- a fresh wave is created only for the extra open slots
- no reconfirmation is needed

### Capacity Reopened

This is a system-triggered event, not a normal client action.

It happens when a previously filled request becomes short again, for example:

- an accepted candidate declines during reconfirmation
- a provider reduces committed slots
- an accepted assignment is cancelled before start

Effect:

- the system creates a fresh broadcast wave
- older closed offers remain historical only

## Expiry Rules

The lifecycle uses two different expiry concepts.

### Request Expiry

`request_expires_at` is controlled by the client.

Rules:

- if the request is already expired, it cannot be edited
- if the request is still active, the client can update the request expiry
- changing only the request expiry does not force reconfirmation
- an expired request remains viewable but becomes read-only

### Wave Expiry

`wave_expires_at` is controlled by the system.

Rules:

- each wave gets a response deadline
- once the wave expires, its offers become non-actionable
- if the request itself is still active and still has open slots, a new wave can be created later

### Expiry Outcome

If a request expires while only partially filled:

- already accepted assignments remain valid
- the unfilled portion dies
- remaining open offers are closed
- the request stays visible but cannot be edited

If more staffing is needed after that, the client must create a new request or duplicate the old one.

## Admin Review Criteria

Platform review should happen only when the system cannot safely auto-broadcast the request.

Review is available to both:

- `admin`
- `ops_admin`

### Decision Table

| Outcome | Criteria | Result |
| --- | --- | --- |
| `Auto-broadcast` | request is valid, site geo is usable, distance can be evaluated reliably, travel policy resolves correctly, and no condition crosses the manual review threshold | create the wave and notify matching tenant admins |
| `Send to admin review` | missing or invalid site geo, failed geocoding, unreliable distance calculation, no applicable travel policy, ambiguous or incomplete location data, or distance crosses `manual_review_over_km` | hold the request for `admin` or `ops_admin` review before any candidate notification |
| `Block with validation error` | request is already expired, invalid time range, request expiry is not in the future, request expiry is after shift start, or requested slot reduction would go below already accepted slots | reject the action immediately and require the client to correct the request |

Requests in review are not rejected automatically. They are paused until a platform reviewer either approves the broadcast or returns the request to the client.

## Travel Policy and Billing Interaction

Travel policy is not only a pricing tool. It also affects whether the platform should auto-broadcast safely.

Two separate checks are important:

- `operational radius`
  - can this candidate physically serve the site?

- `travel policy`
  - should the platform auto-broadcast this site distance, or should it be reviewed first?

Recommended rule:

- a candidate must pass operational capability checks
- the request must also pass travel-policy-based broadcast safety checks

This keeps operational matching and business control separate.

## Candidate Offer Lifecycle

An offer is the candidate-facing unit inside a wave.

Recommended offer states:

- `offered`
- `accepted`
- `reconfirmation required`
- `declined`
- `expired`
- `closed because filled`
- `superseded`
- `in progress`
- `completed`
- `cancelled`

Important behavior:

- candidates can still open closed offers for history
- only actionable offers show accept or decline buttons
- if a later wave is created, the candidate can receive a new offer even after declining an older one

## Reconfirmation Rules

Reconfirmation is used when a material request update affects already accepted but not started work.

Examples:

- time changed
- location changed
- other important candidate-facing request details changed

Behavior:

- accepted assignments move to `reconfirmation required`
- the candidate reviews the updated details
- the candidate can `reconfirm` or `decline`
- if the candidate does nothing before the reconfirmation deadline, the slot can reopen for a fresh broadcast wave

## Filled Request Behavior

When the request reaches full staffing:

- the request remains visible
- remaining open offers remain visible
- those offers become non-actionable
- the candidate sees a message such as:
  - `All required slots have already been filled. This offer is no longer accepting responses.`

If capacity later opens again:

- old offers are not reopened
- the system creates a fresh wave
- the new wave can notify candidates again, including candidates who declined older waves

## Recommended User Actions In The UI

### Client Actions

- `Save Draft`
- `Publish Request`
- `Publish Update`
- `Request Additional Coverage`
- `Cancel Request`
- `Close Request`

### Platform Review Actions

- `Approve & Broadcast`
- `Return to Client`

## Recommended Guardrails For Version 1

- Keep broadcast `in-app only`
- Notify `tenant admins only`
- Use platform-controlled pricing
- Do not allow a free-form client-set offer price in version 1
- Keep old offers visible for history
- Use fresh waves instead of reopening old offers
- Keep expired requests read-only

## Simple End-To-End Example

1. Client creates a request for `3` guards.
2. Client publishes the request.
3. The request passes auto-broadcast checks and wave `1` is created.
4. Matching guard and service provider tenant admins receive in-app offers.
5. One direct guard accepts `1` slot.
6. One service provider accepts `2` slots.
7. The request is now fully filled.
8. Remaining open offers stay visible but become closed because the request is full.
9. Later, the provider reduces commitment by `1` slot before start.
10. The request becomes partially filled again.
11. The system creates a fresh broadcast wave for the reopened slot.
12. A candidate who declined wave `1` can still receive wave `2`.

## Summary

The request and broadcast lifecycle should be:

- clear for the client
- safe for operations
- fair to candidates
- easy to audit

The most important design principle is that the platform should preserve history, avoid silent changes, and create fresh broadcast waves whenever the staffing reality changes in a meaningful way.
