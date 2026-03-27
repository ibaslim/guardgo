import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpParams } from '@angular/common/http';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { ButtonComponent } from '../../components/button/button.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { LoaderComponent } from '../../components/loader/loader.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { BillingActivityLogsTableComponent } from '../../components/billing-activity-logs-table/billing-activity-logs-table.component';
import { ApiService } from '../../shared/services/api.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';

interface ProvinceRate {
  region_code: string;
  region_label: string;
  standard_rate: number;
  weekend_rate: number;
  holiday_rate: number;
}

interface BillingActivityContext {
  title: string;
  subtitle: string;
  entityId: string;
  emptyMessage: string;
}

@Component({
  selector: 'app-billing-configurations',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PageComponent,
    SectionComponent,
    ButtonComponent,
    SelectInputComponent,
    BaseInputComponent,
    LoaderComponent,
    SideDrawerComponent,
    BillingActivityLogsTableComponent,
  ],
  templateUrl: './billing-configurations.component.html',
})
export class BillingConfigurationsComponent implements OnInit {
  private readonly activityRows = 20;

  activeBillingTab: 'guards' | 'providers' = 'guards';

  // -- Guard rates --
  guardRates: ProvinceRate[] = [];
  guardLoading = false;
  guardSaving = false;

  // -- Provider default rates --
  providerDefaultRates: ProvinceRate[] = [];
  providerDefaultLoading = false;
  providerDefaultSaving = false;

  // -- Providers --
  providers: { label: string; value: string }[] = [];
  providersLoading = false;
  selectedProviderId = '';

  // -- Provider rates --
  providerRates: ProvinceRate[] = [];
  providerRatesLoading = false;
  providerSaving = false;
  providerSyncing = false;

  // -- Guards --
  guards: { label: string; value: string }[] = [];
  guardsLoading = false;
  selectedGuardId = '';

  // -- Guard override rates --
  guardOverrideRates: ProvinceRate[] = [];
  guardOverrideLoading = false;
  guardOverrideSaving = false;
  guardOverrideSyncing = false;

  showActivityDrawer = false;
  activityLogs: any[] = [];
  activityLoading = false;
  activityPage = 1;
  activityTotalPages = 1;
  activityTotalItems = 0;
  activityContext: BillingActivityContext | null = null;

  constructor(
    private api: ApiService,
    private notification: MessageNotificationService,
  ) {}

  ngOnInit(): void {
    this.loadGuardRates();
    this.loadProviderDefaultRates();
    this.loadProviders();
    this.loadGuards();
  }

  // ----------------------------------------------------------------
  // Guard rates
  // ----------------------------------------------------------------

  loadGuardRates(): void {
    this.guardLoading = true;
    this.api.get<ProvinceRate[]>('billing/guards').subscribe({
      next: (data) => {
        this.guardRates = data;
        this.guardLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load guard pay rates', 'fail');
        this.guardLoading = false;
      },
    });
  }

  onRateInput(rate: ProvinceRate, field: keyof Pick<ProvinceRate, 'standard_rate' | 'weekend_rate' | 'holiday_rate'>, value: any): void {
    const parsed = parseFloat(String(value));
    rate[field] = isNaN(parsed) ? 0 : Math.round(parsed * 100) / 100;
  }

  saveGuardRates(): void {
    this.guardSaving = true;
    this.api.put<any>('billing/guards', this.guardRates).subscribe({
      next: () => {
        this.notification.show('Guard pay rates saved', 'success');
        this.guardSaving = false;
      },
      error: () => {
        this.notification.show('Failed to save guard pay rates', 'fail');
        this.guardSaving = false;
      },
    });
  }

  // ----------------------------------------------------------------
  // Provider default rates
  // ----------------------------------------------------------------

  loadProviderDefaultRates(): void {
    this.providerDefaultLoading = true;
    this.api.get<ProvinceRate[]>('billing/providers/defaults').subscribe({
      next: (data) => {
        this.providerDefaultRates = data;
        this.providerDefaultLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load provider default pay rates', 'fail');
        this.providerDefaultLoading = false;
      },
    });
  }

