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

export interface DropdownOption {
  label: string;
  value: any;
  disabled?: boolean;
}

@Component({
  selector: 'app-base-dropdown',
  imports: [CommonModule],
  templateUrl: './base-dropdown.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => BaseDropdown),
      multi: true,
    },
  ],
})
export class BaseDropdown implements ControlValueAccessor {
  @Input() options: DropdownOption[] = [];
  @Input() placeholder: string = 'Select an option';
  @Input() disabled: boolean = false;
  @Input() searchable: boolean = false;
  @Input() label: string = '';
  @Output() selectionChange = new EventEmitter<any>();

  isOpen: boolean = false;
  selectedOption: DropdownOption | null = null;
  searchTerm: string = '';
  focusedIndex: number = -1;

  private onChange: (value: any) => void = () => {};
  private onTouched: () => void = () => {};

  constructor(private elementRef: ElementRef) {}

  get filteredOptions(): DropdownOption[] {
    if (!this.searchable || !this.searchTerm) {
      return this.options;
    }
    return this.options.filter((option) =>
      option.label.toLowerCase().includes(this.searchTerm.toLowerCase())
    );
  }

  get displayValue(): string {
    return this.selectedOption ? this.selectedOption.label : this.placeholder;
  }

  toggleDropdown(): void {
    if (this.disabled) return;
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.focusedIndex = this.selectedOption
        ? this.options.findIndex((o) => o.value === this.selectedOption?.value)
        : 0;
    } else {
      this.searchTerm = '';
    }
  }

  selectOption(option: DropdownOption): void {
    if (option.disabled) return;
    this.selectedOption = option;
    this.onChange(option.value);
    this.selectionChange.emit(option.value);
    this.isOpen = false;
    this.searchTerm = '';
    this.onTouched();
  }

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.searchTerm = target.value;
    this.focusedIndex = 0;
  }

  @HostListener('document:click', ['$event'])
  onClickOutside(event: MouseEvent): void {
    if (event.target && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.isOpen = false;
      this.searchTerm = '';
    }
  }

  @HostListener('keydown', ['$event'])
  onKeyDown(event: KeyboardEvent): void {
    if (!this.isOpen) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        this.toggleDropdown();
      }
      return;
    }

    const options = this.filteredOptions;

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.focusedIndex = Math.min(this.focusedIndex + 1, options.length - 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.focusedIndex = Math.max(this.focusedIndex - 1, 0);
        break;
      case 'Enter':
        event.preventDefault();
        if (this.focusedIndex >= 0 && this.focusedIndex < options.length) {
          this.selectOption(options[this.focusedIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        this.isOpen = false;
        this.searchTerm = '';
        break;
    }
  }

  // ControlValueAccessor implementation
  writeValue(value: any): void {
    if (value !== undefined && value !== null) {
      this.selectedOption = this.options.find((o) => o.value === value) || null;
    } else {
      this.selectedOption = null;
    }
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
