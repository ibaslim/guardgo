import { Component, EventEmitter, OnInit, OnDestroy, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { PageComponent } from '../../components/page/page.component';
import { GuardSettingComponent } from '../guard-setting/guard-setting.component';
import { ClientSettingComponent } from '../client-setting/client-setting.component';
import { ServiceProviderSettingComponent } from '../service-provider-setting/service-provider-setting.component';
import { ApiService } from '../../shared/services/api.service';
import { readableTitle } from '../../shared/helpers/format.helper';
import { AlertComponent } from '../../components/alert/alert.component';
import { LoadingShellComponent } from '../../components/loading-shell/loading-shell.component';

@Component({
  selector: 'app-tenant-settings',
  standalone: true,
  imports: [
    CommonModule,
    PageComponent,
    GuardSettingComponent,
    ClientSettingComponent,
    ServiceProviderSettingComponent,
    AlertComponent,
    LoadingShellComponent
  ],
  templateUrl: './tenant-settings.component.html'
})
export class TenantSettingsComponent implements OnInit, OnDestroy {
  readonly tenantLoadingScope = 'tenant-settings';
  @Input() showPageWrapper: boolean = true;
  @Input() tenantDataInput: any = null;
  @Input() readonly: boolean = false;
  @Input() allowProviderOperationalCoverageEdit: boolean = false;
  @Output() managedOperationalCoverageUpdated = new EventEmitter<void>();
  private destroy$ = new Subject<void>();

  tenantType: 'guard' | 'client' | 'service_provider' | 'admin' | null = null;
  tenantData: any = null;
  isLoading = true;
  errorMessage: string | null = null;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    if (this.tenantDataInput) {
      this.tenantData = this.tenantDataInput;
      this.isLoading = false;
      this.tenantType = this.tenantData?.tenant_type || this.tenantType;
    } else {
      this.fetchTenantData();
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['tenantDataInput'] && !changes['tenantDataInput'].isFirstChange()) {
      this.tenantData = this.tenantDataInput;
      this.tenantType = this.tenantData?.tenant_type || this.tenantType;
      this.isLoading = false;
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  // Return a readable title for readonly profile view: "{Tenant Type} Profile"
  getReadonlyProfileTitle(): string {
    const t = this.tenantData?.tenant_type || this.tenantData?.type || this.tenantType || '';
    const human = readableTitle(t);
    return human ? `${human} Profile` : 'Profile';
  }

  fetchTenantData(): void {
    this.isLoading = true;
    this.errorMessage = null;

    this.apiService.get<any>('tenant', { loadingScope: this.tenantLoadingScope })
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
