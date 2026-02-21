// ...existing code...
  // ...existing code...
import { Component, Input, TemplateRef, Output, EventEmitter, HostListener } from '@angular/core';
export interface ColumnDef {
  key?: string;
  label?: string;
  sortable?: boolean;
  width?: string;
  cellTemplate?: TemplateRef<any> | null;
}
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BadgeComponent } from '../badge/badge.component';
import { AvatarComponent } from '../avatar/avatar.component';
import { TableThComponent } from './table-th.component';
import { TableTdComponent } from './table-td.component';
import { SelectInputComponent } from '../form/select-input/select-input.component';

@Component({
  selector: 'app-table',
  standalone: true,
  imports: [CommonModule, FormsModule, TableThComponent, TableTdComponent, SelectInputComponent],
  templateUrl: './table.component.html'
})
export class TableComponent {
  @Input() columns: ColumnDef[] = [];
  @Input() selectable: 'none' | 'single' | 'multiple' = 'none';
  @Output() selectionChange = new EventEmitter<any[]>();
  @Input() rowActions?: TemplateRef<any> | null = null;

  // internal selection state
  selectedRows: any[] = [];

  toggleRowSelection(row: any, multi = false) {
    if (this.selectable === 'none') return;
    const idx = this.selectedRows.indexOf(row);
    if (idx === -1) {
      if (!multi && this.selectable === 'single') {
        this.selectedRows = [row];
      } else {
        this.selectedRows = [...this.selectedRows, row];
      }
    } else {
      this.selectedRows = this.selectedRows.filter(r => r !== row);
    }
    this.selectionChange.emit(this.selectedRows);
  }

  isRowSelected(row: any) {
    return this.selectedRows.indexOf(row) !== -1;
  }

  // called from template when the header select-all checkbox changes
  onSelectAllChange(event: Event) {
    const input = event.target as HTMLInputElement;
    const checked = !!(input && input.checked);
    this.selectedRows = checked ? [...this.pagedData] : [];
    this.selectionChange.emit(this.selectedRows);
  }

  // called when a row checkbox changes
  onRowCheckboxChange(event: Event, row: any) {
    // prevent row click bubbling
    event.stopPropagation?.();
    // ignore modifier keys for now, treat as toggle
    this.toggleRowSelection(row, this.selectable === 'multiple');
  }

  // keyboard interaction for a row
  onRowKeydown(event: KeyboardEvent, row: any) {
    if (event.key === 'Enter') {
      this.handleRowClick(row);
    } else if (event.key === ' ' || event.key === 'Spacebar') {
      event.preventDefault();
      this.toggleRowSelection(row, this.selectable === 'multiple');
    }
  }

  getBadgeColor(value: string): 'primary' | 'secondary' | 'success' | 'danger' {
    const allowed = ['primary', 'secondary', 'success', 'danger'] as const;
    return (allowed.includes(value as any) ? value : 'secondary') as 'primary' | 'secondary' | 'success' | 'danger';
  }
  @Input() data: any[] = [];
  @Input() loading = false;
  @Input() emptyText = 'No data available.';
  @Input() pageSize = 5;
  @Input() showFilter = false;
  @Input() showPagination = false;
  @Input() showSort = false;
  @Input() badgeColumn: string | null = null;
  @Input() badgeMap: { [key: string]: string } = {};
  @Input() rowTemplate?: TemplateRef<any> | null = null;
  @Input() headerTemplate?: TemplateRef<any> | null = null;
  @Input() columnCount: number = 5;
  @Output() rowClick = new EventEmitter<any>();
  @Output() search = new EventEmitter<string>();
  @Output() sortChange = new EventEmitter<{ sort_by: string; sort_order: 'asc' | 'desc' }>();
  @Output() pageSizeChange = new EventEmitter<number>();
  @Input() serverSide = false;
  @Input() externalPage?: number | null = null;
  @Input() externalTotalPages?: number | null = null;
  @Input() showPageSizeSelector: boolean = true;
  @Output() pageChange = new EventEmitter<number>();

  // Filtering, sorting, pagination state
  filter = '';
  sortColumn: string | null = null;
  sortDirection: 'asc' | 'desc' = 'asc';
  private currentPage = 1;

  get filteredData() {
    let filtered = this.data;
    if (this.filter) {
      filtered = filtered.filter(row =>
        Object.values(row).some(val =>
          String(val).toLowerCase().includes(this.filter.toLowerCase())
        )
      );
    }
    if (this.sortColumn) {
      filtered = [...filtered].sort((a, b) => {
        const aVal = a[this.sortColumn!];
        const bVal = b[this.sortColumn!];
        if (aVal === bVal) return 0;
        if (this.sortDirection === 'asc') {
          return aVal > bVal ? 1 : -1;
        } else {
          return aVal < bVal ? 1 : -1;
        }
      });
    }
    return filtered;
  }

  get pagedData() {
    if (this.serverSide) {
      // assume parent provides already-paged `data`
      return this.data;
    }
    const start = (this.page - 1) * this.pageSize;
    return this.filteredData.slice(start, start + this.pageSize);
  }
  get totalPages() {
    if (this.serverSide) return this.externalTotalPages || 1;
    return Math.ceil(this.filteredData.length / this.pageSize) || 1;
  }

  get page() {
    return this.serverSide ? (this.externalPage || 1) : this.currentPage;
  }

  setSort(col: string) {
    if (this.sortColumn === col) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = col;
      this.sortDirection = 'asc';
    }
    if (this.serverSide) {
      this.sortChange.emit({ sort_by: col, sort_order: this.sortDirection });
      // reset to first page when sorting server-side
      this.setPage(1);
    }
  }

  onFilterChange(value: string) {
    this.filter = value;
    if (this.serverSide) {
      this.search.emit(value);
      // reset to first page for server side search
      this.setPage(1);
    }
  }

  onPageSizeChange(value: number) {
    this.pageSize = Number(value);
    this.pageSizeChange.emit(this.pageSize);
    if (this.serverSide) {
      this.setPage(1);
    }
  }

  // expose context for header templates
  get headerContext() {
    return {
      setSort: (col: string) => this.setSort(col),
      sortColumn: this.sortColumn,
      sortDirection: this.sortDirection
    };
  }

  setPage(page: number) {
    if (page < 1) return;
    if (this.serverSide) {
      this.pageChange.emit(page);
      this.currentPage = page;
      return;
    }
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
    }
  }

  handleRowClick(row: any) {
    this.rowClick.emit(row);
  }
}
