import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

import { ButtonComponent } from '../button/button.component';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { ShiftInstanceItem } from '../../shared/model/request/client-request.model';

interface ShiftCalendarDay {
  isoDate: string;
  dateNumber: number;
  inCurrentMonth: boolean;
  isToday: boolean;
  isFilteredDate: boolean;
  shifts: ShiftInstanceItem[];
}

@Component({
  selector: 'app-shift-calendar',
  standalone: true,
  imports: [CommonModule, ButtonComponent],
  templateUrl: './shift-calendar.component.html',
})
export class ShiftCalendarComponent {
  @Input() monthAnchor: Date = new Date();
  @Input() shifts: ShiftInstanceItem[] = [];
  @Input() loading = false;
  @Input() filteredIsoDate = '';
  @Input() requestSummaries: Record<string, { title: string; siteName: string }> = {};
  @Input() openShiftHandler: ((shift: ShiftInstanceItem) => void) | null = null;

  @Output() previousMonth = new EventEmitter<void>();
  @Output() nextMonth = new EventEmitter<void>();
  @Output() currentMonth = new EventEmitter<void>();
  @Output() selectDate = new EventEmitter<string>();

  formatBackendDateTime = formatBackendDateTime;

  get monthLabel(): string {
    return new Intl.DateTimeFormat('en-CA', {
      month: 'long',
      year: 'numeric',
    }).format(this.monthAnchor);
  }

  get weekdayLabels(): string[] {
    return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  }

  get weeks(): ShiftCalendarDay[][] {
    const monthStart = this.getStartOfMonth(this.monthAnchor);
    const gridStart = new Date(monthStart);
    const weekday = gridStart.getDay();
    const offset = weekday === 0 ? 6 : weekday - 1;
    gridStart.setDate(gridStart.getDate() - offset);

    const todayIso = this.formatDateInput(new Date());
    const shiftsByDate = this.shifts.reduce<Record<string, ShiftInstanceItem[]>>((accumulator, shift) => {
      const key = String(shift.shift_date_local || '').trim();
      if (!key) {
        return accumulator;
      }
      if (!accumulator[key]) {
        accumulator[key] = [];
      }
      accumulator[key].push(shift);
      accumulator[key].sort((left, right) => String(left.shift_start_at_utc || '').localeCompare(String(right.shift_start_at_utc || '')));
      return accumulator;
    }, {});

    const weeks: ShiftCalendarDay[][] = [];
    for (let weekIndex = 0; weekIndex < 6; weekIndex += 1) {
      const week: ShiftCalendarDay[] = [];
      for (let dayIndex = 0; dayIndex < 7; dayIndex += 1) {
        const currentDate = new Date(gridStart);
        currentDate.setDate(gridStart.getDate() + (weekIndex * 7) + dayIndex);
        const isoDate = this.formatDateInput(currentDate);
        week.push({
          isoDate,
          dateNumber: currentDate.getDate(),
          inCurrentMonth: currentDate.getMonth() === this.monthAnchor.getMonth(),
          isToday: isoDate === todayIso,
          isFilteredDate: isoDate === this.filteredIsoDate,
          shifts: shiftsByDate[isoDate] || [],
        });
      }
      weeks.push(week);
    }

    return weeks;
  }

  getDayClasses(day: ShiftCalendarDay): string {
    if (!day.inCurrentMonth) {
      return 'border-gray-100 bg-gray-50/60 text-gray-400 dark:border-gray-800 dark:bg-gray-900/30 dark:text-gray-600';
    }
    if (day.isFilteredDate) {
      return 'border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-100';
    }
    if (day.isToday) {
      return 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100';
    }
    if (day.shifts.length) {
      return 'border-gray-200 bg-white text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100';
    }
    return 'border-gray-100 bg-white text-gray-900 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-100';
  }

  getCountLabel(day: ShiftCalendarDay): string {
    if (!day.shifts.length) {
      return 'No shifts';
    }
    if (day.shifts.length === 1) {
      return '1 shift';
    }
    return `${day.shifts.length} shifts`;
  }

  getShiftTitle(shift: ShiftInstanceItem): string {
    return this.requestSummaries[shift.request_id]?.title || `Request ${shift.request_id.slice(0, 8)}`;
  }

  formatShiftStart(shift: ShiftInstanceItem): string {
    return formatBackendDateTime(shift.shift_start_at_utc, 'en-CA', {
      timeZone: shift.timezone || undefined,
    });
  }

  getDayPrimaryActionLabel(day: ShiftCalendarDay): string {
    if (day.shifts.length > 1) {
      return `View all ${day.shifts.length} shifts`;
    }
    return 'Filter list to this day';
  }

  runDayPrimaryAction(day: ShiftCalendarDay): void {
    this.selectDate.emit(day.isoDate);
  }

  openDayCell(event: Event, day: ShiftCalendarDay): void {
    if (day.shifts.length === 1) {
      event.stopPropagation();
      this.requestShiftDetails(day.shifts[0]);
    }
  }

  requestShiftDetails(shift: ShiftInstanceItem): void {
    this.openShiftHandler?.(shift);
  }

  trackByShiftId(_index: number, item: ShiftInstanceItem): string {
    return item.id;
  }

  private getStartOfMonth(value: Date): Date {
    return new Date(value.getFullYear(), value.getMonth(), 1);
  }

  private formatDateInput(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

}
