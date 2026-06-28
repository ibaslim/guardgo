import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';

import { ButtonComponent } from '../../components/button/button.component';
import { CardComponent } from '../../components/card/card.component';
import { DrawerActionRowComponent } from '../../components/drawer-action-row/drawer-action-row.component';
import { DrawerTitleBlockComponent } from '../../components/drawer-title-block/drawer-title-block.component';
import { FilterActionBarComponent } from '../../components/filter-action-bar/filter-action-bar.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { ListStatePanelComponent } from '../../components/list-state-panel/list-state-panel.component';
import { ListToolbarComponent } from '../../components/list-toolbar/list-toolbar.component';
import { PageComponent } from '../../components/page/page.component';
import { PaginationFooterComponent } from '../../components/pagination-footer/pagination-footer.component';
import { RecordListItemComponent } from '../../components/record-list-item/record-list-item.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { AppService } from '../../services/core/app/app.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import {
  GuardLeaveBalanceItem,
  GuardLeavePolicyItem,
  GuardLeavePolicyUpsertPayload,
  GuardPlannedLeaveCreatePayload,
  GuardPlannedLeaveDecisionPayload,
  GuardPlannedLeaveItem,
  GuardPlannedLeaveType,
  GuardLeaveQuotaTargetItem,
} from '../../shared/model/request/client-request.model';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';
import { RequestService } from '../../shared/services/request.service';

interface GuardLeaveQuotaRow {
  target: GuardLeaveQuotaTargetItem;
  policy: GuardLeavePolicyItem | null;
  balance: GuardLeaveBalanceItem | null;
  form: {
    annualPaidLeaveDays: number;
    annualUnpaidLeaveDays: number;
    carryForwardDays: number;
    effectiveFrom: string;
  };
}

@Component({
  selector: 'app-leaves',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PageComponent,
    CardComponent,
    ButtonComponent,
    ListToolbarComponent,
    FilterActionBarComponent,
    SelectInputComponent,
    BaseInputComponent,
    TextareaComponent,
    ListStatePanelComponent,
    RecordListItemComponent,
    PaginationFooterComponent,
    SummaryMetricCardComponent,
    SideDrawerComponent,
    DrawerTitleBlockComponent,
    DrawerActionRowComponent,
  ],
  templateUrl: './leaves.component.html',
})
export class LeavesComponent implements OnInit {
  readonly plannedLeaveListScope = 'leaves:list';
  readonly plannedLeaveBalanceScope = 'leaves:balance';
  readonly plannedLeaveQuotaTargetsScope = 'leaves:quota-targets';
  readonly plannedLeaveQuotaRowsScope = 'leaves:quota-rows';

  activeView: 'leaves' | 'quota' = 'leaves';
  plannedLeaves: GuardPlannedLeaveItem[] = [];
  plannedLeavePage = 1;
  plannedLeaveRows = 10;
  plannedLeaveTotalPages = 1;
  plannedLeaveTotalItems = 0;
  plannedLeaveStatusFilter = '';
  quotaRows: GuardLeaveQuotaRow[] = [];
  guardLeaveBalance: GuardLeaveBalanceItem | null = null;
  guardLeavePolicy: GuardLeavePolicyItem | null = null;
  selectedPlannedLeave: GuardPlannedLeaveItem | null = null;
  showPlannedLeaveRequestDrawer = false;
  showPlannedLeaveDecisionDrawer = false;
  plannedLeaveErrors: Record<string, string> = {};
  plannedLeaveDecisionErrors: Record<string, string> = {};
  plannedLeaveForm = {
    leaveType: 'paid' as GuardPlannedLeaveType,
    startAt: '',
    endAt: '',
    reason: '',
  };
  plannedLeaveDecisionForm = {
    action: 'approve' as 'approve' | 'reject' | 'cancel',
    note: '',
  };

  plannedLeaveStatusOptions = [
    { label: 'All Leave Requests', value: '' },
    { label: 'Pending', value: 'pending' },
    { label: 'Approved', value: 'approved' },
    { label: 'Rejected', value: 'rejected' },
    { label: 'Cancelled', value: 'cancelled' },
  ];

