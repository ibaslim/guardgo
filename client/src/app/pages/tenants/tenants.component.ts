import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TableComponent } from '../../components/table/table.component';
import type { ColumnDef } from '../../components/table/table.component';
import { BadgeComponent } from '../../components/badge/badge.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { IconComponent } from '../../components/icon/icon.component';
import { ButtonComponent } from '../../components/button/button.component';
import { TableThComponent } from '../../components/table/table-th.component';
import { TableTdComponent } from '../../components/table/table-td.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { ApiService } from '../../shared/services/api.service';
import { HttpParams } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-tenants',
  standalone: true,
  imports: [CommonModule, FormsModule, TableComponent, BadgeComponent, SideDrawerComponent, IconComponent, TableThComponent, TableTdComponent, ButtonComponent, SelectInputComponent],
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
    { label: 'Active', value: 'active' },
    { label: 'Inactive', value: 'inactive' },
    { label: 'Banned', value: 'banned' }
  ];

  showDrawer = false;
  tenantDetail: any = null;
  selectedRows: any[] = [];

  onSelectionChange(selected: any[]) {
    this.selectedRows = selected || [];
  }

  constructor(private api: ApiService, private router: Router, private route: ActivatedRoute) {}

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

  onCloseDrawer() {
    this.showDrawer = false;
    // clear route id
    this.router.navigate(['/dashboard/tenants']);
  }
}
