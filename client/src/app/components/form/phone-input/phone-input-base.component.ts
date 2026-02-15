import { Component, Input, OnInit, OnDestroy, forwardRef, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { parsePhoneNumber, isValidPhoneNumber, AsYouType } from 'libphonenumber-js';
import { PHONE_COUNTRIES, PhoneCountry, getPhoneCountry } from '../../../shared/constants/phone-countries.constants';

/**
 * Base Phone Input Component
 * Shared functionality for mobile and landline phone inputs
 * Uses libphonenumber-js for validation and formatting
 */
@Component({
  selector: 'app-phone-input-base',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `<div>Base component - should not be used directly</div>`,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PhoneInputBaseComponent),
      multi: true
    }
  ]
})
export class PhoneInputBaseComponent implements ControlValueAccessor, OnInit, OnDestroy {
  @Input() label: string = 'Phone Number';
  @Input() placeholder: string = '(XXX) XXX-XXXX';
  @Input() required: boolean = false;
  @Input() helperText: string = '';
  @Input() disabled: boolean = false;
  @Input() disableCountrySelector: boolean = false; // New: disable only country dropdown
  @Input() defaultCountry: string = 'CA'; // Default to Canada
  @Input() allowedCountries?: string[]; // Optional: restrict to specific countries
  
  // Phone type to be overridden by subclasses ('mobile' | 'landline')
  protected phoneType: 'mobile' | 'landline' = 'mobile';

  // Form control values
  phoneNumber: string = '';
  selectedCountry: string = 'CA';
  countryCode: string = '';
  formattedNumber: string = '';
  validationError: string | null = null;

  // Dropdown and formatting
  phoneCountries: PhoneCountry[] = [];
  filteredCountries: PhoneCountry[] = [];
  showCountryDropdown = false;
  countrySearch = '';

  // ControlValueAccessor callbacks
  protected onChange: (value: any) => void = () => {};
  protected onTouched: () => void = () => {};

  constructor(private elementRef: ElementRef) {
    if (typeof window !== 'undefined') {
      window.addEventListener('mousedown', this.handleClickOutside);
    }
  }

  ngOnInit() {
    // Initialize country list
    this.phoneCountries = this.allowedCountries
      ? PHONE_COUNTRIES.filter((c: PhoneCountry) => this.allowedCountries?.includes(c.code))
      : PHONE_COUNTRIES;

    this.filteredCountries = [...this.phoneCountries];

    // Set default country
    if (getPhoneCountry(this.defaultCountry)) {
      this.selectedCountry = this.defaultCountry;
    }
    
    this.updateCountryCode();
  }

  ngOnDestroy(): void {
    if (typeof window !== 'undefined') {
      window.removeEventListener('mousedown', this.handleClickOutside);
    }
  }

  handleClickOutside = (event: MouseEvent) => {
    const dropdown = this.elementRef.nativeElement.querySelector('.phone-country-dropdown');
    if (dropdown && !this.elementRef.nativeElement.contains(event.target as Node)) {
      if (this.showCountryDropdown) {
        this.showCountryDropdown = false;
        this.countrySearch = '';
        this.filteredCountries = [...this.phoneCountries];
      }
    }
  }

  /**
   * Update country code when country changes
   */
  onCountryChange(countryCode: string) {
    this.selectedCountry = countryCode;
    this.updateCountryCode();
    this.formatPhoneNumber();
    this.showCountryDropdown = false;
    this.countrySearch = '';
    this.onChange(this.getFormattedValue());
  }

  /**
   * Handle phone number input
   */
  onPhoneInput(value: string) {
    this.phoneNumber = value;

    // Format as user types - create new formatter for each input to avoid accumulation
    if (value) {
      try {
        const formatter = new AsYouType(this.selectedCountry as any);
        this.formattedNumber = formatter.input(value);
      } catch (error) {
        this.formattedNumber = value;
      }
    } else {
      this.formattedNumber = '';
    }

    this.validatePhoneNumber();
    this.onChange(this.getFormattedValue());
  }

