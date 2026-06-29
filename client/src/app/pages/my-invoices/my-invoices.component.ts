import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ButtonComponent } from '../../components/button/button.component';
import { DrawerActionRowComponent } from '../../components/drawer-action-row/drawer-action-row.component';
import { DrawerTitleBlockComponent } from '../../components/drawer-title-block/drawer-title-block.component';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { AppService } from '../../services/core/app/app.service';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { normalizeRole } from '../../shared/helpers/access-control.helper';
import { MyInvoiceItem, MyInvoiceLineItem } from '../../shared/model/request/client-request.model';
import { RequestService } from '../../shared/services/request.service';

@Component({
  selector: 'app-my-invoices',
  standalone: true,
  imports: [
    CommonModule,
    PageComponent,
    SectionComponent,
    ButtonComponent,
    SideDrawerComponent,
    DrawerTitleBlockComponent,
    DrawerActionRowComponent,
    SummaryMetricCardComponent,
  ],
  templateUrl: './my-invoices.component.html',
})
export class MyInvoicesComponent implements OnInit, OnDestroy {
  invoices: MyInvoiceItem[] = [];
  selectedInvoice: MyInvoiceItem | null = null;
  showInvoiceDrawer = false;
  listLoading = false;
  detailLoading = false;
  readonly listRows = 50;
  private readonly subscriptions = new Subscription();

  constructor(
    private readonly appService: AppService,
    private readonly requestService: RequestService,
    private readonly route: ActivatedRoute,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    void this.appService.loadSession(true).then(() => {
      this.loadInvoices();
      this.subscriptions.add(this.route.queryParams.subscribe((params) => this.handleRouteParams(params)));
    });
  }

  ngOnDestroy(): void {
    this.subscriptions.unsubscribe();
  }

  get role(): string {
    return normalizeRole(this.appService.userSessionData()?.user?.role);
  }

  get isProvider(): boolean {
    return this.role === 'sp_admin';
  }

  get pageSubtitle(): string {
    return this.isProvider
      ? 'Weekly payout invoices for completed scheduled provider coverage, plus per-job invoices for short-term work.'
      : 'Weekly payout invoices for completed scheduled guard coverage, plus per-job invoices for short-term work.';
  }

  get invoiceCount(): number {
    return this.invoices.length;
  }

  get currentMonthExpectedPay(): number {
    return this.invoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_amount || 0), 0);
  }

  get currentMonthHours(): number {
    return this.invoices
      .filter((item) => this.isCurrentMonth(item.billing_period_start_local || item.created_at))
      .reduce((sum, item) => sum + Number(item.estimated_total_hours || 0), 0);
  }

  get averageHourlyRate(): number | null {
    const rates = this.invoices
      .map((item) => Number(item.payout_hourly_rate))
      .filter((value) => Number.isFinite(value) && value > 0);
    if (!rates.length) {
      return null;
    }
    return Math.round((rates.reduce((sum, value) => sum + value, 0) / rates.length) * 100) / 100;
  }

  loadInvoices(): void {
    this.listLoading = true;
    this.requestService.listMyInvoices(1, this.listRows, { loadingMode: 'global' }).subscribe({
      next: (response) => {
        this.invoices = response.items || [];
        this.listLoading = false;
      },
      error: () => {
        this.invoices = [];
        this.listLoading = false;
      },
    });
  }

  openInvoice(invoice: MyInvoiceItem): void {
    this.selectedInvoice = invoice;
    this.showInvoiceDrawer = true;
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { invoice: invoice.id },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  private openInvoiceById(invoiceId: string): void {
    this.showInvoiceDrawer = true;
    const existingInvoice = this.invoices.find((item) => item.id === invoiceId) || null;
    if (existingInvoice) {
      this.selectedInvoice = existingInvoice;
    }
    this.detailLoading = true;
    this.requestService.getMyInvoice(invoiceId, { loadingMode: 'global' }).subscribe({
      next: (response) => {
        this.selectedInvoice = response;
        this.detailLoading = false;
      },
      error: () => {
        this.detailLoading = false;
      },
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

  getInvoiceLineItems(invoice: MyInvoiceItem | null): MyInvoiceLineItem[] {
    return invoice?.line_items || [];
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

  formatDateTime(value: string | null | undefined): string {
    return formatBackendDateTime(value || null);
  }

  formatServiceWindowDateTime(value: string | null | undefined): string {
    return formatBackendDateTime(value || null, 'en-CA', { preserveLocalTime: true });
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

  private resetInvoiceDrawerState(): void {
    this.showInvoiceDrawer = false;
    this.selectedInvoice = null;
    this.detailLoading = false;
  }
}
