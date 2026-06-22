import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableComponent } from '../../components/table/table.component';
import { BadgeComponent } from '../../components/badge/badge.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { IconComponent } from '../../components/icon/icon.component';
import { ButtonComponent } from '../../components/button/button.component';
import { ModalComponent } from '../../components/modal/modal.component';
import { TableThComponent } from '../../components/table/table-th.component';
import { TableTdComponent } from '../../components/table/table-td.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { PageComponent } from '../../components/page/page.component';
import { TenantSettingsComponent } from '../tenant-settings/tenant-settings.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import { formatBackendDateTime, readableTitle } from '../../shared/helpers/format.helper';
import { HttpParams } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { LogListTableComponent } from '../../components/activity-logs-table/activity-logs-table.component';
import { TenantAdminUserSummaryComponent } from '../../components/tenant-admin-user-summary/tenant-admin-user-summary.component';
import { PlaceloadComponent } from '../../components/placeload/placeload.component';

@Component({
  selector: 'app-tenants',
  standalone: true,
  imports: [CommonModule, FormsModule, TableComponent, BadgeComponent, SideDrawerComponent, IconComponent, TableThComponent, TableTdComponent, ButtonComponent, ModalComponent, SelectInputComponent, BaseInputComponent, PageComponent, TenantSettingsComponent, LogListTableComponent, TenantAdminUserSummaryComponent, PlaceloadComponent],
  templateUrl: './tenants.component.html',
})
export class TenantsComponent implements OnInit {
  readonly listScope = 'tenants:list';
  readonly detailScope = 'tenants:detail';
  readonly activityScope = 'tenants:activity';
  readonly inviteScope = 'tenants:invite';
  readonly spActionScope = 'tenants:sp-action';
  readonly statusScope = 'tenants:status';
  tenants: any[] = [];
  activityLogs: any[] = [];
  loading = false;
  activityLoading = false;
  page = 1;
  rows = 10;
  activityPage = 1;
  activityRows = 20;
  totalPages = 1;
  totalItems = 0;
  activityTotalPages = 1;
  activityTotalItems = 0;
  keyword = '';
  sort_by = 'created_at';
  sort_order: 'asc' | 'desc' = 'desc';
  tenant_type = '';
  tenant_status = '';
  tenantTypeOptions = [
    { label: 'All', value: '' },
    { label: 'Guard', value: 'guard' },
    { label: 'Client', value: 'client' },
    { label: 'Service Provider', value: 'service_provider' },
  ];
  tenantStatusOptions = [
    { label: 'All', value: '' },
    { label: 'Onboarding', value: 'onboarding' },
    { label: 'Pending Activation', value: 'pending_activation' },
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Banned', value: 'banned' }
  ];

  showDrawer = false;
  showActivityDrawer = false;
  tenantDetail: any = null;
  tenantDetailLoading = false;
  selectedTenantForLogs: any = null;
  selectedRows: any[] = [];
  // UI state for modal/alerts
  showConfirmModal = false;
  pendingAction: 'verify' | 'deactivate' | 'ban' | null = null;
  confirmLabel = '';
  confirmButtonType: 'primary' | 'secondary' | 'warning' | 'danger' = 'primary';
  showInviteGuardModal = false;
  inviteGuardEmail = '';
  showDeactivateReasonModal = false;
  deactivateReason = '';
  selectedGuardForStatusRequest: any = null;
  submittingSpAction = false;
  invitingGuard = false;
  private tenantDetailLoadTimer: ReturnType<typeof setTimeout> | null = null;
  private tenantDetailRequestToken = 0;

  onSelectionChange(selected: any[]) {
    this.selectedRows = selected || [];
  }

  constructor(
    private api: ApiService,
    private router: Router,
    private route: ActivatedRoute,
    protected appService: AppService,
    private notification: MessageNotificationService,
  ) {}

  // expose helper to template
  readableTitle = readableTitle;
  formatBackendDateTime = formatBackendDateTime;

