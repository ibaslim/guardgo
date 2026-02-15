import { CommonModule } from '@angular/common';
import { Component, forwardRef } from '@angular/core';
import { FormsModule, NG_VALUE_ACCESSOR, ControlValueAccessor } from '@angular/forms';
import { NgxMaterialTimepickerModule } from 'ngx-material-timepicker';

interface TimeRange {
  start: string;
  end: string;
}

interface DayAvailability {
  enabled: boolean;
  timeRanges: TimeRange[];
}

@Component({
  selector: 'app-weekly-availability',
  standalone: true,
  imports: [CommonModule, FormsModule, NgxMaterialTimepickerModule],
  templateUrl: './weekly-availability.component.html',
  styleUrl: './weekly-availability.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => WeeklyAvailabilityComponent),
      multi: true
    }
  ]
})
export class WeeklyAvailabilityComponent implements ControlValueAccessor {
  availability: { [day: string]: DayAvailability } = {};
  daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  // Validation errors
  validationErrors: { [day: string]: string[] } = {};
  globalError: string = '';

  private onChange: any = () => { };
  private onTouched: any = () => { };

  constructor() {
    // Initialize all days as disabled with empty ranges
    this.daysOfWeek.forEach(day => {
      this.availability[day] = { enabled: false, timeRanges: [] };
      this.validationErrors[day] = [];
    });
  }

  // ControlValueAccessor methods
  writeValue(value: any): void {
    if (value) this.availability = value;
  }

