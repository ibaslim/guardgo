import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ButtonComponent } from '../../components/button/button.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { DrawerActionRowComponent } from '../../components/drawer-action-row/drawer-action-row.component';
import { DrawerTitleBlockComponent } from '../../components/drawer-title-block/drawer-title-block.component';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { MyInvoiceLineItem, PlatformPayoutInvoiceItem, RequestPayoutAdjustmentItem } from '../../shared/model/request/client-request.model';
import { RequestService } from '../../shared/services/request.service';

@Component({
  selector: 'app-platform-payout-invoices',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PageComponent,
    SectionComponent,
    SelectInputComponent,
    ButtonComponent,
    SideDrawerComponent,
    DrawerTitleBlockComponent,
    DrawerActionRowComponent,
    SummaryMetricCardComponent,
  ],
  templateUrl: './platform-payout-invoices.component.html',
})
export class PlatformPayoutInvoicesComponent implements OnInit, OnDestroy {
  invoices: PlatformPayoutInvoiceItem[] = [];
  selectedInvoice: PlatformPayoutInvoiceItem | null = null;
  summary: {
    invoice_count?: number;
    total_client_revenue?: number;
    total_payout?: number;
    total_baseline_payout?: number;
    total_payout_adjustments?: number;
    draft_payout_adjustment_count?: number;
    approved_payout_adjustment_count?: number;
    voided_payout_adjustment_count?: number;
    total_platform_earning?: number;
    total_baseline_platform_earning?: number;
    total_hours?: number;
    total_guard_payout?: number;
    total_provider_payout?: number;
    total_guard_earning?: number;
    total_provider_earning?: number;
    platform_margin_percent?: number | null;
  } | null = null;
  showInvoiceDrawer = false;
  listLoading = false;
  detailLoading = false;
  adjustmentSubmitting = false;
  adjustmentActingId = '';
  readonly listRows = 100;
  readonly assigneeTenantTypeOptions = [
    { label: 'All assignees', value: '' },
    { label: 'Guards', value: 'guard' },
    { label: 'Service Providers', value: 'service_provider' },
  ];
  keyword = '';
  assigneeTenantType = '';
  adjustmentAmount: number | null = null;
  adjustmentReason = '';
  editingAdjustmentId = '';

  private readonly subscriptions = new Subscription();

