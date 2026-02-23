import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'th[app-table-th]',
  standalone: true,
  imports: [CommonModule],
  host: {
    '[class]': "baseClasses + (extraClass ? ' ' + extraClass : '')"
  },
  template: `
    <ng-content></ng-content>
  `
})
export class TableThComponent {
  @Input() extraClass = '';
  baseClasses = 'px-4 py-2 text-left text-xs font-bold text-gray-700 dark:text-gray-200 uppercase tracking-wider cursor-pointer select-none group sticky top-0 bg-gray-50 dark:bg-gray-800 z-20';
}
