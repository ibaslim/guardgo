import { CommonModule } from '@angular/common';
import { HttpParams } from '@angular/common/http';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, Subscription, forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { AppService } from '../../services/core/app/app.service';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { isServiceProviderOwnedGuardTenant, normalizeRole } from '../../shared/helpers/access-control.helper';
import {
  ClientRequestItem,
  MyInvoiceItem,
  PlatformPayoutInvoiceItem,
  RequestAssignmentItem,
  RequestInvoiceItem,
  ServiceProviderGuardSummaryItem,
  ShiftInstanceItem,
} from '../../shared/model/request/client-request.model';
import { ApiService } from '../../shared/services/api.service';
import { RequestService } from '../../shared/services/request.service';

type DashboardMetric = {
  label: string;
  value: string | number;
  helperText?: string;
};

type DashboardSectionItem = {
  title: string;
  subtitle: string;
  meta: string;
  route?: string;
};

type DashboardSection = {
  title: string;
  subtitle: string;
  emptyMessage: string;
  actionLabel?: string;
  actionRoute?: string;
  items: DashboardSectionItem[];
};

type PlatformPayoutSummary = {
  invoice_count?: number;
  total_client_revenue?: number;
  total_payout?: number;
  total_payout_adjustments?: number;
  total_platform_earning?: number;
  total_hours?: number;
  total_guard_payout?: number;
  total_provider_payout?: number;
  total_guard_earning?: number;
  total_provider_earning?: number;
  draft_payout_adjustment_count?: number;
  approved_payout_adjustment_count?: number;
  voided_payout_adjustment_count?: number;
  platform_margin_percent?: number | null;
};