  ngOnInit(): void {
    this.appService.loadRoleMetadata();
    this.loadPage(1);
    this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      if (id) {
        this.openTenantDrawer(id);
        return;
      }
      this.cancelTenantDetailFlow();
      this.showDrawer = false;
      this.tenantDetailLoading = false;
      this.tenantDetail = null;
    });
  }

  loadPage(page: number) {
    if (this.isSpAdmin()) {
      this.loadSpGuardPage(page);
      return;
    }
    this.loading = true;
    const params = new HttpParams()
      .set('page', String(page))
      .set('rows', String(this.rows))
      .set('sort_by', this.sort_by)
      .set('sort_order', this.sort_order)
      .set('keyword', this.keyword || '')
      .set('tenant_type', this.tenant_type || '')
      .set('tenant_status', this.tenant_status || '');

    this.api.get<any>('tenants/datatable', { params, loadingScope: this.listScope }).subscribe({
      next: res => {
        this.tenants = res.items || [];
        this.totalItems = res.pagination?.total_items || 0;
        this.totalPages = res.pagination?.total_pages || 1;
        this.page = res.pagination?.page || page;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  loadSpGuardPage(page: number) {
    this.loading = true;
    const params = new HttpParams()
      .set('page', String(page))
      .set('rows', String(this.rows));

    this.api.get<any>('sp/guards', { params, loadingScope: this.listScope }).subscribe({
      next: res => {
        this.tenants = res.items || [];
        this.totalItems = res.pagination?.total_items || 0;
        this.totalPages = res.pagination?.total_pages || 1;
        this.page = res.pagination?.page || page;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }

  onTenantTypeChange(val: any) {
    this.tenant_type = val || '';
    this.loadPage(1);
  }


  onTenantStatusChange(val: any) {
    this.tenant_status = val || '';
    this.loadPage(1);
  }

  resetFilters() {
    this.keyword = '';
    this.tenant_type = '';
    this.tenant_status = '';
    this.rows = 10;
    this.loadPage(1);
  }

  removeType() {
    this.tenant_type = '';
    this.loadPage(1);
  }

  removeStatus() {
    this.tenant_status = '';
    this.loadPage(1);
  }

  removeKeyword() {
    this.keyword = '';
    this.loadPage(1);
  }

  onSearch(q: string) {
    this.keyword = q || '';
    this.loadPage(1);
  }

  onSortChange(sort: { sort_by: string; sort_order: 'asc' | 'desc' }) {
    this.sort_by = sort.sort_by;
    this.sort_order = sort.sort_order;
    this.loadPage(1);
  }

  onPageSizeChange(size: number) {
    this.rows = Number(size) || this.rows;
    this.loadPage(1);
  }

  openTenant(row: any) {
    const id = row.id || row._id;
    if (id) {
      this.router.navigate(['/dashboard/tenants', id]).then();
    }
  }

  private prepareTenantDrawer(): void {
    this.showDrawer = true;
    this.tenantDetailLoading = true;
    this.tenantDetail = null;
  }

  private clearPendingTenantDetailLoad(): void {
    if (this.tenantDetailLoadTimer) {
      clearTimeout(this.tenantDetailLoadTimer);
      this.tenantDetailLoadTimer = null;
    }
  }

  private cancelTenantDetailFlow(): void {
    this.clearPendingTenantDetailLoad();
    this.tenantDetailRequestToken += 1;
  }

  private openTenantDrawer(id: string): void {
    this.clearPendingTenantDetailLoad();
    this.prepareTenantDrawer();
    const requestToken = ++this.tenantDetailRequestToken;
    this.tenantDetailLoadTimer = setTimeout(() => {
      this.tenantDetailLoadTimer = null;
      this.loadTenantById(id, requestToken);
    }, 180);
  }

  loadTenantById(id: string, requestToken?: number) {
    const endpoint = this.isSpAdmin() ? `sp/guards/${id}` : `tenants/${id}`;
    this.api.get<any>(endpoint, { loadingScope: this.detailScope }).subscribe({
      next: res => {
        if (requestToken && requestToken !== this.tenantDetailRequestToken) {
          return;
        }
        this.tenantDetail = res;
        this.tenantDetailLoading = false;
      },
      error: () => {
        if (requestToken && requestToken !== this.tenantDetailRequestToken) {
          return;
        }
        this.tenantDetail = null;
        this.tenantDetailLoading = false;
      }
    });
  }

  isAdmin(): boolean {
    const rawRole = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    const allowedRoles = this.appService.roleMetadata().tenantManagementRoles || [];
    return !!role && allowedRoles.includes(role);
  }

  isSpAdmin(): boolean {
    const rawRole = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    return role === 'sp_admin';
  }

  isSuperAdmin(): boolean {
    const rawRole = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    return role === 'admin';
  }

  confirmChange(action: 'verify' | 'deactivate' | 'ban') {
    if (!this.tenantDetail || !this.tenantDetail.id) return;
    const map: any = { verify: 'Approve', deactivate: 'Deactivate', ban: 'Ban' };
    this.pendingAction = action;
    // If verifying a previously inactive or banned tenant, present as "Re-activate"
    if (action === 'verify' && (this.tenantDetail?.status === 'inactive' || this.tenantDetail?.status === 'banned')) {
      this.confirmLabel = 'Approve & Re-activate';
    } else {
      this.confirmLabel = map[action];
    }
    // set confirm button style per action
    const typeMap: any = { verify: 'primary', deactivate: 'warning', ban: 'danger' };
    this.confirmButtonType = typeMap[action] || 'primary';
    this.showConfirmModal = true;
  }

  openInviteGuardModal() {
    this.inviteGuardEmail = '';
    this.showInviteGuardModal = true;
  }

  closeInviteGuardModal() {
    this.showInviteGuardModal = false;
    this.inviteGuardEmail = '';
    this.invitingGuard = false;
  }

  submitInviteGuard() {
    const email = String(this.inviteGuardEmail || '').trim();
    if (!email) {
      this.notification.show('Please enter guard email', 'fail', 4000);
      return;
    }

    this.invitingGuard = true;
    this.api.post<any>('sp/guards/invite', { email }, { loadingScope: this.inviteScope }).subscribe({
      next: res => {
        this.notification.show(res?.message || 'Guard invite sent', 'success', 4000);
        this.invitingGuard = false;
        this.closeInviteGuardModal();
        this.loadPage(1);
      },
      error: err => {
        this.notification.show(err?.error?.detail || 'Failed to invite guard', 'fail', 6000);
        this.invitingGuard = false;
      }
    });
  }

  canRequestActivate(row: any): boolean {
    const status = String(row?.status || '').toLowerCase();
    return status === 'inactive' || status === 'pending_activation';
  }

  canRequestDeactivate(row: any): boolean {
    return String(row?.status || '').toLowerCase() === 'active';
  }

  spRowActionScope(row: any, action: 'activate' | 'deactivate' | 'delete-invite'): string {
    const id = String(row?.id || row?._id || '').trim();
    return id ? `tenants:sp-action:${action}:${id}` : this.spActionScope;
  }

  requestActivate(row: any) {
    const id = row?.id || row?._id;
    if (!id) return;
    this.submittingSpAction = true;
    this.api.post<any>(
      `sp/guards/${id}/status-request`,
      { action: 'activate' },
      { loadingScope: this.spRowActionScope(row, 'activate') }
    ).subscribe({
      next: res => {
        this.notification.show(res?.message || 'Guard status updated', 'success', 4000);
        this.submittingSpAction = false;
        this.loadPage(this.page);
      },
      error: err => {
        this.notification.show(err?.error?.detail || 'Failed to update guard status', 'fail', 6000);
        this.submittingSpAction = false;
      }
    });
  }

  openDeactivateReasonModal(row: any) {
    this.selectedGuardForStatusRequest = row;
    this.deactivateReason = '';
    this.showDeactivateReasonModal = true;
  }

  closeDeactivateReasonModal() {
    this.showDeactivateReasonModal = false;
    this.deactivateReason = '';
    this.selectedGuardForStatusRequest = null;
    this.submittingSpAction = false;
  }

  submitDeactivateRequest() {
    const row = this.selectedGuardForStatusRequest;
    const id = row?.id || row?._id;
    const reason = String(this.deactivateReason || '').trim();
    if (!id) return;
    if (!reason) {
      this.notification.show('Reason is required for deactivation request', 'fail', 4000);
      return;
    }

    this.submittingSpAction = true;
    this.api.post<any>(
      `sp/guards/${id}/status-request`,
      { action: 'deactivate', reason },
      { loadingScope: this.spRowActionScope(row, 'deactivate') }
    ).subscribe({
      next: res => {
        this.notification.show(res?.message || 'Guard status updated', 'success', 4000);
        this.submittingSpAction = false;
        this.closeDeactivateReasonModal();
        this.loadPage(this.page);
      },
      error: err => {
        this.notification.show(err?.error?.detail || 'Failed to update guard status', 'fail', 6000);
        this.submittingSpAction = false;
      }
    });
  }

  isServiceProviderOwnedGuard(tenant: any): boolean {
    const tenantType = String(tenant?.tenant_type || tenant?.type || '').trim().toLowerCase();
    const ownership = String(tenant?.ownership_type || '').trim().toLowerCase();
    return tenantType === 'guard' && ownership === 'service_provider';
  }

  spActivateLabel(row: any): string {
    const status = String(row?.status || '').trim().toLowerCase();
    return status === 'pending_activation' ? 'Approve Guard' : 'Activate Guard';
  }

  spActivateAriaLabel(row: any): string {
    const status = String(row?.status || '').trim().toLowerCase();
    return status === 'pending_activation' ? 'Approve guard' : 'Activate guard';
  }

  canAdminApproveTenant(): boolean {
    if (!this.isAdmin() || this.isSpAdmin()) return false;
    if (!this.tenantDetail || this.tenantDetail?.status === 'active') return false;
    return !this.isServiceProviderOwnedGuard(this.tenantDetail);
  }

  private parseInviteExpiry(row: any): Date | null {
    const expiry = row?.tenant_admin_user?.invite_expires_at || row?.tenant_admin_user?.verification_expiry;
    if (!expiry) return null;
    const date = new Date(expiry);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  isPendingInvite(row: any): boolean {
    return !!row?.tenant_admin_user?.invite_pending;
  }

  isExpiredPendingInvite(row: any): boolean {
    if (!this.isPendingInvite(row)) return false;
    const expiryDate = this.parseInviteExpiry(row);
    if (!expiryDate) return false;
    return Date.now() > expiryDate.getTime();
  }

  inviteStateLabel(row: any): string {
    if (!this.isPendingInvite(row)) return 'Joined';
    return this.isExpiredPendingInvite(row) ? 'Pending (expired)' : 'Pending';
  }

  ownershipLabel(tenant: any): string {
    const tenantType = String(tenant?.tenant_type || tenant?.type || '').trim().toLowerCase();
    if (tenantType !== 'guard') return '';
    const ownership = String(tenant?.ownership_type || '').trim().toLowerCase();
    if (ownership === 'platform') return 'Platform Owned';
    const providerTenantId = String(tenant?.service_provider_tenant_id || '').trim();
    return providerTenantId ? 'Service Provider Owned' : 'Platform Owned';
  }

  ownershipColor(tenant: any): 'primary' | 'secondary' | 'success' | 'danger' | 'warning' {
    const ownership = String(tenant?.ownership_type || '').trim().toLowerCase();
    if (ownership === 'service_provider') return 'primary';
    if (ownership === 'platform') return 'secondary';
    return 'warning';
  }

  linkedServiceProviderLabel(tenant: any): string {
    const provider = tenant?.service_provider;
    const providerName = String(provider?.name || '').trim();
    const providerId = String(provider?.id || tenant?.service_provider_tenant_id || '').trim();
    return providerName || providerId || 'N/A';
  }

  ownerColumnLabel(row: any): string {
    const tenantType = String(row?.tenant_type || row?.type || '').trim().toLowerCase();
    if (tenantType !== 'guard') return '-';
    const ownership = String(row?.ownership_type || '').trim().toLowerCase();
    if (ownership === 'platform') return 'Platform';
    const provider = row?.service_provider;
    const providerName = String(provider?.name || '').trim();
    const providerId = String(provider?.id || row?.service_provider_tenant_id || '').trim();
    return providerName || providerId || 'Platform';
  }

  deleteExpiredPendingInvite(row: any) {
    const id = row?.id || row?._id;
    if (!id || !this.isExpiredPendingInvite(row)) return;

    this.submittingSpAction = true;
    this.api.delete<any>(
      `sp/guards/pending/${id}`,
      { loadingScope: this.spRowActionScope(row, 'delete-invite') }
    ).subscribe({
      next: res => {
        this.notification.show(res?.message || 'Expired invite deleted', 'success', 4000);
        this.submittingSpAction = false;
        this.loadPage(this.page);
      },
      error: err => {
        this.notification.show(err?.error?.detail || 'Failed to delete expired invite', 'fail', 6000);
        this.submittingSpAction = false;
      }
    });
  }

  private approvalFeedback(res: any): { message: string; type: 'success' | 'warning' } {
    const rawMessage = String(res?.message || '').trim();
    const approvalsDone = Number(res?.approvals_done || 0);
    const approvalsRequired = Number(res?.approvals_required || 2);

    if (rawMessage === 'Approval already recorded for this user') {
      return {
        type: 'warning',
        message: `You already approved this tenant. A different admin or compliance user is required (${approvalsDone}/${approvalsRequired} approvals recorded).`
      };
    }

    return {
      type: 'success',
      message: rawMessage || 'Tenant status updated'
    };
  }

  performStatusAction(action: 'verify' | 'deactivate' | 'ban') {
    if (!this.tenantDetail || !this.tenantDetail.id) return;
    const id = this.tenantDetail.id || this.tenantDetail._id;
    const endpointAction = action === 'verify' ? 'approve' : action;
    this.api.patch<any>(`tenants/${id}/${endpointAction}`, undefined, { loadingScope: this.statusScope }).subscribe({
      next: res => {
        const feedback = action === 'verify'
          ? this.approvalFeedback(res)
          : { message: res?.message || 'Tenant status updated', type: 'success' as const };

        this.notification.show(feedback.message, feedback.type, 4500);
        this.showConfirmModal = false;
        this.pendingAction = null;
        // reload tenant detail and list
        this.openTenantDrawer(id);
        this.loadPage(this.page);
      },
      error: err => {
        this.notification.show(err?.error?.detail || 'Failed to update tenant status', 'fail', 6000);
        this.showConfirmModal = false;
        this.pendingAction = null;
      }
    });
  }

  onConfirmModalClose() {
    this.showConfirmModal = false;
    this.pendingAction = null;
  }

  handleConfirm() {
    if (this.pendingAction) {
      this.performStatusAction(this.pendingAction);
    }
  }

  onCloseDrawer() {
    this.cancelTenantDetailFlow();
    this.router.navigate(['/dashboard/tenants']).then();
  }

  openTenantLogs(row: any) {
    if (!this.isSuperAdmin()) return;
    const id = row?.id || row?._id;
    if (!id) return;
    this.selectedTenantForLogs = row;
    this.showActivityDrawer = true;
    this.loadTenantActivityLogs(id, 1);
  }

  loadTenantActivityLogs(tenantId: string, page: number = 1) {
    this.activityLoading = true;
    const params = new HttpParams()
      .set('module', 'tenant')
      .set('entity_type', 'tenant')
      .set('entity_id', String(tenantId))
      .set('page', String(page))
      .set('rows', String(this.activityRows));

    this.api.get<any>('activity', { params, loadingScope: this.activityScope }).subscribe({
      next: res => {
        this.activityLogs = res?.items || [];
        this.activityTotalItems = res?.pagination?.total_items || 0;
        this.activityTotalPages = res?.pagination?.total_pages || 1;
        this.activityPage = res?.pagination?.page || page;
        this.activityLoading = false;
      },
      error: () => {
        this.activityLogs = [];
        this.activityTotalItems = 0;
        this.activityTotalPages = 1;
        this.activityLoading = false;
      }
    });
  }

  closeActivityModal() {
    this.showActivityDrawer = false;
    this.selectedTenantForLogs = null;
    this.activityLogs = [];
    this.activityPage = 1;
    this.activityTotalPages = 1;
    this.activityTotalItems = 0;
  }

  nextActivityPage() {
    if (!this.selectedTenantForLogs) return;
    const id = this.selectedTenantForLogs.id || this.selectedTenantForLogs._id;
    if (!id || this.activityPage >= this.activityTotalPages) return;
    this.loadTenantActivityLogs(id, this.activityPage + 1);
  }

  prevActivityPage() {
    if (!this.selectedTenantForLogs) return;
    const id = this.selectedTenantForLogs.id || this.selectedTenantForLogs._id;
    if (!id || this.activityPage <= 1) return;
    this.loadTenantActivityLogs(id, this.activityPage - 1);
  }
}
