import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';

import { TableComponent } from '../../components/table/table.component';
import { TableThComponent } from '../../components/table/table-th.component';
import { TableTdComponent } from '../../components/table/table-td.component';
import { ButtonComponent } from '../../components/button/button.component';
import { ModalComponent } from '../../components/modal/modal.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { BadgeComponent } from '../../components/badge/badge.component';
import { IconComponent } from '../../components/icon/icon.component';
import { PageComponent } from '../../components/page/page.component';
import { isValidEmail } from '../../shared/helpers/email.helper';

interface PlatformAdminUser {
  id: string;
  username: string;
  full_name?: string;
  email: string;
  role: string;
  status: string;
  status_reason?: string | null;
  tenant_uuid?: string | null;
  licenses: string[];
  invite_pending?: boolean;
  invite_expires_at?: string | null;
  deleted_at?: string | null;
}

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TableComponent,
    TableThComponent,
    TableTdComponent,
    ButtonComponent,
    ModalComponent,
    SelectInputComponent,
    BaseInputComponent,
    BadgeComponent,
    IconComponent,
    PageComponent
  ],
  templateUrl: './admin-users.component.html'
})
export class AdminUsersComponent implements OnInit {
  readonly listScope = 'admin-users:list';
  readonly saveScope = 'admin-users:save';
  loading = false;
  saving = false;
  users: PlatformAdminUser[] = [];
  keyword = '';
  roleFilter = '';
  statusFilter = '';
  rows = 10;

  roleOptions: { label: string; value: string }[] = [];
  statusOptions: { label: string; value: string }[] = [
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Blocked', value: 'blocked' },
    { label: 'Deleted', value: 'deleted' }
  ];

  showCreateModal = false;
  showEditModal = false;
  createFormErrors: Record<string, string> = {};
  editFormErrors: Record<string, string> = {};

  createForm = {
    email: '',
    role: '',
  };

  editTargetId = '';
  editForm = {
    role: '',
    status: 'active',
    status_reason: ''
  };

  constructor(
    private api: ApiService,
    protected appService: AppService,
    private notification: MessageNotificationService
  ) {}

  async ngOnInit(): Promise<void> {
    await this.appService.loadRoleMetadata();
    if (!this.isSuperAdminCompatible()) {
      return;
    }
    this.loadRoleOptions();
    this.loadUsers();
  }

  isSuperAdminCompatible(): boolean {
    const rawRole = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    const allowedRoles = this.appService.roleMetadata().platformUserManagementRoles || [];
    return !!role && allowedRoles.includes(role);
  }

  get filteredUsers(): PlatformAdminUser[] {
    return (this.users || []).filter((user) => {
      const roleMatch = !this.roleFilter || user.role === this.roleFilter;
      const statusMatch = !this.statusFilter || user.status === this.statusFilter;

      const searchable = `${user.username} ${user.email} ${this.getRoleLabel(user.role)} ${user.status}`.toLowerCase();
      const keywordMatch = !this.keyword.trim() || searchable.includes(this.keyword.trim().toLowerCase());

      return roleMatch && statusMatch && keywordMatch;
    });
  }

  get roleFilterOptions(): { label: string; value: string }[] {
    const map = new Map<string, string>();

    (this.roleOptions || []).forEach(r => map.set(r.value, r.label));
    (this.users || []).forEach(u => {
      if (!map.has(u.role)) {
        map.set(u.role, this.formatRoleLabel(u.role));
      }
    });

    return [
      { label: 'All', value: '' },
      ...Array.from(map.entries())
        .map(([value, label]) => ({ value, label }))
        .sort((a, b) => a.label.localeCompare(b.label))
    ];
  }

  get statusFilterOptions(): { label: string; value: string }[] {
    return [
      { label: 'All', value: '' },
      ...this.statusOptions
    ];
  }

  private formatRoleLabel(value: string): string {
    return value
      .split('_')
      .map(v => v ? v.charAt(0).toUpperCase() + v.slice(1) : v)
      .join(' ');
  }

  getRoleLabel(value: string): string {
    return this.roleFilterOptions.find(v => v.value === value)?.label || this.formatRoleLabel(value);
  }

  onSearch(query: string): void {
    this.keyword = query || '';
  }

