import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-drawer-title-block',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './drawer-title-block.component.html',
  host: {
    class: 'block',
  },
})
export class DrawerTitleBlockComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() containerClass = 'flex items-start justify-between gap-4';
  @Input() contentClass = 'min-w-0 flex-1';
  @Input() titleClass = 'text-xl font-semibold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'mt-1 text-xs text-gray-500 dark:text-gray-400';
  @Input() actionsClass = 'shrink-0';
}
