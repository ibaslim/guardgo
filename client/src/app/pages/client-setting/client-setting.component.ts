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
import { GeoLocationPickerComponent } from '../../components/geo-location-picker/geo-location-picker.component';
import { ProfilePictureUploadComponent } from '../../components/profile-picture-upload/profile-picture-upload.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import { TENANT_TYPES } from '../../shared/constants/tenant-types.constants';
import { GoogleMapsAddressConsistencyService } from '../../shared/services/google-maps-address-consistency.service';
import { TenantUpdateResponse } from '../../shared/model/tenant/tenant.model';
import { isValidEmail } from '../../shared/helpers/email.helper';
import {
  buildAlphabeticDummyTag,
  buildSeededCaPhone,
  isLocalhostForDummyData,
  nextDummySeed,
  pickCityValueForProvince,
  pickFirstOptionValue,
} from '../../shared/helpers/onboarding-dummy-data.helper';

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
  latitude: string;
  longitude: string;
}

interface ContactPerson {
  name: string;
  email: string;
  mobilePhone: PhoneNumber | null;
  landlinePhone: PhoneNumber | null;
}

interface BillingCard {
  method: 'credit_card' | 'debit_card';
  cardholderName: string;
  last4: string;
  expiryMonth: string;
  expiryYear: string;
}

interface Site {
  siteName: string;
  siteAddress: Address;
  siteManagerContact: string;
  managerEmail: string;
  numberOfGuardsRequired: number | null;
  siteType: string;
  googleMapsUrl: string;
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
  billingMethod: BillingCard;
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
    GeoLocationPickerComponent,
    ProfilePictureUploadComponent
  ],
  templateUrl: './client-setting.component.html',
  styleUrl: './client-setting.component.css'
})
export class ClientSettingComponent implements OnInit, OnDestroy {
  readonly showDummyDataButton = isLocalhostForDummyData();
  readonly billingExpiryMonthOptions = Array.from({ length: 12 }, (_, index) => {
    const month = String(index + 1).padStart(2, '0');
    return { value: month, label: month };
  });
  readonly billingExpiryYearOptions = Array.from({ length: 11 }, (_, index) => {
    const year = String(new Date().getFullYear() + index);
    return { value: year, label: year };
  });