  saveProviderDefaultRates(): void {
    this.providerDefaultSaving = true;
    this.api.put<any>('billing/providers/defaults', this.providerDefaultRates).subscribe({
      next: () => {
        this.notification.show('Provider default pay rates saved', 'success');
        this.providerDefaultSaving = false;
      },
      error: () => {
        this.notification.show('Failed to save provider default pay rates', 'fail');
        this.providerDefaultSaving = false;
      },
    });
  }

  // ----------------------------------------------------------------
  // Provider list
  // ----------------------------------------------------------------

  loadProviders(): void {
    this.providersLoading = true;
    this.api.get<{ id: string; name: string }[]>('billing/providers/list').subscribe({
      next: (data) => {
        this.providers = data.map((p) => ({ label: p.name, value: p.id }));
        this.providersLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load service providers', 'fail');
        this.providersLoading = false;
      },
    });
  }

  onProviderChange(providerId: any): void {
    this.selectedProviderId = providerId || '';
    if (!this.selectedProviderId) {
      this.providerRates = [];
      return;
    }
    this.loadProviderRates(this.selectedProviderId);
  }

  loadGuards(): void {
    this.guardsLoading = true;
    this.api.get<{ id: string; name: string }[]>('billing/guards/list').subscribe({
      next: (data) => {
        this.guards = data.map((g) => ({ label: g.name, value: g.id }));
        this.guardsLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load guards', 'fail');
        this.guardsLoading = false;
      },
    });
  }

  onGuardChange(guardId: any): void {
    this.selectedGuardId = guardId || '';
    if (!this.selectedGuardId) {
      this.guardOverrideRates = [];
      return;
    }
    this.loadGuardOverrideRates(this.selectedGuardId);
  }

  // ----------------------------------------------------------------
  // Provider rates
  // ----------------------------------------------------------------

  loadProviderRates(providerId: string): void {
    this.providerRatesLoading = true;
    this.api.get<ProvinceRate[]>(`billing/providers/${providerId}`).subscribe({
      next: (data) => {
        this.providerRates = data;
        this.providerRatesLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load provider pay rates', 'fail');
        this.providerRatesLoading = false;
      },
    });
  }

  saveProviderRates(): void {
    if (!this.selectedProviderId) return;
    this.providerSaving = true;
    this.api.put<any>(`billing/providers/${this.selectedProviderId}`, this.providerRates).subscribe({
      next: (res) => {
        const updatedCount = Number(res?.updated_count ?? 0);
        this.notification.show(updatedCount > 0 ? 'Provider pay rates saved' : 'No provider rate changes detected', updatedCount > 0 ? 'success' : 'fail');
        this.providerSaving = false;
        this.loadProviderRates(this.selectedProviderId);
      },
      error: () => {
        this.notification.show('Failed to save provider pay rates', 'fail');
        this.providerSaving = false;
      },
    });
  }

  syncProviderWithDefaults(): void {
    if (!this.selectedProviderId) return;
    this.providerSyncing = true;
    this.api.post<any>(`billing/providers/${this.selectedProviderId}/sync-defaults`, {}).subscribe({
      next: () => {
        this.notification.show('Provider rates synced from defaults', 'success');
        this.providerSyncing = false;
        this.loadProviderRates(this.selectedProviderId);
      },
      error: () => {
        this.notification.show('Failed to sync provider rates from defaults', 'fail');
        this.providerSyncing = false;
      },
    });
  }

  // ----------------------------------------------------------------
  // Guard override rates
  // ----------------------------------------------------------------

  loadGuardOverrideRates(guardId: string): void {
    this.guardOverrideLoading = true;
    this.api.get<ProvinceRate[]>(`billing/guards/${guardId}`).subscribe({
      next: (data) => {
        this.guardOverrideRates = data;
        this.guardOverrideLoading = false;
      },
      error: () => {
        this.notification.show('Failed to load guard pay rates', 'fail');
        this.guardOverrideLoading = false;
      },
    });
  }

