import { Component, Input, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NG_VALUE_ACCESSOR, ControlValueAccessor, FormsModule } from '@angular/forms';
import { MultiselectInputComponent } from '../form/multiselect-input/multiselect-input.component';

@Component({
  selector: 'app-guard-types-multiselect',
  standalone: true,
  imports: [CommonModule, FormsModule, MultiselectInputComponent],
  templateUrl: './client-preferred-guard-types.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => ClientPreferredGuardTypesComponent),
      multi: true
    }
  ]
})
export class ClientPreferredGuardTypesComponent implements ControlValueAccessor {
  @Input() label = 'Guard Types';
  @Input() placeholder = '-- Select Guard Types --';
  @Input() helperText = '';
  @Input() errorText = '';
  @Input() options: { value: string; label: string }[] = [];
  @Input() disabled = false;
  @Input() required = false;
  @Input() name = '';

  value: string[] = [];
  onChange = (_: string[]) => {};
  onTouched = () => {};

  writeValue(value: string[] | null): void {
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

  handleChange(value: string[]): void {
    this.value = value;
    this.onChange(value);
    this.onTouched();
  }
}
