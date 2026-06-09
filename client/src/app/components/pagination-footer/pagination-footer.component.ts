import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { ButtonComponent } from '../button/button.component';

@Component({
  selector: 'app-pagination-footer',
  standalone: true,
  imports: [CommonModule, ButtonComponent],
  templateUrl: './pagination-footer.component.html',
})
export class PaginationFooterComponent {
  @Input() page = 1;
  @Input() totalPages = 1;
  @Input() pages: number[] = [];
  @Input() previousLabel = 'Previous';
  @Input() nextLabel = 'Next';
  @Input() containerClass =
    'flex flex-col gap-3 border-t border-gray-100 px-6 py-6 sm:flex-row sm:items-center sm:justify-between dark:border-gray-800';
  @Input() summaryClass = 'text-sm text-gray-500 dark:text-gray-400';
  @Input() actionsClass = 'flex flex-wrap items-center gap-2 sm:justify-end';

  @Output() pageChange = new EventEmitter<number>();

  get showPagination(): boolean {
    return this.totalPages > 1;
  }

  getPageLabel(pageNumber: number): string {
    return String(pageNumber);
  }

  goTo(pageNumber: number): void {
    if (pageNumber < 1 || pageNumber > this.totalPages || pageNumber === this.page) {
      return;
    }
    this.pageChange.emit(pageNumber);
  }

  trackByPageNumber(_index: number, pageNumber: number): number {
    return pageNumber;
  }
}
