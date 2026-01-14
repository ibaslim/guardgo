// ...existing code...
  // ...existing code...
import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BadgeComponent } from '../badge/badge.component';
import { AvatarComponent } from '../avatar/avatar.component';

@Component({
  selector: 'app-table',
  standalone: true,
  imports: [CommonModule, FormsModule, BadgeComponent, AvatarComponent],
  templateUrl: './table.component.html',
  styleUrls: ['./table.component.scss']
})
export class TableComponent {
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

  // Filtering, sorting, pagination state
  filter = '';
  sortColumn: string | null = null;
  sortDirection: 'asc' | 'desc' = 'asc';
  page = 1;

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
    const start = (this.page - 1) * this.pageSize;
    return this.filteredData.slice(start, start + this.pageSize);
  }

  get totalPages() {
    return Math.ceil(this.filteredData.length / this.pageSize) || 1;
  }

  setSort(col: string) {
    if (this.sortColumn === col) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = col;
      this.sortDirection = 'asc';
    }
  }

  setPage(page: number) {
    if (page >= 1 && page <= this.totalPages) {
      this.page = page;
    }
  }
}
