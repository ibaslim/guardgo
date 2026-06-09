import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { ShiftAttendanceEventItem } from '../../shared/model/request/client-request.model';

@Component({
  selector: 'app-event-timeline',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './event-timeline.component.html',
})
export class EventTimelineComponent {
  @Input() title = 'Event Timeline';
  @Input() events: ShiftAttendanceEventItem[] | null | undefined = [];
  @Input() loading = false;
  @Input() emptyMessage = 'No events recorded yet.';
  @Input() showLocationDetails = false;

  readonly skeletonRows = [1, 2, 3];

  get visibleEvents(): ShiftAttendanceEventItem[] {
    return Array.isArray(this.events) ? this.events : [];
  }

  get countLabel(): string {
    const count = this.visibleEvents.length;
    return `${count} event${count === 1 ? '' : 's'}`;
  }

  formatTokenLabel(value: string): string {
    return String(value || '')
      .split('_')
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  formatTimestamp(value?: string | null): string {
    return value ? formatBackendDateTime(value) : 'Unknown time';
  }

  trackByEventId(_index: number, item: ShiftAttendanceEventItem): string {
    return item.id;
  }
}
