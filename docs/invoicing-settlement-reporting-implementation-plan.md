# Invoicing, Settlement, And Reporting Implementation Plan

This document is the file-by-file execution plan for implementing invoicing, settlement, platform earnings, and reporting on top of the completed request and shift lifecycle.

It assumes the operational request, shift, attendance, and exception layers are already in place.

Related documents:

- `docs/invoicing-settlement-reporting-backend-contract.md`
- `docs/request-broadcast-backend-contract.md`
- `docs/request-shift-operations-backend-contract.md`

## Objectives

Implement these capabilities in a controlled order:

- immutable financial facts from completed shift slots
- configurable settlement cycles
- client invoices
- direct-guard payout statements
- service-provider payable statements
- platform gross margin and commission reporting
- exportable attendance and finance reports

## Design Rules

Keep these rules fixed during implementation:

- completed shift slots are the only atomic financial source of truth
- rate and travel values must be snapshotted, not recalculated later from mutable config
- payroll and tax treatment must be configurable by payee classification
- invoices, payout statements, and reports must derive from locked financial facts
- adjustments should be additive and auditable, not destructive rewrites

## New Backend Collections

Recommended new model file:

- `backend/orion/services/mongo_manager/shared_model/db_finance_model.py`

This file should contain:

- `SettlementRelationshipType`
- `TimeRoundingMode`
- `SettlementCycleType`
- `SettlementCycleStatus`
- `FinancialFactStatus`
- `ClientInvoiceStatus`
- `PayoutStatementStatus`
- `FinancialAdjustmentType`
- `ReportExportStatus`
- `PayeeTaxProfileRecord`
- `SettlementCycleRecord`
- `ShiftFinancialFactRecord`
- `ClientInvoiceRecord`
- `ClientInvoiceLineRecord`
- `PayoutStatementRecord`
- `PayoutStatementLineRecord`
- `FinancialAdjustmentRecord`
- `ReportExportRecord`

## Existing Files To Extend

### 1. `backend/orion/services/mongo_manager/shared_model/db_billing_model.py`

Keep current billing models as source configuration.

Potential additions:

- optional metadata fields if required for finance resolution
- avoid turning this file into the ledger

### 2. `backend/orion/services/mongo_manager/shared_model/db_tenant_model.py`

Potential additions:

- settlement metadata pointer on tenant profile if that becomes useful later

Recommendation:

- prefer keeping tax and settlement details in `PayeeTaxProfileRecord` instead of overloading tenant profiles

### 3. `backend/orion/services/mongo_manager/shared_model/db_request_model.py`

Likely additions:

- optional foreign-key references from completed shift slots to finance fact ids later if useful

Recommendation:

- keep this minimal
- the finance layer should mostly reference shift slots, not the other way around

## New Managers

### 1. `backend/orion/api/interactive/finance_manager/finance_manager.py`

Primary responsibilities:

- resolve payee classification
- resolve applicable billing rates and travel policy
- classify shift day type: standard, weekend, holiday
- generate `ShiftFinancialFactRecord` from completed shift slots
- apply rounding policy
- calculate:
  - client bill rate
  - payee rate
  - travel charge
  - platform margin or commission
- prevent duplicate fact generation for the same slot
- lock or void facts when cycles progress

### 2. `backend/orion/api/interactive/settlement_manager/settlement_manager.py`

Primary responsibilities:

- create settlement cycles
- gather eligible financial facts into cycles
- lock cycles
- generate client invoices
- generate payout statements
- post cycles
- expose review summaries

### 3. `backend/orion/api/interactive/reporting_manager/reporting_manager.py`

Primary responsibilities:

- operational report aggregation
- attendance report aggregation
- finance and margin report aggregation
- CSV/XLSX export generation
- export job tracking

## Existing Managers To Update

### 1. `backend/orion/api/interactive/request_shift_manager/request_shift_manager.py`

Add hooks when a shift slot completes:

- optionally enqueue or mark the slot as finance-eligible
- expose enough data for finance generation

Do not calculate invoice amounts directly here.

### 2. `backend/orion/api/interactive/billing_manager/billing_manager.py`

Add reusable resolution helpers if not already present:

- get effective guard pay rate by province/city and day type
- get effective provider rate by province/city and day type
- get effective guard margin by province/city and day type
- get effective provider commission by province/city and day type
- get effective travel policy by province/city and coverage type

Recommendation:

- finance manager should call billing manager for resolution
- billing manager should remain the source for configurable pricing inputs

## New Backend Routes

Recommended new route file:

- `backend/routes/finance_routes.py`

Suggested endpoints:

### Payee tax profiles

- `GET /api/payees/tax-profiles`
- `GET /api/payees/tax-profiles/{tenant_id}`
- `PUT /api/payees/tax-profiles/{tenant_id}`

### Settlement cycles

- `GET /api/settlement-cycles`
- `POST /api/settlement-cycles`
- `POST /api/settlement-cycles/{cycle_id}/generate-facts`
- `POST /api/settlement-cycles/{cycle_id}/lock`
- `POST /api/settlement-cycles/{cycle_id}/post`

### Financial facts

- `GET /api/financial-facts`
- `GET /api/financial-facts/{fact_id}`
- `POST /api/financial-facts/{fact_id}/adjust`

### Client invoices

- `GET /api/invoices`
- `GET /api/invoices/{invoice_id}`
- `POST /api/settlement-cycles/{cycle_id}/generate-client-invoices`
- `POST /api/invoices/{invoice_id}/issue`
- `POST /api/invoices/{invoice_id}/mark-paid`

### Payout statements

- `GET /api/payout-statements`
- `GET /api/payout-statements/{statement_id}`
- `POST /api/settlement-cycles/{cycle_id}/generate-payout-statements`
- `POST /api/payout-statements/{statement_id}/approve`
- `POST /api/payout-statements/{statement_id}/mark-paid`

### Reporting and exports

- `GET /api/reports/attendance`
- `GET /api/reports/exceptions`
- `GET /api/reports/revenue`
- `GET /api/reports/margins`
- `POST /api/reports/export`
- `GET /api/reports/exports/{export_id}`

## App Registration Changes

### 1. `backend/main.py`

Add new route registration for:

- `finance_routes`

### 2. `backend/configs/app_dependency.py`

If needed:

- add role restrictions for finance and reporting actions
- separate admin-only and read-only reporting access

## Frontend Model And Service Layer

### New shared model file

- `client/src/app/shared/model/finance/finance.model.ts`

Suggested types:

- settlement cycle
- financial fact
- payee tax profile
- invoice
- invoice line
- payout statement
- payout statement line
- report export
- summary KPIs

### New service file

- `client/src/app/shared/services/finance.service.ts`

Methods should map to the new finance/reporting endpoints.

## Frontend Pages

Recommended new pages:

### 1. `client/src/app/pages/invoices/`

Purpose:

- client invoice list
- invoice detail
- invoice issue/paid states
- export access

### 2. `client/src/app/pages/payout-statements/`

Purpose:

- direct-guard statement list
- provider payable statement list
- approval and paid states

### 3. `client/src/app/pages/settlement-cycles/`

Purpose:

- cycle creation
- generate facts
- lock
- post
- review totals before issuing finance documents

### 4. `client/src/app/pages/reports/`

Purpose:

- attendance reports
- exception reports
- revenue and margin reports
- export actions

## Existing Frontend Pages To Extend

### 1. `client/src/app/pages/billing-configurations/`

Add small affordances if needed for finance context:

- explain that these values feed settlement calculations
- surface whether changes affect future settlements only

### 2. `client/src/app/pages/requests/`

Optional later enhancement:

- show invoice or settlement linkage on completed shifts
- show whether a completed shift slot is settled or not

Recommendation:

- do not overload the requests page in the first finance slice

## New Reusable Frontend Components

Recommended reusable components:

- `financial-summary-card`
- `invoice-status-badge`
- `statement-status-badge`
- `report-filter-bar`
- `export-history-table`
- `cycle-review-metrics`

Keep these shared so the finance pages do not repeat structure.

## Tests To Add

### Backend unit/integration tests

Recommended files:

- `backend/tests/test_finance_manager.py`
- `backend/tests/test_settlement_manager.py`
- `backend/tests/test_reporting_manager.py`
- `backend/tests/test_finance_routes.py`

Coverage should include:

