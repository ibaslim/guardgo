import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-section',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './section.component.html',
  styleUrls: ['./section.component.scss']
})
export class SectionComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() containerClass = 'rounded-xl border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/60 shadow-sm p-6 space-y-6';
  @Input() headerClass = 'flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-0';
  @Input() titleClass = 'text-lg font-semibold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'text-sm sm:text-xs text-gray-500 dark:text-gray-400 mt-1 sm:mt-0';
}