  onRoleFilterChange(value: string): void {
    this.roleFilter = value || '';
  }

  onStatusFilterChange(value: string): void {
    this.statusFilter = value || '';
  }

  onPageSizeChange(value: number): void {
    this.rows = Number(value) || 10;
  }

  removeKeyword(): void {
    this.keyword = '';
  }

  removeRole(): void {
    this.roleFilter = '';
  }

  removeStatus(): void {
    this.statusFilter = '';
  }

  resetFilters(): void {
    this.keyword = '';
    this.roleFilter = '';
    this.statusFilter = '';
    this.rows = 10;
  }

  loadRoleOptions(): void {
    this.api.get<any[]>('admin/platform-roles', { loadingScope: 'admin-users:roles' }).subscribe({
      next: (res) => {
        this.roleOptions = (res || []).map((r: any) => ({ label: r.label, value: r.value }));
      },
      error: () => {
        this.roleOptions = [];
      }
    });
  }

  loadUsers(): void {
    this.loading = true;
    this.api.get<PlatformAdminUser[]>('admin/platform-users', { loadingScope: this.listScope }).subscribe({
      next: (res) => {
        this.users = (res || []).map((u: any) => ({
          ...u,
          status: (u.status || 'active').toLowerCase()
        }));
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.notification.show(err?.error?.detail || 'Failed to load admin users', 'fail', 5000);
      }
    });
  }

  openCreateModal(): void {
    this.createForm = {
      email: '',
      role: this.roleOptions[0]?.value || '',
    };
    this.createFormErrors = {};
    this.showCreateModal = true;
  }

  closeCreateModal(): void {
    this.showCreateModal = false;
    this.createFormErrors = {};
  }

  private extractApiErrorMessage(err: any, fallback: string): string {
    const detail = err?.error?.detail;

    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      if (typeof first === 'string' && first.trim()) {
        return first;
      }
      if (first?.msg) {
        return String(first.msg);
      }
    }

    if (typeof err?.error?.message === 'string' && err.error.message.trim()) {
      return err.error.message;
    }

    if (typeof err?.message === 'string' && err.message.trim()) {
      return err.message;
    }

