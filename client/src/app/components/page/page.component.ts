import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './page.component.html',
  styleUrls: ['./page.component.scss']
})
export class PageComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() containerClass = 'w-full px-4 py-8 sm:px-6 lg:px-8';
  @Input() contentClass = 'max-w-4xl mx-auto space-y-6';
  @Input() headerClass = 'flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2';
  @Input() titleClass = 'text-2xl sm:text-xl font-bold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'text-sm sm:text-xs text-gray-500 dark:text-gray-400';
}
