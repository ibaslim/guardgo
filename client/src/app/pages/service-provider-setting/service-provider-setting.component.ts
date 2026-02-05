import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { ButtonComponent } from '../../components/button/button.component';
import { StickyActionBarComponent } from '../../components/sticky-action-bar/sticky-action-bar.component';
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { TENANT_TYPES } from '../../shared/constants/tenant-types.constants';

interface Address {
  street: string;
  city: string;
  country: string;
  postalCode: string;
}

interface ContactPerson {
  name: string;
  email: string;
  phone: string;
}

interface EmergencyServiceProviderContact {
  name: string;
  email: string;
  phone: string;
  landlinePhone: string;
}

interface SecurityLicense {
  licenseNumber: string;
  issuingAuthority: string;
  expiryDate: string;
  document?: File | null;
}

interface ServiceProvider {
  legalCompanyName: string;
  companyRegistrationNumber: string;
  companyLogo: File | null;
  headOfficeAddress: Address;
  companyPhone: string;
  companyEmail: string;
  emergencyContact: EmergencyServiceProviderContact;
  securityLicense: SecurityLicense;
  operatingRegions: string[];
  guardCategoriesOffered: string[];
}

@Component({
  selector: 'app-service-provider-setting',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    FileUploadComponent,
    PageComponent,
    SectionComponent,
    ButtonComponent,
    StickyActionBarComponent,
    ErrorMessageComponent
  ],
  templateUrl: './service-provider-setting.component.html',
  styleUrls: ['./service-provider-setting.component.css']
})
export class ServiceProviderSettingComponent {

  @Input() providerData?: ServiceProvider;

  providerFormModel: ServiceProvider = {
    legalCompanyName: '',
    companyRegistrationNumber: '',
    companyLogo: null,
    headOfficeAddress: {
      street: '',
      city: '',
      country: '',
      postalCode: ''
    },
    companyPhone: '',
    companyEmail: '',
    emergencyContact: {
      name: '',
      email: '',
      phone: '',
      landlinePhone: ''
    },
    securityLicense: {
      licenseNumber: '',
      issuingAuthority: '',
      expiryDate: '',
      document: null
    },
    operatingRegions: [''],
    guardCategoriesOffered: ['']
  };

  providerErrors: any = {};