  saveGuardOverrideRates(): void {
    if (!this.selectedGuardId) return;
    this.guardOverrideSaving = true;
    this.api.put<any>(`billing/guards/${this.selectedGuardId}`, this.guardOverrideRates).subscribe({
      next: (res) => {
        const updatedCount = Number(res?.updated_count ?? 0);
        this.notification.show(updatedCount > 0 ? 'Guard pay rates saved' : 'No guard rate changes detected', updatedCount > 0 ? 'success' : 'fail');
        this.guardOverrideSaving = false;
        this.loadGuardOverrideRates(this.selectedGuardId);
      },
      error: () => {
        this.notification.show('Failed to save guard pay rates', 'fail');
        this.guardOverrideSaving = false;
      },
    });
  }

  syncGuardWithDefaults(): void {
    if (!this.selectedGuardId) return;
    this.guardOverrideSyncing = true;
    this.api.post<any>(`billing/guards/${this.selectedGuardId}/sync-defaults`, {}).subscribe({
      next: () => {
        this.notification.show('Guard rates synced from defaults', 'success');
        this.guardOverrideSyncing = false;
        this.loadGuardOverrideRates(this.selectedGuardId);
      },
      error: () => {
        this.notification.show('Failed to sync guard rates from defaults', 'fail');
        this.guardOverrideSyncing = false;
      },
    });
  }

  openGuardDefaultLogs(): void {
    this.openBillingLogs({
      title: 'Guard Billing Activity Logs',
      subtitle: 'Default guard rate changes',
      entityId: 'guard-default-rates',
      emptyMessage: 'No activity logs found for guard default rates.',
    });
  }

  openGuardOverrideLogs(): void {
    if (!this.selectedGuardId) return;
    const selectedGuard = this.guards.find((guard) => guard.value === this.selectedGuardId);
    this.openBillingLogs({
      title: 'Guard Billing Activity Logs',
      subtitle: `Guard: ${selectedGuard?.label || this.selectedGuardId}`,
      entityId: this.selectedGuardId,
      emptyMessage: 'No activity logs found for this guard billing override.',
    });
  }

  openProviderDefaultLogs(): void {
    this.openBillingLogs({
      title: 'Provider Billing Activity Logs',
      subtitle: 'Default service provider rate changes',
      entityId: 'provider-default-rates',
      emptyMessage: 'No activity logs found for provider default rates.',
    });
  }

  openProviderOverrideLogs(): void {
    if (!this.selectedProviderId) return;
    const selectedProvider = this.providers.find((provider) => provider.value === this.selectedProviderId);
    this.openBillingLogs({
      title: 'Provider Billing Activity Logs',
      subtitle: `Service Provider: ${selectedProvider?.label || this.selectedProviderId}`,
      entityId: this.selectedProviderId,
      emptyMessage: 'No activity logs found for this service provider billing override.',
    });
  }

  closeActivityDrawer(): void {
    this.showActivityDrawer = false;
    this.activityContext = null;
    this.activityLogs = [];
    this.activityLoading = false;
    this.activityPage = 1;
    this.activityTotalPages = 1;
    this.activityTotalItems = 0;
  }

  nextActivityPage(): void {
    if (!this.activityContext || this.activityPage >= this.activityTotalPages) return;
    this.loadBillingActivityLogs(this.activityContext, this.activityPage + 1);
  }

  prevActivityPage(): void {
    if (!this.activityContext || this.activityPage <= 1) return;
    this.loadBillingActivityLogs(this.activityContext, this.activityPage - 1);
  }

  private openBillingLogs(context: BillingActivityContext): void {
    this.activityContext = context;
    this.showActivityDrawer = true;
    this.loadBillingActivityLogs(context, 1);
  }

  private loadBillingActivityLogs(context: BillingActivityContext, page: number): void {
    this.activityLoading = true;

    const params = new HttpParams()
      .set('module', 'billing')
      .set('entity_type', 'billing_rate')
      .set('entity_id', context.entityId)
      .set('action', 'rate_changed')
      .set('page', String(page))
      .set('rows', String(this.activityRows));

    this.api.get<any>('activity', { params }).subscribe({
      next: (res) => {
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
        this.activityPage = 1;
        this.activityLoading = false;
        this.notification.show('Failed to load billing activity logs', 'fail');
      },
    });
  }
}
