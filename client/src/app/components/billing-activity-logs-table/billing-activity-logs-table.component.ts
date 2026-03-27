import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { formatBackendDateTime, readableTitle } from '../../shared/helpers/format.helper';
import { ButtonComponent } from '../button/button.component';
import { IconComponent } from '../icon/icon.component';
import { TableComponent } from '../table/table.component';
import { TableTdComponent } from '../table/table-td.component';
import { TableThComponent } from '../table/table-th.component';

@Component({
  selector: 'app-billing-log-list-table',
  standalone: true,
  imports: [
    CommonModule,
    TableComponent,
    TableThComponent,
    TableTdComponent,
    ButtonComponent,
    IconComponent,
  ],
  templateUrl: './billing-activity-logs-table.component.html',
})
export class BillingActivityLogsTableComponent {
  @Input() logs: any[] = [];
  @Input() loading = false;
  @Input() page = 1;
  @Input() totalPages = 1;
  @Input() totalItems = 0;
  @Input() emptyMessage = 'No activity logs found for this billing context.';

  @Output() previous = new EventEmitter<void>();
  @Output() next = new EventEmitter<void>();

  readableTitle = readableTitle;
  formatBackendDateTime = formatBackendDateTime;

  get canPrev(): boolean {
    return !this.loading && this.page > 1;
  }

  get canNext(): boolean {
    return !this.loading && this.page < this.totalPages;
  }

  onPrevious(): void {
    if (!this.canPrev) return;
    this.previous.emit();
  }

  onNext(): void {
    if (!this.canNext) return;
    this.next.emit();
  }

  getScopeLabel(log: any): string {
    return readableTitle(log?.metadata?.scope || '-');
  }

  getRegionLabel(log: any): string {
    return log?.metadata?.region_label || log?.metadata?.region_code || '-';
  }

  getRateSummary(log: any, key: 'previous_rates' | 'new_rates'): string {
    const rates = log?.metadata?.[key];
    if (!rates) return '-';

    const standardRate = this.formatCurrency(rates.standard_rate);
    const weekendRate = this.formatCurrency(rates.weekend_rate);
    const holidayRate = this.formatCurrency(rates.holiday_rate);

    return `Std ${standardRate} | Wkd ${weekendRate} | Hol ${holidayRate}`;
  }

  private formatCurrency(value: unknown): string {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return '-';
    return `$${numericValue.toFixed(2)}`;
  }
}