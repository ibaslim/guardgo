import { Component, Input, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NG_VALUE_ACCESSOR, ControlValueAccessor, FormsModule } from '@angular/forms';

@Component({
  selector: 'app-base-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './base-input.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => BaseInputComponent),
      multi: true
    }
  ]
})
export class BaseInputComponent implements ControlValueAccessor {
  @Input() type: 'text' | 'number' | 'email' | 'password' | 'tel' | 'date' = 'text';
  @Input() label = '';
  @Input() placeholder?: string;
  @Input() disabled = false;
  @Input() readonly = false;
  @Input() required = false;
  @Input() name = '';
  @Input() helperText: string = '';
  @Input() errorText: string = '';
  @Input() min?: number;
  @Input() max?: number;
  value: string | number = '';
  onChange = (value: any) => { };
  onTouched = () => { };

  touched = false;

  get effectivePlaceholder(): string {
    return this.placeholder ?? (this.label ? `Enter ${this.label.toLowerCase()}` : 'Enter value');
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
