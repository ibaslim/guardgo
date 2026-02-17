import { Component, Input, forwardRef, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { PhoneInputBaseComponent } from './phone-input-base.component';

/**
 * Landline Phone Input Component
 * Specialized for landline phone numbers with landline validation
 */
@Component({
  selector: 'app-landline-phone-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './landline-phone-input.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => LandlinePhoneInputComponent),
      multi: true
    }
  ]
})
export class LandlinePhoneInputComponent extends PhoneInputBaseComponent {
  @Input() override label: string = 'Landline Phone Number';
  @Input() override placeholder: string = '';
  @Input() override helperText: string = 'Enter your landline phone number (can include extensions)';
  
  protected override phoneType: 'mobile' | 'landline' = 'landline';

  constructor(elementRef: ElementRef) {
    super(elementRef);
  }

  override ngOnInit(): void {
    super.ngOnInit();
    // Set country-specific landline placeholder
    this.updatePlaceholder();
  }

  override onCountryChange(countryCode: string): void {
    super.onCountryChange(countryCode);
    this.updatePlaceholder();
  }

  private updatePlaceholder(): void {
    // Landline-specific placeholders based on country (typically with area codes)
    const placeholders: { [key: string]: string } = {
      'CA': '(416) 555-1234',
      'US': '(212) 555-1234',
      'GB': '020 7946 0958',
      'FR': '01 42 68 53 00',
      'DE': '030 12345678',
      'AU': '(02) 1234 5678',
      'IN': '011 2345 6789',
      'CN': '010 1234 5678'
    };
    this.placeholder = placeholders[this.selectedCountry] || 'Landline number';
  }
}
