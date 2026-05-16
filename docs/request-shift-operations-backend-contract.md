# Request Shift Operations Backend Contract

This document converts the agreed scheduling, attendance, and long-term contract workflow into a backend implementation contract for FastAPI and Mongo/ODMantic.

It assumes the request broadcast phase is already implemented and remains the staffing entry point.

Related documents:

- `docs/client-request-broadcast-lifecycle.md`
- `docs/request-broadcast-backend-contract.md`
- `docs/request-broadcast-implementation-plan.md`

## Goals

- support one-time, date-range, and recurring weekly schedules
- support long-term contracts without flattening them into one giant assignment
- support daily shift attendance and client arrival confirmation
- support service-provider rostering of named guards after provider-level acceptance
- support direct-guard unavailability, no-show, and replacement without breaking the whole contract
- use actual confirmed shift times for payroll and billing later

## Current Constraints In The Codebase

The current request system has four important limitations:

1. `ClientRequestRecord` only stores one `requested_start_at` and one `requested_end_at`.
2. `RequestAssignmentRecord` only stores one `started_at` and one `completed_at`.
3. The current job lifecycle is assignment-level, not shift-level, in `RequestManager.update_job_status()`.
4. The Angular request form still captures date-only scheduling inputs, not recurring shift definitions.

These constraints are visible in:

- [db_request_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_request_model.py:128)
- [db_request_model.py](/home/ibsalim/Projects/guardgo/backend/orion/services/mongo_manager/shared_model/db_request_model.py:162)
- [request_manager.py](/home/ibsalim/Projects/guardgo/backend/orion/api/interactive/request_manager/request_manager.py:2069)
- [requests.component.html](/home/ibsalim/Projects/guardgo/client/src/app/pages/requests/requests.component.html:395)

## Design Direction

### Recommendation

Keep the current request/broadcast records and add a new operations layer under them.

Keep:

- `ClientRequestRecord`
- `RequestBroadcastWaveRecord`
- `RequestAssignmentRecord`

Add:

- `RequestScheduleTemplateRecord`
- `ShiftInstanceRecord`
- `ShiftSlotRecord`
- `ShiftAttendanceEventRecord`

This is the smallest clean design because:

- request and wave logic already handle commercial demand and candidate offers
- request assignments already capture who accepted commercial responsibility
- shift execution is a separate operational problem and should not overload request-level status

## Existing Model Reinterpretation

### ClientRequestRecord

Keep `ClientRequestRecord` as the contract or staffing header.

It continues to own:

- client demand
- site information
- fulfillment mode
- requested guard type
- total required slots
- broadcast waves
- accepted slot counts

It should not become the daily attendance record.

### RequestAssignmentRecord

Keep `RequestAssignmentRecord` as the commercial commitment record.

Meaning after this phase:

- direct guard accepted assignment = one recurring coverage commitment
- service provider accepted assignment = N recurring provider-owned coverage commitments

It should not be the daily check-in record for long-term contracts.

The current assignment statuses still matter for acceptance, reconfirmation, cancellation, and history. They simply stop being the full source of truth for day-by-day execution.

## New Schedule Template Contract

Add a new collection:

```python
class RequestScheduleType(str, Enum):
    ONE_TIME = "one_time"
    DATE_RANGE = "date_range"
    RECURRING_WEEKLY = "recurring_weekly"


class RequestScheduleTemplateRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    timezone: str = Field(index=True)
    schedule_type: RequestScheduleType = Field(index=True)
    start_date: date
    end_date: Optional[date] = Field(default=None, index=True)
    start_time_local: str
    end_time_local: str
    is_overnight: bool = False
    recurrence_days: List[str] = []
    generation_horizon_days: int = 30
    roster_due_offset_minutes: int = 120
    unavailable_cutoff_minutes: int = 120
    late_grace_minutes: int = 15
    no_show_cutoff_minutes: int = 30
    checkin_geofence_meters: int = 200
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Schedule Template Rules

- one request gets one schedule pattern in v1
- schedule timezone is mandatory
- overnight shifts are supported
- recurring contracts generate only a rolling horizon, for example the next `30` days
- the request still owns `request_expires_at`; the schedule template owns operational shift generation

### Schedule Meaning

- `one_time`: one shift occurrence
- `date_range`: one shift per day between `start_date` and `end_date`
- `recurring_weekly`: one shift on selected weekdays for the active date range

## New Shift Instance Contract

Add a new collection:

```python
class ShiftInstanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    PARTIALLY_STAFFED = "partially_staffed"
    STAFFED = "staffed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ShiftInstanceRecord(Model):
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    schedule_template_id: str = Field(index=True)
    shift_date_local: date = Field(index=True)
    shift_start_at_utc: datetime = Field(index=True)
    shift_end_at_utc: datetime = Field(index=True)
    timezone: str = Field(index=True)
    instance_status: ShiftInstanceStatus = Field(default=ShiftInstanceStatus.SCHEDULED, index=True)
    slots_required: int = 1
    slots_staffed: int = 0
    slots_checked_in: int = 0
    slots_completed: int = 0
    client_action_required: bool = False
    roster_due_at: Optional[datetime] = Field(default=None, index=True)
    created_from_revision: int = Field(default=0, index=True)
    cancel_reason: Optional[str] = None
    reduction_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Shift Instance Rules

