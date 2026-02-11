import { CommonModule } from '@angular/common';
import { Component, Input, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { MobilePhoneInputComponent } from '../../components/form/phone-input/mobile-phone-input.component';
import { LandlinePhoneInputComponent } from '../../components/form/phone-input/landline-phone-input.component';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { ButtonComponent } from '../../components/button/button.component';
import { StickyActionBarComponent } from '../../components/sticky-action-bar/sticky-action-bar.component';
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { ProfilePictureUploadComponent } from '../../components/profile-picture-upload/profile-picture-upload.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { TENANT_TYPES } from '../../shared/constants/tenant-types.constants';

interface PhoneNumber {
  e164: string;
  national: string;
  international: string;
  country: string;
  phoneType: 'mobile' | 'landline';
  rawInput: string;
}

interface Address {
  street: string;
  city: string;
  country: string;
  province: string;
  postalCode: string;
}

interface ContactPerson {
  name: string;
  email: string;
  mobilePhone: PhoneNumber | null;
  landlinePhone: PhoneNumber | null;
}

interface Site {
  siteName: string;
  siteAddress: Address;
  siteManagerContact: string;
  managerEmail: string;
  numberOfGuardsRequired: number | null;
  siteType: string;
}

interface Client {
  legalEntityName: string;
  clientType: 'company' | 'individual';
  industry: string;
  companyRegistrationNumber: string;
  companyWebsite: string;
  taxVatNumber: string;
  primaryContact: ContactPerson;
  secondaryContact: ContactPerson;
  billingAddress: Address;
  preferredGuardTypes: string[];
  sites: Site[];
}

@Component({
  selector: 'app-client-setting',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    SelectInputComponent,
    MobilePhoneInputComponent,
    LandlinePhoneInputComponent,
    PageComponent,
    SectionComponent,
    ButtonComponent,
    StickyActionBarComponent,
    ErrorMessageComponent,
    ProfilePictureUploadComponent
  ],
  templateUrl: './client-setting.component.html',
  styleUrl: './client-setting.component.css'
})
export class ClientSettingComponent implements OnInit, OnDestroy {

  @Input() clientData?: Client;

  clientFormModel: Client = {
    legalEntityName: '',
    clientType: 'company',
    industry: '',
    companyRegistrationNumber: '',
    companyWebsite: '',
    taxVatNumber: '',
    primaryContact: {
      name: '',
      email: '',
      mobilePhone: null,
      landlinePhone: null
    },
    secondaryContact: {
      name: '',
      email: '',
      mobilePhone: null,
      landlinePhone: null
    },
    billingAddress: {
      street: '',
      city: '',
      country: 'CA',
      province: '',
      postalCode: ''
    },
    preferredGuardTypes: [],
    sites: []
  };

  clientErrors: any = {};

  isEditMode: boolean = false;

  countryOptions: { value: string; label: string }[] = [];
  provinceOptions: { value: string; label: string }[] = [];
  siteTypeOptions: { value: string; label: string }[] = [];
  guardTypeOptions: { value: string; label: string }[] = [];
  clientTypeOptions: { value: string; label: string }[] = [];

