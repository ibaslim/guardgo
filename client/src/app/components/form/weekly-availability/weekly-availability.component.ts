import { CommonModule } from '@angular/common';
import { Component, forwardRef } from '@angular/core';
import { FormsModule, NG_VALUE_ACCESSOR, ControlValueAccessor } from '@angular/forms';

@Component({
  selector: 'app-weekly-availability',
  standalone: true,
  imports: [CommonModule, FormsModule],
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
  availability: { [day: string]: string[] } = {
    Monday: [],
    Tuesday: [],
    Wednesday: [],
    Thursday: [],
    Friday: [],
    Saturday: [],
    Sunday: []
  };

  daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  timeSlots = ['Morning', 'Evening', 'Night'];

  private onChange: any = () => {};
  private onTouched: any = () => {};

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

  // Checkbox toggle
  toggle(day: string, slot: string, event: Event) {
    const checked = (event.target as HTMLInputElement).checked;
    const slots = this.availability[day];

    if (checked && !slots.includes(slot)) {
      slots.push(slot);
    } else if (!checked && slots.includes(slot)) {
      slots.splice(slots.indexOf(slot), 1);
    }

    this.onChange(this.availability); // Notify parent
  }

  toggleSlot(slot: string) {
    const allSelected = this.daysOfWeek.every(day => this.availability[day]?.includes(slot));

    this.daysOfWeek.forEach(day => {
      if (!this.availability[day]) this.availability[day] = [];

      if (allSelected) {
        this.availability[day] = this.availability[day].filter(s => s !== slot);
      } else {
        if (!this.availability[day].includes(slot)) this.availability[day].push(slot);
      }
    });

    this.onChange(this.availability); // Notify parent
  }

  selectAll() {
    this.daysOfWeek.forEach(day => this.availability[day] = [...this.timeSlots]);
    this.onChange(this.availability); // Notify parent
  }

  clearAll() {
    this.daysOfWeek.forEach(day => this.availability[day] = []);
    this.onChange(this.availability); // Notify parent
  }
}