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

interface EmergencyClientContact {
  name: string;
  email: string;
  phone: string;
  landlinePhone: string;
}

interface Site {
  siteName: string;
  siteAddress: Address;
}

interface Client {
  legalEntityName: string;
  companyRegistrationNumber: string;
  primaryContact: ContactPerson;
  emergencyContact: EmergencyClientContact;
  billingAddress: Address;
  businessLogo: File | null;
  sites: Site[];
}

@Component({
  selector: 'app-client-setting',
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
  templateUrl: './client-setting.component.html',
  styleUrl: './client-setting.component.css'
})
export class ClientSettingComponent {

  @Input() clientData?: Client;

  clientFormModel: Client = {
    legalEntityName: '',
    companyRegistrationNumber: '',
    primaryContact: {
      name: '',
      email: '',
      phone: ''
    },
    emergencyContact: {
      name: '',
      email: '',
      phone: '',
      landlinePhone: ''
    },
    billingAddress: {
      street: '',
      city: '',
      country: '',
      postalCode: ''
    },
    businessLogo: null,
    sites: [
      {
        siteName: '',
        siteAddress: {
          street: '',
          city: '',
          country: '',
          postalCode: ''
        }
      }
    ]
  };

  clientErrors: any = {};
  isEditMode: boolean = false;

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) { }

  ngOnInit() {
    if (this.clientData) {
      this.clientFormModel = JSON.parse(JSON.stringify(this.clientData));
      this.isEditMode = true;
    }
  }

  addSite() {
    this.clientFormModel.sites.push({
      siteName: '',
      siteAddress: {
        street: '',
        city: '',
        country: '',
        postalCode: ''
      }
    });
  }

  validateClientForm(): boolean {
    this.clientErrors = {};

    // Company
    if (!this.clientFormModel.legalEntityName.trim()) {
      this.clientErrors.legalEntityName = 'Legal Entity Name is required.';
    }

    if (!this.clientFormModel.companyRegistrationNumber.trim()) {
      this.clientErrors.companyRegistrationNumber = 'Company Registration Number is required.';
    }

    // Primary Contact
    if (!this.clientFormModel.primaryContact.name.trim()) {
      this.clientErrors.primaryContactName = 'Primary contact name is required.';
    }

    if (!this.clientFormModel.primaryContact.email.trim()) {
      this.clientErrors.primaryContactEmail = 'Primary contact email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(this.clientFormModel.primaryContact.email)) {
      this.clientErrors.primaryContactEmail = 'Invalid email format.';
    }

    if (!this.clientFormModel.primaryContact.phone.trim()) {
      this.clientErrors.primaryContactPhone = 'Primary contact phone is required.';
    } else {
      const digits = this.clientFormModel.primaryContact.phone.replace(/[^0-9]/g, '');
      if (digits.length < 10 || digits.length > 15) {
        this.clientErrors.primaryContactPhone = 'Phone must be 10–15 digits.';
      }
    }

    // Emergency Contact
    if (!this.clientFormModel.emergencyContact.name.trim()) {
      this.clientErrors.emergencyContactName = 'Emergency contact name is required.';
    }

    if (!this.clientFormModel.emergencyContact.email.trim()) {
      this.clientErrors.emergencyContactEmail = 'Emergency contact email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(this.clientFormModel.emergencyContact.email)) {
      this.clientErrors.emergencyContactEmail = 'Invalid email format.';
    }

    if (!this.clientFormModel.emergencyContact.phone.trim()) {
      this.clientErrors.emergencyContactPhone = 'Emergency mobile phone is required.';
    } else {
      const digits = this.clientFormModel.emergencyContact.phone.replace(/[^0-9]/g, '');
      if (digits.length < 10 || digits.length > 15) {
        this.clientErrors.emergencyContactPhone = 'Phone must be 10–15 digits.';
      }
    }

    if (!this.clientFormModel.emergencyContact.landlinePhone.trim()) {
      this.clientErrors.emergencyContactLandline = 'Emergency landline phone is required.';
    } else {
      const digits = this.clientFormModel.emergencyContact.landlinePhone.replace(/[^0-9]/g, '');
      if (digits.length < 10 || digits.length > 15) {
        this.clientErrors.emergencyContactLandline = 'Landline must be 10–15 digits.';
      }
    }

    // Billing Address
    if (!this.clientFormModel.billingAddress.street.trim()) {
      this.clientErrors.billingStreet = 'Billing street is required.';
    }

    if (!this.clientFormModel.billingAddress.city.trim()) {
      this.clientErrors.billingCity = 'Billing city is required.';
    }

    if (!this.clientFormModel.billingAddress.country.trim()) {
      this.clientErrors.billingCountry = 'Billing country is required.';
    }

    if (!this.clientFormModel.billingAddress.postalCode.trim()) {
      this.clientErrors.billingPostalCode = 'Billing postal code is required.';
    }

    return Object.keys(this.clientErrors).length === 0;
  }

  submitClientForm() {
    if (!this.validateClientForm()) return;

    const tenantUpdatePayload = {
      tenant_type: TENANT_TYPES.CLIENT,
      profile: {
        legal_entity_name: this.clientFormModel.legalEntityName,
        company_registration_number: this.clientFormModel.companyRegistrationNumber,
        primary_contact: this.clientFormModel.primaryContact,
        emergency_contact: {
          name: this.clientFormModel.emergencyContact.name,
          email: this.clientFormModel.emergencyContact.email,
          phone: this.clientFormModel.emergencyContact.phone,
          landline_phone: this.clientFormModel.emergencyContact.landlinePhone
        },
        billing_address: this.clientFormModel.billingAddress,
        sites: this.clientFormModel.sites.map(site => ({
          site_name: site.siteName,
          site_address: site.siteAddress
        }))
      },
      status: 'active'
    };

    this.apiService.put('tenant', tenantUpdatePayload).subscribe({
      next: () => {
        this.appService.setTenantStatus('active', false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.clientErrors.submit = err?.error?.detail || 'Failed to submit client profile.';
      }
    });
  }
}
