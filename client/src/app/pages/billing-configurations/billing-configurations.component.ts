import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { ButtonComponent } from '../../components/button/button.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { LoaderComponent } from '../../components/loader/loader.component';
import { ApiService } from '../../shared/services/api.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';

interface ProvinceRate {
  region_code: string;
  region_label: string;
  standard_rate: number;
  weekend_rate: number;
  holiday_rate: number;
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
  ],
  templateUrl: './billing-configurations.component.html',
})
export class BillingConfigurationsComponent implements OnInit {
  // -- Guard rates --
  guardRates: ProvinceRate[] = [];
  guardLoading = false;
  guardSaving = false;

  // -- Providers --
  providers: { label: string; value: string }[] = [];
  providersLoading = false;
  selectedProviderId = '';

  // -- Provider rates --
  providerRates: ProvinceRate[] = [];
  providerRatesLoading = false;
  providerSaving = false;

  constructor(
    private api: ApiService,
    private notification: MessageNotificationService,
  ) {}

  ngOnInit(): void {
    this.loadGuardRates();
    this.loadProviders();
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
      next: () => {
        this.notification.show('Provider pay rates saved', 'success');
        this.providerSaving = false;
      },
      error: () => {
        this.notification.show('Failed to save provider pay rates', 'fail');
        this.providerSaving = false;
      },
    });
  }
}
