import { Component, Input, forwardRef, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NG_VALUE_ACCESSOR } from '@angular/forms';
import { PhoneInputBaseComponent } from './phone-input-base.component';

/**
 * Mobile Phone Input Component
 * Specialized for mobile phone numbers with mobile-only validation
 */
@Component({
  selector: 'app-mobile-phone-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mobile-phone-input.component.html',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => MobilePhoneInputComponent),
      multi: true
    }
  ]
})
export class MobilePhoneInputComponent extends PhoneInputBaseComponent {
  @Input() override label: string = 'Mobile Phone Number';
  @Input() override placeholder: string = '';
  @Input() override helperText: string = 'Enter your mobile phone number';
  
  protected override phoneType: 'mobile' | 'landline' = 'mobile';

  constructor(elementRef: ElementRef) {
    super(elementRef);
  }

  override ngOnInit(): void {
    super.ngOnInit();
    // Set country-specific mobile placeholder
    this.updatePlaceholder();
  }

  override onCountryChange(countryCode: string): void {
    super.onCountryChange(countryCode);
    this.updatePlaceholder();
  }

  private updatePlaceholder(): void {
    // Mobile-specific placeholders based on country
    const placeholders: { [key: string]: string } = {
      'CA': '(555) 123-4567',
      'US': '(555) 123-4567',
      'GB': '07700 900000',
      'FR': '06 12 34 56 78',
      'DE': '0151 23456789',
      'AU': '0412 345 678',
      'IN': '91234 56789',
      'CN': '139 1234 5678'
    };
    this.placeholder = placeholders[this.selectedCountry] || 'Mobile number';
  }
}