- each shift instance is one real operational occurrence
- `slots_required` is copied from the request demand at generation time
- future shift instances can be cancelled or reduced without cancelling the whole request
- cancelling or reducing a started shift should require platform review

## New Shift Slot Contract

Add a new collection:

```python
class ShiftCoverageSourceType(str, Enum):
    DIRECT_GUARD = "direct_guard"
    SERVICE_PROVIDER = "service_provider"


class ShiftSlotStatus(str, Enum):
    OPEN = "open"
    RESERVED = "reserved"
    ROSTERED = "rostered"
    UNAVAILABLE = "unavailable"
    LATE_RISK = "late_risk"
    ARRIVAL_PENDING = "arrival_pending"
    CLIENT_CONFIRMATION_PENDING = "client_confirmation_pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW_SUSPECTED = "no_show_suspected"
    NO_SHOW_CONFIRMED = "no_show_confirmed"
    REPLACEMENT_REQUIRED = "replacement_required"
    CANCELLED = "cancelled"


class ShiftSlotRecord(Model):
    shift_instance_id: str = Field(index=True)
    request_id: str = Field(index=True)
    client_tenant_id: str = Field(index=True)
    parent_assignment_id: Optional[str] = Field(default=None, index=True)
    slot_number: int = Field(index=True)
    coverage_source_type: Optional[ShiftCoverageSourceType] = Field(default=None, index=True)
    coverage_tenant_id: Optional[str] = Field(default=None, index=True)
    service_provider_tenant_id: Optional[str] = Field(default=None, index=True)
    assigned_guard_tenant_id: Optional[str] = Field(default=None, index=True)
    slot_status: ShiftSlotStatus = Field(default=ShiftSlotStatus.OPEN, index=True)
    replacement_of_slot_id: Optional[str] = Field(default=None, index=True)
    rostered_at: Optional[datetime] = None
    roster_due_at: Optional[datetime] = Field(default=None, index=True)
    guard_unavailable_reported_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    client_confirmed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    no_show_confirmed_at: Optional[datetime] = None
    geo_check_passed: Optional[bool] = None
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Shift Slot Meaning

This becomes the real operational unit.

It answers:

- who is expected on this shift slot
- whether this is direct coverage or provider-managed coverage
- whether the worker arrived
- whether the client confirmed arrival
- whether the shift started
- whether the slot became unavailable or no-show
- whether a replacement was required

## New Attendance Event Contract

Add a new collection:

```python
class ShiftAttendanceEventType(str, Enum):
    ROSTERED = "rostered"
    UNAVAILABLE_REPORTED = "unavailable_reported"
    CHECKIN_ATTEMPTED = "checkin_attempted"
    ARRIVED = "arrived"
    GEO_FAILED = "geo_failed"
    CLIENT_CONFIRMED = "client_confirmed"
    OPS_START_OVERRIDE = "ops_start_override"
    STARTED = "started"
    CHECKOUT = "checkout"
    COMPLETED = "completed"
    NO_SHOW_SUSPECTED = "no_show_suspected"
    NO_SHOW_CONFIRMED = "no_show_confirmed"
    REPLACEMENT_REQUESTED = "replacement_requested"
    REPLACEMENT_ASSIGNED = "replacement_assigned"
    CANCELLATION = "cancellation"