  isEditMode: boolean = false;

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) { }

  ngOnInit() {
    if (this.providerData && this.hasProviderData(this.providerData)) {
      this.providerFormModel = JSON.parse(JSON.stringify(this.providerData));
      this.isEditMode = true;
    } else {
      this.isEditMode = false;
    }
  }

  hasProviderData(data: ServiceProvider): boolean {
    return !!(
      data.legalCompanyName.trim() ||
      data.companyRegistrationNumber.trim() ||
      data.companyPhone.trim() ||
      data.headOfficeAddress.street.trim() ||
      data.emergencyContact.name.trim()
    );
  }

  addRegion() {
    this.providerFormModel.operatingRegions.push('');
  }

  trackByIndex(index: number, item: any): any {
    return index;
  }

  addCategory() {
    this.providerFormModel.guardCategoriesOffered.push('');
  }

  validateProviderForm(): boolean {
    this.providerErrors = {};

    // Legal Company Name
    if (!this.providerFormModel.legalCompanyName.trim()) {
      this.providerErrors.legalCompanyName = 'Legal company name is required.';
    }

    // Company Registration Number
    if (!this.providerFormModel.companyRegistrationNumber.trim()) {
      this.providerErrors.companyRegistrationNumber = 'Company registration number is required.';
    }

    // Head Office Address
    if (!this.providerFormModel.headOfficeAddress.street.trim()) {
      this.providerErrors.officeStreet = 'Office street address is required.';
    }
    if (!this.providerFormModel.headOfficeAddress.city.trim()) {
      this.providerErrors.officeCity = 'Office city is required.';
    }
    if (!this.providerFormModel.headOfficeAddress.country.trim()) {
      this.providerErrors.officeCountry = 'Office country is required.';
    }
    if (!this.providerFormModel.headOfficeAddress.postalCode.trim()) {
      this.providerErrors.officePostalCode = 'Office postal code is required.';
    }

    // Company Contact
    if (!this.providerFormModel.companyPhone.trim()) {
      this.providerErrors.companyPhone = 'Company phone is required.';
    } else {
      const companyDigits = this.providerFormModel.companyPhone.replace(/[^0-9]/g, '');
      if (companyDigits.length < 10 || companyDigits.length > 15) {
        this.providerErrors.companyPhone = 'Phone number must be 10-15 digits.';
      }
    }
    if (!this.providerFormModel.companyEmail.trim()) {
      this.providerErrors.companyEmail = 'Company email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(this.providerFormModel.companyEmail)) {
      this.providerErrors.companyEmail = 'Invalid email format.';
    }

    // Emergency Contact
    if (!this.providerFormModel.emergencyContact.name.trim()) {
      this.providerErrors.emergencyContactName = 'Emergency contact name is required.';
    }

    if (!this.providerFormModel.emergencyContact.email.trim()) {
      this.providerErrors.emergencyContactEmail = 'Emergency contact email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(this.providerFormModel.emergencyContact.email)) {
      this.providerErrors.emergencyContactEmail = 'Invalid email format.';
    }

    if (!this.providerFormModel.emergencyContact.phone.trim()) {
      this.providerErrors.emergencyContactPhone = 'Emergency mobile phone is required.';
    } else {
      const digits = this.providerFormModel.emergencyContact.phone.replace(/[^0-9]/g, '');
      if (digits.length < 10 || digits.length > 15) {
        this.providerErrors.emergencyContactPhone = 'Phone must be 10–15 digits.';
      }
    }

    if (!this.providerFormModel.emergencyContact.landlinePhone.trim()) {
      this.providerErrors.emergencyContactLandline = 'Emergency landline phone is required.';
    } else {
      const digits = this.providerFormModel.emergencyContact.landlinePhone.replace(/[^0-9]/g, '');
      if (digits.length < 10 || digits.length > 15) {
        this.providerErrors.emergencyContactLandline = 'Landline must be 10–15 digits.';
      }
    }

    // Security License
    if (!this.providerFormModel.securityLicense.licenseNumber.trim()) {
      this.providerErrors.licenseNumber = 'Security license number is required.';
    }
    if (!this.providerFormModel.securityLicense.issuingAuthority.trim()) {
      this.providerErrors.issuingAuthority = 'Issuing authority is required.';
    }
    if (!this.providerFormModel.securityLicense.expiryDate) {
      this.providerErrors.expiryDate = 'Expiry date is required.';
    }

    // Operating Regions (at least one required)
    const validRegions = this.providerFormModel.operatingRegions.filter(r => r.trim());
    if (validRegions.length === 0) {
      this.providerErrors.operatingRegions = 'At least one operating region is required.';
    }

    // Guard Categories (at least one required)
    const validCategories = this.providerFormModel.guardCategoriesOffered.filter(c => c.trim());
    if (validCategories.length === 0) {
      this.providerErrors.guardCategories = 'At least one guard category is required.';
    }

    return Object.keys(this.providerErrors).length === 0;
  }

  submitProviderForm() {
    if (!this.validateProviderForm()) {
      return;
    }

    // Filter out empty strings from arrays
    const validRegions = this.providerFormModel.operatingRegions.filter(r => r.trim());
    const validCategories = this.providerFormModel.guardCategoriesOffered.filter(c => c.trim());

    const tenantUpdatePayload = {
      tenant_type: TENANT_TYPES.SERVICE_PROVIDER,
      profile: {
        legal_company_name: this.providerFormModel.legalCompanyName,
        company_registration_number: this.providerFormModel.companyRegistrationNumber,
        head_office_address: this.providerFormModel.headOfficeAddress,
        company_phone: this.providerFormModel.companyPhone,
        company_email: this.providerFormModel.companyEmail,
        emergency_contact: {
          name: this.providerFormModel.emergencyContact.name,
          email: this.providerFormModel.emergencyContact.email,
          phone: this.providerFormModel.emergencyContact.phone,
          landline_phone: this.providerFormModel.emergencyContact.landlinePhone
        },
        security_license: {
          license_number: this.providerFormModel.securityLicense.licenseNumber,
          issuing_authority: this.providerFormModel.securityLicense.issuingAuthority,
          expiry_date: this.providerFormModel.securityLicense.expiryDate
        },
        operating_regions: validRegions,
        guard_categories_offered: validCategories
      },
      status: 'active'
    };

    this.apiService.put('tenant', tenantUpdatePayload).subscribe({
      next: (response) => {
        console.log('Service provider profile submitted successfully', response);
        this.appService.setTenantStatus('active', false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error('Error submitting service provider profile:', err);
        this.providerErrors.submit = err?.error?.detail || 'Failed to submit service provider profile.';
      }
    });
  }
}