  private destroy$ = new Subject<void>();

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) {}

  ngOnInit(): void {
    this.loadClientMetadata(() => {
      if (this.clientData && this.hasClientData(this.clientData)) {
        this.clientFormModel = this.transformBackendDataToForm(this.clientData as any);
        this.isEditMode = true;
      } else {
        this.isEditMode = false;
      }

      if (!this.clientFormModel.billingAddress.country) {
        this.clientFormModel.billingAddress.country = 'CA';
      }
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadClientMetadata(onLoaded?: () => void): void {
    this.apiService.get<any>('public/client-metadata')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          if (response?.countries?.length) {
            this.countryOptions = response.countries;
          }
          if (response?.canadianProvinces?.length) {
            this.provinceOptions = response.canadianProvinces;
          }
          if (response?.siteTypeOptions?.length) {
            this.siteTypeOptions = response.siteTypeOptions;
          }
          if (response?.guardTypeOptions?.length) {
            this.guardTypeOptions = response.guardTypeOptions;
          }
          if (response?.clientTypeOptions?.length) {
            this.clientTypeOptions = response.clientTypeOptions;
          }
          onLoaded?.();
        },
        error: () => {
          onLoaded?.();
        }
      });
  }

  hasClientData(data: Client): boolean {
    return !!(
      data.legalEntityName.trim() ||
      data.companyRegistrationNumber.trim() ||
      data.industry?.trim() ||
      data.companyWebsite?.trim() ||
      data.taxVatNumber?.trim() ||
      data.primaryContact.name.trim() ||
      data.primaryContact.mobilePhone?.e164 ||
      data.primaryContact.landlinePhone?.e164 ||
      data.secondaryContact?.name.trim() ||
      data.secondaryContact?.email.trim() ||
      data.secondaryContact?.mobilePhone?.e164 ||
      data.secondaryContact?.landlinePhone?.e164 ||
      data.billingAddress.street.trim() ||
      data.preferredGuardTypes?.some((type: string) => type.trim()) ||
      (data.sites && data.sites.some((site: Site) => site.siteName.trim() || site.siteAddress.street.trim()))
    );
  }

  onClientTypeChange(): void {
    if (this.clientFormModel.clientType === 'individual') {
      this.clientFormModel.companyRegistrationNumber = '';
      this.clientFormModel.taxVatNumber = '';
    }
  }

  private normalizeOptionValue(value: string, options: { value: string; label: string }[]): string {
    const normalized = String(value || '').trim();
    const byValue = options.find(opt => opt.value === normalized);
    if (byValue) {
      return byValue.value;
    }
    const byLabel = options.find(opt => opt.label.toLowerCase() === normalized.toLowerCase());
    return byLabel?.value || normalized;
  }

  private mapPhoneFromBackend(phone: string, phoneType: 'mobile' | 'landline'): PhoneNumber {
    return {
      e164: phone,
      national: phone,
      international: phone,
      country: 'CA',
      phoneType,
      rawInput: phone
    };
  }

  private mapAddressFromBackend(raw: any): Address {
    return {
      street: raw?.street || '',
      city: raw?.city || '',
      country: raw?.country || 'CA',
      province: raw?.province || '',
      postalCode: raw?.postal_code || raw?.postalCode || ''
    };
  }

  private transformBackendDataToForm(data: any): Client {
    const profile = data?.profile || data || {};
    const primaryContact = profile.primary_contact || profile.primaryContact || {};
    const secondaryContact = profile.secondary_contact || profile.secondaryContact || {};
    const billingAddress = this.mapAddressFromBackend(profile.billing_address || profile.billingAddress || {});
    const preferredTypes = Array.isArray(profile.preferred_guard_types)
      ? profile.preferred_guard_types
      : Array.isArray(profile.preferredGuardTypes)
        ? profile.preferredGuardTypes
        : [];
    const normalizedPreferredTypes = preferredTypes
      .map((type: string) => this.normalizeOptionValue(type, this.guardTypeOptions))
      .filter((type: string) => type);

    const rawSites = profile.sites || [];
    const mappedSites: Site[] = Array.isArray(rawSites)
      ? rawSites.map((site: any) => {
          const siteAddress = this.mapAddressFromBackend(site.site_address || site.siteAddress || {});
          return {
            siteName: site.site_name || site.siteName || '',
            siteAddress,
            siteManagerContact: site.site_manager_contact || site.siteManagerContact || '',
            managerEmail: site.manager_email || site.managerEmail || '',
            numberOfGuardsRequired: site.number_of_guards_required ?? site.numberOfGuardsRequired ?? null,
            siteType: this.normalizeOptionValue(site.site_type || site.siteType || '', this.siteTypeOptions)
          };
        })
      : [];

    return {
      legalEntityName: profile.legal_entity_name || profile.legalEntityName || '',
      clientType: (profile.business_type || profile.businessType) === 'individual'
        ? 'individual'
        : 'company',
      industry: profile.industry || profile.business_sector || '',
      companyRegistrationNumber: profile.company_registration_number || profile.companyRegistrationNumber || '',
      companyWebsite: profile.company_website || profile.companyWebsite || '',
      taxVatNumber: profile.tax_vat_number || profile.taxVatNumber || '',
      primaryContact: {
        name: primaryContact.name || '',
        email: primaryContact.email || '',
        mobilePhone: primaryContact.phone
          ? this.mapPhoneFromBackend(primaryContact.phone, 'mobile')
          : null,
        landlinePhone: null
      },
      secondaryContact: {
        name: secondaryContact.name || '',
        email: secondaryContact.email || '',
        mobilePhone: secondaryContact.phone
          ? this.mapPhoneFromBackend(secondaryContact.phone, 'mobile')
          : null,
        landlinePhone: null
      },
      billingAddress,
      preferredGuardTypes: normalizedPreferredTypes.length > 0 ? normalizedPreferredTypes : [],
      sites: mappedSites
    };
  }

  validateClientForm(): boolean {
    this.clientErrors = {};

    // Legal Entity Name
    if (!this.clientFormModel.legalEntityName || this.clientFormModel.legalEntityName.trim() === '') {
      this.clientErrors.legalEntityName = this.clientFormModel.clientType === 'individual'
        ? 'Full name is required.'
        : 'Legal Entity Name is required.';
    }

    // Company Registration Number
    if (!this.clientFormModel.companyRegistrationNumber || this.clientFormModel.companyRegistrationNumber.trim() === '') {
      if (this.clientFormModel.clientType === 'company') {
        this.clientErrors.companyRegistrationNumber = 'Company Registration Number is required.';
      }
    }

    if (this.clientFormModel.clientType === 'company' && !this.clientFormModel.industry.trim()) {
      this.clientErrors.industry = 'Industry/Business sector is required.';
    }

    if (this.clientFormModel.companyWebsite?.trim()) {
      const websitePattern = /^(https?:\/\/)?[\w.-]+\.[a-z]{2,}(\/.*)?$/i;
      if (!websitePattern.test(this.clientFormModel.companyWebsite.trim())) {
        this.clientErrors.companyWebsite = 'Please enter a valid website URL.';
      }
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
    const hasMobile = this.clientFormModel.primaryContact.mobilePhone?.e164;
    const hasLandline = this.clientFormModel.primaryContact.landlinePhone?.e164;
    if (!hasMobile && !hasLandline) {
      this.clientErrors.primaryContactPhoneNumbers = 'At least one phone number (mobile or landline) is required.';
    } else if (hasMobile && hasLandline) {
      if (this.clientFormModel.primaryContact.mobilePhone?.country !== this.clientFormModel.primaryContact.landlinePhone?.country) {
        this.clientErrors.primaryContactPhoneNumbers = 'Mobile and landline phone numbers must be from the same country.';
      }
    }

    // Secondary Contact (optional)
    const secondary = this.clientFormModel.secondaryContact;
    const secondaryHasAny =
      secondary.name.trim() ||
      secondary.email.trim() ||
      secondary.mobilePhone?.e164 ||
      secondary.landlinePhone?.e164;
    if (secondaryHasAny) {
      if (!secondary.name.trim()) {
        this.clientErrors.secondaryContactName = 'Secondary contact name is required.';
      }
      if (!secondary.email.trim()) {
        this.clientErrors.secondaryContactEmail = 'Secondary contact email is required.';
      } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(secondary.email)) {
        this.clientErrors.secondaryContactEmail = 'Invalid email format.';
      }

      const secondaryHasMobile = secondary.mobilePhone?.e164;
      const secondaryHasLandline = secondary.landlinePhone?.e164;
      if (!secondaryHasMobile && !secondaryHasLandline) {
        this.clientErrors.secondaryContactPhoneNumbers = 'At least one phone number (mobile or landline) is required.';
      } else if (secondaryHasMobile && secondaryHasLandline) {
        if (secondary.mobilePhone?.country !== secondary.landlinePhone?.country) {
          this.clientErrors.secondaryContactPhoneNumbers = 'Mobile and landline phone numbers must be from the same country.';
        }
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
    } else {
      const validCountries = this.countryOptions.map(c => c.value);
      if (validCountries.length && !validCountries.includes(this.clientFormModel.billingAddress.country)) {
        this.clientErrors.billingCountry = 'Please select a valid country from the list.';
      }
    }
    if (this.clientFormModel.billingAddress.country === 'CA' && !this.clientFormModel.billingAddress.province.trim()) {
      this.clientErrors.billingProvince = 'Billing province is required for Canada.';
    } else if (this.clientFormModel.billingAddress.province?.trim()) {
      const validProvinces = this.provinceOptions.map(p => p.value);
      if (validProvinces.length && !validProvinces.includes(this.clientFormModel.billingAddress.province)) {
        this.clientErrors.billingProvince = 'Please select a valid province from the list.';
      }
    }
    if (!this.clientFormModel.billingAddress.postalCode.trim()) {
      this.clientErrors.billingPostalCode = 'Billing postal code is required.';
    } else if (this.clientFormModel.billingAddress.country === 'CA') {
      const postalCodePattern = /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i;
      if (!postalCodePattern.test(this.clientFormModel.billingAddress.postalCode.trim())) {
        this.clientErrors.billingPostalCode = 'Invalid Canadian postal code format (e.g., A1A 1A1).';
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
        business_type: this.clientFormModel.clientType,
        industry: this.clientFormModel.industry || undefined,
        company_registration_number: this.clientFormModel.clientType === 'company'
          ? this.clientFormModel.companyRegistrationNumber
          : '',
        company_website: this.clientFormModel.companyWebsite || undefined,
        tax_vat_number: this.clientFormModel.clientType === 'company'
          ? this.clientFormModel.taxVatNumber || undefined
          : undefined,
        primary_contact: {
          name: this.clientFormModel.primaryContact.name,
          email: this.clientFormModel.primaryContact.email,
          phone: this.clientFormModel.primaryContact.mobilePhone?.e164
            || this.clientFormModel.primaryContact.landlinePhone?.e164
            || ''
        },
        secondary_contact: this.clientFormModel.secondaryContact.name.trim()
          || this.clientFormModel.secondaryContact.email.trim()
          || this.clientFormModel.secondaryContact.mobilePhone?.e164
          || this.clientFormModel.secondaryContact.landlinePhone?.e164
          ? {
              name: this.clientFormModel.secondaryContact.name,
              email: this.clientFormModel.secondaryContact.email,
              phone: this.clientFormModel.secondaryContact.mobilePhone?.e164
                || this.clientFormModel.secondaryContact.landlinePhone?.e164
                || ''
            }
          : undefined,
        billing_address: {
          street: this.clientFormModel.billingAddress.street,
          city: this.clientFormModel.billingAddress.city,
          country: this.clientFormModel.billingAddress.country,
          province: this.clientFormModel.billingAddress.province || '',
          postal_code: this.clientFormModel.billingAddress.postalCode
        }
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