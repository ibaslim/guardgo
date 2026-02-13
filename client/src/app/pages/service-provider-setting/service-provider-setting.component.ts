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
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

interface OperatingRegion {
  city: string;
  country: string;
  province: string;
  coverageRadiusKm: number | null;
}

interface InsurancePolicy {
  policyNumber: string;
  coverageAmount: number | null;
  currency: string;
  expiryDate: string;
  coverageDetails: string;
}

interface ServiceProvider {
  legalCompanyName: string;
  tradingName: string;
  companyRegistrationNumber: string;
  yearOfEstablishment: number | null;
  companyWebsite: string;
  taxRegistrationNumber: string;
  headOfficeAddress: Address;
  primaryRepresentative: ContactPerson;
  secondaryContact: ContactPerson;
  securityLicense: SecurityLicense;
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

  @Input() providerData?: ServiceProvider;

  providerFormModel: ServiceProvider = {
    legalCompanyName: '',
    tradingName: '',
    companyRegistrationNumber: '',
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
    securityLicense: {
      licenseNumber: '',
      licenseType: '',
      issuingProvince: '',
      issuingAuthority: '',
      issueDate: '',
      expiryDate: '',
      file: null
    },
    insuranceDetails: {
      policyNumber: '',
      coverageAmount: null,
      currency: 'USD',
      expiryDate: '',
      coverageDetails: ''
    },
    operatingRegions: [
      {
        city: '',
        country: 'CA',
        province: '',
        coverageRadiusKm: null
      }
    ],
    guardCategoriesOffered: []
  };

  providerErrors: any = {};

  isEditMode: boolean = false;

  countryOptions: { value: string; label: string }[] = [];
  provinceOptions: { value: string; label: string }[] = [];
  securityLicenseTypeOptions: { value: string; label: string }[] = [];
  guardTypeOptions: { value: string; label: string }[] = [];

  securityLicenseUploadInProgress = false;
  securityLicenseUploadError = '';

