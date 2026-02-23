import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'td[app-table-td]',
  standalone: true,
  imports: [CommonModule],
  host: {
    '[class]': "baseClasses + (extraClass ? ' ' + extraClass : '')"
  },
  template: `
    <ng-content></ng-content>
  `
})
export class TableTdComponent {
  @Input() extraClass = '';
  baseClasses = 'px-4 py-2 text-sm text-gray-900 dark:text-gray-100';
}