  constructor(
    private readonly requestService: RequestService,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.subscriptions.add(this.route.queryParams.subscribe((params) => {
      this.keyword = String(params['keyword'] || '').trim();
      this.assigneeTenantType = String(params['assignee_tenant_type'] || '').trim();
      this.loadInvoices();
      this.handleRouteParams(params);
    }));
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  get invoiceCount(): number {
    return Number(this.summary?.invoice_count || 0);
  }

  get totalClientRevenue(): number {
    return Number(this.summary?.total_client_revenue || 0);
  }

  get totalPayout(): number {
    return Number(this.summary?.total_payout || 0);
  }

  get totalPlatformEarning(): number {
    return Number(this.summary?.total_platform_earning || 0);
  }

  get totalPayoutAdjustments(): number {
    return Number(this.summary?.total_payout_adjustments || 0);
  }

  get draftPayoutAdjustmentCount(): number {
    return Number(this.summary?.draft_payout_adjustment_count || 0);
  }

  get approvedPayoutAdjustmentCount(): number {
    return Number(this.summary?.approved_payout_adjustment_count || 0);
  }

  get voidedPayoutAdjustmentCount(): number {
    return Number(this.summary?.voided_payout_adjustment_count || 0);
  }

  get totalHours(): number {
    return Number(this.summary?.total_hours || 0);
  }

  get totalGuardPayout(): number {
    return Number(this.summary?.total_guard_payout || 0);
  }

  get totalProviderPayout(): number {
    return Number(this.summary?.total_provider_payout || 0);
  }

  get platformMarginPercent(): number | null {
    const value = this.summary?.platform_margin_percent;
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }

  loadInvoices(): void {
    this.listLoading = true;
    this.requestService.listPlatformPayoutInvoices(
      1,
      this.listRows,
      this.keyword,
      this.assigneeTenantType,
      { loadingMode: 'global' },
    ).subscribe({
      next: (response) => {
        this.invoices = response.items || [];
        this.summary = response.summary || null;
        this.listLoading = false;
      },
      error: () => {
        this.invoices = [];
        this.summary = null;
        this.listLoading = false;
      },
    });
  }

  applyFilters(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {
        keyword: this.keyword || null,
        assignee_tenant_type: this.assigneeTenantType || null,
      },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  clearFilters(): void {
    this.keyword = '';
    this.assigneeTenantType = '';
    this.applyFilters();
  }

  openInvoice(invoice: PlatformPayoutInvoiceItem): void {
    this.selectedInvoice = invoice;
    this.resetAdjustmentForm();
    this.showInvoiceDrawer = true;
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { invoice: invoice.id },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  closeInvoiceDrawer(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { invoice: null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  getInvoiceLineItems(invoice: PlatformPayoutInvoiceItem | null): MyInvoiceLineItem[] {
    return invoice?.line_items || [];
  }

  get canAdjustSelectedInvoice(): boolean {
    return this.canAdjustInvoice(this.selectedInvoice);
  }

  canAdjustInvoice(invoice: PlatformPayoutInvoiceItem | null | undefined): boolean {
    if (!invoice) {
      return false;
    }
    return String(invoice.assignee_tenant_type || '').trim().toLowerCase() === 'service_provider'
      && String(invoice.request_fulfillment_mode || '').trim().toLowerCase() === 'hybrid';
  }

  submitAdjustment(): void {
    const invoice = this.selectedInvoice;
    if (!this.canAdjustInvoice(invoice) || !invoice?.id) {
      return;
    }
    const amount = Number(this.adjustmentAmount);
    const reason = String(this.adjustmentReason || '').trim();
    if (!Number.isFinite(amount) || amount === 0 || !reason) {
      return;
    }

    this.adjustmentSubmitting = true;
    const request$ = this.editingAdjustmentId
      ? this.requestService.updatePlatformPayoutAdjustment(
          this.editingAdjustmentId,
          { amount, reason },
          { loadingMode: 'global' },
        )
      : this.requestService.createPlatformPayoutAdjustment(
          invoice.id,
          { amount, reason },
          { loadingMode: 'global' },
        );

    request$.subscribe({
      next: (response) => {
        this.selectedInvoice = response;
        this.resetAdjustmentForm();
        this.adjustmentSubmitting = false;
        this.loadInvoices();
      },
      error: () => {
        this.adjustmentSubmitting = false;
      },
    });
  }

  isDraftAdjustment(adjustment: RequestPayoutAdjustmentItem | null | undefined): boolean {
    return String(adjustment?.adjustment_status || '').trim().toLowerCase() === 'draft';
  }

  isApprovedAdjustment(adjustment: RequestPayoutAdjustmentItem | null | undefined): boolean {
    return String(adjustment?.adjustment_status || '').trim().toLowerCase() === 'approved';
  }

  isVoidedAdjustment(adjustment: RequestPayoutAdjustmentItem | null | undefined): boolean {
    return String(adjustment?.adjustment_status || '').trim().toLowerCase() === 'voided';
  }

  startAdjustmentEdit(adjustment: RequestPayoutAdjustmentItem): void {
    if (!this.isDraftAdjustment(adjustment)) {
      return;
    }
    this.editingAdjustmentId = String(adjustment.id || '').trim();
    this.adjustmentAmount = Number(adjustment.amount || 0) || null;
    this.adjustmentReason = String(adjustment.reason || '').trim();
  }

  cancelAdjustmentEdit(): void {
    this.resetAdjustmentForm();
  }

  approveAdjustment(adjustmentId: string): void {
    const normalizedId = String(adjustmentId || '').trim();
    if (!normalizedId || this.adjustmentActingId) {
      return;
    }
    this.adjustmentActingId = normalizedId;
    this.requestService.approvePlatformPayoutAdjustment(
      normalizedId,
      {},
      { loadingMode: 'global' },
    ).subscribe({
      next: (response) => {
        this.selectedInvoice = response;
        this.adjustmentActingId = '';
        this.loadInvoices();
      },
      error: () => {
        this.adjustmentActingId = '';
      },
    });
  }

  voidAdjustment(adjustmentId: string): void {
    const normalizedId = String(adjustmentId || '').trim();
    if (!normalizedId || this.adjustmentActingId) {
      return;
    }
    this.adjustmentActingId = normalizedId;
    this.requestService.voidPlatformPayoutAdjustment(
      normalizedId,
      {},
      { loadingMode: 'global' },
    ).subscribe({
      next: (response) => {
        this.selectedInvoice = response;
        if (this.editingAdjustmentId === normalizedId) {
          this.resetAdjustmentForm();
        }
        this.adjustmentActingId = '';
        this.loadInvoices();
      },
      error: () => {
        this.adjustmentActingId = '';
      },
    });
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

  formatHours(value: number | null | undefined): string {
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

  formatDate(value: string | null | undefined): string {
    if (!value) {
      return '—';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    }).format(parsed);
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

  getStatusClasses(value: string | null | undefined): string {
    const token = String(value || '').trim().toLowerCase();
    if (token === 'issued') {
      return 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-200';
    }
    if (token === 'revised') {
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-200';
    }
    return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200';
  }

  getAdjustmentStatusClasses(value: string | null | undefined): string {
    const token = String(value || '').trim().toLowerCase();
    if (token === 'approved') {
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200';
    }
    if (token === 'draft') {
      return 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-200';
    }
    if (token === 'voided') {
      return 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-200';
    }
    return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200';
  }

  private handleRouteParams(params: Record<string, any>): void {
    const invoiceId = String(params['invoice'] || '').trim();
    if (!invoiceId) {
      this.resetInvoiceDrawerState();
      return;
    }
    if (this.showInvoiceDrawer && this.selectedInvoice?.id === invoiceId && !this.detailLoading) {
      return;
    }
    this.openInvoiceById(invoiceId);
  }

  private openInvoiceById(invoiceId: string): void {
    this.showInvoiceDrawer = true;
    const existingInvoice = this.invoices.find((item) => item.id === invoiceId) || null;
    if (existingInvoice) {
      this.selectedInvoice = existingInvoice;
    }
    this.detailLoading = true;
    this.requestService.getPlatformPayoutInvoice(invoiceId, { loadingMode: 'global' }).subscribe({
      next: (response) => {
        this.selectedInvoice = response;
        this.resetAdjustmentForm();
        this.detailLoading = false;
      },
      error: () => {
        this.detailLoading = false;
      },
    });
  }

  private resetInvoiceDrawerState(): void {
    this.showInvoiceDrawer = false;
    this.selectedInvoice = null;
    this.detailLoading = false;
    this.resetAdjustmentForm();
  }

  private resetAdjustmentForm(): void {
    this.adjustmentAmount = null;
    this.adjustmentReason = '';
    this.adjustmentSubmitting = false;
    this.editingAdjustmentId = '';
  }
}
