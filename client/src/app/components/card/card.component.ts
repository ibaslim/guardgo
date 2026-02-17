import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './card.component.html'
})
export class CardComponent {
  @Input() title = '';
  @Input() showHeader = true;
  @Input() containerClass = 'bg-white dark:bg-gray-800 rounded shadow p-4 border border-gray-200 dark:border-gray-700';
  @Input() headerClass = 'flex items-start justify-between gap-4';
  @Input() titleClass = 'font-semibold text-gray-900 dark:text-gray-100';
  @Input() bodyClass = '';
}
