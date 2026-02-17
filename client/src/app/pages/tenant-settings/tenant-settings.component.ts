import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { PageComponent } from '../../components/page/page.component';
import { GuardSettingComponent } from '../guard-setting/guard-setting.component';
import { ClientSettingComponent } from '../client-setting/client-setting.component';
import { ServiceProviderSettingComponent } from '../service-provider-setting/service-provider-setting.component';
import { ApiService } from '../../shared/services/api.service';
import { LoaderComponent } from '../../components/loader/loader.component';
import { AlertComponent } from '../../components/alert/alert.component';

@Component({
  selector: 'app-tenant-settings',
  standalone: true,
  imports: [
    CommonModule,
    PageComponent,
    GuardSettingComponent,
    ClientSettingComponent,
    ServiceProviderSettingComponent,
    LoaderComponent,
    AlertComponent
  ],
  templateUrl: './tenant-settings.component.html'
})
export class TenantSettingsComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();

  tenantType: 'guard' | 'client' | 'service_provider' | 'admin' | null = null;
  tenantData: any = null;
  isLoading = true;
  errorMessage: string | null = null;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.fetchTenantData();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  fetchTenantData(): void {
    this.isLoading = true;
    this.errorMessage = null;

    this.apiService.get<any>('tenant')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.tenantType = response.tenant_type;
          this.tenantData = response.profile || {};
          this.isLoading = false;
        },
        error: (error) => {
          console.error('Error fetching tenant data:', error);
          this.errorMessage = error?.error?.detail || 'Failed to load tenant settings. Please try again.';
          this.isLoading = false;
        }
      });
  }
}
