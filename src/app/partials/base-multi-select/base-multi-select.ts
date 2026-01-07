import {
  Component,
  Input,
  Output,
  EventEmitter,
  HostListener,
  ElementRef,
  forwardRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface MultiSelectOption {
  label: string;
  value: any;
  disabled?: boolean;
}

@Component({
  selector: 'app-base-multi-select',
  imports: [CommonModule],
  templateUrl: './base-multi-select.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => BaseMultiSelect),
      multi: true,
    },
  ],
})
export class BaseMultiSelect implements ControlValueAccessor {
  @Input() options: MultiSelectOption[] = [];
  @Input() placeholder: string = 'Select options';
  @Input() disabled: boolean = false;
  @Input() label: string = '';
  @Input() maxDisplayChips: number = 3;
  @Output() selectionChange = new EventEmitter<any[]>();

  isOpen: boolean = false;
  selectedValues: any[] = [];
  searchTerm: string = '';

  private onChange: (value: any[]) => void = () => {};
  private onTouched: () => void = () => {};

  constructor(private elementRef: ElementRef) {}

  get filteredOptions(): MultiSelectOption[] {
    if (!this.searchTerm) {
      return this.options;
    }
    return this.options.filter((option) =>
      option.label.toLowerCase().includes(this.searchTerm.toLowerCase())
    );
  }

  get selectedOptions(): MultiSelectOption[] {
    return this.options.filter((option) => this.selectedValues.includes(option.value));
  }

  get displayChips(): MultiSelectOption[] {
    return this.selectedOptions.slice(0, this.maxDisplayChips);
  }

  get remainingCount(): number {
    return Math.max(0, this.selectedOptions.length - this.maxDisplayChips);
  }

  get allSelected(): boolean {
    return this.options.length > 0 && this.selectedValues.length === this.options.length;
  }

  toggleDropdown(): void {
    if (this.disabled) return;
    this.isOpen = !this.isOpen;
    if (!this.isOpen) {
      this.searchTerm = '';
    }
  }

  toggleOption(option: MultiSelectOption): void {
    if (option.disabled) return;

    const index = this.selectedValues.indexOf(option.value);
    if (index > -1) {
      this.selectedValues = this.selectedValues.filter((v) => v !== option.value);
    } else {
      this.selectedValues = [...this.selectedValues, option.value];
    }

    this.onChange(this.selectedValues);
    this.selectionChange.emit(this.selectedValues);
  }

  isSelected(option: MultiSelectOption): boolean {
    return this.selectedValues.includes(option.value);
  }

  removeChip(option: MultiSelectOption, event: Event): void {
    event.stopPropagation();
    this.toggleOption(option);
  }

  selectAll(): void {
    this.selectedValues = this.options
      .filter((option) => !option.disabled)
      .map((option) => option.value);
    this.onChange(this.selectedValues);
    this.selectionChange.emit(this.selectedValues);
  }

  clearAll(): void {
    this.selectedValues = [];
    this.onChange(this.selectedValues);
    this.selectionChange.emit(this.selectedValues);
  }

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchTerm = target.value;
  }

  @HostListener('document:click', ['$event'])
  onClickOutside(event: MouseEvent): void {
    if (!this.elementRef.nativeElement.contains(event.target)) {
      this.isOpen = false;
      this.searchTerm = '';
    }
  }

  @HostListener('keydown.escape')
  onEscape(): void {
    this.isOpen = false;
    this.searchTerm = '';
  }

  // ControlValueAccessor implementation
  writeValue(values: any[]): void {
    this.selectedValues = Array.isArray(values) ? values : [];
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
