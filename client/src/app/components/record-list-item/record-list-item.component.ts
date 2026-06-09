import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-record-list-item',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './record-list-item.component.html',
})
export class RecordListItemComponent {
  @Input() containerClass = 'px-6 py-6';
  @Input() layoutClass = 'flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between';
  @Input() contentClass = 'min-w-0 flex-1';
  @Input() badgesClass = 'mb-3 flex flex-wrap items-center gap-2 empty:hidden';
  @Input() metaClass = 'mt-2 flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-gray-300 empty:hidden';
  @Input() bodyClass = 'mt-3 empty:hidden';
  @Input() actionsClass = 'flex shrink-0 flex-wrap gap-2 pt-1 xl:pl-6 empty:hidden';
  @Input() extraClass = 'mt-5 empty:hidden';
}
