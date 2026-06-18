// ...existing code...
import { Component, Input, forwardRef, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NG_VALUE_ACCESSOR, ControlValueAccessor, FormsModule } from '@angular/forms';

@Component({
  selector: 'app-select-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './select-input.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectInputComponent),
      multi: true
    }
  ]
})
export class SelectInputComponent implements ControlValueAccessor {
    constructor(private elementRef: ElementRef<HTMLElement>) {
      if (typeof window !== 'undefined') {
        window.addEventListener('mousedown', this.handleClickOutside, true);
        window.addEventListener('pointerdown', this.handleClickOutside, true);
        window.addEventListener('touchstart', this.handleClickOutside, true);
      }
    }

    ngOnDestroy() {
      if (typeof window !== 'undefined') {
        window.removeEventListener('mousedown', this.handleClickOutside, true);
        window.removeEventListener('pointerdown', this.handleClickOutside, true);
        window.removeEventListener('touchstart', this.handleClickOutside, true);
      }
    }

    handleClickOutside = (event: Event) => {
      if (!this.dropdownOpen) {
        return;
      }

      const host = this.elementRef?.nativeElement;
      if (!host) {
        this.dropdownOpen = false;
        return;
      }

      const clickedInsideCurrentSelect = host.contains(event.target as Node);
      if (!clickedInsideCurrentSelect) {
        this.dropdownOpen = false;
      }
    }
  dropdownOpen = false;

  selectOption(val: any) {
    this.value = val;
    this.onChange(val);
    this.onTouched();
    this.dropdownOpen = false;
  }
  @Input() label = '';
  @Input() options: { label: string; value: any }[] = [];
  @Input() placeholder = '';
  @Input() disabled = false;
  @Input() required = false;
  @Input() searchable = true;
  @Input() name = '';
    @Input() helperText: string = '';
    @Input() errorText: string = '';

  value: any = '';
  search = '';
  onChange = (value: any) => {};
  onTouched = () => {};

  getSelectedLabel(): string {
    const selected = this.options.find(opt => opt.value === this.value);
    if (selected) {
      return selected.label;
    }
    return this.value ? String(this.value) : '';
  }

  get filteredOptions() {
    if (!this.searchable || !this.search) return this.options;
    return this.options.filter(opt => opt.label.toLowerCase().includes(this.search.toLowerCase()));
  }

  writeValue(value: any): void {
    this.value = value;
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
