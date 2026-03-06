import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { formatBackendDateTime, readableTitle } from '../../shared/helpers/format.helper';
import { ButtonComponent } from '../button/button.component';
import { IconComponent } from '../icon/icon.component';
import { TableComponent } from '../table/table.component';
import { TableTdComponent } from '../table/table-td.component';
import { TableThComponent } from '../table/table-th.component';

@Component({
  selector: 'app-log-list-table',
  standalone: true,
  imports: [
    CommonModule,
    TableComponent,
    TableThComponent,
    TableTdComponent,
    ButtonComponent,
    IconComponent,
  ],
  templateUrl: './activity-logs-table.component.html'
})
export class LogListTableComponent {
  @Input() logs: any[] = [];
  @Input() loading = false;
  @Input() page = 1;
  @Input() totalPages = 1;
  @Input() totalItems = 0;

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
}
