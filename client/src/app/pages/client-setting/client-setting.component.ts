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

interface Site {
  siteName: string;
  siteAddress: Address;
}

interface Client {
  legalEntityName: string;
  companyRegistrationNumber: string;
  primaryContact: ContactPerson;
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
  ) {}

  ngOnInit() {
    if (this.clientData && this.hasClientData(this.clientData)) {
      this.clientFormModel = JSON.parse(JSON.stringify(this.clientData));
      this.isEditMode = true;
    } else {
      this.isEditMode = false;
    }
  }

  hasClientData(data: Client): boolean {
    return !!(
      data.legalEntityName.trim() ||
      data.companyRegistrationNumber.trim() ||
      data.primaryContact.name.trim() ||
      data.billingAddress.street.trim() ||
      (data.sites && data.sites.some(site => site.siteName.trim() || site.siteAddress.street.trim()))
    );
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

    // Legal Entity Name
    if (!this.clientFormModel.legalEntityName || this.clientFormModel.legalEntityName.trim() === '') {
      this.clientErrors.legalEntityName = 'Legal Entity Name is required.';
    }

    // Company Registration Number
    if (!this.clientFormModel.companyRegistrationNumber || this.clientFormModel.companyRegistrationNumber.trim() === '') {
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
      const phoneDigits = this.clientFormModel.primaryContact.phone.replace(/[^0-9]/g, '');
      if (phoneDigits.length < 10 || phoneDigits.length > 15) {
        this.clientErrors.primaryContactPhone = 'Phone number must be 10-15 digits.';
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

    // Sites validation (first site required)
    if (!this.clientFormModel.sites || this.clientFormModel.sites.length === 0) {
      this.clientErrors.sites = 'At least one site is required.';
    } else {
      const firstSite = this.clientFormModel.sites[0];
      if (!firstSite.siteName || firstSite.siteName.trim() === '') {
        this.clientErrors.siteName0 = 'Site name is required.';
      }
      if (!firstSite.siteAddress.street.trim()) {
        this.clientErrors.siteStreet0 = 'Site street is required.';
      }
      if (!firstSite.siteAddress.city.trim()) {
        this.clientErrors.siteCity0 = 'Site city is required.';
      }
      if (!firstSite.siteAddress.country.trim()) {
        this.clientErrors.siteCountry0 = 'Site country is required.';
      }
      if (!firstSite.siteAddress.postalCode.trim()) {
        this.clientErrors.sitePostalCode0 = 'Site postal code is required.';
      }
    }

    return Object.keys(this.clientErrors).length === 0;
  }

  submitClientForm() {
    if (!this.validateClientForm()) {
      return;
    }

    const tenantUpdatePayload = {
      tenant_type: TENANT_TYPES.CLIENT,
      profile: {
        legal_entity_name: this.clientFormModel.legalEntityName,
        company_registration_number: this.clientFormModel.companyRegistrationNumber,
        primary_contact: {
          name: this.clientFormModel.primaryContact.name,
          email: this.clientFormModel.primaryContact.email,
          phone: this.clientFormModel.primaryContact.phone
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
      next: (response) => {
        console.log('Client profile submitted successfully', response);
        this.appService.setTenantStatus('active', false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error('Error submitting client profile:', err);
        this.clientErrors.submit = err?.error?.detail || 'Failed to submit client profile.';
      }
    });
  }
}