  plannedLeaveTypeOptions = [
    { label: 'Paid Leave', value: 'paid' },
    { label: 'Unpaid Leave', value: 'unpaid' },
  ];

  constructor(
    private readonly appService: AppService,
    private readonly requestService: RequestService,
    private readonly notification: MessageNotificationService,
    private readonly loadingFeedback: LoadingFeedbackService,
  ) {}

  ngOnInit(): void {
    void this.appService.loadSession(true).then(() => {
      this.loadPlannedLeaves(1);
      if (this.isGuardAdmin) {
        this.loadOwnLeaveBalance();
      }
      if (this.canReviewPlannedLeave) {
        this.loadQuotaRows();
      }
    });
  }

  get role(): string {
    const raw = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    return raw.includes('.') ? (raw.split('.').pop() || '') : raw;
  }

  get tenantType(): string {
    return String(this.appService.userSessionData()?.tenant?.tenant_type || '').trim().toLowerCase();
  }

  get currentTenantId(): string {
    return String(this.appService.userSessionData()?.tenant?.id || '').trim();
  }

  get isPlatformAdmin(): boolean {
    return ['admin', 'ops_admin', 'support_admin', 'compliance_admin'].includes(this.role);
  }

  get isGuardAdmin(): boolean {
    return this.role === 'guard_admin' && this.tenantType === 'guard';
  }

  get isProviderAdmin(): boolean {
    return this.role === 'sp_admin' && this.tenantType === 'service_provider';
  }

  get canReviewPlannedLeave(): boolean {
    return this.isPlatformAdmin || this.isProviderAdmin;
  }

  get canRequestPlannedLeave(): boolean {
    return this.isGuardAdmin;
  }

  get pageSubtitle(): string {
    if (this.isGuardAdmin) {
      return 'Review your leave balance, submit leave requests, and track approval outcomes in one place.';
    }
    if (this.isProviderAdmin) {
      return 'Approve provider guard leave, manage quota, and keep future availability aligned with rostering.';
    }
    return 'Review direct-guard leave, manage quota, and keep operational coverage aligned with approvals.';
  }

  get plannedLeaveListTitle(): string {
    if (this.isGuardAdmin) {
      return 'My Leave Requests';
    }
    if (this.isProviderAdmin) {
      return 'Provider Guard Leave Queue';
    }
    return 'Direct Guard Leave Queue';
  }

  get plannedLeaveListSubtitle(): string {
    return `${this.plannedLeaveTotalItems} leave request${this.plannedLeaveTotalItems === 1 ? '' : 's'} visible in your current role scope.`;
  }

  get quotaListSubtitle(): string {
    if (this.isProviderAdmin) {
      return 'Edit quota for guards owned by your service provider. Approved paid leave will consume these balances.';
    }
    return 'Edit quota for direct guards. Approved paid leave will consume these balances.';
  }

  get canShowQuotaTab(): boolean {
    return this.canReviewPlannedLeave;
  }

  get visibleQuotaRows(): GuardLeaveQuotaRow[] {
    return this.quotaRows;
  }

