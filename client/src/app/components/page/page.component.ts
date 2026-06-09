import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './page.component.html'
})
export class PageComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() containerClass = 'w-full px-4 py-8 sm:px-6 lg:px-8';
  @Input() contentClass = 'max-w-4xl mx-auto space-y-6';
  @Input() headerClass = 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between';
  @Input() titleClass = 'text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'text-sm leading-6 text-gray-500 dark:text-gray-400';
}
