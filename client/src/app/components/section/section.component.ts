import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-section',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './section.component.html',
  host: {
    'class': 'block'
  }
})
export class SectionComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() containerClass = 'rounded-xl border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/60 shadow-sm p-4 sm:p-6 space-y-6';
  @Input() headerClass = 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between';
  @Input() titleClass = 'text-lg font-semibold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400';
}
