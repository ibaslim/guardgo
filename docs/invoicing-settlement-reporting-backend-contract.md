# Invoicing, Settlement, And Reporting Backend Contract

This document converts the agreed next phase into a backend design contract for FastAPI and Mongo/ODMantic.

It covers:

- invoicing
- payout and settlement
- platform revenue calculation
- month-end or cycle close behavior
- attendance-based financial calculation
- exportable operational and financial reporting

This document is intentionally technical. It should be read after the request and shift lifecycle documents.

Related documents:

- `docs/request-broadcast-backend-contract.md`
- `docs/request-shift-operations-backend-contract.md`
- `docs/request-shift-operations-implementation-plan.md`

## Goals

- use completed shift-slot attendance as the financial source of truth
- calculate client billing from actual confirmed work
- calculate direct-guard pay and provider pay from the same source facts
- calculate platform margin and commission explicitly, not by inference
- support configurable settlement cycles
- freeze rate snapshots so later billing-config edits do not change history
- support exportable finance and attendance reports
- keep Canadian payroll and tax obligations visible in the design without pretending to finalize legal treatment in code prematurely

## Current Constraints In The Codebase

The current product has the operational foundation, but it does not yet have a settlement layer.

Current strengths:

- billing configuration already stores:
  - guard pay rates
  - provider pay rates
  - guard margin rates
  - provider commission rates
  - travel pricing policy
- completed shift slots already store:
  - `actual_start_at`
  - `actual_end_at`
  - `client_confirmed_at`
  - shift and slot completion state

Current gaps:

1. There is no immutable rate snapshot tied to a completed shift slot.
2. There is no settlement-cycle concept.
3. There is no client invoice model.
4. There is no direct-guard payout model.
5. There is no service-provider payable model.
6. There is no platform revenue ledger.
7. There is no structured reporting/export layer.

## Compliance Guardrails

This design should be treated as implementation guidance, not final tax or employment advice.

Before coding remittance logic, the team should validate the final legal treatment with a Canadian accountant or payroll advisor.

Key official-source constraints:

- CRA says worker classification matters first: employee versus self-employed directly affects payroll treatment.
  - Source: `RC4110 Employee or Self-employed`
  - https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4110/employee-self-employed.html
- If the worker is treated as an employee, the employer is responsible for deducting and remitting CPP, EI, and income tax.
  - Source: `RC4110 Employee or Self-employed`
  - https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/rc4110/employee-self-employed.html
- GST/HST registration may become mandatory depending on taxable supplies and the small-supplier threshold, commonly `$30,000`.
  - Source: `When to register for and start charging the GST/HST`
  - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/when-register-charge.html
- GST/HST invoicing depends on place of supply and invoice date.
  - Source: `Charge and collect the GST/HST`
  - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html#receipt
- Payroll remittance due dates depend on remitter type. Regular remitters are generally due on the `15th day of the next month`.
  - Source: `When to remit (pay)`
  - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/payroll/remitting-source-deductions/how-when-remit-due-dates.html#h_2
- Business records generally need to be retained for `six years`.
  - Source: `Where to keep your records`
  - https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/keeping-records/where-keep-your-records-long-request-permission-destroy-them-early.html

## Design Direction

### Recommendation

Do not start with PDF invoices.

Start with a financial fact layer built from completed shift slots. Everything else should be derived from that layer:

- client invoices
- direct-guard payout statements
- service-provider payable statements
- platform margin and commission reports
- attendance and finance exports

### Core Principle

`Completed shift slot` is the atomic financial event.

Reason:

- request-level data is too coarse
- accepted assignment data is too coarse for recurring work
- completed shift slots already reflect the operational truth of what actually happened

## Existing Models To Reuse

Keep using these as source inputs:

- `BillingRate`
- `TravelPricingPolicy`
- `ClientRequestRecord`
- `RequestAssignmentRecord`
- `ShiftInstanceRecord`
- `ShiftSlotRecord`
- `ShiftAttendanceEventRecord`

Do not mutate those records to become the settlement ledger.

Add a separate settlement layer.

## Financial Concepts

The financial model should separate four concepts clearly:

1. `Client billing`
What the client owes the platform.

2. `Guard compensation`
What the platform owes a direct guard when the guard is paid directly by the platform.

3. `Provider payable`
What the platform owes a service provider.

4. `Platform revenue`
What the platform keeps after cost or payable is separated.

These should never be collapsed into one generic amount field.

## Coverage Financial Rules

### Direct Guard Coverage

Recommended rate logic per hour:

- `guard_pay_rate` comes from guard rate override if present, otherwise guard default
- `guard_margin_rate` comes from guard margin config
- `client_bill_rate = guard_pay_rate + guard_margin_rate`