class ShiftAttendanceEventRecord(Model):
    shift_slot_id: str = Field(index=True)
    shift_instance_id: str = Field(index=True)
    request_id: str = Field(index=True)
    event_type: ShiftAttendanceEventType = Field(index=True)
    actor_user_id: Optional[str] = Field(default=None, index=True)
    actor_role: Optional[str] = Field(default=None, index=True)
    guard_tenant_id: Optional[str] = Field(default=None, index=True)
    service_provider_tenant_id: Optional[str] = Field(default=None, index=True)
    client_tenant_id: Optional[str] = Field(default=None, index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_meters: Optional[float] = None
    note: Optional[str] = None
    metadata: Dict[str, Any] = {}
```

### Attendance Event Rules

- events are immutable audit logs
- slot state changes may update `ShiftSlotRecord`
- every important transition should also write an event record
- dispute resolution should rely on these events instead of only current slot state

## Direct Guard Coverage Contract

When a direct guard accepts a long-term or recurring request:

- that accepted `RequestAssignmentRecord` represents recurring responsibility for one slot
- generated shift slots should attach back to that assignment
- the guard is the default named worker for those future shift slots

### Direct Guard Unavailability

If the guard reports unavailability before `T-2h`:

- only that one future shift slot becomes uncovered
- the wider contract remains active
- the client is asked whether that slot still needs coverage
- if yes, the platform reopens only that shift slot

If the guard fails to report unavailability:

- `start + 15m` becomes `no_show_suspected`
- `start + 30m` becomes `no_show_confirmed`
- only that shift slot reopens through replacement logic

Direct guards must not nominate their own replacement in v1.

## Service Provider Coverage Contract

When a service provider accepts:

- the assignment captures provider-owned committed capacity
- the provider still must choose named guards for each shift occurrence

### Provider Roster Rules

- providers may bulk apply roster patterns to future shifts
- providers may edit day-level exceptions later
- roster deadline should default to `shift_start - 2h`
- if the provider accepts after that deadline, rostering becomes due immediately

### Provider Roster Failure

If the provider misses roster deadline:

- do not silently reopen immediately
- ask the client whether those missing slots are still needed
- if the client confirms, reopen only the missing slots
- if the client does not respond by emergency cutoff, `admin` may reopen those slots automatically

### Provider Guard No-Show

If a named provider guard no-shows:

- give the provider a short replacement window first
- recommended v1 limit: until `shift_start + 30m`
- if still uncovered after that, platform fallback opens only the missing slots

## Attendance And Shift Start Contract

### Check-In

Recommended v1 rules:

- guard check-in requires location proof
- geofence radius defaults to `200m`
- failed geofence does not start the shift
- failed geofence should create an attendance event for audit

### Client Arrival Confirmation

Recommended v1 rules:

- client admin confirms in-app only
- client may confirm guards individually
- UI should also support bulk confirmation for many guards

### Shift Start

Recommended v1 rules:

- shift start requires both guard arrival and client confirmation
- if the client is unavailable, `admin` or `ops_admin` may override with audit trail

### Shift End

Recommended v1 rules:

- guard checks out
- system records actual end time
- client acknowledgement is optional
- disputes go to platform review

## Shift Cancellation And Reduction Contract

Clients may:

- cancel a future shift
- reduce slots on a future shift

Rules:

- allow direct client action only before attendance/start cutoff
- if the shift has already started or workers are already checked in, require platform review
- shift cancellation or reduction must not silently rewrite historical attendance

## Replacement Wave Contract

Replacement should reuse the existing broadcast engine where possible.

Recommended behavior:

- a shift slot that becomes uncovered should create a targeted refill action
- that refill should create a fresh request broadcast wave or a shift-scoped derivative of it
- original fulfillment mode should be respected by default
- `admin` may widen emergency fallback to hybrid if the original mode is not recovering coverage fast enough

For v1, it is acceptable to implement replacement by creating a request-linked shift refill wave rather than a fully separate replacement collection.

## Billing And Payroll Contract

Planning uses scheduled shift times.

Future billing and payroll should use:

- `actual_start_at`
- `actual_end_at`

Rules:

- variance between scheduled and actual time should be reviewable
- very large variance should create an ops-review condition later

## API Contract Direction

Recommended backend API groups:

### Schedule

- `POST /api/requests/{request_id}/schedule`
- `GET /api/requests/{request_id}/schedule`
- `PATCH /api/requests/{request_id}/schedule`

### Shifts

- `GET /api/shifts`
- `GET /api/shifts/{shift_id}`
- `POST /api/shifts/{shift_id}/cancel`
- `POST /api/shifts/{shift_id}/reduce-slots`

### Provider Rostering

- `POST /api/shifts/{shift_id}/roster`
- `POST /api/shifts/{shift_id}/bulk-roster-pattern`
- `POST /api/shift-slots/{slot_id}/replace`

### Attendance

- `POST /api/shift-slots/{slot_id}/check-in`
- `POST /api/shift-slots/{slot_id}/client-confirm`
- `POST /api/shift-slots/{slot_id}/start`
- `POST /api/shift-slots/{slot_id}/check-out`
- `POST /api/shift-slots/{slot_id}/report-unavailable`

### Admin And Ops

- `GET /api/shift-exceptions`
- `POST /api/shift-slots/{slot_id}/ops-start-override`
- `POST /api/shift-slots/{slot_id}/reopen`

## Migration Strategy

Do not try to migrate old one-off jobs into full recurring schedules immediately.

Recommendation:

- keep existing request assignments working for legacy/simple flows
- introduce schedule and shift records for new requests using the new scheduling UI
- optionally backfill a one-time schedule and one shift instance for compatible active requests later

This reduces risk and allows phased delivery.
