import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-summary-metric-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './summary-metric-card.component.html',
})
export class SummaryMetricCardComponent {
  @Input() label = '';
  @Input() value: string | number | null | undefined = '';
  @Input() helperText = '';
  @Input() containerClass =
    'rounded-md border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-800/70';
  @Input() labelClass =
    'text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-gray-500';
  @Input() valueClass = 'mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100';
  @Input() helperClass = 'mt-1 text-xs text-gray-500 dark:text-gray-400';
}
