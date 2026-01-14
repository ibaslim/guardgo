// ...existing imports...
import { Component, Input, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NG_VALUE_ACCESSOR, ControlValueAccessor, FormsModule } from '@angular/forms';

@Component({
  selector: 'app-multiselect-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './multiselect-input.component.html',
  styleUrls: ['./multiselect-input.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => MultiselectInputComponent),
      multi: true
    }
  ]
})
export class MultiselectInputComponent implements ControlValueAccessor {
      // Utility to detect dark mode
      isDarkMode(): boolean {
        return document.documentElement.classList.contains('dark');
      }
    dropdownOpen = false;

    constructor() {
      if (typeof window !== 'undefined') {
        window.addEventListener('click', (e: any) => {
          if (!e.target.closest('.select-dropdown')) {
            this.dropdownOpen = false;
          }
        });
      }
    }
  @Input() label = '';
  @Input() options: { label: string; value: any }[] = [];
  @Input() placeholder = '';
  @Input() helperText: string = '';
  @Input() errorText: string = '';
  @Input() disabled = false;
  @Input() required = false;
  @Input() searchable = false;
  @Input() name = '';

  value: any[] = [];
  search = '';
  onChange = (value: any) => {};
  onTouched = () => {};

  get filteredOptions() {
    if (!this.searchable || !this.search) return this.options;
    return this.options.filter(opt => opt.label.toLowerCase().includes(this.search.toLowerCase()));
  }

  isSelected(val: any) {
    return this.value.includes(val);
  }

  toggle(val: any) {
    if (this.disabled) return;
    if (this.isSelected(val)) {
      this.value = this.value.filter(v => v !== val);
    } else {
      this.value = [...this.value, val];
    }
    this.onChange(this.value);
    this.onTouched();
  }

  getLabel = (val: any): string => {
    const opts = this.options || [];
    const found = opts.find((o: any) => o.value === val);
    return found ? found.label : val;
  }

  writeValue(value: any): void {
    this.value = value || [];
  }
  registerOnChange(fn: any): void {
    this.onChange = fn;
  }
  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }
  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }
}
