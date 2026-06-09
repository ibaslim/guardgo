import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-list-toolbar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './list-toolbar.component.html',
  host: {
    class: 'block',
  },
})
export class ListToolbarComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() showControls = true;
  @Input() showFooter = false;
  @Input() containerClass = 'border-b border-gray-100 px-6 py-6 dark:border-gray-800';
  @Input() layoutClass = 'flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between';
  @Input() contentClass = 'min-w-0';
  @Input() titleClass = 'text-xl font-semibold text-gray-900 dark:text-gray-100';
  @Input() subtitleClass = 'mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400';
  @Input() controlsClass = 'grid grid-cols-1 gap-3 rounded-md bg-gray-50/70 p-3 sm:grid-cols-2 xl:items-end dark:bg-gray-800/50';
  @Input() footerClass = 'mt-4';
}
