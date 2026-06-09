import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subscription, forkJoin } from 'rxjs';

import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { AppService } from '../../services/core/app/app.service';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { normalizeRole } from '../../shared/helpers/access-control.helper';
import {
  ClientRequestItem,
  MyInvoiceItem,
  RequestAssignmentItem,
  ServiceProviderGuardSummaryItem,
  ShiftInstanceItem,
} from '../../shared/model/request/client-request.model';
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
  requests: ClientRequestItem[] = [];
  jobs: RequestAssignmentItem[] = [];
  offeredJobs: RequestAssignmentItem[] = [];
  reconfirmationJobs: RequestAssignmentItem[] = [];
  shifts: ShiftInstanceItem[] = [];
  myInvoices: MyInvoiceItem[] = [];
  providerGuards: ServiceProviderGuardSummaryItem[] = [];

  private readonly subscriptions = new Subscription();

  constructor(
    private readonly appService: AppService,
    private readonly requestService: RequestService,
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

  get isGuard(): boolean {
    return this.role === 'guard_admin' && this.tenantType === 'guard';
  }

  get pageSubtitle(): string {
    if (this.isPlatformAdmin) {
      return 'Operational view of open demand, active staffing, and the next shift workload across the platform.';
    }
    if (this.isServiceProvider) {
      return 'Live view of your incoming offers, committed coverage, issued invoices, and provider team capacity.';
    }
    return 'Live view of your offers, accepted work, upcoming shifts, and issued payout-side invoices.';
  }

  get metrics(): DashboardMetric[] {
    if (this.isPlatformAdmin) {
      return [
        {
          label: 'Open Requests',
          value: this.openRequests.length,
          helperText: `${this.pendingReviewRequests.length} pending review`,
        },
        {
          label: 'Active Jobs',
          value: this.activeJobs.length,
          helperText: `${this.inProgressJobs.length} already in progress`,
        },
        {
          label: 'Upcoming Shifts (7d)',
          value: this.upcomingShifts.length,
          helperText: `${this.partiallyStaffedShifts.length} not fully staffed`,
        },
        {
          label: 'Coverage Risk',
          value: this.coverageRiskRequests.length + this.partiallyStaffedShifts.length,
          helperText: 'Requests or shifts still missing coverage',
        },
      ];
    }

    if (this.isServiceProvider) {
      return [
        {
          label: 'New Offers',
          value: this.allActionRequiredOffers.length,
          helperText: `${this.reconfirmationJobs.length} need reconfirmation`,
        },
        {
          label: 'Active Coverage',
          value: this.activeJobs.length,
          helperText: `${this.upcomingShifts.length} shifts in the next 7 days`,
        },
        {
          label: 'My Guards',
          value: this.providerGuards.length,
          helperText: 'Active provider roster',
        },
        {
          label: "This Month's Pay",
          value: this.formatMoney(this.currentMonthInvoiceTotal),
          helperText: `${this.currentMonthInvoiceHours} planned hours`,
        },
      ];
    }

    return [
      {
        label: 'New Offers',
        value: this.allActionRequiredOffers.length,
        helperText: `${this.reconfirmationJobs.length} need reconfirmation`,
      },
      {
        label: 'Accepted Jobs',
        value: this.activeJobs.length,
        helperText: `${this.inProgressJobs.length} already in progress`,
      },
      {
        label: 'Upcoming Shifts (7d)',
        value: this.upcomingShifts.length,
        helperText: 'Assigned shifts approaching soon',
      },
      {
        label: "This Month's Pay",
        value: this.formatMoney(this.currentMonthInvoiceTotal),
        helperText: `${this.currentMonthInvoiceHours} planned hours`,
      },
    ];
  }

  get sections(): DashboardSection[] {
    if (this.isPlatformAdmin) {
      return [
        {
          title: 'Requests Needing Attention',
          subtitle: 'Demand that still needs review or additional staffing coverage.',
          emptyMessage: 'No requests currently need staffing attention.',
          actionLabel: 'Open Requests',
          actionRoute: '/dashboard/requests?tab=requests',
          items: this.platformAttentionItems,
        },
        {
          title: 'Upcoming Shift Operations',
          subtitle: 'The next scheduled shift workload across client requests.',
          emptyMessage: 'No shifts are scheduled in the next 7 days.',
          actionLabel: 'Open Shifts',
          actionRoute: '/dashboard/requests?tab=shifts',
          items: this.platformShiftItems,
        },
        {
          title: 'Recent Job Activity',
          subtitle: 'The most recently updated assignment records on the platform.',
          emptyMessage: 'No job activity has been recorded yet.',
          actionLabel: 'Open Jobs',
          actionRoute: '/dashboard/requests?tab=jobs',
          items: this.platformJobItems,
        },
      ];
    }

    if (this.isServiceProvider) {
      return [
        {
          title: 'Offers Awaiting Response',
          subtitle: 'Provider-side offers that still need an accept or reject decision.',
          emptyMessage: 'No provider offers are awaiting response right now.',
          actionLabel: 'Open Requests',
          actionRoute: '/dashboard/requests?tab=jobs',
          items: this.assigneeOfferItems,
        },
        {
          title: 'Upcoming Coverage',
          subtitle: 'Your next scheduled shifts that need roster execution or attendance follow-through.',
          emptyMessage: 'No scheduled coverage is visible in the next 7 days.',
          actionLabel: 'Open Shifts',
          actionRoute: '/dashboard/requests?tab=shifts',
          items: this.assigneeShiftItems,
        },
        {
          title: 'Recent Invoices',
          subtitle: 'Issued payout-side invoices for your committed provider coverage.',
          emptyMessage: 'No provider invoices have been issued yet.',
          actionLabel: 'Open My Invoices',
          actionRoute: '/dashboard/my-invoices',
          items: this.invoiceItems,
        },
      ];
    }

    return [
      {
        title: 'Offers Awaiting Response',
        subtitle: 'Guard-side offers that still need an accept or reject decision.',
        emptyMessage: 'No guard offers are awaiting response right now.',
        actionLabel: 'Open Requests',
        actionRoute: '/dashboard/requests?tab=jobs',
        items: this.assigneeOfferItems,
      },
      {
        title: 'Upcoming Assignments',
        subtitle: 'Your next scheduled work so you can prepare for check-in and start times.',
        emptyMessage: 'No assigned shifts are visible in the next 7 days.',
        actionLabel: 'Open Shifts',
        actionRoute: '/dashboard/requests?tab=shifts',
        items: this.assigneeShiftItems,
      },
      {
        title: 'Recent Invoices',
        subtitle: 'Issued payout-side invoices for your accepted guard coverage.',
        emptyMessage: 'No guard invoices have been issued yet.',
        actionLabel: 'Open My Invoices',
        actionRoute: '/dashboard/my-invoices',
        items: this.invoiceItems,
      },
    ];
  }

  private get openRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => ['pending_review', 'review_returned', 'open', 'partially_filled'].includes(String(item.staffing_status || '')));
  }

  private get pendingReviewRequests(): ClientRequestItem[] {
    return this.requests.filter((item) => String(item.staffing_status || '') === 'pending_review');
  }

  private get activeJobs(): RequestAssignmentItem[] {
    return this.jobs.filter((item) => ['accepted', 'in_progress'].includes(String(item.assignment_status || '')));
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

  private get partiallyStaffedShifts(): ShiftInstanceItem[] {
    return this.upcomingShifts.filter((item) => String(item.instance_status || '') === 'partially_staffed');
  }

  private get allActionRequiredOffers(): RequestAssignmentItem[] {
    return [...this.offeredJobs, ...this.reconfirmationJobs]
      .sort((left, right) => String(right.updated_at || '').localeCompare(String(left.updated_at || '')));
  }

  private get currentMonthInvoiceTotal(): number {
    return this.myInvoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_amount || 0), 0);
  }

  private get currentMonthInvoiceHours(): string {
    const hours = this.myInvoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_total_hours || 0), 0);
    return this.formatHours(hours);
  }

  private get platformAttentionItems(): DashboardSectionItem[] {
    return this.openRequests
      .sort((left, right) => Number(right.open_slots || 0) - Number(left.open_slots || 0))
      .slice(0, 5)
      .map((item) => ({
        title: item.title,
        subtitle: `${item.site_snapshot?.site_name || 'Site unavailable'} • ${this.formatTokenLabel(item.staffing_status)}`,
        meta: `${Number(item.open_slots || 0)} open slot(s) • ${this.formatTokenLabel(item.request_status)} • ${this.relativeWindowLabel(item.request_expires_at)}`,
        route: `/dashboard/requests?tab=requests&request=${item.id}`,
      }));
  }

  private get platformShiftItems(): DashboardSectionItem[] {
    return this.upcomingShifts.slice(0, 5).map((item) => ({
      title: item.request_title || 'Scheduled shift',
      subtitle: `${item.site_name || 'Site unavailable'} • ${this.formatDateTime(item.shift_start_at_utc)}`,
      meta: `${item.slots_staffed}/${item.slots_required} staffed • ${this.formatTokenLabel(item.instance_status)}`,
      route: `/dashboard/requests?tab=shifts&shift=${item.id}`,
    }));
  }

  private get platformJobItems(): DashboardSectionItem[] {
    return [...this.jobs]
      .sort((left, right) => String(right.updated_at || '').localeCompare(String(left.updated_at || '')))
      .slice(0, 5)
      .map((item) => ({
        title: item.request?.title || 'Assignment',
        subtitle: `${item.request?.site_name || 'Site unavailable'} • ${this.formatTokenLabel(item.assignment_status)}`,
        meta: `Updated ${this.formatDateTime(item.updated_at)} • ${item.assignee_tenant_type === 'service_provider' ? 'Service provider' : 'Guard'} offer`,
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

  loadDashboard(): void {
    this.loading = true;
    const today = this.toIsoDate(new Date());
    const nextWeek = this.toIsoDate(this.addDays(new Date(), 7));
    const rows = 200;

    if (this.isPlatformAdmin) {
      this.subscriptions.add(forkJoin({
        requests: this.requestService.listRequests(1, rows, '', '', '', '', { loadingMode: 'global' }),
        jobs: this.requestService.listJobs(1, rows, '', '', { loadingMode: 'global' }),
        shifts: this.requestService.listShifts(1, rows, '', '', today, nextWeek, { loadingMode: 'global' }),
      }).subscribe({
        next: (response) => {
          this.requests = response.requests.items || [];
          this.jobs = response.jobs.items || [];
          this.shifts = response.shifts.items || [];
          this.loading = false;
        },
        error: () => {
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
          this.loading = false;
        },
        error: () => {
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
      myInvoices: this.requestService.listMyInvoices(1, rows, { loadingMode: 'global' }),
    }).subscribe({
      next: (response) => {
        this.jobs = response.jobs.items || [];
        this.offeredJobs = response.offeredJobs.items || [];
        this.reconfirmationJobs = response.reconfirmationJobs.items || [];
        this.shifts = response.shifts.items || [];
        this.myInvoices = response.myInvoices.items || [];
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    }));
  }

  goTo(route: string | undefined | null): void {
    const target = String(route || '').trim();
    if (!target) {
      return;
    }
    window.location.assign(target);
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
    const payout = item.assignee_tenant_type === 'service_provider'
      ? Number(item.request?.pricing_snapshot?.provider_hourly_pay)
      : Number(item.request?.pricing_snapshot?.guard_hourly_pay);
    return Number.isFinite(payout)
      ? `${this.formatMoney(payout)} / hr`
      : 'Payment snapshot pending';
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
