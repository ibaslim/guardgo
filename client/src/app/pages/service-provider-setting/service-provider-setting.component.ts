import { CommonModule } from '@angular/common';
import { Component, Input, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { MobilePhoneInputComponent } from '../../components/form/phone-input/mobile-phone-input.component';
import { LandlinePhoneInputComponent } from '../../components/form/phone-input/landline-phone-input.component';
import { PageComponent } from '../../components/page/page.component';
import { SectionComponent } from '../../components/section/section.component';
import { ButtonComponent } from '../../components/button/button.component';
import { StickyActionBarComponent } from '../../components/sticky-action-bar/sticky-action-bar.component';
import { ErrorMessageComponent } from "../../components/error-message/error-message.component";
import { ProfilePictureUploadComponent } from '../../components/profile-picture-upload/profile-picture-upload.component';
import { CardComponent } from '../../components/card/card.component';
import { ClientPreferredGuardTypesComponent } from '../../components/client-preferred-guard-types/client-preferred-guard-types.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { TENANT_TYPES } from '../../shared/constants/tenant-types.constants';
import { getIssuingAuthorityForProvince } from '../../shared/constants/provincial-authorities.constants';
import { DistanceUnit, formatDistance, kmToMiles, milesToKm } from '../../shared/helpers/distance.helper';

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

interface SecurityLicense {
  licenseNumber: string;
  licenseType: string;
  issuingProvince: string;
  issuingAuthority: string;
  issueDate: string;
  expiryDate: string;
  file?: File | null;
  id?: string;
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

interface OperatingRegion {
  country: string;
  regionCode: string;
  cityEntries: { cityCode: string; coverageRadiusKm: number | null }[];
}

interface InsurancePolicy {
  policyNumber: string;
  coverageAmount: number | null;
  currency: string;
  expiryDate: string;
  coverageDetails: string;
  file?: File | null;
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

interface ServiceProvider {
  legalCompanyName: string;
  tradingName: string;
  corporationNumber: string;
  yearOfEstablishment: number | null;
  companyWebsite: string;
  taxRegistrationNumber: string;
  headOfficeAddress: Address;
  primaryRepresentative: ContactPerson;
  secondaryContact: ContactPerson;
  securityLicenses: SecurityLicense[];
  insuranceDetails: InsurancePolicy;
  operatingRegions: OperatingRegion[];
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
    SelectInputComponent,
    MobilePhoneInputComponent,
    LandlinePhoneInputComponent,
    PageComponent,
    SectionComponent,
    ButtonComponent,
    StickyActionBarComponent,
    ErrorMessageComponent,
    ProfilePictureUploadComponent,
    CardComponent,
    ClientPreferredGuardTypesComponent
  ],
  templateUrl: './service-provider-setting.component.html',
  styleUrls: ['./service-provider-setting.component.css']
})
export class ServiceProviderSettingComponent implements OnInit, OnDestroy {

  @Input() showPageWrapper: boolean = true;
  @Input() readonly: boolean = false;
  @Input() providerData?: ServiceProvider;
  @Input() profileTenantId?: string;

  providerFormModel: ServiceProvider = {
    legalCompanyName: '',
    tradingName: '',
    corporationNumber: '',
    yearOfEstablishment: null,
    companyWebsite: '',
    taxRegistrationNumber: '',
    headOfficeAddress: {
      street: '',
      city: '',
      country: 'CA',
      province: '',
      postalCode: ''
    },
    primaryRepresentative: {
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
    securityLicenses: [
      {
        licenseNumber: '',
        licenseType: '',
        issuingProvince: '',
        issuingAuthority: '',
        issueDate: '',
        expiryDate: '',
        file: null,
        id: `sec_license_initial_${Date.now()}`
      }
    ],
    insuranceDetails: {
      policyNumber: '',
      coverageAmount: null,
      currency: 'CAD',
      expiryDate: '',
      coverageDetails: '',
      file: null
    },
    operatingRegions: [
      {
        country: 'CA',
        regionCode: '',
        cityEntries: [{ cityCode: '', coverageRadiusKm: null }]
      }
    ],
    guardCategoriesOffered: []
  };

  providerErrors: any = {};

  isEditMode: boolean = false;

  countryOptions: { value: string; label: string }[] = [];
  provinceOptions: { value: string; label: string }[] = [];
  canadianCitiesByProvinceOptions: Record<string, { value: string; label: string }[]> = {};
  securityLicenseTypeOptions: { value: string; label: string }[] = [];
  guardTypeOptions: { value: string; label: string }[] = [];
  selectedDistanceUnit: DistanceUnit = 'km';
  readonly distanceUnitOptions: { value: DistanceUnit; label: string }[] = [
    { value: 'km', label: 'Kilometers (km)' },
    { value: 'mi', label: 'Miles (mi)' }
  ];

  securityLicenseUploadInProgress: Record<string, boolean> = {};
  securityLicenseUploadErrors: Record<string, string> = {};
  insuranceUploadInProgress: boolean = false;
  insuranceUploadError: string = '';

  private destroy$ = new Subject<void>();

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) { }

  ngOnInit(): void {
    const preferredUnit = this.appService.getConfig().localSettings.distanceUnit;
    this.selectedDistanceUnit = preferredUnit === 'mi' ? 'mi' : 'km';

    this.loadProviderMetadata(() => {
      if (this.providerData && this.hasProviderData(this.providerData)) {
        this.providerFormModel = this.transformBackendDataToForm(this.providerData as any);
        this.isEditMode = true;
      } else {
        this.isEditMode = false;
      }

      if (!this.providerFormModel.headOfficeAddress.country) {
        this.providerFormModel.headOfficeAddress.country = 'CA';
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

  private loadProviderMetadata(onLoaded?: () => void): void {
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
          onLoaded?.();
        },
        error: () => {
          onLoaded?.();
        }
      });

    this.apiService.get<any>('public/guard-metadata')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          if (response?.securityLicenseTypes?.length) {
            this.securityLicenseTypeOptions = response.securityLicenseTypes;
          }
          if (response?.guardTypeOptions?.length) {
            this.guardTypeOptions = response.guardTypeOptions;
          }
        }
      });
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
    const resolvedCityCode = this.resolveCityCodeForRegion(provinceCode, rawCity);
    const fallbackDefaultCity = this.getCityOptionsForRegion(provinceCode)[0]?.value || '';
    return {
      street: raw?.street || '',
      city: resolvedCityCode || rawCity || fallbackDefaultCity,
      country: raw?.country || 'CA',
      province: provinceCode,
      postalCode: raw?.postal_code || raw?.postalCode || ''
    };
  }

  getHeadOfficeCityOptions(): { value: string; label: string }[] {
    const provinceCode = this.providerFormModel.headOfficeAddress.province;
    const canonical = this.getCityOptionsForRegion(provinceCode);
    const current = String(this.providerFormModel.headOfficeAddress.city || '').trim();
    if (!current) {
      return canonical;
    }

    const exists = canonical.some(option => option.value === current);
    if (exists) {
      return canonical;
    }

    return [...canonical, { value: current, label: current }];
  }

  onHeadOfficeProvinceChange(nextProvinceCode: string): void {
    this.providerFormModel.headOfficeAddress.province = nextProvinceCode;
    const options = this.getHeadOfficeCityOptions();
    const isCurrentValid = options.some(option => option.value === this.providerFormModel.headOfficeAddress.city);
    if (!isCurrentValid) {
      this.providerFormModel.headOfficeAddress.city = '';
    }
  }

  /**
   * Get the suggested issuing authority for a given province code
   * @param provinceCode - Two-letter province code (e.g., 'ON', 'AB')
   * @returns The issuing authority name for the province
   */
  getSuggestedIssuingAuthority(provinceCode: string): string {
    return getIssuingAuthorityForProvince(provinceCode);
  }

  /**
 * Handle changes to the issuing province field
 * Auto-populates the issuing authority based on the selected province
 */
  onIssuingProvinceChange(license: SecurityLicense): void {
    const province = license.issuingProvince;
    if (province) {
      const authority = this.getSuggestedIssuingAuthority(province);
      if (authority) {
        license.issuingAuthority = authority;
      }
    }
  }

  get coverageRadiusLabel(): string {
    return `Coverage Radius (${this.selectedDistanceUnit})`;
  }

  get minimumCoverageRadiusDisplay(): number {
    return this.selectedDistanceUnit === 'mi' ? kmToMiles(1) : 1;
  }

  get minimumCoverageRadiusText(): string {
    return formatDistance(this.minimumCoverageRadiusDisplay, this.selectedDistanceUnit);
  }

  onDistanceUnitChange(nextUnitRaw: string): void {
    const nextUnit: DistanceUnit = nextUnitRaw === 'mi' ? 'mi' : 'km';
    if (nextUnit === this.selectedDistanceUnit) {
      return;
    }

    this.providerFormModel.operatingRegions = this.providerFormModel.operatingRegions.map((region) => {
      return {
        ...region,
        cityEntries: (region.cityEntries || []).map((entry) => {
          const normalizedRadius = this.normalizeCoverageRadius(entry.coverageRadiusKm);
          if (normalizedRadius == null) {
            return entry;
          }
          return {
            ...entry,
            coverageRadiusKm: this.convertDistanceBetweenUnits(normalizedRadius, this.selectedDistanceUnit, nextUnit)
          };
        })
      };
    });

    this.selectedDistanceUnit = nextUnit;
    this.appService.set('distanceUnit', nextUnit);
  }

  private toDisplayDistance(kmValue: number): number {
    return this.selectedDistanceUnit === 'mi'
      ? kmToMiles(kmValue)
      : Number(kmValue.toFixed(1));
  }

  private toStorageKm(displayValue: number): number {
    return this.selectedDistanceUnit === 'mi'
      ? milesToKm(displayValue)
      : Number(displayValue.toFixed(2));
  }

  private convertDistanceBetweenUnits(value: number, from: DistanceUnit, to: DistanceUnit): number {
    if (from === to) {
      return value;
    }
    return from === 'km' ? kmToMiles(value) : milesToKm(value);
  }

  private normalizeCoverageRadius(value: unknown): number | null {
    if (value == null) {
      return null;
    }
    if (typeof value === 'string' && !value.trim()) {
      return null;
    }
    const normalized = Number(value);
    return Number.isFinite(normalized) ? normalized : null;
  }

  getCoverageRadiusDualLabel(displayRadius: number | null | undefined): string {
    const displayValue = Number(displayRadius);
    if (!Number.isFinite(displayValue) || displayValue <= 0) {
      return '';
    }

    const kmValue = this.toStorageKm(displayValue);
    const miValue = kmToMiles(kmValue);
    if (this.selectedDistanceUnit === 'mi') {
      return `${formatDistance(miValue, 'mi')} (${formatDistance(kmValue, 'km')})`;
    }
    return `${formatDistance(kmValue, 'km')} (${formatDistance(miValue, 'mi')})`;
  }

  getCityOptionsForRegion(regionCode: string): { value: string; label: string }[] {
    if (!regionCode) {
      return [];
    }
    return this.canadianCitiesByProvinceOptions[regionCode] || [];
  }

  getProvinceLabel(regionCode: string): string {
    const normalized = String(regionCode || '').trim().toUpperCase();
    if (!normalized) {
      return '';
    }
    return this.provinceOptions.find(option => option.value === normalized)?.label || normalized;
  }

  onRegionCodeChange(index: number, regionCode: string): void {
    const region = this.providerFormModel.operatingRegions[index];
    if (!region) {
      return;
    }

    region.regionCode = regionCode;
    const options = this.getCityOptionsForRegion(regionCode);
    region.cityEntries = (region.cityEntries || []).map((entry) => {
      const normalized = String(entry.cityCode || '').trim().toUpperCase();
      return {
        ...entry,
        cityCode: options.some(opt => opt.value === normalized) ? normalized : ''
      };
    });

    if (!region.cityEntries.length) {
      region.cityEntries = [{ cityCode: '', coverageRadiusKm: null }];
    }
  }

  addRegionCity(index: number): void {
    const region = this.providerFormModel.operatingRegions[index];
    if (!region) {
      return;
    }
    region.cityEntries = [...(region.cityEntries || []), { cityCode: '', coverageRadiusKm: null }];
  }

  removeRegionCity(regionIndex: number, cityIndex: number): void {
    const region = this.providerFormModel.operatingRegions[regionIndex];
    if (!region) {
      return;
    }

    region.cityEntries.splice(cityIndex, 1);
    if (!region.cityEntries.length) {
      region.cityEntries = [{ cityCode: '', coverageRadiusKm: null }];
    }
  }

  private resolveCityCodeForRegion(regionCode: string, valueOrLabel: string): string {
    const options = this.getCityOptionsForRegion(regionCode);
    const normalized = String(valueOrLabel || '').trim();
    if (!normalized) {
      return '';
    }

    const byValue = options.find(opt => opt.value === normalized.toUpperCase());
    if (byValue) {
      return byValue.value;
    }

    const byLabel = options.find(opt => opt.label.toLowerCase() === normalized.toLowerCase());
    return byLabel?.value || '';
  }

  private cityLabelFromCode(regionCode: string, cityCode: string): string {
    const options = this.getCityOptionsForRegion(regionCode);
    const raw = String(cityCode || '').trim();
    const normalized = raw.toUpperCase();
    return options.find(opt => opt.value === normalized)?.label || raw;
  }

  private transformBackendDataToForm(data: any): ServiceProvider {
    const profile = data?.profile || data || {};
    const headOfficeAddress = this.mapAddressFromBackend(profile.head_office_address || profile.headOfficeAddress || {});
    const primaryRep = profile.primary_representative || profile.primaryRepresentative || {};
    const secondaryContact = profile.emergency_contact || profile.secondaryContact || {};
    const securityLicensesRaw =
      (Array.isArray(profile.security_licenses) ? profile.security_licenses : null)
      || (Array.isArray(profile.securityLicenses) ? profile.securityLicenses : null)
      || ((profile.security_license || profile.securityLicense)
        ? [profile.security_license || profile.securityLicense]
        : []);
    const insurance = profile.insurance_details || profile.insuranceDetails || {};

    const mappedRegions = Array.isArray(profile.operating_regions)
      ? profile.operating_regions.map((region: any) => ({
        country: region.country || 'CA',
        regionCode: region.region_code || region.province || '',
        cityEntries: (() => {
          const regionCode = (region.region_code || region.province || '').toString().trim();
          const firstCityByProvince = this.getCityOptionsForRegion(regionCode)[0]?.value || '';
          const defaultRadius = (() => {
            const kmValue = Number(region.coverage_radius_km ?? region.coverageRadiusKm);
            return Number.isFinite(kmValue) ? this.toDisplayDistance(kmValue) : null;
          })();

          if (Array.isArray(region.city_entries) && region.city_entries.length > 0) {
            const mappedEntries = region.city_entries
              .map((entry: any) => {
                const cityCode = this.resolveCityCodeForRegion(regionCode, entry?.city_code || entry?.cityCode || '');
                if (!cityCode) {
                  return null;
                }
                const kmValue = Number(entry?.coverage_radius_km ?? entry?.coverageRadiusKm);
                return {
                  cityCode,
                  coverageRadiusKm: Number.isFinite(kmValue) ? this.toDisplayDistance(kmValue) : defaultRadius
                };
              })
              .filter((entry: any) => !!entry);
            return mappedEntries.length ? mappedEntries : (firstCityByProvince ? [{ cityCode: firstCityByProvince, coverageRadiusKm: defaultRadius }] : [{ cityCode: '', coverageRadiusKm: defaultRadius }]);
          }

          if (Array.isArray(region.city_codes) && region.city_codes.length > 0) {
            const mappedEntries = region.city_codes
              .map((code: string) => this.resolveCityCodeForRegion(regionCode, code))
              .filter((code: string) => !!code)
              .map((cityCode: string) => ({ cityCode, coverageRadiusKm: defaultRadius }));
            return mappedEntries.length ? mappedEntries : (firstCityByProvince ? [{ cityCode: firstCityByProvince, coverageRadiusKm: defaultRadius }] : [{ cityCode: '', coverageRadiusKm: defaultRadius }]);
          }

          const legacyCityCode = this.resolveCityCodeForRegion(regionCode, region.city || '');
          return legacyCityCode
            ? [{ cityCode: legacyCityCode, coverageRadiusKm: defaultRadius }]
            : (firstCityByProvince ? [{ cityCode: firstCityByProvince, coverageRadiusKm: defaultRadius }] : [{ cityCode: '', coverageRadiusKm: defaultRadius }]);
        })(),
      }))
      : [];

    return {
      legalCompanyName: profile.legal_company_name || profile.legalCompanyName || '',
      tradingName: profile.trading_name || profile.tradingName || '',
      corporationNumber: profile.corporation_number || profile.corporationNumber || '',
      yearOfEstablishment: profile.year_of_establishment ?? profile.yearOfEstablishment ?? null,
      companyWebsite: profile.company_website || profile.companyWebsite || '',
      taxRegistrationNumber: profile.tax_registration_number || profile.taxRegistrationNumber || '',
      headOfficeAddress,
      primaryRepresentative: {
        name: primaryRep.name || '',
        email: primaryRep.email || '',
        mobilePhone: primaryRep.phone ? this.mapPhoneFromBackend(primaryRep.phone, 'mobile') : null,
        landlinePhone: null
      },
      secondaryContact: {
        name: secondaryContact.name || '',
        email: secondaryContact.email || '',
        mobilePhone: secondaryContact.phone ? this.mapPhoneFromBackend(secondaryContact.phone, 'mobile') : null,
        landlinePhone: null
      },
      securityLicenses: (securityLicensesRaw.length ? securityLicensesRaw : [{}]).map((license: any, index: number) => ({
        licenseNumber: license.license_number || license.licenseNumber || '',
        licenseType: license.license_type || license.licenseType || '',
        issuingProvince: license.issuing_province || license.issuingProvince || '',
        issuingAuthority: license.issuing_authority || license.issuingAuthority || '',
        issueDate: license.issue_date || license.issueDate || '',
        expiryDate: license.expiry_date || license.expiryDate || '',
        file: null,
        id: license.id || `sec_license_${index}_${Date.now()}`,
        existingFileUrl: license.document_file_url || license.document_url || undefined,
        existingFileName: license.document_file_name || undefined,
        existingFileId: license.document_file_id || undefined,
        existingFileMimeType: license.document_file_mime_type || undefined,
        existingFileSize: license.document_file_size || undefined
      })),
      insuranceDetails: {
        policyNumber: insurance.policy_number || insurance.policyNumber || '',
        coverageAmount: insurance.coverage_amount ?? insurance.coverageAmount ?? null,
        currency: insurance.currency || 'USD',
        expiryDate: insurance.expiry_date || insurance.expiryDate || '',
        coverageDetails: insurance.coverage_details || insurance.coverageDetails || '',
        file: null,
        existingFileUrl: insurance.document_file_url || insurance.document_url || undefined,
        existingFileName: insurance.document_file_name || undefined,
        existingFileId: insurance.document_file_id || undefined,
        existingFileMimeType: insurance.document_file_mime_type || undefined,
        existingFileSize: insurance.document_file_size || undefined
      },
      operatingRegions: mappedRegions.length
        ? mappedRegions
        : [
          {
            country: 'CA',
            regionCode: '',
            cityEntries: [{ cityCode: '', coverageRadiusKm: null }]
          }
        ],
      guardCategoriesOffered: Array.isArray(profile.guard_categories_offered)
        ? profile.guard_categories_offered
        : []
    };
  }

  hasProviderData(data: ServiceProvider): boolean {
    const safe = (v: any) => (v === null || v === undefined) ? '' : String(v);

    const legalName = safe((data as any).legalCompanyName || (data as any).legal_company_name || (data as any).full_name || '');
    const companyReg = safe((data as any).corporationNumber || (data as any).corporation_number || '');
    const street = safe((data as any).headOfficeAddress?.street || (data as any).head_office_address?.street || '');
    const primaryName = safe((data as any).primaryRepresentative?.name || (data as any).primary_representative?.name || '');
    const primaryMobile = (data as any).primaryRepresentative?.mobilePhone?.e164 || (data as any).primaryRepresentative?.phone || (data as any).primary_representative?.phone || '';
    const primaryLandline = (data as any).primaryRepresentative?.landlinePhone?.e164 || '';

    return !!(
      legalName.trim() ||
      companyReg.trim() ||
      street.trim() ||
      primaryName.trim() ||
      primaryMobile ||
      primaryLandline
    );
  }

  addRegion(): void {
    this.providerFormModel.operatingRegions.push({
      country: 'CA',
      regionCode: '',
      cityEntries: [{ cityCode: '', coverageRadiusKm: null }]
    });
  }

  removeRegion(index: number): void {
    this.providerFormModel.operatingRegions.splice(index, 1);
  }

  trackByIndex(index: number, item: any): any {
    return index;
  }

  addSecurityLicense(): void {
    this.providerFormModel.securityLicenses.push({
      licenseNumber: '',
      licenseType: '',
      issuingProvince: '',
      issuingAuthority: '',
      issueDate: '',
      expiryDate: '',
      file: null,
      id: `sec_license_new_${this.providerFormModel.securityLicenses.length}_${Date.now()}`
    });
  }

  removeSecurityLicense(index: number): void {
    const license = this.providerFormModel.securityLicenses[index];
    if (!license) {
      return;
    }

    if (license.id) {
      delete this.providerErrors[`security_license_${license.id}_licenseNumber`];
      delete this.providerErrors[`security_license_${license.id}_licenseType`];
      delete this.providerErrors[`security_license_${license.id}_issuingProvince`];
      delete this.providerErrors[`security_license_${license.id}_issuingAuthority`];
      delete this.providerErrors[`security_license_${license.id}_issueDate`];
      delete this.providerErrors[`security_license_${license.id}_expiryDate`];
      delete this.securityLicenseUploadErrors[license.id];
      delete this.securityLicenseUploadInProgress[license.id];
    }

    if (license.existingFileId) {
      this.deleteSecurityLicenseFile(license);
    }

    this.providerFormModel.securityLicenses.splice(index, 1);

    if (this.providerFormModel.securityLicenses.length === 0) {
      this.addSecurityLicense();
    }
  }


  validateProviderForm(): boolean {
    this.providerErrors = {};

    // Legal Company Name
    if (!this.providerFormModel.legalCompanyName.trim()) {
      this.providerErrors.legalCompanyName = 'Legal company name is required.';
    }

    if (this.providerFormModel.yearOfEstablishment) {
      const estDate = new Date(this.providerFormModel.yearOfEstablishment);
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (estDate > today) {
        this.providerErrors.yearOfEstablishment =
          'Date of establishment cannot be in the future.';
      }
    }

    if (this.providerFormModel.companyWebsite?.trim()) {
      const websitePattern = /^(https?:\/\/)?[\w.-]+\.[a-z]{2,}(\/.*)?$/i;
      if (!websitePattern.test(this.providerFormModel.companyWebsite.trim())) {
        this.providerErrors.companyWebsite = 'Please enter a valid website URL.';
      }
    }

    // Company Registration Number
    if (!this.providerFormModel.corporationNumber.trim()) {
      this.providerErrors.corporationNumber = 'Corporation number is required.';
    }

    // Head Office Address
    if (!this.providerFormModel.headOfficeAddress.street.trim()) {
      this.providerErrors.officeStreet = 'Office street address is required.';
    }
    if (!this.providerFormModel.headOfficeAddress.city.trim()) {
      this.providerErrors.officeCity = 'Office city is required.';
    } else {
      const cityOptions = this.getHeadOfficeCityOptions();
      if (cityOptions.length && !cityOptions.some(option => option.value === this.providerFormModel.headOfficeAddress.city)) {
        this.providerErrors.officeCity = 'Please select a valid city for the selected province.';
      }
    }
    if (!this.providerFormModel.headOfficeAddress.country.trim()) {
      this.providerErrors.officeCountry = 'Office country is required.';
    }
    if (this.providerFormModel.headOfficeAddress.country === 'CA' && !this.providerFormModel.headOfficeAddress.province.trim()) {
      this.providerErrors.officeProvince = 'Office province is required for Canada.';
    }
    if (!this.providerFormModel.headOfficeAddress.postalCode.trim()) {
      this.providerErrors.officePostalCode = 'Office postal code is required.';
    } else if (this.providerFormModel.headOfficeAddress.country === 'CA') {
      const postalCodePattern = /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i;
      if (!postalCodePattern.test(this.providerFormModel.headOfficeAddress.postalCode.trim())) {
        this.providerErrors.officePostalCode = 'Invalid Canadian postal code format (e.g., A1A 1A1).';
      }
    }

    // Primary Representative
    if (!this.providerFormModel.primaryRepresentative.name.trim()) {
      this.providerErrors.repName = 'Representative name is required.';
    } else if (!/^[a-zA-Z\s]+$/.test(this.providerFormModel.primaryRepresentative.name)) {
      this.providerErrors.repName = 'Representative name can only contain letters and spaces.';
    }
    if (!this.providerFormModel.primaryRepresentative.email.trim()) {
      this.providerErrors.repEmail = 'Representative email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(this.providerFormModel.primaryRepresentative.email)) {
      this.providerErrors.repEmail = 'Invalid email format.';
    }
    const hasRepMobile = this.providerFormModel.primaryRepresentative.mobilePhone?.e164;
    const hasRepLandline = this.providerFormModel.primaryRepresentative.landlinePhone?.e164;

    // Validate representative mobile phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasRepMobile) {
      const repMobileE164 = this.providerFormModel.primaryRepresentative.mobilePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(repMobileE164)) {
        this.providerErrors.repMobilePhone = 'Invalid Canadian mobile phone number format.';
      } else if (this.providerFormModel.primaryRepresentative.mobilePhone!.country !== 'CA') {
        this.providerErrors.repMobilePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    // Validate representative landline phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasRepLandline) {
      const repLandlineE164 = this.providerFormModel.primaryRepresentative.landlinePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(repLandlineE164)) {
        this.providerErrors.repLandlinePhone = 'Invalid Canadian landline phone number format.';
      } else if (this.providerFormModel.primaryRepresentative.landlinePhone!.country !== 'CA') {
        this.providerErrors.repLandlinePhone = 'Only Canadian phone numbers are accepted.';
      }
    }

    // At least one phone number is required
    if (!hasRepMobile && !hasRepLandline) {
      this.providerErrors.repPhone = 'Representative phone is required.';
    }

    // If both phone numbers are provided, they must be from the same country
    if (hasRepMobile && hasRepLandline) {
      if (this.providerFormModel.primaryRepresentative.mobilePhone?.country !== this.providerFormModel.primaryRepresentative.landlinePhone?.country) {
        this.providerErrors.repPhone = 'Representative phone numbers must be from the same country.';
      }
    }

    // Secondary Contact (Required)
    const secondary = this.providerFormModel.secondaryContact;

    // Name validation
    if (!secondary.name.trim()) {
      this.providerErrors.secondaryContactName = 'Secondary contact name is required.';
    } else if (!/^[a-zA-Z\s]+$/.test(secondary.name)) {
      this.providerErrors.secondaryContactName = 'Contact name can only contain letters and spaces.';
    }

    // Email validation
    if (!secondary.email.trim()) {
      this.providerErrors.secondaryContactEmail = 'Secondary contact email is required.';
    } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(secondary.email)) {
      this.providerErrors.secondaryContactEmail = 'Invalid email format.';
    }

    // Phone validation
    const hasSecondaryMobile = secondary.mobilePhone?.e164;
    const hasSecondaryLandline = secondary.landlinePhone?.e164;

    if (!hasSecondaryMobile && !hasSecondaryLandline) {
      this.providerErrors.secondaryContactPhone = 'At least one phone number is required.';
    }

    // Mobile phone format validation
    if (hasSecondaryMobile) {
      const pattern = /^\+1[2-9]\d{9}$/;
      const phone = secondary.mobilePhone!.e164;

      if (!pattern.test(phone)) {
        this.providerErrors.secondaryContactMobilePhone =
          'Invalid Canadian mobile phone number format.';
      } else if (secondary.mobilePhone!.country !== 'CA') {
        this.providerErrors.secondaryContactMobilePhone =
          'Only Canadian phone numbers are accepted.';
      }
    }

    // Landline phone format validation
    if (hasSecondaryLandline) {
      const pattern = /^\+1[2-9]\d{9}$/;
      const phone = secondary.landlinePhone!.e164;

      if (!pattern.test(phone)) {
        this.providerErrors.secondaryContactLandlinePhone =
          'Invalid Canadian landline phone number format.';
      } else if (secondary.landlinePhone!.country !== 'CA') {
        this.providerErrors.secondaryContactLandlinePhone =
          'Only Canadian phone numbers are accepted.';
      }
    }

    // Same country rule
    if (hasSecondaryMobile && hasSecondaryLandline) {
      if (secondary.mobilePhone?.country !== secondary.landlinePhone?.country) {
        this.providerErrors.secondaryContactPhone =
          'Secondary contact phone numbers must be from the same country.';
      }
    }

    // Security Licenses
    if (!this.providerFormModel.securityLicenses || this.providerFormModel.securityLicenses.length === 0) {
      this.providerErrors.securityLicenses = 'At least one security license is required.';
    } else {
      this.providerFormModel.securityLicenses.forEach((license, index) => {
        const id = license.id || `idx_${index}`;
        const hasAnyData =
          license.licenseNumber.trim() ||
          license.licenseType.trim() ||
          license.issuingProvince.trim() ||
          license.issuingAuthority.trim() ||
          license.issueDate ||
          license.expiryDate;

        const isRequired = index === 0;
        if (!isRequired && !hasAnyData) {
          return;
        }

        if (!license.licenseNumber.trim()) {
          this.providerErrors[`security_license_${id}_licenseNumber`] = 'Security license number is required.';
        }
        if (!license.licenseType.trim()) {
          this.providerErrors[`security_license_${id}_licenseType`] = 'License type is required.';
        }
        if (!license.issuingProvince.trim()) {
          this.providerErrors[`security_license_${id}_issuingProvince`] = 'Issuing province is required.';
        }
        if (!license.issuingAuthority.trim()) {
          this.providerErrors[`security_license_${id}_issuingAuthority`] = 'Issuing authority is required.';
        }

        if (license.issueDate) {
          const issueDate = new Date(license.issueDate);
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          issueDate.setHours(0, 0, 0, 0);

          if (issueDate > today) {
            this.providerErrors[`security_license_${id}_issueDate`] = 'Issue date cannot be in the future.';
          }
        }

        if (!license.expiryDate) {
          this.providerErrors[`security_license_${id}_expiryDate`] = 'Expiry date is required.';
        } else if (license.issueDate) {
          const issueDate = new Date(license.issueDate);
          const expiryDate = new Date(license.expiryDate);
          if (expiryDate < issueDate) {
            this.providerErrors[`security_license_${id}_expiryDate`] = 'Expiry date cannot be before issue date.';
          }
        }
      });
    }

    // Operating Regions (at least one required)
    const validRegions = this.providerFormModel.operatingRegions.filter(region => {
      const validEntries = (region.cityEntries || []).filter(entry => String(entry.cityCode || '').trim());
      return !!region.regionCode.trim() && validEntries.length > 0;
    });
    if (validRegions.length === 0) {
      this.providerErrors.operatingRegions = 'At least one operating region is required.';
    }
    this.providerFormModel.operatingRegions.forEach((region, index) => {
      if (!region.country.trim()) {
        this.providerErrors[`region_${index}_country`] = 'Country is required.';
      }

      if (region.country === 'CA' && !region.regionCode.trim()) {
        this.providerErrors[`region_${index}_regionCode`] = 'Province is required for Canada.';
      } else if (region.country === 'CA') {
        const validProvinces = this.provinceOptions.map(option => option.value);
        if (validProvinces.length && !validProvinces.includes(region.regionCode)) {
          this.providerErrors[`region_${index}_regionCode`] = 'Please select a valid province.';
        }
      }

      const cityOptions = this.getCityOptionsForRegion(region.regionCode);
      const cityCodes = (region.cityEntries || []).map(entry => String(entry.cityCode || '').trim().toUpperCase());
      const uniqueCityCodes = Array.from(new Set(cityCodes.filter(code => !!code)));
      if (!uniqueCityCodes.length) {
        this.providerErrors[`region_${index}_cityCodes`] = 'Select at least one city for this province.';
      } else if (cityOptions.length && uniqueCityCodes.some(code => !cityOptions.some(opt => opt.value === code))) {
        this.providerErrors[`region_${index}_cityCodes`] = 'One or more selected cities are invalid for this province.';
      }

      (region.cityEntries || []).forEach((entry, cityIndex) => {
        const cityCode = String(entry.cityCode || '').trim();
        if (!cityCode) {
          return;
        }
        const normalizedRadius = this.normalizeCoverageRadius(entry.coverageRadiusKm);
        if (normalizedRadius == null) {
          this.providerErrors[`region_${index}_city_${cityIndex}_radius`] = 'Coverage radius is required for each selected city.';
          return;
        }
        if (normalizedRadius < this.minimumCoverageRadiusDisplay) {
          this.providerErrors[`region_${index}_city_${cityIndex}_radius`] = `Coverage radius must be at least ${this.minimumCoverageRadiusText}.`;
        }
      });
    });

    // Guard Categories (at least one required)
    const validCategories = this.providerFormModel.guardCategoriesOffered.filter(c => c.trim());
    if (validCategories.length === 0) {
      this.providerErrors.guardCategories = 'At least one guard category is required.';
    }

    // Insurance Details (optional)
    const insurance = this.providerFormModel.insuranceDetails;
    const insuranceHasAny =
      insurance.policyNumber.trim() ||
      insurance.coverageAmount != null ||
      insurance.expiryDate.trim() ||
      insurance.coverageDetails.trim();
    if (insuranceHasAny) {
      if (!insurance.policyNumber.trim()) {
        this.providerErrors.policyNumber = 'Policy number is required.';
      }
      if (!insurance.expiryDate.trim()) {
        this.providerErrors.policyExpiryDate = 'Policy expiry date is required.';
      }
    }

    return Object.keys(this.providerErrors).length === 0;
  }

  onSecurityLicenseFileSelected(license: SecurityLicense, file: File | null): void {
    if (!license.id) {
      license.id = `sec_license_${Date.now()}`;
    }
    const key = license.id;
    this.securityLicenseUploadErrors[key] = '';

    if (!file) {
      if (license.existingFileId) {
        this.deleteSecurityLicenseFile(license);
      }
      license.file = null;
      license.existingFileUrl = undefined;
      license.existingFileName = undefined;
      license.existingFileId = undefined;
      license.existingFileMimeType = undefined;
      license.existingFileSize = undefined;
      return;
    }

    this.securityLicenseUploadInProgress[key] = true;
    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/security-license', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.securityLicenseUploadInProgress[key] = false;
          license.file = null;
          license.existingFileId = response?.file_id;
          license.existingFileUrl = response?.file_url;
          license.existingFileName = response?.file_name;
          license.existingFileMimeType = response?.mime_type;
          license.existingFileSize = response?.size;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress[key] = false;
          this.securityLicenseUploadErrors[key] = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  deleteSecurityLicenseFile(license: SecurityLicense): void {
    if (!license.id || !license.existingFileId) {
      return;
    }

    const key = license.id;
    this.securityLicenseUploadInProgress[key] = true;
    this.apiService.delete(`tenant/files/security-license/${license.existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.securityLicenseUploadInProgress[key] = false;
          license.existingFileUrl = undefined;
          license.existingFileName = undefined;
          license.existingFileId = undefined;
          license.existingFileMimeType = undefined;
          license.existingFileSize = undefined;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress[key] = false;
          this.securityLicenseUploadErrors[key] = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  onInsuranceFileSelected(file: File | null): void {
    this.insuranceUploadError = '';

    if (!file) {
      if (this.providerFormModel.insuranceDetails.existingFileId) {
        this.deleteInsuranceFile();
      }
      this.providerFormModel.insuranceDetails.file = null;
      this.providerFormModel.insuranceDetails.existingFileUrl = undefined;
      this.providerFormModel.insuranceDetails.existingFileName = undefined;
      this.providerFormModel.insuranceDetails.existingFileId = undefined;
      this.providerFormModel.insuranceDetails.existingFileMimeType = undefined;
      this.providerFormModel.insuranceDetails.existingFileSize = undefined;
      return;
    }

    this.insuranceUploadInProgress = true;
    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/insurance', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.insuranceUploadInProgress = false;
          this.providerFormModel.insuranceDetails.file = null;
          this.providerFormModel.insuranceDetails.existingFileId = response?.file_id;
          this.providerFormModel.insuranceDetails.existingFileUrl = response?.file_url;
          this.providerFormModel.insuranceDetails.existingFileName = response?.file_name;
          this.providerFormModel.insuranceDetails.existingFileMimeType = response?.mime_type;
          this.providerFormModel.insuranceDetails.existingFileSize = response?.size;
        },
        error: (err) => {
          this.insuranceUploadInProgress = false;
          this.insuranceUploadError = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  deleteInsuranceFile(): void {
    const fileId = this.providerFormModel.insuranceDetails.existingFileId;
    if (!fileId) {
      return;
    }

    this.insuranceUploadInProgress = true;
    this.apiService.delete(`tenant/files/insurance/${fileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.insuranceUploadInProgress = false;
          this.providerFormModel.insuranceDetails.existingFileUrl = undefined;
          this.providerFormModel.insuranceDetails.existingFileName = undefined;
          this.providerFormModel.insuranceDetails.existingFileId = undefined;
          this.providerFormModel.insuranceDetails.existingFileMimeType = undefined;
          this.providerFormModel.insuranceDetails.existingFileSize = undefined;
        },
        error: (err) => {
          this.insuranceUploadInProgress = false;
          this.insuranceUploadError = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  submitProviderForm() {
    if (this.readonly) {
      return;
    }

    if (!this.validateProviderForm()) {
      return;
    }

    // Filter out empty strings from arrays
    const validRegions = this.providerFormModel.operatingRegions.filter(region => {
      const validEntries = (region.cityEntries || [])
        .filter(entry => String(entry.cityCode || '').trim().toUpperCase())
        .filter(entry => this.normalizeCoverageRadius(entry.coverageRadiusKm) != null);
      return !!region.regionCode.trim() && validEntries.length > 0;
    });
    const validCategories = this.providerFormModel.guardCategoriesOffered.filter(c => c.trim());

    const primaryRepPhone = this.providerFormModel.primaryRepresentative.mobilePhone?.e164
      || this.providerFormModel.primaryRepresentative.landlinePhone?.e164
      || '';

    const secondaryContact = this.providerFormModel.secondaryContact;
    const hasSecondaryContact =
      secondaryContact.name.trim() ||
      secondaryContact.email.trim() ||
      secondaryContact.mobilePhone?.e164 ||
      secondaryContact.landlinePhone?.e164;

    const validSecurityLicenses = (this.providerFormModel.securityLicenses || []).filter((license, index) => {
      if (index === 0) {
        return true;
      }
      return !!(
        license.licenseNumber.trim() ||
        license.licenseType.trim() ||
        license.issuingProvince.trim() ||
        license.issuingAuthority.trim() ||
        license.issueDate ||
        license.expiryDate ||
        license.existingFileId
      );
    });

    const mappedSecurityLicenses = validSecurityLicenses.map((license) => ({
      license_number: license.licenseNumber,
      license_type: license.licenseType,
      issuing_province: license.issuingProvince,
      issuing_authority: license.issuingAuthority,
      ...(license.issueDate && { issue_date: license.issueDate }),
      expiry_date: license.expiryDate,
      ...(license.existingFileId && { document_file_id: license.existingFileId }),
      ...(license.existingFileUrl && { document_file_url: license.existingFileUrl }),
      ...(license.existingFileName && { document_file_name: license.existingFileName }),
      ...(license.existingFileMimeType && { document_file_mime_type: license.existingFileMimeType }),
      ...(license.existingFileSize != null && { document_file_size: license.existingFileSize })
    }));

    const primarySecurityLicense = mappedSecurityLicenses[0];

    const tenantUpdatePayload = {
      tenant_type: TENANT_TYPES.SERVICE_PROVIDER,
      profile: {
        legal_company_name: this.providerFormModel.legalCompanyName,
        trading_name: this.providerFormModel.tradingName || undefined,
        company_registration_number: this.providerFormModel.corporationNumber,
        year_of_establishment: this.providerFormModel.yearOfEstablishment || undefined,
        company_website: this.providerFormModel.companyWebsite || undefined,
        tax_registration_number: this.providerFormModel.taxRegistrationNumber || undefined,
        head_office_address: {
          street: this.providerFormModel.headOfficeAddress.street,
          city: this.cityLabelFromCode(
            this.providerFormModel.headOfficeAddress.province,
            this.providerFormModel.headOfficeAddress.city
          ),
          country: this.providerFormModel.headOfficeAddress.country,
          province: this.providerFormModel.headOfficeAddress.province || '',
          postal_code: this.providerFormModel.headOfficeAddress.postalCode
        },
        company_phone: primaryRepPhone,
        company_email: this.providerFormModel.primaryRepresentative.email,
        primary_representative: {
          name: this.providerFormModel.primaryRepresentative.name,
          email: this.providerFormModel.primaryRepresentative.email,
          phone: primaryRepPhone
        },
        emergency_contact: hasSecondaryContact
          ? {
            name: secondaryContact.name,
            email: secondaryContact.email,
            phone: secondaryContact.mobilePhone?.e164
              || secondaryContact.landlinePhone?.e164
              || ''
          }
          : undefined,
        ...(primarySecurityLicense && { security_license: primarySecurityLicense }),
        security_licenses: mappedSecurityLicenses,
        insurance_details: {
          policy_number: this.providerFormModel.insuranceDetails.policyNumber || undefined,
          coverage_amount: this.providerFormModel.insuranceDetails.coverageAmount ?? undefined,
          currency: this.providerFormModel.insuranceDetails.currency || 'USD',
          expiry_date: this.providerFormModel.insuranceDetails.expiryDate || undefined,
          coverage_details: this.providerFormModel.insuranceDetails.coverageDetails || undefined,
          ...(this.providerFormModel.insuranceDetails.existingFileId && { document_file_id: this.providerFormModel.insuranceDetails.existingFileId }),
          ...(this.providerFormModel.insuranceDetails.existingFileUrl && { document_file_url: this.providerFormModel.insuranceDetails.existingFileUrl }),
          ...(this.providerFormModel.insuranceDetails.existingFileName && { document_file_name: this.providerFormModel.insuranceDetails.existingFileName }),
          ...(this.providerFormModel.insuranceDetails.existingFileMimeType && { document_file_mime_type: this.providerFormModel.insuranceDetails.existingFileMimeType }),
          ...(this.providerFormModel.insuranceDetails.existingFileSize != null && { document_file_size: this.providerFormModel.insuranceDetails.existingFileSize })
        },
        operating_regions: validRegions.map(region => {
          const cityEntries = (region.cityEntries || [])
            .map(entry => ({
              cityCode: String(entry.cityCode || '').trim().toUpperCase(),
              coverageRadiusKm: this.normalizeCoverageRadius(entry.coverageRadiusKm)
            }))
            .filter(entry => !!entry.cityCode)
            .filter(entry => entry.coverageRadiusKm != null);

          const dedupedEntriesMap = new Map<string, number>();
          cityEntries.forEach(entry => {
            if (!dedupedEntriesMap.has(entry.cityCode)) {
              dedupedEntriesMap.set(entry.cityCode, Number(entry.coverageRadiusKm));
            }
          });

          const dedupedEntries = Array.from(dedupedEntriesMap.entries()).map(([cityCode, coverageRadiusKm]) => ({ cityCode, coverageRadiusKm }));
          const cityCodes = dedupedEntries.map(entry => entry.cityCode);
          const firstCityCode = cityCodes[0] || '';
          return {
            country: 'CA',
            province: region.regionCode,
            region_code: region.regionCode,
            city: this.cityLabelFromCode(region.regionCode, firstCityCode),
            city_code: firstCityCode,
            city_codes: cityCodes,
            coverage_radius_km: dedupedEntries.length ? this.toStorageKm(dedupedEntries[0].coverageRadiusKm) : null,
            city_entries: dedupedEntries.map(entry => ({
              city_code: entry.cityCode,
              city: this.cityLabelFromCode(region.regionCode, entry.cityCode),
              coverage_radius_km: this.toStorageKm(entry.coverageRadiusKm)
            }))
          };
        }),
        guard_categories_offered: validCategories
      },
      status: 'active'
    };

    const isOnboarding = this.appService.userSessionData().tenant.has_onboarding;
    tenantUpdatePayload.status = isOnboarding ? 'pending_activation' : 'active';

    this.apiService.put('tenant', tenantUpdatePayload).subscribe({
      next: (response) => {
        console.log('Service provider profile submitted successfully', response);
        const newStatus = isOnboarding ? 'pending_activation' : 'active';
        this.appService.setTenantStatus(newStatus, false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        console.error('Error submitting service provider profile:', err);
        this.providerErrors.submit = err?.error?.detail || 'Failed to submit service provider profile.';
      }
    });
  }
}