  private destroy$ = new Subject<void>();

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) { }

  ngOnInit(): void {
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
    return {
      street: raw?.street || '',
      city: raw?.city || '',
      country: raw?.country || 'CA',
      province: raw?.province || '',
      postalCode: raw?.postal_code || raw?.postalCode || ''
    };
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
  onIssuingProvinceChange(): void {
    const province = this.providerFormModel.securityLicense.issuingProvince;
    if (province) {
      const authority = this.getSuggestedIssuingAuthority(province);
      if (authority) {
        this.providerFormModel.securityLicense.issuingAuthority = authority;
      }
    }
  }

  private transformBackendDataToForm(data: any): ServiceProvider {
    const profile = data?.profile || data || {};
    const headOfficeAddress = this.mapAddressFromBackend(profile.head_office_address || profile.headOfficeAddress || {});
    const primaryRep = profile.primary_representative || profile.primaryRepresentative || {};
    const secondaryContact = profile.emergency_contact || profile.secondaryContact || {};
    const securityLicense = profile.security_license || profile.securityLicense || {};
    const insurance = profile.insurance_details || profile.insuranceDetails || {};

    const mappedRegions = Array.isArray(profile.operating_regions)
      ? profile.operating_regions.map((region: any) => ({
        city: region.city || '',
        country: region.country || 'CA',
        province: region.province || '',
        coverageRadiusKm: region.coverage_radius_km ?? region.coverageRadiusKm ?? null
      }))
      : [];

    return {
      legalCompanyName: profile.legal_company_name || profile.legalCompanyName || '',
      tradingName: profile.trading_name || profile.tradingName || '',
      companyRegistrationNumber: profile.company_registration_number || profile.companyRegistrationNumber || '',
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
      securityLicense: {
        licenseNumber: securityLicense.license_number || securityLicense.licenseNumber || '',
        licenseType: securityLicense.license_type || securityLicense.licenseType || '',
        issuingProvince: securityLicense.issuing_province || securityLicense.issuingProvince || '',
        issuingAuthority: securityLicense.issuing_authority || securityLicense.issuingAuthority || '',
        issueDate: securityLicense.issue_date || securityLicense.issueDate || '',
        expiryDate: securityLicense.expiry_date || securityLicense.expiryDate || '',
        file: null,
        existingFileUrl: securityLicense.document_file_url || securityLicense.document_url || undefined,
        existingFileName: securityLicense.document_file_name || undefined,
        existingFileId: securityLicense.document_file_id || undefined,
        existingFileMimeType: securityLicense.document_file_mime_type || undefined,
        existingFileSize: securityLicense.document_file_size || undefined
      },
      insuranceDetails: {
        policyNumber: insurance.policy_number || insurance.policyNumber || '',
        coverageAmount: insurance.coverage_amount ?? insurance.coverageAmount ?? null,
        currency: insurance.currency || 'USD',
        expiryDate: insurance.expiry_date || insurance.expiryDate || '',
        coverageDetails: insurance.coverage_details || insurance.coverageDetails || ''
      },
      operatingRegions: mappedRegions.length
        ? mappedRegions
        : [
          {
            city: '',
            country: 'CA',
            province: '',
            coverageRadiusKm: null
          }
        ],
      guardCategoriesOffered: Array.isArray(profile.guard_categories_offered)
        ? profile.guard_categories_offered
        : []
    };
  }

  hasProviderData(data: ServiceProvider): boolean {
    return !!(
      data.legalCompanyName.trim() ||
      data.companyRegistrationNumber.trim() ||
      data.headOfficeAddress.street.trim() ||
      data.primaryRepresentative.name.trim() ||
      data.primaryRepresentative.mobilePhone?.e164 ||
      data.primaryRepresentative.landlinePhone?.e164
    );
  }

  addRegion(): void {
    this.providerFormModel.operatingRegions.push({
      city: '',
      country: 'CA',
      province: '',
      coverageRadiusKm: null
    });
  }

  removeRegion(index: number): void {
    this.providerFormModel.operatingRegions.splice(index, 1);
  }

  trackByIndex(index: number, item: any): any {
    return index;
  }


  validateProviderForm(): boolean {
    this.providerErrors = {};

    // Legal Company Name
    if (!this.providerFormModel.legalCompanyName.trim()) {
      this.providerErrors.legalCompanyName = 'Legal company name is required.';
    }

    if (this.providerFormModel.yearOfEstablishment != null) {
      const year = Number(this.providerFormModel.yearOfEstablishment);
      const currentYear = new Date().getFullYear();
      if (!Number.isFinite(year) || year < 1800 || year > currentYear) {
        this.providerErrors.yearOfEstablishment = 'Enter a valid year of establishment.';
      }
    }

    if (this.providerFormModel.companyWebsite?.trim()) {
      const websitePattern = /^(https?:\/\/)?[\w.-]+\.[a-z]{2,}(\/.*)?$/i;
      if (!websitePattern.test(this.providerFormModel.companyWebsite.trim())) {
        this.providerErrors.companyWebsite = 'Please enter a valid website URL.';
      }
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
    } else if (!/^[a-zA-Z\s]+$/.test(this.providerFormModel.headOfficeAddress.city)) {
      this.providerErrors.officeCity = 'City can only contain letters and spaces.';
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

    // Secondary Contact (optional)
    const secondary = this.providerFormModel.secondaryContact;
    const secondaryHasAny =
      secondary.name.trim() ||
      secondary.email.trim() ||
      secondary.mobilePhone?.e164 ||
      secondary.landlinePhone?.e164;
    if (secondaryHasAny) {
      if (!secondary.name.trim()) {
        this.providerErrors.secondaryContactName = 'Secondary contact name is required.';
      } else if (!/^[a-zA-Z\s]+$/.test(secondary.name)) {
        this.providerErrors.secondaryContactName = 'Contact name can only contain letters and spaces.';
      }
      if (!secondary.email.trim()) {
        this.providerErrors.secondaryContactEmail = 'Secondary contact email is required.';
      } else if (!/^[\w.-]+@[\w.-]+\.\w+$/.test(secondary.email)) {
        this.providerErrors.secondaryContactEmail = 'Invalid email format.';
      }
      const hasSecondaryMobile = secondary.mobilePhone?.e164;
      const hasSecondaryLandline = secondary.landlinePhone?.e164;

      // Validate secondary mobile phone format if provided (Canadian: +1 followed by 10 digits)
      if (hasSecondaryMobile) {
        const secondaryMobileE164 = secondary.mobilePhone!.e164;
        const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

        if (!canadianPhonePattern.test(secondaryMobileE164)) {
          this.providerErrors.secondaryContactMobilePhone = 'Invalid Canadian mobile phone number format.';
        } else if (secondary.mobilePhone!.country !== 'CA') {
          this.providerErrors.secondaryContactMobilePhone = 'Only Canadian phone numbers are accepted.';
        }
      }

      // Validate secondary landline phone format if provided (Canadian: +1 followed by 10 digits)
      if (hasSecondaryLandline) {
        const secondaryLandlineE164 = secondary.landlinePhone!.e164;
        const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

        if (!canadianPhonePattern.test(secondaryLandlineE164)) {
          this.providerErrors.secondaryContactLandlinePhone = 'Invalid Canadian landline phone number format.';
        } else if (secondary.landlinePhone!.country !== 'CA') {
          this.providerErrors.secondaryContactLandlinePhone = 'Only Canadian phone numbers are accepted.';
        }
      }

      // At least one phone number is required
      if (!hasSecondaryMobile && !hasSecondaryLandline) {
        this.providerErrors.secondaryContactPhone = 'At least one phone number is required.';
      }

      // If both phone numbers are provided, they must be from the same country
      if (hasSecondaryMobile && hasSecondaryLandline) {
        if (secondary.mobilePhone?.country !== secondary.landlinePhone?.country) {
          this.providerErrors.secondaryContactPhone = 'Secondary contact phone numbers must be from the same country.';
        }
      }
    }

    // Security License
    if (!this.providerFormModel.securityLicense.licenseNumber.trim()) {
      this.providerErrors.licenseNumber = 'Security license number is required.';
    }
    if (!this.providerFormModel.securityLicense.licenseType.trim()) {
      this.providerErrors.licenseType = 'License type is required.';
    }
    if (!this.providerFormModel.securityLicense.issuingProvince.trim()) {
      this.providerErrors.issuingProvince = 'Issuing province is required.';
    }
    if (!this.providerFormModel.securityLicense.issuingAuthority.trim()) {
      this.providerErrors.issuingAuthority = 'Issuing authority is required.';
    }

    // Validate issue date (cannot be in the future)
    if (this.providerFormModel.securityLicense.issueDate) {
      const issueDate = new Date(this.providerFormModel.securityLicense.issueDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      issueDate.setHours(0, 0, 0, 0);

      if (issueDate > today) {
        this.providerErrors.issueDate = 'Issue date cannot be in the future.';
      }
    }

    if (!this.providerFormModel.securityLicense.expiryDate) {
      this.providerErrors.expiryDate = 'Expiry date is required.';
    } else if (this.providerFormModel.securityLicense.issueDate) {
      const issueDate = new Date(this.providerFormModel.securityLicense.issueDate);
      const expiryDate = new Date(this.providerFormModel.securityLicense.expiryDate);
      if (expiryDate < issueDate) {
        this.providerErrors.expiryDate = 'Expiry date cannot be before issue date.';
      }
    }

    // Operating Regions (at least one required)
    const validRegions = this.providerFormModel.operatingRegions.filter(region => region.city.trim());
    if (validRegions.length === 0) {
      this.providerErrors.operatingRegions = 'At least one operating region is required.';
    }
    this.providerFormModel.operatingRegions.forEach((region, index) => {
      if (!region.city.trim()) {
        this.providerErrors[`region_${index}_city`] = 'City is required.';
      } else if (!/^[a-zA-Z\s]+$/.test(region.city)) {
        this.providerErrors[`region_${index}_city`] = 'City can only contain letters and spaces.';
      }
      if (!region.country.trim()) {
        this.providerErrors[`region_${index}_country`] = 'Country is required.';
      }
      if (region.country === 'CA' && !region.province.trim()) {
        this.providerErrors[`region_${index}_province`] = 'Province is required for Canada.';
      }
      if (region.coverageRadiusKm != null && region.coverageRadiusKm < 1) {
        this.providerErrors[`region_${index}_radius`] = 'Coverage radius must be at least 1 km.';
      }
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

  onSecurityLicenseFileSelected(file: File | null): void {
    this.securityLicenseUploadError = '';

    if (!file) {
      if (this.providerFormModel.securityLicense.existingFileId) {
        this.deleteSecurityLicenseFile();
      }
      this.providerFormModel.securityLicense.file = null;
      this.providerFormModel.securityLicense.existingFileUrl = undefined;
      this.providerFormModel.securityLicense.existingFileName = undefined;
      this.providerFormModel.securityLicense.existingFileId = undefined;
      this.providerFormModel.securityLicense.existingFileMimeType = undefined;
      this.providerFormModel.securityLicense.existingFileSize = undefined;
      return;
    }

    this.securityLicenseUploadInProgress = true;
    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/security-license', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.securityLicenseUploadInProgress = false;
          this.providerFormModel.securityLicense.file = null;
          this.providerFormModel.securityLicense.existingFileId = response?.file_id;
          this.providerFormModel.securityLicense.existingFileUrl = response?.file_url;
          this.providerFormModel.securityLicense.existingFileName = response?.file_name;
          this.providerFormModel.securityLicense.existingFileMimeType = response?.mime_type;
          this.providerFormModel.securityLicense.existingFileSize = response?.size;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress = false;
          this.securityLicenseUploadError = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  deleteSecurityLicenseFile(): void {
    const existingFileId = this.providerFormModel.securityLicense.existingFileId;
    if (!existingFileId) {
      return;
    }

    this.securityLicenseUploadInProgress = true;
    this.apiService.delete(`tenant/files/security-license/${existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.securityLicenseUploadInProgress = false;
          this.providerFormModel.securityLicense.existingFileUrl = undefined;
          this.providerFormModel.securityLicense.existingFileName = undefined;
          this.providerFormModel.securityLicense.existingFileId = undefined;
          this.providerFormModel.securityLicense.existingFileMimeType = undefined;
          this.providerFormModel.securityLicense.existingFileSize = undefined;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress = false;
          this.securityLicenseUploadError = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  submitProviderForm() {
    if (!this.validateProviderForm()) {
      return;
    }

    // Filter out empty strings from arrays
    const validRegions = this.providerFormModel.operatingRegions.filter(region => region.city.trim());
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

    const tenantUpdatePayload = {
      tenant_type: TENANT_TYPES.SERVICE_PROVIDER,
      profile: {
        legal_company_name: this.providerFormModel.legalCompanyName,
        trading_name: this.providerFormModel.tradingName || undefined,
        company_registration_number: this.providerFormModel.companyRegistrationNumber,
        year_of_establishment: this.providerFormModel.yearOfEstablishment || undefined,
        company_website: this.providerFormModel.companyWebsite || undefined,
        tax_registration_number: this.providerFormModel.taxRegistrationNumber || undefined,
        head_office_address: {
          street: this.providerFormModel.headOfficeAddress.street,
          city: this.providerFormModel.headOfficeAddress.city,
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
        security_license: {
          license_number: this.providerFormModel.securityLicense.licenseNumber,
          license_type: this.providerFormModel.securityLicense.licenseType,
          issuing_province: this.providerFormModel.securityLicense.issuingProvince,
          issuing_authority: this.providerFormModel.securityLicense.issuingAuthority,
          ...(this.providerFormModel.securityLicense.issueDate && {
            issue_date: this.providerFormModel.securityLicense.issueDate
          }),
          expiry_date: this.providerFormModel.securityLicense.expiryDate,
          ...(this.providerFormModel.securityLicense.existingFileId && {
            document_file_id: this.providerFormModel.securityLicense.existingFileId
          }),
          ...(this.providerFormModel.securityLicense.existingFileUrl && {
            document_file_url: this.providerFormModel.securityLicense.existingFileUrl
          }),
          ...(this.providerFormModel.securityLicense.existingFileName && {
            document_file_name: this.providerFormModel.securityLicense.existingFileName
          }),
          ...(this.providerFormModel.securityLicense.existingFileMimeType && {
            document_file_mime_type: this.providerFormModel.securityLicense.existingFileMimeType
          }),
          ...(this.providerFormModel.securityLicense.existingFileSize != null && {
            document_file_size: this.providerFormModel.securityLicense.existingFileSize
          })
        },
        insurance_details: {
          policy_number: this.providerFormModel.insuranceDetails.policyNumber || undefined,
          coverage_amount: this.providerFormModel.insuranceDetails.coverageAmount ?? undefined,
          currency: this.providerFormModel.insuranceDetails.currency || 'USD',
          expiry_date: this.providerFormModel.insuranceDetails.expiryDate || undefined,
          coverage_details: this.providerFormModel.insuranceDetails.coverageDetails || undefined
        },
        operating_regions: validRegions.map(region => ({
          city: region.city,
          country: region.country,
          province: region.province,
          coverage_radius_km: region.coverageRadiusKm
        })),
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