  @Input() showPageWrapper: boolean = true;
  @Input() readonly: boolean = false;
  @Input() clientData?: Client;
  @Input() profileTenantId?: string;

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
      postalCode: '',
      latitude: '',
      longitude: '',
    },
    billingMethod: {
      method: 'credit_card',
      cardholderName: '',
      last4: '',
      expiryMonth: '',
      expiryYear: '',
    },
    preferredGuardTypes: [],
    sites: []
  };

  clientErrors: any = {};

  isEditMode: boolean = false;

  countryOptions: { value: string; label: string }[] = [];
  provinceOptions: { value: string; label: string }[] = [];
  canadianCitiesByProvinceOptions: Record<string, { value: string; label: string }[]> = {};
  siteTypeOptions: { value: string; label: string }[] = [];
  guardTypeOptions: { value: string; label: string }[] = [];
  clientTypeOptions: { value: string; label: string }[] = [];

  private destroy$ = new Subject<void>();
  private readonly errorFieldPriority = [
    'legalEntityName',
    'industry',
    'companyRegistrationNumber',
    'companyWebsite',
    'primaryContactName',
    'primaryContactEmail',
    'primaryContactMobilePhone',
    'primaryContactLandlinePhone',
    'primaryContactPhoneNumbers',
    'secondaryContactName',
    'secondaryContactEmail',
    'secondaryContactMobilePhone',
    'secondaryContactLandlinePhone',
    'secondaryContactPhoneNumbers',
    'billingStreet',
    'billingCountry',
    'billingProvince',
    'billingCity',
    'billingPostalCode',
    'billingMethod',
    'billingCardholderName',
    'billingCardLast4',
    'billingCardExpiryMonth',
    'billingCardExpiryYear',
    'submit',
  ];

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService,
    private addressConsistencyService: GoogleMapsAddressConsistencyService,
    private notification: MessageNotificationService,
  ) { }

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

  getProfileImageUrl(): string | null {
    if (this.profileTenantId) {
      return `/api/s/static/tenant/${this.profileTenantId}?t=${new Date().getTime()}`;
    }
    return null;
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
          if (response?.canadianCitiesByProvince) {
            this.canadianCitiesByProvinceOptions = response.canadianCitiesByProvince;
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
    const safe = (v: any) => (v === null || v === undefined) ? '' : String(v);

    const legalName = safe((data as any).legalEntityName || (data as any).legal_entity_name || (data as any).legal_name || '');
    const companyReg = safe((data as any).companyRegistrationNumber || (data as any).company_registration_number || '');
    const industry = safe((data as any).industry || (data as any).business_sector || '');
    const website = safe((data as any).companyWebsite || (data as any).company_website || '');
    const tax = safe((data as any).taxVatNumber || (data as any).tax_vat_number || '');

    const primary = (data as any).primaryContact || (data as any).primary_contact || {};
    const secondary = (data as any).secondaryContact || (data as any).secondary_contact || {};
    const billing = (data as any).billingAddress || (data as any).billing_address || {};
    const billingMethod = (data as any).billingMethod || (data as any).billing_method || {};

    const primaryName = safe(primary.name || '');
    const primaryMobile = primary.mobilePhone?.e164 || primary.phone || '';
    const primaryLandline = primary.landlinePhone?.e164 || '';

    const secondaryName = safe(secondary.name || '');
    const secondaryEmail = safe(secondary.email || '');
    const secondaryMobile = secondary.mobilePhone?.e164 || secondary.phone || '';
    const secondaryLandline = secondary.landlinePhone?.e164 || '';

    const billingStreet = safe(billing.street || billing.address_line || '');

    const preferred = Array.isArray((data as any).preferredGuardTypes)
      ? (data as any).preferredGuardTypes
      : Array.isArray((data as any).preferred_guard_types)
        ? (data as any).preferred_guard_types
        : [];

    const sites = Array.isArray((data as any).sites) ? (data as any).sites : [];

    return !!(
      legalName.trim() ||
      companyReg.trim() ||
      industry.trim() ||
      website.trim() ||
      tax.trim() ||
      primaryName.trim() ||
      primaryMobile ||
      primaryLandline ||
      secondaryName.trim() ||
      secondaryEmail.trim() ||
      secondaryMobile ||
      secondaryLandline ||
      billingStreet.trim() ||
      safe(billingMethod.method || billingMethod.type || '').trim() ||
      safe(billingMethod.cardholderName || billingMethod.cardholder_name || '').trim() ||
      safe(billingMethod.last4 || billingMethod.card_last4 || '').trim() ||
      safe(billingMethod.expiryMonth || billingMethod.expiry_month || '').trim() ||
      safe(billingMethod.expiryYear || billingMethod.expiry_year || '').trim() ||
      preferred.some((t: string) => safe(t).trim()) ||
      sites.some((site: any) => safe(site.siteName || site.site_name || '').trim() || safe(site.siteAddress?.street || site.site_address?.street || '').trim())
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
    const provinceCode = (raw?.province || '').toString().trim();
    const rawCity = (raw?.city || '').toString().trim();
    const resolvedCityCode = this.resolveCityCodeForProvince(provinceCode, rawCity);
    const fallbackDefaultCity = this.getDefaultCityCodeForProvince(provinceCode);
    return {
      street: raw?.street || '',
      city: resolvedCityCode || rawCity || fallbackDefaultCity,
      country: raw?.country || 'CA',
      province: provinceCode,
      postalCode: raw?.postal_code || raw?.postalCode || '',
      latitude: raw?.latitude != null ? String(raw.latitude) : '',
      longitude: raw?.longitude != null ? String(raw.longitude) : '',
    };
  }

  private resolveCityCodeForProvince(provinceCode: string, valueOrLabel: string): string {
    const options = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    const normalized = String(valueOrLabel || '').trim();
    if (!normalized) {
      return '';
    }

    const byValue = options.find(option => option.value === normalized.toUpperCase());
    if (byValue) {
      return byValue.value;
    }

    const byLabel = options.find(option => option.label.toLowerCase() === normalized.toLowerCase());
    return byLabel?.value || '';
  }

  private getDefaultCityCodeForProvince(provinceCode: string): string {
    const options = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    return options[0]?.value || '';
  }

  getBillingCityOptions(): { value: string; label: string }[] {
    const provinceCode = this.clientFormModel.billingAddress.province || '';
    const canonical: { value: string; label: string }[] = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    const current = String(this.clientFormModel.billingAddress.city || '').trim();
    if (!current) {
      return canonical;
    }

    const exists = canonical.some(option => option.value === current);
    if (exists) {
      return canonical;
    }

    return [...canonical, { value: current, label: current }];
  }

  onBillingProvinceChange(nextProvinceCode: string): void {
    this.clientFormModel.billingAddress.province = nextProvinceCode;
    const options = this.getBillingCityOptions();
    const isCurrentValid = options.some(city => city.value === this.clientFormModel.billingAddress.city);
    if (!isCurrentValid) {
      this.clientFormModel.billingAddress.city = this.getDefaultCityCodeForProvince(nextProvinceCode);
    }
  }

  createEmptySite(): Site {
    return {
      siteName: '',
      siteAddress: {
        street: '',
        city: '',
        country: 'CA',
        province: '',
        postalCode: '',
        latitude: '',
        longitude: '',
      },
      siteManagerContact: '',
      managerEmail: '',
      numberOfGuardsRequired: null,
      siteType: '',
      googleMapsUrl: '',
    };
  }

  addSite(): void {
    this.clientFormModel.sites = [...this.clientFormModel.sites, this.createEmptySite()];
  }

  removeSite(index: number): void {
    this.clientFormModel.sites = this.clientFormModel.sites.filter((_site, siteIndex) => siteIndex !== index);
    Object.keys(this.clientErrors)
      .filter((key) => key.startsWith('sites.'))
      .forEach((key) => delete this.clientErrors[key]);
  }

  getSiteCityOptions(siteIndex: number): { value: string; label: string }[] {
    const site = this.clientFormModel.sites[siteIndex];
    const provinceCode = site?.siteAddress.province || '';
    const canonical: { value: string; label: string }[] = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    const current = String(site?.siteAddress.city || '').trim();
    if (!current) {
      return canonical;
    }

    const exists = canonical.some((option) => option.value === current);
    if (exists) {
      return canonical;
    }

    return [...canonical, { value: current, label: current }];
  }

  onSiteProvinceChange(siteIndex: number, nextProvinceCode: string): void {
    const site = this.clientFormModel.sites[siteIndex];
    if (!site) {
      return;
    }

    site.siteAddress.province = nextProvinceCode;
    const options = this.getSiteCityOptions(siteIndex);
    const isCurrentValid = options.some((city) => city.value === site.siteAddress.city);
    if (!isCurrentValid) {
      site.siteAddress.city = this.getDefaultCityCodeForProvince(nextProvinceCode);
    }
  }

  getSiteAddressCityLabel(siteIndex: number): string {
    const site = this.clientFormModel.sites[siteIndex];
    if (!site) {
      return '';
    }

    return this.getCityLabelForProvince(site.siteAddress.province || '', site.siteAddress.city || '');
  }

  private getCityLabelForProvince(provinceCode: string, cityCode: string): string {
    const options = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    const raw = String(cityCode || '').trim();
    const normalized = raw.toUpperCase();
    return options.find(option => option.value === normalized)?.label || raw;
  }

  private transformBackendDataToForm(data: any): Client {
    const profile = data?.profile || data || {};
    const primaryContact = profile.primary_contact || profile.primaryContact || {};
    const secondaryContact = profile.secondary_contact || profile.secondaryContact || {};
    const billingAddress = this.mapAddressFromBackend(profile.billing_address || profile.billingAddress || {});
    const billingMethod = profile.billing_method || profile.billingMethod || {};
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
          siteType: this.normalizeOptionValue(site.site_type || site.siteType || '', this.siteTypeOptions),
          googleMapsUrl: site.google_maps_url || site.googleMapsUrl || '',
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
      billingMethod: this.normalizeBillingMethod(billingMethod),
      preferredGuardTypes: normalizedPreferredTypes.length > 0 ? normalizedPreferredTypes : [],
      sites: mappedSites
    };
  }

  private normalizeBillingMethod(raw: any): BillingCard {
    const method = String(raw?.method || raw?.type || '').trim().toLowerCase();
    const normalizedMethod: 'credit_card' | 'debit_card' = method === 'debit_card' ? 'debit_card' : 'credit_card';
    return {
      method: normalizedMethod,
      cardholderName: String(raw?.cardholderName || raw?.cardholder_name || '').trim(),
      last4: String(raw?.last4 || raw?.card_last4 || '').trim(),
      expiryMonth: String(raw?.expiryMonth || raw?.expiry_month || '').trim(),
      expiryYear: String(raw?.expiryYear || raw?.expiry_year || '').trim(),
    };
  }

  validateClientForm(): boolean {
    this.clientErrors = {};

    // Legal Entity Name
    if (!this.clientFormModel.legalEntityName || this.clientFormModel.legalEntityName.trim() === '') {
      this.clientErrors.legalEntityName = this.clientFormModel.clientType === 'individual'
        ? 'Full name is required.'
        : 'Legal Entity Name is required.';
    } else if (this.clientFormModel.clientType === 'individual' && !/^[a-zA-Z\s]+$/.test(this.clientFormModel.legalEntityName)) {
      this.clientErrors.legalEntityName = 'Full name can only contain letters and spaces.';
    }

    // Company Registration Number
    if (!this.clientFormModel.companyRegistrationNumber || this.clientFormModel.companyRegistrationNumber.trim() === '') {
      if (this.clientFormModel.clientType === 'company') {
        this.clientErrors.companyRegistrationNumber = 'Company Registration Number is required.';
      }
    }

    if (this.clientFormModel.clientType === 'company') {
      if (!this.clientFormModel.industry.trim()) {
        this.clientErrors.industry = 'Industry/Business sector is required.';
      } else if (!/^[a-zA-Z\s]+$/.test(this.clientFormModel.industry)) {
        this.clientErrors.industry = 'Industry can only contain letters and spaces.';
      }
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
    } else if (!/^[a-zA-Z\s]+$/.test(this.clientFormModel.primaryContact.name)) {
      this.clientErrors.primaryContactName = 'Contact name can only contain letters and spaces.';
    }
    if (!this.clientFormModel.primaryContact.email.trim()) {
      this.clientErrors.primaryContactEmail = 'Primary contact email is required.';
    } else if (!isValidEmail(this.clientFormModel.primaryContact.email)) {
      this.clientErrors.primaryContactEmail = 'Invalid email format.';
    }
    const hasMobile = this.clientFormModel.primaryContact.mobilePhone?.e164;
    const hasLandline = this.clientFormModel.primaryContact.landlinePhone?.e164;

    // Validate mobile phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasMobile) {
      const mobileE164 = this.clientFormModel.primaryContact.mobilePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(mobileE164)) {
        this.clientErrors.primaryContactMobilePhone = 'Invalid Canadian mobile phone number format.';
      } else if (this.clientFormModel.primaryContact.mobilePhone!.country !== 'CA') {
        this.clientErrors.primaryContactMobilePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    // Validate landline phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasLandline) {
      const landlineE164 = this.clientFormModel.primaryContact.landlinePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(landlineE164)) {
        this.clientErrors.primaryContactLandlinePhone = 'Invalid Canadian landline phone number format.';
      } else if (this.clientFormModel.primaryContact.landlinePhone!.country !== 'CA') {
        this.clientErrors.primaryContactLandlinePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    // At least one phone number is required
    if (!hasMobile && !hasLandline) {
      this.clientErrors.primaryContactPhoneNumbers = 'At least one phone number (mobile or landline) is required.';
    }

    // If both phone numbers are provided, they must be from the same country
    if (hasMobile && hasLandline) {
      if (this.clientFormModel.primaryContact.mobilePhone?.country !== this.clientFormModel.primaryContact.landlinePhone?.country) {
        this.clientErrors.primaryContactPhoneNumbers = 'Mobile and landline phone numbers must be from the same country.';
      }
    }

    // Secondary Contact (required)
    const secondary = this.clientFormModel.secondaryContact;

    if (!secondary.name.trim()) {
      this.clientErrors.secondaryContactName = 'Secondary contact name is required.';
    } else if (!/^[a-zA-Z\s]+$/.test(secondary.name)) {
      this.clientErrors.secondaryContactName = 'Contact name can only contain letters and spaces.';
    }

    if (!secondary.email.trim()) {
      this.clientErrors.secondaryContactEmail = 'Secondary contact email is required.';
    } else if (!isValidEmail(secondary.email)) {
      this.clientErrors.secondaryContactEmail = 'Invalid email format.';
    }

    const secondaryHasMobile = secondary.mobilePhone?.e164;
    const secondaryHasLandline = secondary.landlinePhone?.e164;

    if (secondaryHasMobile) {
      const secondaryMobileE164 = secondary.mobilePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(secondaryMobileE164)) {
        this.clientErrors.secondaryContactMobilePhone = 'Invalid Canadian mobile phone number format.';
      } else if (secondary.mobilePhone!.country !== 'CA') {
        this.clientErrors.secondaryContactMobilePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    if (secondaryHasLandline) {
      const secondaryLandlineE164 = secondary.landlinePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(secondaryLandlineE164)) {
        this.clientErrors.secondaryContactLandlinePhone = 'Invalid Canadian landline phone number format.';
      } else if (secondary.landlinePhone!.country !== 'CA') {
        this.clientErrors.secondaryContactLandlinePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    // At least one phone number is required
    if (!secondaryHasMobile && !secondaryHasLandline) {
      this.clientErrors.secondaryContactPhoneNumbers = 'At least one phone number (mobile or landline) is required.';
    }

    // If both provided, must be same country
    if (secondaryHasMobile && secondaryHasLandline) {
      if (secondary.mobilePhone?.country !== secondary.landlinePhone?.country) {
        this.clientErrors.secondaryContactPhoneNumbers = 'Mobile and landline phone numbers must be from the same country.';
      }
    }

    // Billing Address
    if (!this.clientFormModel.billingAddress.street.trim()) {
      this.clientErrors.billingStreet = 'Billing street is required.';
    }
    if (!this.clientFormModel.billingAddress.city.trim()) {
      this.clientErrors.billingCity = 'Billing city is required.';
    } else {
      const cityOptions = this.getBillingCityOptions();
      if (cityOptions.length && !cityOptions.some(city => city.value === this.clientFormModel.billingAddress.city)) {
        this.clientErrors.billingCity = 'Please select a valid city for the selected province.';
      }
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

    // Billing Method
    if (!this.clientFormModel.billingMethod.method) {
      this.clientErrors.billingMethod = 'Billing method is required.';
    }
    if (!this.clientFormModel.billingMethod.cardholderName.trim()) {
      this.clientErrors.billingCardholderName = 'Cardholder name is required.';
    }
    if (!/^[0-9]{4}$/.test(this.clientFormModel.billingMethod.last4.trim())) {
      this.clientErrors.billingCardLast4 = 'Enter the last 4 digits of the card.';
    }
    if (!/^(0[1-9]|1[0-2])$/.test(this.clientFormModel.billingMethod.expiryMonth.trim())) {
      this.clientErrors.billingCardExpiryMonth = 'Expiry month must be two digits between 01 and 12.';
    }
    if (!/^\d{2,4}$/.test(this.clientFormModel.billingMethod.expiryYear.trim())) {
      this.clientErrors.billingCardExpiryYear = 'Expiry year must be 2 to 4 digits.';
    }

    this.clientFormModel.sites.forEach((site, index) => {
      const errorPrefix = `sites.${index}.`;

      if (!site.siteName.trim()) {
        this.clientErrors[`${errorPrefix}siteName`] = 'Site name is required.';
      }

      if (!site.siteType.trim()) {
        this.clientErrors[`${errorPrefix}siteType`] = 'Site type is required.';
      }

      if (!site.siteAddress.street.trim()) {
        this.clientErrors[`${errorPrefix}street`] = 'Site street is required.';
      }

      if (!site.siteAddress.country.trim()) {
        this.clientErrors[`${errorPrefix}country`] = 'Site country is required.';
      }

      if (site.siteAddress.country === 'CA' && !site.siteAddress.province.trim()) {
        this.clientErrors[`${errorPrefix}province`] = 'Site province is required for Canada.';
      } else if (site.siteAddress.province.trim()) {
        const validProvinces = this.provinceOptions.map((p) => p.value);
        if (validProvinces.length && !validProvinces.includes(site.siteAddress.province)) {
          this.clientErrors[`${errorPrefix}province`] = 'Please select a valid province from the list.';
        }
      }

      if (!site.siteAddress.city.trim()) {
        this.clientErrors[`${errorPrefix}city`] = 'Site city is required.';
      } else {
        const cityOptions = this.getSiteCityOptions(index);
        if (cityOptions.length && !cityOptions.some((city) => city.value === site.siteAddress.city)) {
          this.clientErrors[`${errorPrefix}city`] = 'Please select a valid city for the selected province.';
        }
      }

      if (!site.siteAddress.postalCode.trim()) {
        this.clientErrors[`${errorPrefix}postalCode`] = 'Site postal code is required.';
      } else if (site.siteAddress.country === 'CA') {
        const postalCodePattern = /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i;
        if (!postalCodePattern.test(site.siteAddress.postalCode.trim())) {
          this.clientErrors[`${errorPrefix}postalCode`] = 'Invalid Canadian postal code format (e.g., A1A 1A1).';
        }
      }

      if (site.managerEmail.trim() && !isValidEmail(site.managerEmail)) {
        this.clientErrors[`${errorPrefix}managerEmail`] = 'Invalid email format.';
      }

      const latitude = Number(site.siteAddress.latitude);
      const longitude = Number(site.siteAddress.longitude);

      if (!String(site.siteAddress.latitude || '').trim()) {
        this.clientErrors[`${errorPrefix}latitude`] = 'Latitude is required.';
      } else if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
        this.clientErrors[`${errorPrefix}latitude`] = 'Latitude must be between -90 and 90.';
      }

      if (!String(site.siteAddress.longitude || '').trim()) {
        this.clientErrors[`${errorPrefix}longitude`] = 'Longitude is required.';
      } else if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
        this.clientErrors[`${errorPrefix}longitude`] = 'Longitude must be between -180 and 180.';
      }

      if (
        this.clientErrors[`${errorPrefix}latitude`]
        || this.clientErrors[`${errorPrefix}longitude`]
      ) {
        this.clientErrors[`${errorPrefix}coordinates`] = 'Valid coordinates are required for every saved client site.';
      }

      const recommendedGuardsRaw = String(site.numberOfGuardsRequired ?? '').trim();
      if (recommendedGuardsRaw) {
        const recommendedGuards = Number(recommendedGuardsRaw);
        if (!Number.isFinite(recommendedGuards) || recommendedGuards < 1) {
          this.clientErrors[`${errorPrefix}numberOfGuardsRequired`] = 'Recommended guards must be at least 1 when provided.';
        }
      }
    });

    return Object.keys(this.clientErrors).length === 0;
  }

  async submitClientForm() {
    if (this.readonly) {
      return;
    }

    if (!this.validateClientForm()) {
      this.handleValidationFailure();
      return;
    }

    if (!(await this.validateSiteAddressConsistency())) {
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
        secondary_contact: {
          name: this.clientFormModel.secondaryContact.name,
          email: this.clientFormModel.secondaryContact.email,
          phone: this.clientFormModel.secondaryContact.mobilePhone?.e164
            || this.clientFormModel.secondaryContact.landlinePhone?.e164
            || ''
        },
        billing_address: {
          street: this.clientFormModel.billingAddress.street,
          city: this.getCityLabelForProvince(
            this.clientFormModel.billingAddress.province || '',
            this.clientFormModel.billingAddress.city
          ),
          country: this.clientFormModel.billingAddress.country,
          province: this.clientFormModel.billingAddress.province || '',
          postal_code: this.clientFormModel.billingAddress.postalCode
        },
        billing_method: {
          method: this.clientFormModel.billingMethod.method,
          cardholder_name: this.clientFormModel.billingMethod.cardholderName.trim(),
          last4: this.clientFormModel.billingMethod.last4.trim(),
          expiry_month: this.clientFormModel.billingMethod.expiryMonth.trim(),
          expiry_year: this.clientFormModel.billingMethod.expiryYear.trim(),
        },
        sites: this.clientFormModel.sites.map((site) => ({
          site_name: site.siteName.trim(),
          site_manager_contact: site.siteManagerContact.trim() || undefined,
          manager_email: site.managerEmail.trim() || undefined,
          number_of_guards_required: String(site.numberOfGuardsRequired ?? '').trim()
            ? Number(site.numberOfGuardsRequired)
            : undefined,
          site_type: site.siteType || undefined,
          google_maps_url: site.googleMapsUrl.trim() || undefined,
          site_address: {
            street: site.siteAddress.street.trim(),
            city: this.getCityLabelForProvince(site.siteAddress.province || '', site.siteAddress.city),
            country: site.siteAddress.country,
            province: site.siteAddress.province || '',
            postal_code: site.siteAddress.postalCode.trim(),
            latitude: Number(site.siteAddress.latitude),
            longitude: Number(site.siteAddress.longitude),
          }
        }))
      },
      status: 'active'
    };

    const isOnboarding = this.appService.userSessionData().tenant.has_onboarding;
    tenantUpdatePayload.status = isOnboarding ? 'pending_activation' : 'active';

    this.apiService.put<TenantUpdateResponse>('tenant', tenantUpdatePayload).subscribe({
      next: (response) => {
        console.log('Client profile submitted successfully', response);
        const newStatus = String(response?.status || (isOnboarding ? 'pending_activation' : 'active')).toLowerCase();
        this.appService.setTenantStatus(newStatus, false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error('Error submitting client profile:', err);
        this.clientErrors.submit = err?.error?.detail || 'Failed to submit client profile.';
      }
    });
  }

  fillDummyData(): void {
    const seed = nextDummySeed();
    const nameTag = buildAlphabeticDummyTag(seed.sequence);
    const province = pickFirstOptionValue(this.provinceOptions, 'ON');
    const city = pickCityValueForProvince(this.canadianCitiesByProvinceOptions, province, 'TORONTO');
    const legalEntityName = `Local Test Client ${nameTag} Inc`;

    this.clientFormModel.clientType = 'company';
    this.clientFormModel.legalEntityName = legalEntityName;
    this.clientFormModel.industry = 'Security';
    this.clientFormModel.companyRegistrationNumber = `CL-REG-${seed.suffix}`;
    this.clientFormModel.companyWebsite = `https://local-client-${seed.suffix}.example.com`;
    this.clientFormModel.taxVatNumber = `TAX-${seed.suffix}`;
    this.clientFormModel.primaryContact = {
      name: `Primary Client Contact ${nameTag}`,
      email: `client.primary+${seed.suffix}@example.com`,
      mobilePhone: buildSeededCaPhone(seed.phoneSuffix, 10, 'mobile'),
      landlinePhone: buildSeededCaPhone(seed.phoneSuffix, 16, 'landline'),
    };
    this.clientFormModel.secondaryContact = {
      name: `Secondary Client Contact ${nameTag}`,
      email: `client.secondary+${seed.suffix}@example.com`,
      mobilePhone: buildSeededCaPhone(seed.phoneSuffix, 11, 'mobile'),
      landlinePhone: buildSeededCaPhone(seed.phoneSuffix, 17, 'landline'),
    };
    this.clientFormModel.billingAddress = {
      street: `${200 + seed.sequence} Client Avenue`,
      city,
      country: 'CA',
      province,
      postalCode: 'M5H 2N2',
      latitude: '',
      longitude: '',
    };
    this.clientFormModel.billingMethod = {
      method: 'credit_card',
      cardholderName: `Client Billing ${nameTag}`,
      last4: '4242',
      expiryMonth: '12',
      expiryYear: '29',
    };
    this.clientFormModel.sites = [{
      siteName: `Primary Operations Site ${nameTag}`,
      siteAddress: {
        street: `${100 + seed.sequence} Front Street W`,
        city,
        country: 'CA',
        province,
        postalCode: 'M5V 2T6',
        latitude: '43.644865',
        longitude: '-79.394820',
      },
      siteManagerContact: `Site Manager ${nameTag}`,
      managerEmail: `site.manager+${seed.suffix}@example.com`,
      numberOfGuardsRequired: 2,
      siteType: this.siteTypeOptions[0]?.value || '',
      googleMapsUrl: 'https://maps.google.com/?q=43.644865,-79.394820',
    }];
    this.clientErrors = {};
  }

  private async validateSiteAddressConsistency(): Promise<boolean> {
    for (let index = 0; index < this.clientFormModel.sites.length; index += 1) {
      const site = this.clientFormModel.sites[index];
      const result = await this.addressConsistencyService.validate({
        latitude: site.siteAddress.latitude,
        longitude: site.siteAddress.longitude,
        expectedCountryCode: site.siteAddress.country,
        expectedCountryName: this.countryOptions.find((option) => option.value === site.siteAddress.country)?.label || site.siteAddress.country,
        expectedProvinceCode: site.siteAddress.province,
        expectedProvinceName: this.provinceOptions.find((option) => option.value === site.siteAddress.province)?.label || site.siteAddress.province,
        expectedCity: this.getSiteAddressCityLabel(index),
        expectedPostalCode: site.siteAddress.postalCode,
      });

      if (!result.ok) {
        this.clientErrors[`sites.${index}.coordinates`] = result.message || 'The selected coordinates do not match the site address.';
        this.handleValidationFailure();
        return false;
      }
    }

    return true;
  }

  private handleValidationFailure(): void {
    const firstErrorKey = this.getFirstValidationErrorKey();
    const message = firstErrorKey
      ? this.clientErrors[firstErrorKey]
      : 'Please review the highlighted fields before submitting.';
    this.notification.error(message || 'Please review the highlighted fields before submitting.', 5000);
    this.scrollToErrorField(firstErrorKey);
  }

  private getFirstValidationErrorKey(): string {
    const keys = Object.keys(this.clientErrors).filter(key => !!this.clientErrors[key]);
    if (!keys.length) {
      return '';
    }
    return this.errorFieldPriority.find(key => keys.includes(key))
      || keys.find(key => key.startsWith('sites.'))
      || keys[0];
  }

  private scrollToErrorField(errorKey: string): void {
    const controlName = this.getControlNameForErrorKey(errorKey);
    if (!controlName || typeof document === 'undefined') {
      return;
    }
    const escapedControlName = this.escapeCssValue(controlName);
    const target = document.querySelector<HTMLElement>(
      `[name="${escapedControlName}"], [data-control-name="${escapedControlName}"]`
    );
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    window.setTimeout(() => {
      this.findFocusableElement(target)?.focus({ preventScroll: true });
    }, 250);
  }

  private getControlNameForErrorKey(errorKey: string): string {
    const directMap: Record<string, string> = {
      legalEntityName: 'legalEntityName',
      industry: 'industry',
      companyRegistrationNumber: 'companyRegistrationNumber',
      companyWebsite: 'companyWebsite',
      primaryContactName: 'primaryContactName',
      primaryContactEmail: 'primaryContactEmail',
      primaryContactMobilePhone: 'primaryContactMobile',
      primaryContactLandlinePhone: 'primaryContactLandline',
      primaryContactPhoneNumbers: 'primaryContactMobile',
      secondaryContactName: 'secondaryContactName',
      secondaryContactEmail: 'secondaryContactEmail',
      secondaryContactMobilePhone: 'secondaryContactMobile',
      secondaryContactLandlinePhone: 'secondaryContactLandline',
      secondaryContactPhoneNumbers: 'secondaryContactMobile',
      billingStreet: 'billingStreet',
      billingCountry: 'billingCountry',
      billingProvince: 'billingProvince',
      billingCity: 'billingCity',
      billingPostalCode: 'billingPostalCode',
      billingMethod: 'billingCardType',
      billingCardholderName: 'billingCardholderName',
      billingCardLast4: 'billingCardLast4',
      billingCardExpiryMonth: 'billingCardExpiryMonth',
      billingCardExpiryYear: 'billingCardExpiryYear',
    };
    if (directMap[errorKey]) {
      return directMap[errorKey];
    }

    const siteMatch = errorKey.match(/^sites\.(\d+)\.(siteName|siteType|managerEmail|numberOfGuardsRequired|latitude|longitude|coordinates|country|province|city|postalCode|street)$/);
    if (siteMatch) {
      const index = siteMatch[1];
      const suffixMap: Record<string, string> = {
        siteName: `siteName${index}`,
        siteType: `siteType${index}`,
        managerEmail: `siteManagerEmail${index}`,
        numberOfGuardsRequired: `siteRecommendedGuards${index}`,
        latitude: `siteLatitude${index}`,
        longitude: `siteLongitude${index}`,
        coordinates: `siteLatitude${index}`,
        country: `siteCountry${index}`,
        province: `siteProvince${index}`,
        city: `siteCity${index}`,
        postalCode: `sitePostalCode${index}`,
        street: `siteStreet${index}`,
      };
      return suffixMap[siteMatch[2]] || '';
    }

    return '';
  }

  private findFocusableElement(element: HTMLElement): HTMLElement | null {
    if (this.isFocusable(element)) {
      return element;
    }
    return element.querySelector<HTMLElement>(
      'input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
  }

  private isFocusable(element: HTMLElement): boolean {
    const tagName = element.tagName.toLowerCase();
    return (
      ['input', 'button', 'select', 'textarea', 'a'].includes(tagName) ||
      element.hasAttribute('tabindex')
    ) && !element.hasAttribute('disabled');
  }

  private escapeCssValue(value: string): string {
    if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
      return CSS.escape(value);
    }
    return value.replace(/["\\]/g, '\\$&');
  }
}