- rate resolution precedence
- day-type selection
- travel-charge calculation
- financial fact idempotency
- cycle generation
- invoice generation
- payout generation
- adjustment behavior
- report aggregation
- export request behavior

### Frontend tests

If frontend test coverage is used later, add:

- invoice list/detail behaviors
- settlement-cycle action flows
- report filter and export behaviors

## Migration And Backfill Strategy

### Step 1

Add the new finance collections without touching existing request data.

### Step 2

Backfill payee classification records for known tenants:

- direct guards
- service providers

Do not assume all direct guards are the same classification without business review.

### Step 3

Allow financial fact generation only for completed shift slots after a chosen cutoff date in the first release.

Recommendation:

- do not backfill every historical shift immediately
- start with forward-only generation unless historical migration is a firm business requirement

### Step 4

Add controlled backfill command later if historical settlement is required.

Recommended script:

- `backend/migrations/scripts/seed_finance_defaults.py` if defaults are needed
- separate backfill script for historical financial fact generation

## Recommended Delivery Slices

### Slice 1: Foundation

Implement:

- `db_finance_model.py`
- payee tax profile CRUD
- settlement cycle CRUD
- finance manager skeleton

Goal:

- create the finance layer without yet generating client-visible invoices

### Slice 2: Financial facts

Implement:

- shift-slot-to-financial-fact generation
- rate, margin, commission, and travel snapshotting
- day-type logic
- idempotent fact generation

Goal:

- one completed shift slot becomes one immutable financial fact

### Slice 3: Settlement cycles

Implement:

- cycle review page
- generate facts into cycles
- lock cycle behavior
- summary totals

Goal:

- reviewable cycle close process

### Slice 4: Client invoices

Implement:

- invoice generation from cycle facts
- invoice list/detail UI
- issue and paid workflow

Goal:

- client billing works end-to-end

### Slice 5: Guard and provider payout statements

Implement:

- payout statement generation
- direct guard and provider statement views
- approval and paid state handling

Goal:

- outbound settlement works end-to-end

### Slice 6: Reporting and exports

Implement:

- attendance reports
- margin and revenue reports
- CSV/XLSX export
- export job history

Goal:

- ops and finance reporting becomes usable

## File-Level Change Summary

### Backend new files

- `backend/orion/services/mongo_manager/shared_model/db_finance_model.py`
- `backend/orion/api/interactive/finance_manager/finance_manager.py`
- `backend/orion/api/interactive/settlement_manager/settlement_manager.py`
- `backend/orion/api/interactive/reporting_manager/reporting_manager.py`
- `backend/routes/finance_routes.py`
- `backend/tests/test_finance_manager.py`
- `backend/tests/test_settlement_manager.py`
- `backend/tests/test_reporting_manager.py`
- `backend/tests/test_finance_routes.py`

### Backend existing files likely touched

- `backend/main.py`
- `backend/configs/app_dependency.py`
- `backend/orion/api/interactive/billing_manager/billing_manager.py`
- `backend/orion/api/interactive/request_shift_manager/request_shift_manager.py`
- optionally `backend/orion/services/mongo_manager/shared_model/db_request_model.py`

### Frontend new files

- `client/src/app/shared/model/finance/finance.model.ts`
- `client/src/app/shared/services/finance.service.ts`
- `client/src/app/pages/invoices/`
- `client/src/app/pages/payout-statements/`
- `client/src/app/pages/settlement-cycles/`
- `client/src/app/pages/reports/`

### Frontend existing files likely touched

- `client/src/app/app.routes.ts`
- `client/src/app/pages/billing-configurations/`
- optionally `client/src/app/pages/requests/`

## Open Risks

These are the main design risks before implementation:

1. direct-guard worker classification is still a business and compliance decision, not just a technical one
2. holiday-rate logic may need a proper Canadian holiday calendar by province
3. travel reimbursement logic may differ from client travel billing logic in real operations
4. payout cycles may need to diverge from invoice cycles
5. future payroll integration may require more detail than payout statements alone

## Recommendation

The best next implementation move is:

1. finish the lifecycle QA using the QA plan
2. lock direct-guard classification assumptions
3. build `Slice 1` and `Slice 2` first

Do not begin invoice PDFs or polished reporting UI before immutable financial facts exist.