  registerOnChange(fn: any): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }

  // Toggle day enabled/disabled
  toggleDay(day: string, event: Event) {
    const checked = (event.target as HTMLInputElement).checked;
    this.availability[day].enabled = checked;

    if (checked && this.availability[day].timeRanges.length === 0) {
      // Add first mandatory time range
      this.availability[day].timeRanges.push({ start: '', end: '' });
    } else if (!checked) {
      // Clear time ranges when disabled
      this.availability[day].timeRanges = [];
    }

    this.validateAvailability();
    this.notifyChange();
  }

  // Add more time range for a day
  addTimeRange(day: string) {
    this.availability[day].timeRanges.push({ start: '', end: '' });
    this.notifyChange();
  }

  // Remove a time range
  removeTimeRange(day: string, index: number) {
    if (this.availability[day].timeRanges.length > 1) {
      this.availability[day].timeRanges.splice(index, 1);
      this.validateAvailability();
      this.notifyChange();
    }
  }

  // Called when time picker changes
  onTimeChange() {
    this.validateAvailability();
    this.notifyChange();
  }

  // Notify parent of changes
  private notifyChange() {
    this.onChange(this.availability);
    this.onTouched();
  }

  // Main validation method
  validateAvailability(): boolean {
    this.validationErrors = {};
    this.globalError = '';
    let isValid = true;

    // Check if at least one day is selected
    const hasAtLeastOneDay = this.daysOfWeek.some(day => this.availability[day].enabled);
    if (!hasAtLeastOneDay) {
      this.globalError = 'Please select at least one day of availability.';
      isValid = false;
    }

    // Validate each enabled day
    this.daysOfWeek.forEach(day => {
      this.validationErrors[day] = [];

      if (this.availability[day].enabled) {
        const ranges = this.availability[day].timeRanges;

        // Check if at least one time range exists
        if (ranges.length === 0) {
          this.validationErrors[day].push('At least one time range is required.');
          isValid = false;
          return;
        }

        // Track if any field has been touched (not empty)
        let hasAnyInput = false;

        // Validate each time range
        ranges.forEach((range, index) => {
          // Check if this range has any input
          if (range.start || range.end) {
            hasAnyInput = true;
          }

          // For the first time range (index 0), both start and end are REQUIRED
          if (index === 0) {
            // Only show error if user has started filling but not completed
            if (hasAnyInput && (!range.start || !range.end)) {
              if (!this.validationErrors[day].includes('Please fill in both start and end times for the first time range.')) {
                this.validationErrors[day].push('Please fill in both start and end times for the first time range.');
              }
              isValid = false;
              return;
            }
          } else {
            // For additional time ranges (index > 0), they are OPTIONAL
            // But if either start OR end is filled, BOTH must be filled
            if ((range.start && !range.end) || (!range.start && range.end)) {
              if (!this.validationErrors[day].includes('Please complete both start and end times for all additional ranges, or leave them empty.')) {
                this.validationErrors[day].push('Please complete both start and end times for all additional ranges, or leave them empty.');
              }
              isValid = false;
              return;
            }

            // If both are empty, skip further validation for this range (it's optional)
            if (!range.start && !range.end) {
              return;
            }
          }

          // Check if start time is before end time (only if both are filled)
          if (range.start && range.end && !this.isStartBeforeEnd(range.start, range.end)) {
            if (!this.validationErrors[day].includes('Start time must be before end time.')) {
              this.validationErrors[day].push('Start time must be before end time.');
            }
            isValid = false;
          }
        });

        // Check for overlapping time ranges (only check filled ranges)
        if (this.hasOverlap(day)) {
          this.validationErrors[day].push('Time ranges cannot overlap.');
          isValid = false;
        }

        // Check if total duration exceeds 24 hours
        if (this.exceedsTotalDuration(day)) {
          this.validationErrors[day].push('Total duration cannot exceed 24 hours.');
          isValid = false;
        }
      }
    });

    return isValid;
  }

  // Check if total duration of all time ranges exceeds 24 hours
  private exceedsTotalDuration(day: string): boolean {
    const ranges = this.availability[day].timeRanges.filter(r => r.start && r.end);

    let totalMinutes = 0;

    ranges.forEach(range => {
      const startMinutes = this.parseTime(range.start);
      const endMinutes = this.parseTime(range.end);

      if (startMinutes !== null && endMinutes !== null) {
        // Calculate duration for this range
        let duration = endMinutes - startMinutes;

        // Handle overnight shifts (e.g., 11:00 PM to 2:00 AM)
        if (duration < 0) {
          duration = (24 * 60) + duration;
        }

        totalMinutes += duration;
      }
    });

    // Check if total exceeds 24 hours (1440 minutes)
    return totalMinutes > (24 * 60);
  }

  // Check if time ranges overlap for a specific day
  hasOverlap(day: string): boolean {
    const ranges = this.availability[day].timeRanges.filter(r => r.start && r.end);

    for (let i = 0; i < ranges.length; i++) {
      for (let j = i + 1; j < ranges.length; j++) {
        if (this.doRangesOverlap(ranges[i], ranges[j])) {
          return true;
        }
      }
    }
    return false;
  }

  // Check if two time ranges overlap
  private doRangesOverlap(range1: TimeRange, range2: TimeRange): boolean {
    const start1 = this.parseTime(range1.start);
    const end1 = this.parseTime(range1.end);
    const start2 = this.parseTime(range2.start);
    const end2 = this.parseTime(range2.end);

    if (start1 === null || end1 === null || start2 === null || end2 === null) {
      return false;
    }

    return (start1 < end2 && end1 > start2);
  }

  // Check if start time is before end time
  private isStartBeforeEnd(start: string, end: string): boolean {
    const startMinutes = this.parseTime(start);
    const endMinutes = this.parseTime(end);

    if (startMinutes === null || endMinutes === null) {
      return true; // Don't show error if times aren't set yet
    }

    return startMinutes < endMinutes;
  }

  // Parse time string (e.g., "09:30 AM") to minutes since midnight
  private parseTime(timeString: string): number | null {
    if (!timeString) return null;

    const match = timeString.match(/(\d+):(\d+)\s*(AM|PM)/i);
    if (!match) return null;

    let hours = parseInt(match[1]);
    const minutes = parseInt(match[2]);
    const period = match[3].toUpperCase();

    if (period === 'PM' && hours !== 12) hours += 12;
    if (period === 'AM' && hours === 12) hours = 0;

    return hours * 60 + minutes;
  }

  // Select all days
  selectAll() {
    this.daysOfWeek.forEach(day => {
      this.availability[day].enabled = true;
      if (this.availability[day].timeRanges.length === 0) {
        this.availability[day].timeRanges.push({ start: '', end: '' });
      }
    });
    this.validateAvailability();
    this.notifyChange();
  }

  // Clear all days
  clearAll() {
    this.daysOfWeek.forEach(day => {
      this.availability[day].enabled = false;
      this.availability[day].timeRanges = [];
    });
    this.validateAvailability();
    this.notifyChange();
  }

  // Get errors for a specific day
  getDayErrors(day: string): string[] {
    return this.validationErrors[day] || [];
  }

  // Check if a day has errors
  hasDayErrors(day: string): boolean {
    return this.validationErrors[day] && this.validationErrors[day].length > 0;
  }
}