Platform result:

- `platform_gross_margin = client_bill_amount - direct_guard_pay_amount`

### Service Provider Coverage

Recommended rate logic per hour:

- `provider_base_rate` comes from provider rate override if present, otherwise provider default
- `provider_commission_rate` comes from provider commission config
- `client_bill_rate = provider_base_rate + provider_commission_rate`

Platform result:

- `platform_gross_commission = client_bill_amount - provider_payable_amount`

### Travel

Travel should be handled separately from the hourly rate.

Recommended rule:

- resolve travel policy from the same province/city scope used during matching and pricing
- calculate travel charge using:
  - `included_radius_km`
  - `rate_per_km`
- store the actual travel charge on the financial fact record
- do not recalculate travel from mutable policy later

### Weekend And Holiday Rates

The system already stores:

- `standard_rate`
- `weekend_rate`
- `holiday_rate`

Financial calculation should resolve the correct day type for each shift slot and snapshot the selected hourly rates.

## Time Calculation Contract

Use actual confirmed execution time, not only scheduled time.

Recommended raw formula:

- `actual_minutes_worked = max(0, actual_end_at - actual_start_at)`

### Rounding

Do not hardcode rounding in multiple places.

Add a settlement-policy configuration:

```python
class TimeRoundingMode(str, Enum):
    EXACT = "exact"
    ROUND_UP = "round_up"
    ROUND_NEAREST = "round_nearest"


class SettlementCycleType(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
```

Recommended v1 defaults:

- `rounding_increment_minutes = 15`
- `rounding_mode = round_nearest`
- still store raw minutes separately for audit

Derived values:

- `rounded_minutes_worked`
- `billable_hours`
- `payable_hours`

## Worker And Payee Classification Contract

The product needs one explicit settlement relationship per payee.

Add a settlement profile concept:

```python
class SettlementRelationshipType(str, Enum):
    DIRECT_GUARD_EMPLOYEE = "direct_guard_employee"
    DIRECT_GUARD_CONTRACTOR = "direct_guard_contractor"
    SERVICE_PROVIDER_VENDOR = "service_provider_vendor"


class PayeeTaxProfileRecord(Model):
    tenant_id: str = Field(index=True)
    relationship_type: SettlementRelationshipType = Field(index=True)
    legal_name: str
    billing_email: Optional[str] = None
    gst_hst_registered: bool = False
    gst_hst_number: Optional[str] = None
    payroll_enabled: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Why This Is Needed

Without explicit classification:

- you cannot determine whether a direct guard belongs in payroll or contractor settlement
- you cannot decide whether GST/HST should apply on provider invoices
- you cannot build compliant payout statements or exports

## Financial Fact Layer

Add a new collection:

```python
class FinancialFactStatus(str, Enum):
    OPEN = "open"
    LOCKED = "locked"
    ADJUSTED = "adjusted"
    VOIDED = "voided"


class ShiftFinancialFactRecord(Model):
    request_id: str = Field(index=True)
    shift_instance_id: str = Field(index=True)
    shift_slot_id: str = Field(index=True, unique=True)
    parent_assignment_id: Optional[str] = Field(default=None, index=True)
    client_tenant_id: str = Field(index=True)
    payee_tenant_id: str = Field(index=True)
    payee_relationship_type: SettlementRelationshipType = Field(index=True)
    coverage_source_type: str = Field(index=True)
    province_code: str = Field(index=True)
    city_code: str = Field(index=True)
    currency: str = "CAD"
    day_type: str = Field(index=True)
    actual_start_at: datetime
    actual_end_at: datetime
    raw_minutes_worked: int
    rounded_minutes_worked: int
    billable_hours: float
    payable_hours: float
    base_pay_rate_snapshot: float
    margin_rate_snapshot: float = 0.0
    commission_rate_snapshot: float = 0.0
    client_bill_rate_snapshot: float
    travel_charge_snapshot: float = 0.0
    travel_distance_km_snapshot: float = 0.0
    adjustment_total: float = 0.0
    client_subtotal: float
    payee_subtotal: float
    platform_gross_revenue: float
    platform_gross_margin: float
    status: FinancialFactStatus = Field(default=FinancialFactStatus.OPEN, index=True)
    settlement_cycle_id: Optional[str] = Field(default=None, index=True)
    invoice_id: Optional[str] = Field(default=None, index=True)
    payout_statement_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Why The Fact Record Is Unique Per Shift Slot

One completed slot should create one financial fact record.

That avoids:

- duplicate billing on re-runs
- recalculation against mutable configuration
- mixing multiple shift days into one financial line too early

## Settlement Cycle Contract

Add a cycle model:

```python
class SettlementCycleStatus(str, Enum):
    DRAFT = "draft"
    REVIEW_READY = "review_ready"
    LOCKED = "locked"
    POSTED = "posted"
    CANCELLED = "cancelled"


class SettlementCycleRecord(Model):
    cycle_type: SettlementCycleType = Field(index=True)
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    status: SettlementCycleStatus = Field(default=SettlementCycleStatus.DRAFT, index=True)
    rounding_increment_minutes: int = 15
    rounding_mode: TimeRoundingMode = TimeRoundingMode.ROUND_NEAREST
    generated_fact_count: int = 0
    generated_invoice_count: int = 0
    generated_payout_count: int = 0
    locked_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    created_by_user_id: Optional[str] = None
    created_by_username: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Recommendation

Support multiple cycle types in the model, but start v1 operations with:

- `monthly` for client invoicing
- configurable `monthly` or `biweekly` for payables later if needed

Do not assume one cycle type must govern every money flow forever.

## Invoice Contract

Add a client invoice model:

```python
class ClientInvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOIDED = "voided"


class ClientInvoiceRecord(Model):
    client_tenant_id: str = Field(index=True)
    settlement_cycle_id: str = Field(index=True)
    invoice_number: str = Field(index=True, unique=True)
    invoice_status: ClientInvoiceStatus = Field(default=ClientInvoiceStatus.DRAFT, index=True)
    currency: str = "CAD"
    billing_period_start: datetime = Field(index=True)
    billing_period_end: datetime = Field(index=True)
    subtotal: float = 0.0
    gst_hst_rate: float = 0.0
    gst_hst_amount: float = 0.0
    total: float = 0.0
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ClientInvoiceLineRecord(Model):
    invoice_id: str = Field(index=True)
    financial_fact_id: str = Field(index=True)
    request_id: str = Field(index=True)
    shift_instance_id: str = Field(index=True)
    shift_slot_id: str = Field(index=True)
    description: str
    quantity_hours: float
    hourly_rate: float
    travel_charge: float = 0.0
    adjustment_total: float = 0.0
    line_subtotal: float
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Invoice Rules

- group client financial facts by client and cycle
- invoice lines should remain traceable to request, shift, and slot
- do not mutate line amounts after invoice issue; use credit or adjustment flows instead

## Payout / Payable Contract

Use one statement model for both direct guards and providers, keyed by relationship type.

```python
class PayoutStatementStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    PAID = "paid"
    VOIDED = "voided"


class PayoutStatementRecord(Model):
    payee_tenant_id: str = Field(index=True)
    relationship_type: SettlementRelationshipType = Field(index=True)
    settlement_cycle_id: str = Field(index=True)
    statement_number: str = Field(index=True, unique=True)
    status: PayoutStatementStatus = Field(default=PayoutStatementStatus.DRAFT, index=True)
    currency: str = "CAD"
    payout_period_start: datetime = Field(index=True)
    payout_period_end: datetime = Field(index=True)
    subtotal: float = 0.0
    gst_hst_rate: float = 0.0
    gst_hst_amount: float = 0.0
    total: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class PayoutStatementLineRecord(Model):
    payout_statement_id: str = Field(index=True)
    financial_fact_id: str = Field(index=True)
    request_id: str = Field(index=True)
    shift_instance_id: str = Field(index=True)
    shift_slot_id: str = Field(index=True)
    description: str
    quantity_hours: float
    hourly_rate: float
    travel_reimbursement: float = 0.0
    adjustment_total: float = 0.0
    line_subtotal: float
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

### Direct Guard Treatment

Recommended handling:

- if `relationship_type = direct_guard_employee`, payout statement is an internal payroll-support statement, not necessarily the final payroll artifact
- if `relationship_type = direct_guard_contractor`, payout statement becomes a contractor settlement statement

### Provider Treatment

Recommended handling:

- provider payout statement represents vendor payable support
- later phases can add provider self-billing or provider invoice reconciliation if needed

## Adjustments And Credits

Do not reopen completed financial facts casually.

Add an adjustment model:

```python
class FinancialAdjustmentType(str, Enum):
    MANUAL_CREDIT = "manual_credit"
    MANUAL_DEBIT = "manual_debit"
    TRAVEL_OVERRIDE = "travel_override"
    ATTENDANCE_CORRECTION = "attendance_correction"
    DISPUTE_RESOLUTION = "dispute_resolution"


class FinancialAdjustmentRecord(Model):
    financial_fact_id: str = Field(index=True)
    adjustment_type: FinancialAdjustmentType = Field(index=True)
    amount: float
    reason: str
    created_by_user_id: str
    created_by_username: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

Use adjustments to preserve auditability instead of rewriting amounts in place.

