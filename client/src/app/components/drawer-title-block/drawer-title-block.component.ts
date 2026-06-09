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
  @Input() containerClass = 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between';
  @Input() contentClass = 'min-w-0 flex-1';
  @Input() titleClass = 'text-xl font-semibold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400 sm:text-xs sm:leading-5';
  @Input() actionsClass = 'shrink-0 self-start sm:self-auto';
}