    return fallback;
  }

  private validateCreateForm(): boolean {
    this.createFormErrors = {};

    if (!this.createForm.email.trim()) {
      this.createFormErrors['email'] = 'Email is required.';
    } else if (!isValidEmail(this.createForm.email)) {
      this.createFormErrors['email'] = 'Enter a valid email address.';
    }

    if (!this.createForm.role) {
      this.createFormErrors['role'] = 'Role is required.';
    }

    return Object.keys(this.createFormErrors).length === 0;
  }

  createUser(): void {
    if (!this.validateCreateForm()) {
      this.notification.show('Please fix the highlighted fields.', 'fail', 3500);
      return;
    }

    this.createFormErrors['form'] = '';

    this.saving = true;
    this.api.post<any>('admin/platform-users', {
      email: this.createForm.email.trim().toLowerCase(),
      role: this.createForm.role,
    }, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.showCreateModal = false;
        this.notification.show('Invite sent successfully. User can set password from email link.', 'success', 4500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        const message = this.extractApiErrorMessage(err, 'Failed to create admin user');

        if (/email|already exists|already taken/i.test(message)) {
          this.createFormErrors['email'] = message;
        } else {
          this.createFormErrors['form'] = message;
        }

        this.notification.show(message, 'fail', 5000);
      }
    });
  }

  openEditModal(row: PlatformAdminUser): void {
    this.editTargetId = row.id;
    this.editForm = {
      role: row.role,
      status: row.status || 'active',
      status_reason: row.status_reason || ''
    };
    this.editFormErrors = {};
    this.showEditModal = true;
  }

  resendInvite(row: PlatformAdminUser): void {
    if (!row?.id) {
      return;
    }

    this.saving = true;
    this.api.post<any>(`admin/platform-users/${row.id}/resend-invite`, {}, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.notification.show('Invite resent successfully.', 'success', 3500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.notification.show(err?.error?.detail || 'Failed to resend invite', 'fail', 5000);
      }
    });
  }

  closeEditModal(): void {
    this.showEditModal = false;
    this.editTargetId = '';
    this.editFormErrors = {};
  }

  private validateEditForm(): boolean {
    this.editFormErrors = {};

    if (!this.editForm.role) {
      this.editFormErrors['role'] = 'Role is required.';
    }

    if (!this.editForm.status) {
      this.editFormErrors['status'] = 'Status is required.';
    }

    const requiresReason = this.editForm.status === 'blocked' || this.editForm.status === 'deleted';
    if (requiresReason && !this.editForm.status_reason.trim()) {
      this.editFormErrors['status_reason'] = 'Reason is required for blocked/deleted status.';
    }

    return Object.keys(this.editFormErrors).length === 0;
  }

  saveEdit(): void {
    if (!this.editTargetId) {
      return;
    }

    if (!this.validateEditForm()) {
      this.notification.show('Please fix the highlighted fields.', 'fail', 3500);
      return;
    }

    this.saving = true;
    this.api.put<any>(`admin/platform-users/${this.editTargetId}`, {
      role: this.editForm.role,
      status: this.editForm.status,
      status_reason: this.editForm.status_reason?.trim() || null
    }, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.showEditModal = false;
        this.editTargetId = '';
        this.notification.show('Admin user updated successfully', 'success', 3500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.notification.show(err?.error?.detail || 'Failed to update admin user', 'fail', 5000);
      }
    });
  }

  softDelete(row: PlatformAdminUser): void {
    if (!row?.id) {
      return;
    }

    const reason = window.prompt('Please provide a reason for deleting this platform user:')?.trim() || '';
    if (!reason) {
      this.notification.show('Delete reason is required.', 'fail', 3500);
      return;
    }

    this.saving = true;
    this.api.post<any>(`admin/platform-users/${row.id}/delete`, { reason }, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.notification.show('User deleted successfully.', 'success', 3500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.notification.show(err?.error?.detail || 'Failed to delete user', 'fail', 5000);
      }
    });
  }

  restoreUser(row: PlatformAdminUser): void {
    if (!row?.id) {
      return;
    }

    this.saving = true;
    this.api.post<any>(`admin/platform-users/${row.id}/restore`, {}, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.notification.show('User restored successfully.', 'success', 3500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.notification.show(err?.error?.detail || 'Failed to restore user', 'fail', 5000);
      }
    });
  }

  permanentlyDeleteUser(row: PlatformAdminUser): void {
    if (!row?.id) {
      return;
    }

    const confirmed = window.confirm('This will permanently delete the user and cannot be undone. Continue?');
    if (!confirmed) {
      return;
    }

    this.saving = true;
    this.api.delete<any>(`admin/platform-users/${row.id}/permanent`, { loadingScope: this.saveScope }).subscribe({
      next: () => {
        this.saving = false;
        this.notification.show('User permanently deleted.', 'success', 3500);
        this.loadUsers();
      },
      error: (err) => {
        this.saving = false;
        this.notification.show(this.extractApiErrorMessage(err, 'Failed to permanently delete user'), 'fail', 5000);
      }
    });
  }

  isInviteExpired(user: PlatformAdminUser): boolean {
    if (!user?.invite_pending || !user?.invite_expires_at) {
      return false;
    }

    const expiryDate = new Date(user.invite_expires_at);
    if (Number.isNaN(expiryDate.getTime())) {
      return false;
    }

    return expiryDate.getTime() <= Date.now();
  }

  getInviteBadgeLabel(user: PlatformAdminUser): string {
    if (!user?.invite_pending) {
      return 'accepted';
    }

    return this.isInviteExpired(user) ? 'expired' : 'pending';
  }

  getInviteBadgeColor(user: PlatformAdminUser): 'secondary' | 'warning' | 'danger' {
    if (!user?.invite_pending) {
      return 'secondary';
    }

    return this.isInviteExpired(user) ? 'danger' : 'warning';
  }

  getInviteExpiryLabel(user: PlatformAdminUser): string {
    if (!user?.invite_pending || !user?.invite_expires_at) {
      return 'No active invite';
    }

    const expiryDate = new Date(user.invite_expires_at);
    if (Number.isNaN(expiryDate.getTime())) {
      return 'No expiry date';
    }

    const formatted = new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(expiryDate);

    return `${this.isInviteExpired(user) ? 'Expired' : 'Expires'} ${formatted}`;
  }
}