## Tax Contract

### Client Tax

Invoice tax should be computed at invoice issue using the approved tax policy for the client supply.

At minimum store:

- whether GST/HST is chargeable
- applicable tax rate
- tax amount

### Payee Tax

Do not assume direct guards and providers are treated the same.

Examples:

- direct guard employee payout may not use GST/HST treatment
- direct guard contractor may require contractor-specific tax handling
- service provider vendor may require GST/HST if registered

This is why `PayeeTaxProfileRecord` must exist before settlement posting is automated.

## Reporting Contract

Reporting should read from locked facts and statements, not from live mutable request objects.

### Operational Reports

Recommended first set:

- request lifecycle report
- wave performance report
- shift fulfillment report
- attendance report
- exception and no-show report
- provider roster performance report

### Financial Reports

Recommended first set:

- revenue by client
- revenue by province and city
- direct-guard payout report
- provider payable report
- platform margin report
- travel charge report
- adjustment report
- cycle close summary

### Attendance-Specific Reports

Recommended first set:

- scheduled versus actual hours
- arrival confirmation report
- check-in geofence pass/fail report
- late arrival report
- no-show and replacement report
- guard utilization report
- provider guard utilization report

## Export Contract

Support exports as first-class artifacts.

Recommended formats:

- `CSV`
- `XLSX`
- `PDF` later for client invoices and settlement statements

Add an export job model:

```python
class ReportExportStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReportExportRecord(Model):
    report_type: str = Field(index=True)
    requested_by_user_id: str = Field(index=True)
    requested_by_username: str
    filters: Dict[str, Any] = {}
    output_format: str = Field(index=True)
    status: ReportExportStatus = Field(default=ReportExportStatus.QUEUED, index=True)
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    completed_at: Optional[datetime] = None
```

### Export Rules

- exports must capture filters used
- exports must be reproducible
- finance exports should prefer locked cycles only unless explicitly run in draft mode

## API Contract

Recommended backend endpoints:

### Settlement Cycles

- `GET /api/settlement-cycles`
- `POST /api/settlement-cycles`
- `POST /api/settlement-cycles/{cycle_id}/generate-facts`
- `POST /api/settlement-cycles/{cycle_id}/lock`
- `POST /api/settlement-cycles/{cycle_id}/post`

### Financial Facts

- `GET /api/financial-facts`
- `GET /api/financial-facts/{fact_id}`
- `POST /api/financial-facts/{fact_id}/adjust`

### Client Invoices

- `GET /api/invoices`
- `GET /api/invoices/{invoice_id}`
- `POST /api/settlement-cycles/{cycle_id}/generate-client-invoices`
- `POST /api/invoices/{invoice_id}/issue`
- `POST /api/invoices/{invoice_id}/mark-paid`

### Payout Statements

- `GET /api/payout-statements`
- `GET /api/payout-statements/{statement_id}`
- `POST /api/settlement-cycles/{cycle_id}/generate-payout-statements`
- `POST /api/payout-statements/{statement_id}/approve`
- `POST /api/payout-statements/{statement_id}/mark-paid`

### Reporting

- `GET /api/reports/attendance`
- `GET /api/reports/exceptions`
- `GET /api/reports/revenue`
- `GET /api/reports/margins`
- `POST /api/reports/export`
- `GET /api/reports/exports/{export_id}`

## Recommended Build Order

1. Add payee settlement profile
2. Add settlement cycle and rounding policy
3. Generate immutable financial facts from completed shift slots
4. Generate client invoices from financial facts
5. Generate direct-guard and provider payout statements
6. Add adjustments and lock/post workflow
7. Add attendance and finance reporting APIs
8. Add CSV/XLSX exports
9. Add PDF invoice and statement rendering

## Open Questions Requiring Business Or Advisor Confirmation

These should be resolved before payroll or tax automation is finalized:

1. Which direct guards are employees versus contractors?
2. Should the platform support mixed treatment across different guards?
3. Does the platform issue client invoices itself in every case, or are there provider-billed exceptions later?
4. Which payees should carry GST/HST registration details in the product?
5. What invoice numbering and statement numbering format is required operationally?
6. What settlement cycle should be used first in production?
7. What rounding policy is acceptable commercially and legally?
8. Are overtime, statutory holiday, or labour-standard rules needed in product logic later for employee-classified guards?

## Recommendation Summary

The safest and most extensible approach is:

- treat completed shift slots as the only financial source of truth
- freeze rate and travel snapshots into immutable financial facts
- derive invoices, payout statements, platform revenue, and reports from those facts
- keep payroll and tax treatment configurable by payee classification
- validate Canadian payroll and GST/HST treatment with a local advisor before automating remittance behavior
