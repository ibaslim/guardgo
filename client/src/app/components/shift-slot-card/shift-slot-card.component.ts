import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

interface ShiftSlotCardBadge {
  label: string;
  className: string;
}

@Component({
  selector: 'app-shift-slot-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './shift-slot-card.component.html',
})
export class ShiftSlotCardComponent {
  @Input() statusLabel = '';
  @Input() statusClass = '';
  @Input() title = '';
  @Input() titleClass = 'text-sm font-semibold text-gray-900 dark:text-gray-100';
  @Input() badges: ShiftSlotCardBadge[] = [];
  @Input() metaItems: string[] = [];
  @Input() detailItems: string[] = [];
  @Input() selectable = false;
  @Input() selected = false;
  @Input() selectionName = 'shiftSlotSelection';
  @Input() containerClass = 'rounded-md border border-gray-100 px-4 py-3 dark:border-gray-700';
  @Input() selectableWrapperClass = 'flex cursor-pointer items-start gap-3';
  @Input() checkboxClass = 'mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500';

  @Output() selectedChange = new EventEmitter<boolean>();

  get visibleMetaItems(): string[] {
    return (this.metaItems || []).map((item) => String(item || '').trim()).filter(Boolean);
  }

  get visibleDetailItems(): string[] {
    return (this.detailItems || []).map((item) => String(item || '').trim()).filter(Boolean);
  }

  onSelectedChange(checked: boolean): void {
    this.selectedChange.emit(checked);
  }

  trackByBadge(_index: number, badge: ShiftSlotCardBadge): string {
    return `${badge.label}:${badge.className}`;
  }

  trackByText(_index: number, value: string): string {
    return value;
  }
}
