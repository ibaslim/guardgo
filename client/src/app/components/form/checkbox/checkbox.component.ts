import { Component, Input, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'app-checkbox',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './checkbox.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CheckboxComponent),
      multi: true
    }
  ]
})
export class CheckboxComponent implements ControlValueAccessor {
  @Input() label = '';
  @Input() name = '';
  @Input() inputId = '';
  @Input() disabled = false;
  @Input() containerClass = 'inline-flex items-center gap-2';
  @Input() checkboxClass = 'h-5 w-5 text-blue-600 rounded focus:outline-none focus:ring-0 focus:ring-offset-0';
  @Input() labelClass = 'text-sm text-gray-900 dark:text-gray-100';

  value = false;
  onChange = (value: any) => {};
  onTouched = () => {};

  writeValue(value: any): void {
    this.value = !!value;
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

  get resolvedId(): string {
    return this.inputId || this.name;
  }

  toggle(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.value = checked;
    this.onChange(this.value);
    this.onTouched();
  }
}