type PlatformTenantSnapshot = {
  id: string;
  name?: string | null;
  full_name?: string | null;
  email?: string | null;
  tenant_type?: string | null;
  status?: string | null;
  verified?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
  tenant_admin_user?: {
    full_name?: string | null;
    email?: string | null;
    username?: string | null;
  } | null;
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    PageComponent,
    SectionComponent,
    SummaryMetricCardComponent,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit, OnDestroy {
  loading = false;
  metrics: DashboardMetric[] = [];
  sections: DashboardSection[] = [];
  requests: ClientRequestItem[] = [];
  jobs: RequestAssignmentItem[] = [];
  offeredJobs: RequestAssignmentItem[] = [];
  reconfirmationJobs: RequestAssignmentItem[] = [];
  shifts: ShiftInstanceItem[] = [];
  myInvoices: MyInvoiceItem[] = [];
  providerGuards: ServiceProviderGuardSummaryItem[] = [];
  platformPayoutInvoices: PlatformPayoutInvoiceItem[] = [];
  platformPayoutSummary: PlatformPayoutSummary | null = null;
  platformPendingTenants: PlatformTenantSnapshot[] = [];
  platformActiveGuardCount = 0;
  platformActiveProviderCount = 0;
  platformPendingApprovalCount = 0;
  clientLatestInvoiceAmountByRequestId: Record<string, number> = {};

  private readonly subscriptions = new Subscription();

  constructor(
    private readonly appService: AppService,
    private readonly requestService: RequestService,
    private readonly api: ApiService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    void this.appService.loadSession(true).then(() => this.loadDashboard());
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  get role(): string {
    return normalizeRole(this.appService.userSessionData()?.user?.role);
  }

  get tenantType(): string {
    return String(this.appService.userSessionData()?.tenant?.tenant_type || '').trim().toLowerCase();
  }

  get isPlatformAdmin(): boolean {
    return new Set(['admin', 'ops_admin', 'support_admin', 'compliance_admin', 'read_only_admin']).has(this.role);
  }

  get isServiceProvider(): boolean {
    return this.role === 'sp_admin' && this.tenantType === 'service_provider';
  }

  get isClient(): boolean {
    return this.role === 'client_admin' && this.tenantType === 'client';
  }

  get isGuard(): boolean {
    return this.role === 'guard_admin' && this.tenantType === 'guard';
  }

  get isServiceProviderOwnedGuard(): boolean {
    return isServiceProviderOwnedGuardTenant(this.appService.userSessionData()?.tenant);
  }

  get guardServiceProviderLabel(): string {
    const provider = this.appService.userSessionData()?.tenant?.service_provider;
    const name = String(provider?.name || '').trim();
    const id = String(provider?.id || this.appService.userSessionData()?.tenant?.service_provider_tenant_id || '').trim();
    return name || id || 'Service provider';
  }

  get pageSubtitle(): string {
    if (this.isPlatformAdmin) {
      return 'Command view of demand pressure, staffing execution, tenant activation, and platform revenue versus payout.';
    }
    if (this.isServiceProvider) {
      return 'Provider command view of offer response pressure, roster execution, shift risk, and payout readiness.';
    }
    if (this.isClient) {
      return 'Client operations view of request demand, shift execution risk, and spend signals across your sites.';
    }
    if (this.isServiceProviderOwnedGuard) {
      return 'Guard workboard view of offers, accepted coverage, and live shifts while coverage, availability, and payout remain provider-managed.';
    }
    return 'Guard workboard view of offers, accepted coverage, live shifts, and payout signals.';
  }

  private buildMetrics(): DashboardMetric[] {
    if (this.isPlatformAdmin) {
      return [
        {
          label: 'Review Queue',
          value: this.reviewQueueRequests.length,
          helperText: `${this.pendingReviewRequests.length} still pending first review`,
        },
        {
          label: 'Coverage Gaps',
          value: this.openCoverageRequests.length,
          helperText: `${this.coverageRiskRequests.length} requests still have uncovered positions`,
        },
        {
          label: 'Shifts At Risk',
          value: this.atRiskShifts.length,
          helperText: `${this.clientActionRequiredShifts.length} need client or ops intervention`,
        },
        {
          label: 'Active Guards',
          value: this.platformActiveGuardCount,
          helperText: 'Platform guard tenant accounts currently active',
        },
        {
          label: 'Active Providers',
          value: this.platformActiveProviderCount,
          helperText: `${this.platformPendingApprovalCount} provider or guard accounts pending activation`,
        },
        {
          label: 'Pending Activation',
          value: this.platformPendingApprovalCount,
          helperText: `${this.platformPendingTenants.length} newest approvals shown below`,
        },
        {
          label: 'Client Coverage Value',
          value: this.formatMoney(this.totalClientRevenue),
          helperText: `${this.platformInvoiceCount} payout invoices normalized into the platform finance view`,
        },
        {
          label: 'Assignee Payout',
          value: this.formatMoney(this.totalPayout),
          helperText: `${this.formatMoney(this.totalProviderPayout)} to providers • ${this.formatMoney(this.totalGuardPayout)} to direct guards`,
        },
        {
          label: 'Provider Adjustments',
          value: this.formatMoney(this.totalPlatformPayoutAdjustments),
          helperText: `${this.platformApprovedAdjustmentCount} approved • ${this.platformDraftAdjustmentCount} drafts waiting in finance`,
        },
        {
          label: 'Platform Margin',
          value: this.formatMoney(this.totalPlatformEarning),
          helperText: `${this.formatPercent(this.platformMarginPercent)} net margin across coverage value and payout`,
        },
      ];
    }

    if (this.isServiceProvider) {
      return [
        {
          label: 'Actionable Offers',
          value: this.allActionRequiredOffers.length,
          helperText: `${this.dueSoonOffers.length} expire or reconfirm soon`,
        },
        {
          label: 'Reconfirmations',
          value: this.reconfirmationJobs.length,
          helperText: `${this.acceptedJobs.length} already accepted and scheduled forward`,
        },
        {
          label: 'Committed Coverage',
          value: this.activeJobs.length,
          helperText: `${this.inProgressJobs.length} assignments already in progress`,
        },
        {
          label: 'Shifts At Risk',
          value: this.atRiskShifts.length,
          helperText: `${this.clientActionRequiredShifts.length} shifts need direct follow-through`,
        },
        {
          label: 'Active Guard Roster',
          value: this.activeProviderGuards.length,
          helperText: `${this.pendingProviderGuardInvites.length} invites or linked guards still pending`,
        },
        {
          label: this.assigneePayoutMetricLabel,
          value: this.formatMoney(this.assigneePayoutMetricValue),
          helperText: this.assigneePayoutMetricHelperText,
        },
        {
          label: 'Average Payout Rate',
          value: this.formatMoney(this.averageInvoiceHourlyRate),
          helperText: `${this.myInvoices.length} provider payout invoices on file`,
        },
      ];
    }

    if (this.isClient) {
      return [
        {
          label: 'Draft Requests',
          value: this.draftRequests.length,
          helperText: `${this.submittedRequests.length} already submitted into staffing operations`,
        },
        {
          label: 'Requests In Motion',
          value: this.attentionRequests.length,
          helperText: `${this.openCoverageRequests.length} still seeking staffing coverage`,
        },
        {
          label: 'Live Assignments',
          value: this.activeJobs.length,
          helperText: `${this.inProgressJobs.length} assignments already on shift`,
        },
        {
          label: 'Upcoming Shifts',
          value: this.upcomingShifts.length,
          helperText: `${this.todayShifts.length} scheduled for today`,
        },
        {
          label: 'Coverage Risk',
          value: this.coverageRiskRequests.length + this.atRiskShifts.length,
          helperText: `${this.clientActionRequiredShifts.length} shifts require client action`,
        },
        {
          label: this.clientSpendMetricLabel,
          value: this.formatMoney(this.clientSpendMetricValue),
          helperText: this.clientSpendMetricHelperText,
        },
      ];
    }

    if (this.isServiceProviderOwnedGuard) {
      return [
        {
          label: 'Actionable Offers',
          value: this.allActionRequiredOffers.length,
          helperText: `${this.dueSoonOffers.length} need a quick response`,
        },
        {
          label: 'Reconfirmations',
          value: this.reconfirmationJobs.length,
          helperText: `${this.acceptedJobs.length} accepted jobs still on your board`,
        },
        {
          label: 'Committed Jobs',
          value: this.activeJobs.length,
          helperText: `${this.inProgressJobs.length} already in progress`,
        },
        {
          label: 'Upcoming Shifts',
          value: this.upcomingShifts.length,
          helperText: `${this.todayShifts.length} shift(s) scheduled today`,
        },
        {
          label: 'Live Shift Work',
          value: this.inProgressShifts.length,
          helperText: `${this.atRiskShifts.length} shift(s) still need attention`,
        },
        {
          label: 'Managed By Provider',
          value: this.guardServiceProviderLabel,
          helperText: 'Operational coverage, weekly availability, and payout are controlled by your service provider',
        },
      ];
    }

    return [
      {
        label: 'Actionable Offers',
        value: this.allActionRequiredOffers.length,
        helperText: `${this.dueSoonOffers.length} need a quick response`,
      },
      {
        label: 'Reconfirmations',
        value: this.reconfirmationJobs.length,
        helperText: `${this.acceptedJobs.length} accepted jobs still on your board`,
      },
        {
        label: 'Committed Jobs',
        value: this.activeJobs.length,
        helperText: `${this.inProgressJobs.length} already in progress`,
      },
      {
        label: 'Upcoming Shifts',
        value: this.upcomingShifts.length,
        helperText: `${this.todayShifts.length} shift(s) scheduled today`,
      },
      {
        label: 'Live Shift Work',
        value: this.inProgressShifts.length,
        helperText: `${this.atRiskShifts.length} shift(s) still need attention`,
      },
      {
        label: this.assigneePayoutMetricLabel,
        value: this.formatMoney(this.assigneePayoutMetricValue),
        helperText: this.assigneePayoutMetricHelperText,
      },
      {
        label: 'Average Payout Rate',
        value: this.formatMoney(this.averageInvoiceHourlyRate),
        helperText: `${this.myInvoices.length} guard payout invoices on file`,
      },
    ];
  }

  private buildSections(): DashboardSection[] {
    if (this.isPlatformAdmin) {
      return [
        {
          title: 'Requests Requiring Intervention',
          subtitle: 'Requests still in review, returned for edits, or carrying open staffing pressure.',
          emptyMessage: 'No requests currently need intervention.',
          actionLabel: 'Open Review Queue',
          actionRoute: '/dashboard/requests?tab=requests',
          items: this.requestInterventionItems,
        },
        {
          title: 'Shift Coverage At Risk',
          subtitle: 'Upcoming shifts that are under-staffed, near roster deadlines, or blocked on client action.',
          emptyMessage: 'No upcoming shifts are currently at risk.',
          actionLabel: 'Open Risk Shifts',
          actionRoute: '/dashboard/requests?tab=shifts',
          items: this.atRiskShiftItems,
        },
        {
          title: 'Assignment Execution Feed',
          subtitle: 'Recently updated guard and service-provider jobs across the platform.',
          emptyMessage: 'No job activity has been recorded yet.',
          actionLabel: 'Open Job Feed',
          actionRoute: '/dashboard/requests?tab=jobs',
          items: this.recentJobItems,
        },
        {
          title: 'Finance And Margin Signals',
          subtitle: 'Linked revenue, payout, and invoice-state signals from the platform finance registry.',
          emptyMessage: 'No payout invoices are available for finance analysis yet.',
          actionLabel: 'Open Finance Analysis',
          actionRoute: '/dashboard/payout-invoices',
          items: this.platformFinanceItems,
        },
        {
          title: 'Tenant Activation Queue',
          subtitle: 'Newest guard or service-provider accounts still waiting on activation or compliance review.',
          emptyMessage: 'No tenant accounts are currently pending activation.',
          actionLabel: 'Open Activation Queue',
          actionRoute: '/dashboard/tenants',
          items: this.platformTenantItems,
        },
      ];
    }

    if (this.isServiceProvider) {
      return [
        {
          title: 'Offers Awaiting Response',
          subtitle: 'Coverage offers that still need an accept, decline, or reconfirmation response.',
          emptyMessage: 'No provider offers are awaiting response right now.',
          actionLabel: 'Open Offer Queue',
          actionRoute: '/dashboard/requests?tab=jobs',
          items: this.assigneeOfferItems,
        },
        {
          title: 'Coverage At Risk',
          subtitle: 'Upcoming shifts with roster gaps, late staffing pressure, or client action requirements.',
          emptyMessage: 'No provider shifts are currently at risk.',
          actionLabel: 'Open Risk Shifts',
          actionRoute: '/dashboard/requests?tab=shifts',
          items: this.atRiskShiftItems,
        },
        {
          title: 'Guard Roster Signals',
          subtitle: 'Managed guard accounts that are active, newly linked, or still pending invite completion.',
          emptyMessage: 'No linked or invited guards are currently visible.',
          actionLabel: 'Open Guard Roster',
          actionRoute: '/dashboard/tenants',
          items: this.providerGuardItems,
        },
        {
          title: 'Recent Invoices',
          subtitle: 'Issued payout-side invoices for your committed provider coverage.',
          emptyMessage: 'No provider invoices have been issued yet.',
          actionLabel: 'Open Provider Invoices',
          actionRoute: '/dashboard/my-invoices',
          items: this.invoiceItems,
        },
      ];
    }

    if (this.isClient) {
      return [
        {
          title: 'Requests Requiring Intervention',
          subtitle: 'Requests still being reviewed, edited, or kept open because coverage is incomplete.',
          emptyMessage: 'No client requests currently need intervention.',
          actionLabel: 'Open Request Queue',
          actionRoute: '/dashboard/requests?tab=requests',
          items: this.requestInterventionItems,
        },
        {
          title: 'Shift Coverage At Risk',
          subtitle: 'Upcoming shifts where staffing is still partial, coverage is late, or client action is required.',
          emptyMessage: 'No client shifts are currently at risk.',
          actionLabel: 'Open Risk Shifts',
          actionRoute: '/dashboard/requests?tab=shifts',
          items: this.atRiskShiftItems,
        },
        {
          title: 'Recent Job Activity',
          subtitle: 'Latest assignment changes and assignee responses attached to your requests.',
          emptyMessage: 'No job activity has been recorded yet.',
          actionLabel: 'Open Job Feed',
          actionRoute: '/dashboard/requests?tab=jobs',
          items: this.recentJobItems,
        },
        {
          title: 'Billing And Revision Signals',
          subtitle: 'Request records already carrying pricing, invoice, or billing-cycle signals.',
          emptyMessage: 'No request invoice or billing signals are available yet.',
          actionLabel: 'Open Billing Signals',
          actionRoute: '/dashboard/requests?tab=requests',
          items: this.requestBillingSignalItems,
        },
      ];
    }

    const guardSections: DashboardSection[] = [
      {
        title: 'Offers Awaiting Response',
        subtitle: 'Guard-side offers that still need an accept or reject decision.',
        emptyMessage: 'No guard offers are awaiting response right now.',
        actionLabel: 'Open Offer Queue',
        actionRoute: '/dashboard/requests?tab=jobs',
        items: this.assigneeOfferItems,
      },
      {
        title: 'Upcoming Assignments',
        subtitle: 'Your next scheduled work so you can prepare for check-in and start times.',
        emptyMessage: 'No assigned shifts are visible in the next 7 days.',
        actionLabel: 'Open Shift Board',
        actionRoute: '/dashboard/requests?tab=shifts',
        items: this.assigneeShiftItems,
      },
      {
        title: 'Recent Job Activity',
        subtitle: 'Latest updates across accepted, reconfirmed, or in-progress work assigned to you.',
        emptyMessage: 'No guard job activity has been recorded yet.',
        actionLabel: 'Open Job Feed',
        actionRoute: '/dashboard/requests?tab=jobs',
        items: this.recentJobItems,
      },
    ];

    if (this.isServiceProviderOwnedGuard) {
      guardSections.push({
        title: 'Managed Account',
        subtitle: 'Your service provider controls payout, weekly availability, and operational coverage for this guard account.',
        emptyMessage: 'Provider-managed account details are not available yet.',
        actionLabel: 'Open Settings',
        actionRoute: '/dashboard/settings',
        items: this.managedGuardItems,
      });
      return guardSections;
    }

    guardSections.push({
        title: 'Recent Invoices',
        subtitle: 'Issued payout-side invoices for your accepted guard coverage.',
        emptyMessage: 'No guard invoices have been issued yet.',
        actionLabel: 'Open Guard Invoices',
        actionRoute: '/dashboard/my-invoices',
        items: this.invoiceItems,
      });
    return guardSections;
  }

  private refreshOverviewState(): void {
    this.metrics = this.buildMetrics();
    this.sections = this.buildSections();
  }

  private get draftRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => String(item.request_status || '') === 'draft');
  }

  private get submittedRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => ['submitted', 'assigned', 'in_progress'].includes(String(item.request_status || '')));
  }

  private get attentionRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => ['pending_review', 'review_returned', 'open', 'partially_filled'].includes(String(item.staffing_status || '')));
  }

  private get openRequests(): ClientRequestItem[] {
    return this.attentionRequests;
  }

  private get reviewQueueRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => ['pending_review', 'review_returned'].includes(String(item.staffing_status || '')));
  }

  private get pendingReviewRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => String(item.staffing_status || '') === 'pending_review');
  }

  private get openCoverageRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => ['open', 'partially_filled'].includes(String(item.staffing_status || '')));
  }

  private get activeJobs(): RequestAssignmentItem[] {
    return this.jobs.filter((item) => ['accepted', 'in_progress'].includes(String(item.assignment_status || '')));
  }

  private get acceptedJobs(): RequestAssignmentItem[] {
    return this.jobs.filter((item) => String(item.assignment_status || '') === 'accepted');
  }

  private get inProgressJobs(): RequestAssignmentItem[] {
    return this.jobs.filter((item) => String(item.assignment_status || '') === 'in_progress');
  }

  private get coverageRiskRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => Number(item.open_slots || 0) > 0 && !['cancelled', 'closed'].includes(String(item.request_status || '')));
  }

  private get upcomingShifts(): ShiftInstanceItem[] {
    return [...this.shifts]
      .filter((item) => ['scheduled', 'partially_staffed', 'staffed', 'in_progress'].includes(String(item.instance_status || '')))
      .sort((left, right) => String(left.shift_start_at_utc || '').localeCompare(String(right.shift_start_at_utc || '')));
  }

  private get todayShifts(): ShiftInstanceItem[] {
    const today = this.toIsoDate(new Date());
    return this.upcomingShifts.filter((item) => item.shift_date_local === today);
  }

  private get inProgressShifts(): ShiftInstanceItem[] {
    return this.shifts.filter((item) => String(item.instance_status || '') === 'in_progress');
  }

  private get partiallyStaffedShifts(): ShiftInstanceItem[] {
    return this.upcomingShifts.filter((item) => String(item.instance_status || '') === 'partially_staffed');
  }

  private get clientActionRequiredShifts(): ShiftInstanceItem[] {
    return this.upcomingShifts.filter((item) => !!item.client_action_required);
  }

  private get atRiskShifts(): ShiftInstanceItem[] {
    return this.upcomingShifts.filter((item) =>
      !!item.client_action_required
      || String(item.instance_status || '') === 'partially_staffed'
      || Number(item.slots_staffed || 0) < Number(item.slots_required || 0)
      || this.isRosterDueSoon(item.roster_due_at),
    );
  }

  private get allActionRequiredOffers(): RequestAssignmentItem[] {
    return [...this.offeredJobs, ...this.reconfirmationJobs]
      .sort((left, right) => String(right.updated_at || '').localeCompare(String(left.updated_at || '')));
  }

  private get dueSoonOffers(): RequestAssignmentItem[] {
    return this.allActionRequiredOffers.filter((item) => this.isDeadlineSoon(item.response_due_at || item.reconfirmation_due_at));
  }

  private get activeProviderGuards(): ServiceProviderGuardSummaryItem[] {
    return this.providerGuards.filter((item) => String(item.status || '').trim().toLowerCase() === 'active');
  }

  private get pendingProviderGuardInvites(): ServiceProviderGuardSummaryItem[] {
    return this.providerGuards.filter((item) => {
      const inviteStatus = String(item.invite_status || '').trim().toLowerCase();
      const status = String(item.status || '').trim().toLowerCase();
      return inviteStatus === 'pending' || ['pending_activation', 'onboarding'].includes(status);
    });
  }

  private get currentMonthInvoiceTotal(): number {
    return this.myInvoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_amount || 0), 0);
  }

  private get currentMonthInvoiceCount(): number {
    return this.myInvoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .length;
  }

  private get currentMonthInvoiceHours(): string {
    const hours = this.myInvoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_total_hours || 0), 0);
    return this.formatHours(hours);
  }

  private get totalInvoiceAmount(): number {
    return this.myInvoices
      .reduce((sum, item) => sum + Number(item.estimated_amount || 0), 0);
  }

  private get totalInvoiceHours(): string {
    const hours = this.myInvoices
      .reduce((sum, item) => sum + Number(item.estimated_total_hours || 0), 0);
    return this.formatHours(hours);
  }

  private get assigneePayoutMetricLabel(): string {
    if (this.currentMonthInvoiceCount > 0) {
      return 'Current Month Payout';
    }
    if (this.myInvoices.length > 0) {
      return 'Issued Payout';
    }
    return 'Projected Payout';
  }

  private get assigneePayoutMetricValue(): number {
    if (this.currentMonthInvoiceCount > 0) {
      return this.currentMonthInvoiceTotal;
    }
    return this.totalInvoiceAmount;
  }

  private get assigneePayoutMetricHelperText(): string {
    if (this.currentMonthInvoiceCount > 0) {
      return `${this.currentMonthInvoiceHours} planned hours this month`;
    }
    if (this.myInvoices.length > 0) {
      return `${this.totalInvoiceHours} across ${this.myInvoices.length} issued payout invoice${this.myInvoices.length === 1 ? '' : 's'}`;
    }
    return 'No payout invoices are available yet';
  }

  private get averageInvoiceHourlyRate(): number | null {
    const totals = this.myInvoices.reduce((accumulator, item) => {
      const amount = Number(item.estimated_amount || 0);
      const hours = Number(item.estimated_total_hours || 0);
      if (!Number.isFinite(amount) || !Number.isFinite(hours) || hours <= 0) {
        return accumulator;
      }
      return {
        amount: accumulator.amount + amount,
        hours: accumulator.hours + hours,
      };
    }, { amount: 0, hours: 0 });
    if (totals.hours <= 0) {
      return null;
    }
    return Math.round((totals.amount / totals.hours) * 100) / 100;
  }

  private get activeBillableRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => !['draft', 'cancelled', 'closed'].includes(String(item.request_status || '')));
  }

  private get activeClientSpendEstimate(): number {
    return this.activeBillableRequests
      .reduce((sum, item) => sum + this.getRequestClientSpendEstimate(item), 0);
  }

  private get issuedClientBillingTotal(): number {
    return Object.values(this.clientLatestInvoiceAmountByRequestId)
      .reduce((sum, value) => sum + Number(value || 0), 0);
  }

  private get issuedClientBillingCount(): number {
    return Object.keys(this.clientLatestInvoiceAmountByRequestId).length;
  }

  private get clientSpendMetricLabel(): string {
    if (this.activeBillableRequests.length > 0) {
      return 'Active Spend Estimate';
    }
    if (this.issuedClientBillingCount > 0) {
      return 'Issued Billing';
    }
    return 'Spend Estimate';
  }

  private get clientSpendMetricValue(): number {
    if (this.activeBillableRequests.length > 0) {
      return this.activeClientSpendEstimate;
    }
    return this.issuedClientBillingTotal;
  }

  private get clientSpendMetricHelperText(): string {
    if (this.activeBillableRequests.length > 0) {
      return `${this.activeBillableRequests.length} active requests priced from saved request snapshots`;
    }
    if (this.issuedClientBillingCount > 0) {
      return `${this.issuedClientBillingCount} requests already carry issued invoice totals`;
    }
    return 'No active or issued client billing signals are available yet';
  }

  private get requestsWithInvoiceSignals(): ClientRequestItem[] {
    return this.requests.filter((item) =>
      !!item.invoicing_snapshot?.latest_invoice_id
      || !!item.invoicing_snapshot?.latest_invoice_number
      || !!item.invoicing_snapshot?.invoice_status,
    );
  }

  private get totalClientRevenue(): number {
    return Number(this.platformPayoutSummary?.total_client_revenue || 0);
  }

  private get totalPayout(): number {
    return Number(this.platformPayoutSummary?.total_payout || 0);
  }

  private get totalGuardPayout(): number {
    return Number(this.platformPayoutSummary?.total_guard_payout || 0);
  }

  private get totalProviderPayout(): number {
    return Number(this.platformPayoutSummary?.total_provider_payout || 0);
  }

  private get totalPlatformEarning(): number {
    return Number(this.platformPayoutSummary?.total_platform_earning || 0);
  }

  private get totalPlatformPayoutAdjustments(): number {
    return Number(this.platformPayoutSummary?.total_payout_adjustments || 0);
  }

  private get platformDraftAdjustmentCount(): number {
    return Number(this.platformPayoutSummary?.draft_payout_adjustment_count || 0);
  }

  private get platformApprovedAdjustmentCount(): number {
    return Number(this.platformPayoutSummary?.approved_payout_adjustment_count || 0);
  }

  private get platformMarginPercent(): number | null {
    const value = this.platformPayoutSummary?.platform_margin_percent;
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }

  private get platformInvoiceCount(): number {
    return Number(this.platformPayoutSummary?.invoice_count || 0);
  }

  private get requestInterventionItems(): DashboardSectionItem[] {
    return this.attentionRequests
      .sort((left, right) => Number(right.open_slots || 0) - Number(left.open_slots || 0))
      .slice(0, 5)
      .map((item) => ({
        title: item.title,
        subtitle: `${item.site_snapshot?.site_name || 'Site unavailable'} • ${this.formatTokenLabel(item.staffing_status)}`,
        meta: `${Number(item.accepted_slots || 0)} accepted • ${Number(item.open_slots || 0)} open • ${this.relativeWindowLabel(item.request_expires_at)}`,
        route: `/dashboard/requests?tab=requests&request=${item.id}`,
      }));
  }

  private get atRiskShiftItems(): DashboardSectionItem[] {
    return this.atRiskShifts.slice(0, 5).map((item) => ({
      title: item.request_title || 'Shift at risk',
      subtitle: `${item.site_name || 'Site unavailable'} • ${this.formatDateTime(item.shift_start_at_utc)}`,
      meta: `${item.slots_staffed}/${item.slots_required} staffed • ${this.getShiftRiskSummary(item)}`,
      route: `/dashboard/requests?tab=shifts&shift=${item.id}`,
    }));
  }

  private get recentJobItems(): DashboardSectionItem[] {
    return [...this.jobs]
      .sort((left, right) => String(right.updated_at || '').localeCompare(String(left.updated_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.request?.title || 'Assignment',
        subtitle: `${item.request?.site_name || 'Site unavailable'} • ${this.formatTokenLabel(item.assignment_status)}`,
        meta: `Updated ${this.formatDateTime(item.updated_at)} • ${item.assignee_tenant_type === 'service_provider' ? 'Service provider' : 'Guard'} coverage`,
        route: `/dashboard/requests?tab=jobs&job=${item.id}`,
      }));
  }

  private get assigneeOfferItems(): DashboardSectionItem[] {
    return this.allActionRequiredOffers.slice(0, 6).map((item) => ({
      title: item.request?.title || 'Offer',
      subtitle: `${item.request?.site_name || 'Site unavailable'} • ${this.formatTokenLabel(item.assignment_status)}`,
      meta: `${this.assignmentPaymentMeta(item)} • Response due ${this.relativeWindowLabel(item.response_due_at || item.reconfirmation_due_at)}`,
      route: `/dashboard/requests?tab=jobs&job=${item.id}`,
    }));
  }

  private get assigneeShiftItems(): DashboardSectionItem[] {
    return this.upcomingShifts.slice(0, 5).map((item) => ({
      title: item.request_title || 'Upcoming shift',
      subtitle: `${item.site_name || 'Site unavailable'} • ${this.formatDateTime(item.shift_start_at_utc)}`,
      meta: `${item.slots_staffed}/${item.slots_required} staffed • ${this.formatTokenLabel(item.instance_status)}`,
      route: `/dashboard/requests?tab=shifts&shift=${item.id}`,
    }));
  }

  private get providerGuardItems(): DashboardSectionItem[] {
    return [...this.providerGuards]
      .sort((left, right) => String(right.updated_at || right.created_at || '').localeCompare(String(left.updated_at || left.created_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.name || item.email || 'Managed guard',
        subtitle: `${this.formatTokenLabel(item.status)} • ${this.formatTokenLabel(item.invite_status || 'linked')}`,
        meta: `${item.verified ? 'Verified' : 'Unverified'} • Updated ${this.formatDateTime(item.updated_at || item.created_at)}`,
        route: `/dashboard/tenants/${item.id}`,
      }));
  }

  private get invoiceItems(): DashboardSectionItem[] {
    return [...this.myInvoices]
      .sort((left, right) => String(right.created_at || '').localeCompare(String(left.created_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.invoice_number,
        subtitle: `${item.request_title || 'Coverage invoice'} • ${item.billing_period_label || this.formatTokenLabel(item.billing_cycle)}`,
        meta: `${this.formatMoney(item.estimated_amount, item.currency || 'CAD')} • ${this.formatHours(item.estimated_total_hours)} • ${this.formatTokenLabel(item.invoice_status)}`,
        route: `/dashboard/my-invoices?invoice=${item.id}`,
      }));
  }

  private get managedGuardItems(): DashboardSectionItem[] {
    return [{
      title: this.guardServiceProviderLabel,
      subtitle: 'Provider-managed guard account',
      meta: 'Weekly availability, operational coverage, and payout invoices are handled by your service provider',
      route: '/dashboard/settings',
    }];
  }

  private get requestBillingSignalItems(): DashboardSectionItem[] {
    return [...this.requestsWithInvoiceSignals]
      .sort((left, right) => String(right.invoicing_snapshot?.last_invoice_issued_at || right.updated_at || '').localeCompare(String(left.invoicing_snapshot?.last_invoice_issued_at || left.updated_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.title,
        subtitle: `${item.site_snapshot?.site_name || 'Site unavailable'} • ${item.invoicing_snapshot?.latest_invoice_number || 'Invoice signal ready'}`,
        meta: `${this.formatMoney(this.getRequestBillingSignalAmount(item))} • ${this.formatTokenLabel(item.invoicing_snapshot?.invoice_status || item.invoicing_snapshot?.billing_cycle || 'billing-ready')}`,
        route: `/dashboard/requests?tab=requests&request=${item.id}`,
      }));
  }

  private get platformFinanceItems(): DashboardSectionItem[] {
    return [...this.platformPayoutInvoices]
      .sort((left, right) => String(right.created_at || '').localeCompare(String(left.created_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.invoice_number,
        subtitle: `${item.assignee_label || item.assignee_tenant_id || 'Assignee unavailable'} • ${item.request_title || 'Coverage invoice'}`,
        meta: `${this.formatMoney(item.estimated_client_revenue, item.currency || 'CAD')} coverage value • ${this.formatMoney(item.estimated_platform_earning, item.currency || 'CAD')} margin • ${this.formatTokenLabel(item.linked_client_invoice_status || item.invoice_status)}`,
        route: `/dashboard/payout-invoices?invoice=${item.id}`,
      }));
  }

  private get platformTenantItems(): DashboardSectionItem[] {
    return [...this.platformPendingTenants]
      .sort((left, right) => String(right.created_at || '').localeCompare(String(left.created_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.name || item.full_name || item.tenant_admin_user?.full_name || item.tenant_admin_user?.username || 'Tenant account',
        subtitle: `${this.formatTokenLabel(item.tenant_type)} • ${this.formatTokenLabel(item.status)}`,
        meta: `${item.verified ? 'Verified profile' : 'Verification pending'} • ${item.email || item.tenant_admin_user?.email || 'No admin email'}`,
        route: `/dashboard/tenants/${item.id}`,
      }));
  }

  loadDashboard(): void {
    this.loading = true;
    this.clientLatestInvoiceAmountByRequestId = {};
    const today = this.toIsoDate(new Date());
    const nextWeek = this.toIsoDate(this.addDays(new Date(), 7));
    const rows = 200;

    if (this.isPlatformAdmin) {
      this.subscriptions.add(forkJoin({
        requests: this.requestService.listRequests(1, rows, '', '', '', '', { loadingMode: 'global' }),
        jobs: this.requestService.listJobs(1, rows, '', '', { loadingMode: 'global' }),
        shifts: this.requestService.listShifts(1, rows, '', '', today, nextWeek, { loadingMode: 'global' }),
        payoutInvoices: this.requestService.listPlatformPayoutInvoices(1, 50, '', '', { loadingMode: 'global' }).pipe(
          catchError(() => of({ items: [], summary: null })),
        ),
        activeGuards: this.listTenantCounts('guard', 'active').pipe(
          catchError(() => of({ items: [], pagination: { total_items: 0 } })),
        ),
        activeProviders: this.listTenantCounts('service_provider', 'active').pipe(
          catchError(() => of({ items: [], pagination: { total_items: 0 } })),
        ),
        pendingTenants: this.listPendingTenants().pipe(
          catchError(() => of({ items: [], pagination: { total_items: 0 } })),
        ),
      }).subscribe({
        next: (response) => {
          this.requests = response.requests.items || [];
          this.jobs = response.jobs.items || [];
          this.shifts = response.shifts.items || [];
          this.platformPayoutInvoices = response.payoutInvoices.items || [];
          this.platformPayoutSummary = response.payoutInvoices.summary || null;
          this.platformActiveGuardCount = Number(response.activeGuards.pagination?.total_items || 0);
          this.platformActiveProviderCount = Number(response.activeProviders.pagination?.total_items || 0);
          this.platformPendingApprovalCount = Number(response.pendingTenants.pagination?.total_items || 0);
          this.platformPendingTenants = response.pendingTenants.items || [];
          this.refreshOverviewState();
          this.loading = false;
        },
        error: () => {
          this.platformPayoutInvoices = [];
          this.platformPayoutSummary = null;
          this.platformActiveGuardCount = 0;
          this.platformActiveProviderCount = 0;
          this.platformPendingApprovalCount = 0;
          this.platformPendingTenants = [];
          this.refreshOverviewState();
          this.loading = false;
        },
      }));
      return;
    }

    if (this.isServiceProvider) {
      this.subscriptions.add(forkJoin({
        jobs: this.requestService.listJobs(1, rows, '', '', { loadingMode: 'global' }),
        offeredJobs: this.requestService.listJobs(1, rows, 'offered', '', { loadingMode: 'global' }),
        reconfirmationJobs: this.requestService.listJobs(1, rows, 'reconfirmation_required', '', { loadingMode: 'global' }),
        shifts: this.requestService.listShifts(1, rows, '', '', today, nextWeek, { loadingMode: 'global' }),
        myInvoices: this.requestService.listMyInvoices(1, rows, { loadingMode: 'global' }),
        providerGuards: this.requestService.listServiceProviderGuards(1, rows, { loadingMode: 'global' }),
      }).subscribe({
        next: (response) => {
          this.jobs = response.jobs.items || [];
          this.offeredJobs = response.offeredJobs.items || [];
          this.reconfirmationJobs = response.reconfirmationJobs.items || [];
          this.shifts = response.shifts.items || [];
          this.myInvoices = response.myInvoices.items || [];
          this.providerGuards = response.providerGuards.items || [];
          this.refreshOverviewState();
          this.loading = false;
        },
        error: () => {
          this.refreshOverviewState();
          this.loading = false;
        },
      }));
      return;
    }

    if (this.isClient) {
      this.subscriptions.add(forkJoin({
        requests: this.requestService.listRequests(1, rows, '', '', '', '', { loadingMode: 'global' }),
        jobs: this.requestService.listJobs(1, rows, '', '', { loadingMode: 'global' }),
        shifts: this.requestService.listShifts(1, rows, '', '', today, nextWeek, { loadingMode: 'global' }),
      }).subscribe({
        next: (response) => {
          this.requests = response.requests.items || [];
          this.jobs = response.jobs.items || [];
          this.shifts = response.shifts.items || [];
          this.loadClientInvoiceAmountLookup(this.requests).subscribe({
            next: (lookup) => {
              this.clientLatestInvoiceAmountByRequestId = lookup;
              this.refreshOverviewState();
              this.loading = false;
            },
            error: () => {
              this.clientLatestInvoiceAmountByRequestId = {};
              this.refreshOverviewState();
              this.loading = false;
            },
          });
        },
        error: () => {
          this.clientLatestInvoiceAmountByRequestId = {};
          this.refreshOverviewState();
          this.loading = false;
        },
      }));
      return;
    }

    this.subscriptions.add(forkJoin({
      jobs: this.requestService.listJobs(1, rows, '', '', { loadingMode: 'global' }),
      offeredJobs: this.requestService.listJobs(1, rows, 'offered', '', { loadingMode: 'global' }),
      reconfirmationJobs: this.requestService.listJobs(1, rows, 'reconfirmation_required', '', { loadingMode: 'global' }),
      shifts: this.requestService.listShifts(1, rows, '', '', today, nextWeek, { loadingMode: 'global' }),
      myInvoices: this.isServiceProviderOwnedGuard
        ? of({ items: [], pagination: { page: 1, rows, total_items: 0, total_pages: 0 } })
        : this.requestService.listMyInvoices(1, rows, { loadingMode: 'global' }).pipe(
          catchError(() => of({ items: [], pagination: { page: 1, rows, total_items: 0, total_pages: 0 } })),
        ),
    }).subscribe({
      next: (response) => {
        this.jobs = response.jobs.items || [];
        this.offeredJobs = response.offeredJobs.items || [];
        this.reconfirmationJobs = response.reconfirmationJobs.items || [];
        this.shifts = response.shifts.items || [];
        this.myInvoices = response.myInvoices.items || [];
        this.refreshOverviewState();
        this.loading = false;
      },
      error: () => {
        this.refreshOverviewState();
        this.loading = false;
      },
    }));
  }

  goTo(route: string | undefined | null): void {
    const target = String(route || '').trim();
    if (!target) {
      return;
    }
    const [path, rawQuery = ''] = target.split('?', 2);
    const queryParams: Record<string, string> = {};
    const searchParams = new URLSearchParams(rawQuery);
    searchParams.forEach((value, key) => {
      queryParams[key] = value;
    });

    void this.router.navigate([path], {
      queryParams,
    });
  }

  trackMetric(_index: number, metric: DashboardMetric): string {
    return metric.label;
  }

  trackSection(_index: number, section: DashboardSection): string {
    return section.title;
  }

  trackSectionItem(_index: number, item: DashboardSectionItem): string {
    return `${item.route || item.title}|${item.meta}`;
  }

  formatMoney(value: number | string | null | undefined, currency = 'CAD'): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) {
      return '—';
    }
    return new Intl.NumberFormat('en-CA', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  }

  formatHours(value: number | string | null | undefined): string {
    const hours = Number(value);
    if (!Number.isFinite(hours)) {
      return '—';
    }
    return `${Math.round(hours * 100) / 100} hrs`;
  }

  formatPercent(value: number | null | undefined): string {
    const percent = Number(value);
    if (!Number.isFinite(percent)) {
      return '—';
    }
    return `${Math.round(percent * 100) / 100}%`;
  }

  formatDateTime(value: string | null | undefined): string {
    return formatBackendDateTime(value || null);
  }

  formatTokenLabel(value: string | null | undefined): string {
    const normalized = String(value || '').trim();
    if (!normalized) {
      return '—';
    }
    return normalized
      .split('_')
      .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
      .join(' ');
  }

  private assignmentPaymentMeta(item: RequestAssignmentItem): string {
    if (this.isServiceProviderOwnedGuard) {
      return 'Payout managed by provider';
    }
    const payout = item.assignee_tenant_type === 'service_provider'
      ? Number(item.request?.pricing_snapshot?.provider_hourly_pay)
      : Number(item.request?.pricing_snapshot?.guard_hourly_pay);
    return Number.isFinite(payout)
      ? `${this.formatMoney(payout)} / hr`
      : 'Payment snapshot pending';
  }

  private getRequestBillingSignalAmount(request: ClientRequestItem): number {
    const invoiceAmount = Number(this.clientLatestInvoiceAmountByRequestId[request.id] || 0);
    if (Number.isFinite(invoiceAmount) && invoiceAmount > 0) {
      return invoiceAmount;
    }
    return this.getRequestClientSpendEstimate(request);
  }

  private getRequestClientSpendEstimate(request: ClientRequestItem): number {
    const snapshotAmount = Number(request.pricing_snapshot?.estimated_client_charge);
    if (Number.isFinite(snapshotAmount) && snapshotAmount > 0) {
      return snapshotAmount;
    }

    const latestInvoiceAmount = Number(this.clientLatestInvoiceAmountByRequestId[request.id] || 0);
    if (Number.isFinite(latestInvoiceAmount) && latestInvoiceAmount > 0) {
      return latestInvoiceAmount;
    }

    const clientQuote = Number(request.pricing_snapshot?.client_hourly_quote);
    const hoursPerPosition = this.getRequestHoursPerPositionEstimate(request);
    if (!Number.isFinite(clientQuote) || clientQuote <= 0 || !Number.isFinite(hoursPerPosition) || hoursPerPosition <= 0) {
      return 0;
    }

    const relatedCommittedJobs = this.jobs.filter((job) =>
      String(job.request_id || '').trim() === String(request.id || '').trim()
      && ['accepted', 'in_progress', 'completed'].includes(String(job.assignment_status || '')),
    );

    if (!relatedCommittedJobs.length) {
      return 0;
    }

    const committedSlots = relatedCommittedJobs.reduce((sum, job) => {
      const slots = Number(job.slots_committed ?? 1);
      if (!Number.isFinite(slots) || slots <= 0) {
        return sum + 1;
      }
      return sum + Math.floor(slots);
    }, 0);

    return Math.round(clientQuote * hoursPerPosition * committedSlots * 100) / 100;
  }

  private getRequestHoursPerPositionEstimate(request: ClientRequestItem): number {
    const snapshotHours = Number(request.pricing_snapshot?.requested_hours_per_position);
    if (Number.isFinite(snapshotHours) && snapshotHours > 0) {
      return Math.round(snapshotHours * 100) / 100;
    }

    const estimatedTotalHours = Number(request.pricing_snapshot?.estimated_total_hours);
    const guardsRequired = Number(request.pricing_snapshot?.guards_required ?? request.guards_required);
    if (Number.isFinite(estimatedTotalHours) && estimatedTotalHours > 0 && Number.isFinite(guardsRequired) && guardsRequired > 0) {
      return Math.round((estimatedTotalHours / guardsRequired) * 100) / 100;
    }

    const requestedStartAt = request.requested_start_at;
    const requestedEndAt = request.requested_end_at;
    if (!requestedStartAt || !requestedEndAt) {
      return 0;
    }

    const start = new Date(requestedStartAt);
    const end = new Date(requestedEndAt);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
      return 0;
    }

    return Math.round((((end.getTime() - start.getTime()) / (1000 * 60 * 60)) * 100)) / 100;
  }

  private loadClientInvoiceAmountLookup(requests: ClientRequestItem[]) {
    const invoiceLookups = requests.reduce<Record<string, ReturnType<RequestService['getRequestInvoice']>>>((accumulator, request) => {
      const invoiceId = String(request.invoicing_snapshot?.latest_invoice_id || '').trim();
      if (!invoiceId) {
        return accumulator;
      }
      accumulator[request.id] = this.requestService.getRequestInvoice(request.id, invoiceId, { loadingMode: 'global' });
      return accumulator;
    }, {});

    if (!Object.keys(invoiceLookups).length) {
      return of({});
    }

    const guardedLookups = Object.entries(invoiceLookups).reduce<Record<string, Observable<RequestInvoiceItem | null>>>((accumulator, [requestId, observable]) => {
        accumulator[requestId] = observable.pipe(catchError(() => of(null)));
        return accumulator;
      }, {});

    return forkJoin(guardedLookups).pipe(
      map((responses) => (
        Object.entries(responses).reduce<Record<string, number>>((accumulator, [requestId, invoice]) => {
          const amount = Number(invoice?.estimated_amount);
          if (Number.isFinite(amount) && amount > 0) {
            accumulator[requestId] = amount;
          }
          return accumulator;
        }, {})
      )),
    );
  }

  private relativeWindowLabel(value: string | null | undefined): string {
    if (!value) {
      return 'No deadline';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return 'No deadline';
    }
    return formatBackendDateTime(parsed.toISOString());
  }

  private isDeadlineSoon(value: string | null | undefined): boolean {
    if (!value) {
      return false;
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return false;
    }
    const now = Date.now();
    return parsed.getTime() >= now && parsed.getTime() - now <= 24 * 60 * 60 * 1000;
  }

  private isRosterDueSoon(value: string | null | undefined): boolean {
    if (!value) {
      return false;
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return false;
    }
    const now = Date.now();
    return parsed.getTime() >= now && parsed.getTime() - now <= 24 * 60 * 60 * 1000;
  }

  private getShiftRiskSummary(item: ShiftInstanceItem): string {
    const reasons: string[] = [];
    if (Number(item.slots_staffed || 0) < Number(item.slots_required || 0)) {
      reasons.push('coverage gap');
    }
    if (String(item.instance_status || '') === 'partially_staffed') {
      reasons.push('partially staffed');
    }
    if (item.client_action_required) {
      reasons.push('client action required');
    }
    if (this.isRosterDueSoon(item.roster_due_at)) {
      reasons.push('roster due soon');
    }
    if (!reasons.length) {
      reasons.push(this.formatTokenLabel(item.instance_status));
    }
    return reasons.join(' • ');
  }

  private listTenantCounts(tenantType: string, tenantStatus: string) {
    const params = new HttpParams()
      .set('page', '1')
      .set('rows', '1')
      .set('sort_by', 'created_at')
      .set('sort_order', 'desc')
      .set('keyword', '')
      .set('tenant_type', tenantType)
      .set('tenant_status', tenantStatus);
    return this.api.get<any>('tenants/datatable', { params, loadingMode: 'global' });
  }

  private listPendingTenants() {
    const params = new HttpParams()
      .set('page', '1')
      .set('rows', '5')
      .set('sort_by', 'created_at')
      .set('sort_order', 'desc')
      .set('keyword', '')
      .set('tenant_type', '')
      .set('tenant_status', 'pending_activation');
    return this.api.get<any>('tenants/datatable', { params, loadingMode: 'global' });
  }

  private isCurrentMonth(value: string | null | undefined): boolean {
    if (!value) {
      return false;
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return false;
    }
    const now = new Date();
    return parsed.getFullYear() === now.getFullYear() && parsed.getMonth() === now.getMonth();
  }

  private addDays(base: Date, days: number): Date {
    const next = new Date(base);
    next.setDate(next.getDate() + days);
    return next;
  }

  private toIsoDate(value: Date): string {
    return value.toISOString().slice(0, 10);
  }
}
