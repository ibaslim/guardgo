import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableComponent } from '../../components/table/table.component';
import type { ColumnDef } from '../../components/table/table.component';
import { BadgeComponent } from '../../components/badge/badge.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { IconComponent } from '../../components/icon/icon.component';
import { ButtonComponent } from '../../components/button/button.component';
import { ModalComponent } from '../../components/modal/modal.component';
import { TableThComponent } from '../../components/table/table-th.component';
import { TableTdComponent } from '../../components/table/table-td.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { TenantSettingsComponent } from '../tenant-settings/tenant-settings.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import { readableTitle } from '../../shared/helpers/format.helper';
import { HttpParams } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-tenants',
  standalone: true,
  imports: [CommonModule, FormsModule, TableComponent, BadgeComponent, SideDrawerComponent, IconComponent, TableThComponent, TableTdComponent, ButtonComponent, ModalComponent, SelectInputComponent, TenantSettingsComponent],
  templateUrl: './tenants.component.html',
})
export class TenantsComponent implements OnInit {
  tenants: any[] = [];
  loading = false;
  page = 1;
  rows = 10;
  totalPages = 1;
  totalItems = 0;
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
    { label: 'Pending Verification', value: 'pending_verification' },
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Banned', value: 'banned' }
  ];

  showDrawer = false;
  tenantDetail: any = null;
  selectedRows: any[] = [];
  // UI state for modal/alerts
  showConfirmModal = false;
  pendingAction: 'verify' | 'deactivate' | 'ban' | null = null;
  confirmLabel = '';
  confirmButtonType: 'primary' | 'secondary' | 'warning' | 'danger' = 'primary';

  onSelectionChange(selected: any[]) {
    this.selectedRows = selected || [];
  }

  constructor(private api: ApiService, private router: Router, private route: ActivatedRoute, protected appService: AppService, private notification: MessageNotificationService) {}

  // expose helper to template
  readableTitle = readableTitle;

  ngOnInit(): void {
    this.loadPage(1);
    this.route.paramMap.subscribe(params => {
      const id = params.get('id');
      if (id) {
        this.loadTenantById(id);
      } else {
        this.showDrawer = false;
        this.tenantDetail = null;
      }
    });
  }

  loadPage(page: number) {
    this.loading = true;
    const params = new HttpParams()
      .set('page', String(page))
      .set('rows', String(this.rows))
      .set('sort_by', this.sort_by)
      .set('sort_order', this.sort_order)
      .set('keyword', this.keyword || '')
      .set('tenant_type', this.tenant_type || '')
      .set('tenant_status', this.tenant_status || '');

    this.api.get<any>('tenants/datatable', { params }).subscribe({
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
      this.router.navigate(['/dashboard/tenants', id]);
    }
  }

  loadTenantById(id: string) {
    this.loading = true;
    this.api.get<any>(`tenants/${id}`).subscribe({
      next: res => {
        this.tenantDetail = res;
        this.showDrawer = true;
        this.loading = false;
      },
      error: () => {
        this.tenantDetail = null;
        this.showDrawer = false;
        this.loading = false;
      }
    });
  }

  isAdmin(): boolean {
    const session = this.appService.userSessionData();
    return !!(session && session.user && session.user.role === 'admin');
  }

  confirmChange(action: 'verify' | 'deactivate' | 'ban') {
    if (!this.tenantDetail || !this.tenantDetail.id) return;
    const map: any = { verify: 'Verify', deactivate: 'Deactivate', ban: 'Ban' };
    this.pendingAction = action;
    // If verifying a previously inactive or banned tenant, present as "Re-activate"
    if (action === 'verify' && (this.tenantDetail?.status === 'inactive' || this.tenantDetail?.status === 'banned')) {
      this.confirmLabel = 'Re-activate';
    } else {
      this.confirmLabel = map[action];
    }
    // set confirm button style per action
    const typeMap: any = { verify: 'primary', deactivate: 'warning', ban: 'danger' };
    this.confirmButtonType = typeMap[action] || 'primary';
    this.showConfirmModal = true;
  }

  performStatusAction(action: 'verify' | 'deactivate' | 'ban') {
    if (!this.tenantDetail || !this.tenantDetail.id) return;
    const id = this.tenantDetail.id || this.tenantDetail._id;
    this.api.patch<any>(`tenants/${id}/${action}`).subscribe({
      next: res => {
        this.notification.show(res?.message || 'Tenant status updated', 'success', 4000);
        this.showConfirmModal = false;
        this.pendingAction = null;
        // reload tenant detail and list
        this.loadTenantById(id);
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
    this.showDrawer = false;
    // clear route id
    this.router.navigate(['/dashboard/tenants']);
  }
}