  /**
   * Handle phone input event from template
   */
  onPhoneInputEvent(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input && input.value !== undefined) {
      this.onPhoneInput(input.value);
    }
  }

  /**
   * Handle country search input event
   */
  onCountrySearchInput(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input && input.value !== undefined) {
      this.filterCountries(input.value);
    }
  }

  /**
   * Validate phone number
   */
  protected validatePhoneNumber() {
    if (!this.phoneNumber.trim()) {
      this.validationError = null;
      return;
    }

    try {
      const isValid = isValidPhoneNumber(this.phoneNumber, this.selectedCountry as any);
      
      if (!isValid) {
        this.validationError = 'Invalid phone number format';
        return;
      }

      // Additional validation for phone type (mobile vs landline)
      const parsed = parsePhoneNumber(this.phoneNumber, this.selectedCountry as any);
      if (parsed) {
        const numberType = parsed.getType();
        
        // Mobile: strict validation - must be MOBILE type
        if (this.phoneType === 'mobile') {
          if (numberType !== 'MOBILE' && numberType !== 'FIXED_LINE_OR_MOBILE') {
            this.validationError = 'Please enter a valid mobile number';
          } else {
            this.validationError = null;
          }
        } 
        // Landline: more flexible - accept FIXED_LINE, FIXED_LINE_OR_MOBILE, or even no specific type
        // (some countries don't distinguish landline from mobile in their numbering plans)
        else if (this.phoneType === 'landline') {
          if (numberType && numberType === 'MOBILE') {
            // Only reject if it's explicitly a mobile-only number
            this.validationError = 'This appears to be a mobile number';
          } else {
            // Accept FIXED_LINE, FIXED_LINE_OR_MOBILE, or undefined/unknown types
            this.validationError = null;
          }
        } else {
          this.validationError = null;
        }
      }
    } catch (error) {
      this.validationError = 'Invalid phone number';
    }
  }

  /**
   * Format phone number to E.164 and display format
   */
  protected formatPhoneNumber() {
    if (!this.phoneNumber.trim()) {
      this.formattedNumber = '';
      return;
    }

    try {
      const parsed = parsePhoneNumber(this.phoneNumber, this.selectedCountry as any);
      if (parsed && parsed.isValid && parsed.isValid()) {
        // Store as E.164 internally, display formatted version
        this.formattedNumber = parsed.formatInternational();
      }
    } catch (error) {
      // Keep original input if parsing fails
    }
  }

  /**
   * Get the value to emit (E.164 format)
   */
  protected getFormattedValue(): any {
    if (!this.phoneNumber.trim()) {
      return null;
    }

    try {
      const parsed = parsePhoneNumber(this.phoneNumber, this.selectedCountry as any);
      if (parsed && parsed.isValid && parsed.isValid()) {
        return {
          e164: parsed.format('E.164'),
          national: parsed.format('NATIONAL'),
          international: parsed.formatInternational(),
          country: this.selectedCountry,
          phoneType: this.phoneType,
          rawInput: this.phoneNumber
        };
      }
    } catch (error) {
      return null;
    }
    return null;
  }

  /**
   * Update country code display
   */
  protected updateCountryCode() {
    const country = getPhoneCountry(this.selectedCountry);
    this.countryCode = country ? `+${country.countryCode}` : '';
  }

  /**
   * Get emoji for currently selected country
   */
  getSelectedCountryEmoji(): string {
    const country = this.phoneCountries.find(c => c.code === this.selectedCountry);
    return country?.flagEmoji || '🌍';
  }

  /**
   * Filter countries based on search
   */
  filterCountries(searchTerm: string) {
    this.countrySearch = searchTerm.toLowerCase();
    this.filteredCountries = this.phoneCountries.filter(c =>
      c.label.toLowerCase().includes(this.countrySearch) ||
      c.code.toLowerCase().includes(this.countrySearch)
    );
  }

  /**
   * Toggle country dropdown
   */
  toggleCountryDropdown() {
    this.showCountryDropdown = !this.showCountryDropdown;
    if (!this.showCountryDropdown) {
      this.countrySearch = '';
      this.filteredCountries = [...this.phoneCountries];
    }
  }

  /**
   * Clear phone number
   */
  clearPhoneNumber() {
    this.phoneNumber = '';
    this.formattedNumber = '';
    this.validationError = null;
    this.onChange(null);
  }

  // ControlValueAccessor implementation
  writeValue(value: any): void {
    if (value) {
      if (typeof value === 'string') {
        this.phoneNumber = value;
      } else if (value.e164) {
        this.phoneNumber = value.e164;
        if (value.country) {
          this.selectedCountry = value.country;
          this.updateCountryCode();
        }
      }
      this.formatPhoneNumber();
    } else {
      this.phoneNumber = '';
      this.formattedNumber = '';
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