  loadPlannedLeaves(page = 1, options?: { silent?: boolean; suppressError?: boolean }): void {
    const suppressError = Boolean(options?.suppressError);
    const guardTenantId = this.isGuardAdmin ? this.currentTenantId : '';
    this.requestService.listPlannedGuardLeaves(page, this.plannedLeaveRows, guardTenantId, this.plannedLeaveStatusFilter, {
      loadingScope: this.plannedLeaveListScope,
      loadingMode: options?.silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.plannedLeaves = response.items || [];
        this.plannedLeavePage = response.pagination?.page || page;
        this.plannedLeaveRows = response.pagination?.rows || this.plannedLeaveRows;
        this.plannedLeaveTotalPages = response.pagination?.total_pages || 1;
        this.plannedLeaveTotalItems = response.pagination?.total_items || 0;
      },
      error: (error) => {
        this.plannedLeaves = [];
        this.plannedLeavePage = page;
        this.plannedLeaveTotalPages = 1;
        this.plannedLeaveTotalItems = 0;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load leave requests', 'fail', 5000);
        }
      },
    });
  }

  loadOwnLeaveBalance(options?: { silent?: boolean; suppressError?: boolean }): void {
    if (!this.isGuardAdmin || !this.currentTenantId) {
      this.guardLeavePolicy = null;
      this.guardLeaveBalance = null;
      return;
    }
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getGuardLeaveBalance(this.currentTenantId, {
      loadingScope: this.plannedLeaveBalanceScope,
      loadingMode: options?.silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.guardLeavePolicy = response.policy;
        this.guardLeaveBalance = response.balance;
      },
      error: (error) => {
        this.guardLeavePolicy = null;
        this.guardLeaveBalance = null;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load leave balance', 'fail', 5000);
        }
      },
    });
  }

  loadQuotaRows(options?: { suppressError?: boolean }): void {
    if (!this.canReviewPlannedLeave) {
      this.quotaRows = [];
      return;
    }
    const suppressError = Boolean(options?.suppressError);
    this.loadingFeedback.begin('silent', this.plannedLeaveQuotaRowsScope);
    this.requestService.listGuardLeaveQuotaTargets({
      loadingScope: this.plannedLeaveQuotaTargetsScope,
      loadingMode: 'silent',
    }).subscribe({
      next: (response) => {
        const targets = response.items || [];
        if (!targets.length) {
          this.quotaRows = [];
          this.loadingFeedback.end('silent', this.plannedLeaveQuotaRowsScope);
          return;
        }
        const balanceRequests = targets.reduce<Record<string, ReturnType<RequestService['getGuardLeaveBalance']>>>((accumulator, target) => {
          accumulator[target.id] = this.requestService.getGuardLeaveBalance(target.id, { loadingMode: 'silent' });
          return accumulator;
        }, {});
        forkJoin(balanceRequests).subscribe({
          next: (balances) => {
            this.quotaRows = targets.map((target) => {
              const snapshot = balances[target.id];
              return {
                target,
                policy: snapshot?.policy || null,
                balance: snapshot?.balance || null,
                form: {
                  annualPaidLeaveDays: Number(snapshot?.policy?.annual_paid_leave_days || 0),
                  annualUnpaidLeaveDays: Number(snapshot?.policy?.annual_unpaid_leave_days || 0),
                  carryForwardDays: Number(snapshot?.policy?.carry_forward_days || 0),
                  effectiveFrom: String(snapshot?.policy?.effective_from || '').slice(0, 10),
                },
              };
            });
            this.loadingFeedback.end('silent', this.plannedLeaveQuotaRowsScope);
          },
          error: (error) => {
            this.quotaRows = [];
            this.loadingFeedback.end('silent', this.plannedLeaveQuotaRowsScope);
            if (!suppressError) {
              this.notification.show(error?.error?.detail || 'Failed to load leave quota list', 'fail', 5000);
            }
          },
        });
      },
      error: (error) => {
        this.quotaRows = [];
        this.loadingFeedback.end('silent', this.plannedLeaveQuotaRowsScope);
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load leave quota targets', 'fail', 5000);
        }
      },
    });
  }

  openPlannedLeaveRequestDrawer(): void {
    if (!this.canRequestPlannedLeave) {
      return;
    }
    this.plannedLeaveErrors = {};
    this.plannedLeaveForm = {
      leaveType: 'paid',
      startAt: '',
      endAt: '',
      reason: '',
    };
    this.showPlannedLeaveRequestDrawer = true;
  }

  closePlannedLeaveRequestDrawer(): void {
    this.showPlannedLeaveRequestDrawer = false;
    this.plannedLeaveErrors = {};
  }

  openPlannedLeaveDecisionDrawer(item: GuardPlannedLeaveItem, action: 'approve' | 'reject' | 'cancel'): void {
    this.selectedPlannedLeave = item;
    this.plannedLeaveDecisionErrors = {};
    this.plannedLeaveDecisionForm = {
      action,
      note: '',
    };
    this.showPlannedLeaveDecisionDrawer = true;
  }

  closePlannedLeaveDecisionDrawer(): void {
    this.showPlannedLeaveDecisionDrawer = false;
    this.selectedPlannedLeave = null;
    this.plannedLeaveDecisionErrors = {};
  }

  submitPlannedLeaveRequest(): void {
    if (!this.canRequestPlannedLeave) {
      return;
    }
    this.plannedLeaveErrors = {};
    const startAt = this.plannedLeaveForm.startAt.trim();
    const endAt = this.plannedLeaveForm.endAt.trim();
    if (!startAt) {
      this.plannedLeaveErrors['startAt'] = 'Leave start is required.';
    }
    if (!endAt) {
      this.plannedLeaveErrors['endAt'] = 'Leave end is required.';
    }
    const startDate = startAt ? new Date(startAt) : null;
    const endDate = endAt ? new Date(endAt) : null;
    if (!startDate || Number.isNaN(startDate.getTime())) {
      this.plannedLeaveErrors['startAt'] = 'Provide a valid leave start date and time.';
    }
    if (!endDate || Number.isNaN(endDate.getTime())) {
      this.plannedLeaveErrors['endAt'] = 'Provide a valid leave end date and time.';
    }
    if (startDate && endDate && startDate >= endDate) {
      this.plannedLeaveErrors['endAt'] = 'Leave end must be after the leave start.';
    }
    if (Object.keys(this.plannedLeaveErrors).length) {
      this.notification.show('Please fix the leave request fields.', 'fail', 4000);
      return;
    }

    const payload: GuardPlannedLeaveCreatePayload = {
      leave_type: this.plannedLeaveForm.leaveType,
      start_at_utc: startDate!.toISOString(),
      end_at_utc: endDate!.toISOString(),
      reason: this.plannedLeaveForm.reason.trim() || null,
    };
    this.requestService.createPlannedGuardLeave(payload, { loadingScope: 'leaves:create' }).subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Leave request submitted', 'success', 4500);
        this.closePlannedLeaveRequestDrawer();
        this.loadPlannedLeaves(1, { silent: true, suppressError: true });
        this.loadOwnLeaveBalance({ silent: true, suppressError: true });
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to submit leave request', 'fail', 5000);
      },
    });
  }

  submitPlannedLeaveDecision(): void {
    const leave = this.selectedPlannedLeave;
    if (!leave) {
      return;
    }
    const notePayload: GuardPlannedLeaveDecisionPayload = {
      note: this.plannedLeaveDecisionForm.note.trim() || null,
    };
    const action = this.plannedLeaveDecisionForm.action;
    const request$ = action === 'approve'
      ? this.requestService.approvePlannedGuardLeave(leave.id, notePayload, { loadingScope: `leaves:approve:${leave.id}` })
      : action === 'reject'
        ? this.requestService.rejectPlannedGuardLeave(leave.id, notePayload, { loadingScope: `leaves:reject:${leave.id}` })
        : this.requestService.cancelPlannedGuardLeave(leave.id, notePayload, { loadingScope: `leaves:cancel:${leave.id}` });
    request$.subscribe({
      next: () => {
        this.notification.show(
          action === 'approve' ? 'Leave request approved' : action === 'reject' ? 'Leave request rejected' : 'Leave request cancelled',
          'success',
          4500,
        );
        this.closePlannedLeaveDecisionDrawer();
        this.loadPlannedLeaves(this.plannedLeavePage, { silent: true, suppressError: true });
        if (this.canReviewPlannedLeave) {
          this.loadQuotaRows({ suppressError: true });
        }
        if (this.isGuardAdmin) {
          this.loadOwnLeaveBalance({ silent: true, suppressError: true });
        }
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to update leave request', 'fail', 5000);
      },
    });
  }

  saveQuotaRow(row: GuardLeaveQuotaRow): void {
    const payload: GuardLeavePolicyUpsertPayload = {
      annual_paid_leave_days: Number(row.form.annualPaidLeaveDays || 0),
      annual_unpaid_leave_days: Number(row.form.annualUnpaidLeaveDays || 0),
      carry_forward_days: Number(row.form.carryForwardDays || 0),
      effective_from: row.form.effectiveFrom || null,
    };
    if (payload.annual_paid_leave_days < 0 || payload.annual_unpaid_leave_days < 0 || payload.carry_forward_days < 0) {
      this.notification.show('Leave quota values must be zero or more.', 'fail', 4000);
      return;
    }
    this.requestService.upsertGuardLeaveBalance(row.target.id, payload, { loadingScope: this.getQuotaSaveScope(row.target.id) }).subscribe({
      next: (response) => {
        row.policy = response.policy;
        row.balance = response.balance;
        row.form = {
          annualPaidLeaveDays: Number(response.policy?.annual_paid_leave_days || 0),
          annualUnpaidLeaveDays: Number(response.policy?.annual_unpaid_leave_days || 0),
          carryForwardDays: Number(response.policy?.carry_forward_days || 0),
          effectiveFrom: String(response.policy?.effective_from || '').slice(0, 10),
        };
        this.notification.show(response.message || 'Leave quota updated', 'success', 4500);
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to update leave quota', 'fail', 5000);
      },
    });
  }

  canApprovePlannedLeaveItem(item: GuardPlannedLeaveItem): boolean {
    return this.canReviewPlannedLeave && String(item.request_status || '') === 'pending';
  }

  canRejectPlannedLeaveItem(item: GuardPlannedLeaveItem): boolean {
    return this.canReviewPlannedLeave && String(item.request_status || '') === 'pending';
  }

  canCancelPlannedLeaveItem(item: GuardPlannedLeaveItem): boolean {
    return this.isGuardAdmin && String(item.request_status || '') === 'pending';
  }

  getPlannedLeaveMetaItems(item: GuardPlannedLeaveItem): string[] {
    const items: string[] = [];
    if (!this.isGuardAdmin) {
      items.push(`Guard ${this.getGuardLabel(item.guard_tenant_id)}`);
    }
    items.push(`${this.formatNumber(item.requested_days)} day${Number(item.requested_days) === 1 ? '' : 's'}`);
    items.push(`Requested ${this.formatDateTime(item.created_at || item.start_at_utc)}`);
    if (item.approved_by_username) {
      items.push(`Approved by ${item.approved_by_username}`);
    }
    return items;
  }

  getGuardLabel(guardTenantId: string): string {
    const row = this.quotaRows.find((item) => item.target.id === guardTenantId);
    return row?.target.name || guardTenantId;
  }

  getStatusClasses(status: string): string {
    const token = String(status || '').trim().toLowerCase();
    if (token === 'approved') {
      return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-200';
    }
    if (token === 'rejected') {
      return 'bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-200';
    }
    if (token === 'cancelled') {
      return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-200';
    }
    return 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-200';
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

  formatDateTime(value: string | null | undefined): string {
    return formatBackendDateTime(value || null);
  }

  formatNumber(value: number | null | undefined): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) {
      return '0';
    }
    return `${Math.round(amount * 100) / 100}`;
  }

  trackByPlannedLeaveId(_index: number, item: GuardPlannedLeaveItem): string {
    return item.id;
  }

  trackByQuotaGuardId(_index: number, row: GuardLeaveQuotaRow): string {
    return row.target.id;
  }

  buildPaginationPages(page: number, totalPages: number): number[] {
    if (totalPages <= 1) {
      return [1];
    }
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_value, index) => start + index);
  }

  isScopeLoading(scope: string): boolean {
    return this.loadingFeedback.isScopeLoading(scope);
  }

  getQuotaSaveScope(guardTenantId: string): string {
    return `leaves:quota:${guardTenantId}`;
  }
}
