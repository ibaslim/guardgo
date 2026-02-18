import { CommonModule } from '@angular/common';
import { Component, Input, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { Router } from '@angular/router';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { FileUploadComponent } from '../../components/form/file-upload/file-upload.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { WeeklyAvailabilityComponent } from "../../components/form/weekly-availability/weekly-availability.component";
import { MobilePhoneInputComponent } from '../../components/form/phone-input/mobile-phone-input.component';
import { LandlinePhoneInputComponent } from '../../components/form/phone-input/landline-phone-input.component';
import { SectionComponent } from '../../components/section/section.component';
import { PageComponent } from '../../components/page/page.component';
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
import { Guard, GuardErrors, IdentificationDocument, SecurityLicenseDocument, PoliceClearanceRecord, TrainingCertificate, WeeklyAvailability } from '../../shared/model/guard';
import { toTitleCase } from '../../shared/helpers/format.helper';

@Component({
  selector: 'app-guard-setting',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    BaseInputComponent,
    FileUploadComponent,
    SelectInputComponent,
    WeeklyAvailabilityComponent,
    MobilePhoneInputComponent,
    LandlinePhoneInputComponent,
    SectionComponent,
    PageComponent,
    ButtonComponent,
    StickyActionBarComponent,
    ErrorMessageComponent,
    ProfilePictureUploadComponent,
    CardComponent,
    ClientPreferredGuardTypesComponent
  ],
  templateUrl: './guard-setting.component.html',
  styleUrls: ['./guard-setting.component.css']
})
export class GuardSettingComponent implements OnInit, OnDestroy {

  @Input() showPageWrapper: boolean = true;
  @Input() guardData?: Guard;

  isEditMode = false;

  // Available options for dropdowns (loaded from backend metadata)
  identityDocumentTypes: { value: string; label: string; requiresProvince: boolean; requiresExpiry: boolean; mandatory?: boolean }[] = [];
  documentTypes: { value: string; label: string; requiresProvince: boolean; requiresExpiry: boolean; mandatory?: boolean }[] = [];

  // Converted options for select-input component
  documentTypeOptions: { value: string; label: string }[] = [];

  securityLicenseTypeOptions: { value: string; label: string }[] = [];

  trainingCertificateOptions: { value: string; label: string }[] = [];

  trainingCertificateIssuerOptionsMap: Record<string, { value: string; label: string }[]> = {};

  getTrainingIssuerOptions(certificateName: string): { value: string; label: string }[] {
    return this.trainingCertificateIssuerOptionsMap[certificateName] || [];
  }

  policeClearanceAuthorityOptions: { value: string; label: string }[] = [];

  guardTypeOptions: { value: string; label: string }[] = [];

  loadGuardMetadata(onLoaded?: () => void): void {
    this.apiService.get<any>('public/guard-metadata')
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          if (response?.countries?.length) {
            this.countryOptions = response.countries;
          }
          if (response?.canadianProvinces?.length) {
            this.provinceOptions = response.canadianProvinces;
          }
          if (response?.identityDocumentTypes?.length) {
            this.identityDocumentTypes = response.identityDocumentTypes;
            this.documentTypes = response.identityDocumentTypes;
            this.documentTypeOptions = response.identityDocumentTypes.map((doc: any) => ({
              value: doc.value,
              label: doc.label
            }));
          }
          if (response?.securityLicenseTypes?.length) {
            this.securityLicenseTypeOptions = response.securityLicenseTypes;
          }
          if (response?.trainingCertificateTypes?.length) {
            this.trainingCertificateOptions = response.trainingCertificateTypes;
          }
          if (response?.trainingIssuerOptionsMap) {
            this.trainingCertificateIssuerOptionsMap = response.trainingIssuerOptionsMap;
          }
          if (response?.policeClearanceAuthorityTypes?.length) {
            this.policeClearanceAuthorityOptions = response.policeClearanceAuthorityTypes;
          }
          if (response?.guardTypeOptions?.length) {
            this.guardTypeOptions = response.guardTypeOptions;
          } else {
            this.apiService.get<any>('public/client-metadata')
              .pipe(takeUntil(this.destroy$))
              .subscribe({
                next: (clientResponse) => {
                  if (clientResponse?.guardTypeOptions?.length) {
                    this.guardTypeOptions = clientResponse.guardTypeOptions;
                  }
                }
              });
          }
          onLoaded?.();
        },
        error: () => {
          onLoaded?.();
        }
      });
  }

  getTrainingCertificateLabel(value: string): string {
    return this.getOptionLabel(value, this.trainingCertificateOptions);
  }

  getPoliceAuthorityLabel(value: string): string {
    return this.getOptionLabel(value, this.policeClearanceAuthorityOptions);
  }

  getSecurityLicenseTypeLabel(value: string): string {
    return this.getOptionLabel(value, this.securityLicenseTypeOptions);
  }

  private getOptionLabel(value: string, options: { value: string; label: string }[]): string {
    const option = options.find(opt => opt.value === value);
    return option?.label || value;
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

  /**
   * Get the suggested issuing authority for a given province code
   * @param provinceCode - Two-letter province code (e.g., 'ON', 'AB')
   * @returns The issuing authority name for the province
   */
  getSuggestedIssuingAuthority(provinceCode: string): string {
    return getIssuingAuthorityForProvince(provinceCode);
  }


  //Convert frontend time-based availability to backend format
  private mapWeeklyAvailabilityToBackend(availability: WeeklyAvailability): any {
    const backendFormat: any = {};

    Object.keys(availability).forEach(day => {
      const dayData = availability[day];

      if (dayData.enabled && dayData.timeRanges.length > 0) {
        // Filter out empty time ranges (where start or end is missing)
        const validRanges = dayData.timeRanges.filter(range => range.start && range.end);

        backendFormat[day] = validRanges.map(range => ({
          start: range.start,
          end: range.end
        }));
      } else {
        backendFormat[day] = [];
      }
    });

    return backendFormat;
  }


  // Convert backend availability format to frontend time-based format
  private mapWeeklyAvailabilityFromBackend(availability: any): WeeklyAvailability {
    const defaultAvailability: WeeklyAvailability = {
      Monday: { enabled: false, timeRanges: [] },
      Tuesday: { enabled: false, timeRanges: [] },
      Wednesday: { enabled: false, timeRanges: [] },
      Thursday: { enabled: false, timeRanges: [] },
      Friday: { enabled: false, timeRanges: [] },
      Saturday: { enabled: false, timeRanges: [] },
      Sunday: { enabled: false, timeRanges: [] }
    };

    if (!availability) {
      return defaultAvailability;
    }

    // Check if backend data is in the new time-based format
    Object.keys(defaultAvailability).forEach(day => {
      if (availability[day] && Array.isArray(availability[day])) {
        const timeRanges = availability[day];

        if (timeRanges.length > 0) {
          defaultAvailability[day] = {
            enabled: true,
            timeRanges: timeRanges.map((range: any) => ({
              start: range.start || '',
              end: range.end || ''
            }))
          };
        }
      }
    });

    return defaultAvailability;
  }

  provinceOptions: { value: string; label: string }[] = [];

  countryOptions: { value: string; label: string }[] = [];

  // UI helper methods
  requiresProvince(type: string): boolean {
    return this.identityDocumentTypes.find(doc => doc.value === type)?.requiresProvince ?? false;
  }

  requiresExpiry(type: string): boolean {
    return this.identityDocumentTypes.find(doc => doc.value === type)?.requiresExpiry ?? false;
  }
  toTitleCase = toTitleCase;

  guardFormModel: Guard = {
    name: '',
    contact: '', // Legacy
    mobilePhone: null,
    landlinePhone: null,
    dob: '',
    address: {
      street: '',
      city: '',
      country: 'CA',
      province: '',
      postalCode: ''
    },
    secondaryContact: {
      name: '',
      email: '',
      mobilePhone: null,
      landlinePhone: null
    },
    identification: {
      documents: [],
      primaryDocumentId: undefined,
      idType: 'canadian_passport', // Legacy
      idNumber: '',
      document: null
    },
    securityLicenses: [],
    policeClearances: [],
    trainingCertificates: [],
    preferredGuardTypes: [],
    operationalRadius: null,
    weeklyAvailability: {
      Monday: { enabled: false, timeRanges: [] },
      Tuesday: { enabled: false, timeRanges: [] },
      Wednesday: { enabled: false, timeRanges: [] },
      Thursday: { enabled: false, timeRanges: [] },
      Friday: { enabled: false, timeRanges: [] },
      Saturday: { enabled: false, timeRanges: [] },
      Sunday: { enabled: false, timeRanges: [] }
    }
  };


  guardErrors: GuardErrors = {};
  isSubmitting = false;
  private destroy$ = new Subject<void>();
  private lastAutoLegalName = '';

  // Identity document upload state
  identityUploadInProgress: Record<string, boolean> = {};
  identityUploadErrors: Record<string, string> = {};

  // Security license upload state
  securityLicenseUploadInProgress: Record<string, boolean> = {};
  securityLicenseUploadErrors: Record<string, string> = {};

  // Police clearance upload state
  policeClearanceUploadInProgress: Record<string, boolean> = {};
  policeClearanceUploadErrors: Record<string, string> = {};

  // Training certificate upload state
  trainingCertificateUploadInProgress: Record<string, boolean> = {};
  trainingCertificateUploadErrors: Record<string, string> = {};

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) { }

  ngOnInit(): void {
    this.loadGuardMetadata(() => {
      if (this.guardData && this.hasGuardData(this.guardData)) {
        this.guardFormModel = this.transformBackendDataToForm(this.guardData);
        this.isEditMode = true;
      } else {
        this.isEditMode = false;
      }

      this.ensureCanadaDocumentDefaults();
      this.lastAutoLegalName = this.guardFormModel.name || '';
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private ensureCanadaDocumentDefaults(): void {
    if (this.guardFormModel.address.country !== 'CA') {
      return;
    }

    if (!this.guardFormModel.identification.documents || this.guardFormModel.identification.documents.length === 0) {
      this.addIdentificationDocument();
    }

    if (!this.guardFormModel.securityLicenses || this.guardFormModel.securityLicenses.length === 0) {
      this.addSecurityLicense();
    }

    if (!this.guardFormModel.policeClearances || this.guardFormModel.policeClearances.length === 0) {
      this.addPoliceClearance();
    }

    if (!this.guardFormModel.trainingCertificates || this.guardFormModel.trainingCertificates.length === 0) {
      this.addTrainingCertificate();
    }
  }

  onGuardNameChanged(newName: string): void {
    this.guardFormModel.name = newName;

    if (!this.guardFormModel.securityLicenses || this.guardFormModel.securityLicenses.length === 0) {
      this.lastAutoLegalName = newName || '';
      return;
    }

    this.guardFormModel.securityLicenses.forEach((license) => {
      if (!license.fullLegalName || license.fullLegalName === this.lastAutoLegalName) {
        license.fullLegalName = newName || '';
      }
    });

    this.lastAutoLegalName = newName || '';
  }


  // Transform backend data format to frontend form format
  private transformBackendDataToForm(data: Guard): Guard {
    const profile = (data as any)?.profile || data || {};
    const formData = JSON.parse(JSON.stringify(profile));

    formData.name = profile.full_name || profile.name || formData.name || '';
    formData.dob = profile.date_of_birth || profile.dateOfBirth || formData.dob || '';

    const rawAddress = profile.home_address || profile.homeAddress || profile.address || {};
    formData.address = {
      street: rawAddress.street || '',
      city: rawAddress.city || '',
      country: rawAddress.country || 'CA',
      province: rawAddress.province || '',
      postalCode: rawAddress.postal_code || rawAddress.postalCode || ''
    };

    const rawAvailability = profile.weekly_availability || profile.weeklyAvailability;
    formData.weeklyAvailability = this.mapWeeklyAvailabilityFromBackend(rawAvailability);

    if (profile.max_travel_radius_km != null) {
      const km = Number(profile.max_travel_radius_km);
      formData.operationalRadius = Number.isFinite(km) ? Number((km / 1.60934).toFixed(1)) : null;
    }

    // Transform phone numbers from backend
    const mobilePhoneValue = profile.mobile_phone || (data as any).mobile_phone;
    const mobilePhoneCountry = profile.mobile_phone_country || (data as any).mobile_phone_country || 'CA';
    if (mobilePhoneValue) {
      formData.mobilePhone = {
        e164: mobilePhoneValue,
        national: mobilePhoneValue, // Backend should provide formatted version
        international: mobilePhoneValue,
        country: mobilePhoneCountry,
        phoneType: 'mobile' as const,
        rawInput: mobilePhoneValue
      };
    }
    const landlinePhoneValue = profile.landline_phone || (data as any).landline_phone;
    const landlinePhoneCountry = profile.landline_phone_country || (data as any).landline_phone_country || 'CA';
    if (landlinePhoneValue) {
      formData.landlinePhone = {
        e164: landlinePhoneValue,
        national: landlinePhoneValue,
        international: landlinePhoneValue,
        country: landlinePhoneCountry,
        phoneType: 'landline' as const,
        rawInput: landlinePhoneValue
      };
    }

    // Transform secondary contact phone numbers
    if (!formData.secondaryContact) {
      formData.secondaryContact = {
        name: '',
        email: '',
        mobilePhone: null,
        landlinePhone: null
      };
    }

    if (profile.secondary_contact) {
      const secondaryContactData = profile.secondary_contact;
      formData.secondaryContact.name = secondaryContactData.name || '';
      formData.secondaryContact.email = secondaryContactData.email || '';

      const secondaryPhone = secondaryContactData.phone || secondaryContactData.mobile_phone;
      if (secondaryPhone) {
        formData.secondaryContact.mobilePhone = {
          e164: secondaryPhone,
          national: secondaryPhone,
          international: secondaryPhone,
          country: secondaryContactData.mobile_phone_country || 'CA',
          phoneType: 'mobile' as const,
          rawInput: secondaryPhone
        };
      }

      if (secondaryContactData.landline_phone) {
        formData.secondaryContact.landlinePhone = {
          e164: secondaryContactData.landline_phone,
          national: secondaryContactData.landline_phone,
          international: secondaryContactData.landline_phone,
          country: secondaryContactData.landline_phone_country || 'CA',
          phoneType: 'landline' as const,
          rawInput: secondaryContactData.landline_phone
        };
      }
    }

    if (formData.address?.country) {
      const normalizedCountry = String(formData.address.country).trim().toLowerCase();
      if (normalizedCountry === 'canada' || normalizedCountry === 'ca') {
        formData.address.country = 'CA';
      }
    }

    if (!formData.identification) {
      formData.identification = { documents: [] };
    }

    // Transform identification documents if they exist
    if (formData.identification?.documents && Array.isArray(formData.identification.documents)) {
      formData.identification.documents = formData.identification.documents.map((doc: any, index: number) => {
        // Use composite ID based on document type + index for stability across edits
        // If backend provides an ID, use that; otherwise create stable ID
        const backendId = doc.id || doc.document_id;
        const stableId = backendId || `doc_type_${doc.document_type || 'unknown'}_idx_${index}`;

        return {
          documentType: doc.document_type || doc.documentType || '',
          number: doc.document_number || doc.number || '',
          province: doc.province || undefined,
          expiryDate: doc.expiry_date || doc.expiryDate || undefined,
          file: null, // Files not loaded from backend (security)
          existingFileUrl: doc.document_file_url || doc.file_url || undefined,
          existingFileName: doc.document_file_name || doc.file_name || undefined,
          existingFileId: doc.document_file_id || doc.file_id || undefined,
          existingFileMimeType: doc.document_file_mime_type || doc.file_mime_type || undefined,
          existingFileSize: doc.document_file_size || doc.file_size || undefined,
          id: stableId
        };
      });
    } else if (formData.identification?.id_type || formData.identification?.id_number) {
      const legacyIdType = formData.identification.id_type || '';
      const legacyIdNumber = formData.identification.id_number || '';
      formData.identification.documents = [
        {
          documentType: legacyIdType,
          number: legacyIdNumber,
          province: undefined,
          expiryDate: undefined,
          file: null,
          existingFileUrl: formData.identification.document_url || undefined,
          existingFileName: undefined,
          existingFileId: undefined,
          existingFileMimeType: undefined,
          existingFileSize: undefined,
          id: `doc_legacy_${Date.now()}`
        }
      ];
    } else if (!formData.identification?.documents) {
      // Initialize documents array if it doesn't exist
      if (formData.identification) {
        formData.identification.documents = [];
      }
    }

    const rawSecurityLicenses = (formData as any).security_licenses || formData.securityLicenses || [];
    if (Array.isArray(rawSecurityLicenses) && rawSecurityLicenses.length > 0) {
      formData.securityLicenses = rawSecurityLicenses.map((license: any, index: number) => {
        const backendId = license.id || license.license_id;
        const stableId = backendId || `sec_license_${license.license_number || 'unknown'}_${index}`;
        return {
          fullLegalName: license.full_legal_name || license.fullLegalName || '',
          licenseNumber: license.license_number || license.licenseNumber || '',
          licenseType: this.normalizeOptionValue(
            license.license_type || license.licenseType || 'securityGuard',
            this.securityLicenseTypeOptions
          ),
          issuingProvince: license.issuing_province || license.issuingProvince || '',
          issuingAuthority: license.issuing_authority || license.issuingAuthority || '',
          issueDate: license.issue_date || license.issueDate || '',
          expiryDate: license.expiry_date || license.expiryDate || '',
          file: null,
          existingFileUrl: license.document_file_url || license.file_url || undefined,
          existingFileName: license.document_file_name || license.file_name || undefined,
          existingFileId: license.document_file_id || license.file_id || undefined,
          existingFileMimeType: license.document_file_mime_type || license.file_mime_type || undefined,
          existingFileSize: license.document_file_size || license.file_size || undefined,
          id: stableId
        } as SecurityLicenseDocument;
      });
    } else if ((formData as any).security_license || formData.securityLicense) {
      const license = (formData as any).security_license || formData.securityLicense || {};
      formData.securityLicenses = [
        {
          fullLegalName: license.full_legal_name || license.fullLegalName || formData.name || '',
          licenseNumber: license.license_number || license.licenseNumber || '',
          licenseType: this.normalizeOptionValue(
            license.license_type || license.licenseType || 'securityGuard',
            this.securityLicenseTypeOptions
          ),
          issuingProvince: license.issuing_province || license.issuingProvince || '',
          issuingAuthority: license.issuing_authority || license.issuingAuthority || '',
          issueDate: license.issue_date || license.issueDate || '',
          expiryDate: license.expiry_date || license.expiryDate || '',
          file: null,
          existingFileUrl: license.document_file_url || license.file_url || undefined,
          existingFileName: license.document_file_name || license.file_name || undefined,
          existingFileId: license.document_file_id || license.file_id || undefined,
          existingFileMimeType: license.document_file_mime_type || license.file_mime_type || undefined,
          existingFileSize: license.document_file_size || license.file_size || undefined,
          id: `sec_license_legacy_${Date.now()}`
        } as SecurityLicenseDocument
      ];
    } else if (!formData.securityLicenses) {
      formData.securityLicenses = [];
    }

    const rawPoliceClearances = (formData as any).police_clearances || formData.policeClearances || [];
    if (Array.isArray(rawPoliceClearances) && rawPoliceClearances.length > 0) {
      formData.policeClearances = rawPoliceClearances.map((record: any, index: number) => {
        const backendId = record.id || record.clearance_id;
        const stableId = backendId || `police_clearance_${record.reference_number || 'unknown'}_${index}`;
        const incomingAuthority = record.issuing_authority || record.issuingAuthority || '';
        const incomingAuthorityOther = record.issuing_authority_other || record.issuingAuthorityOther || '';
        const normalizedAuthority = this.normalizeOptionValue(incomingAuthority, this.policeClearanceAuthorityOptions);
        const knownAuthorities = this.policeClearanceAuthorityOptions.map(opt => opt.value);
        const isKnownAuthority = knownAuthorities.includes(normalizedAuthority);

        return {
          issuingAuthorityType: incomingAuthorityOther
            ? 'other'
            : (isKnownAuthority ? normalizedAuthority : (incomingAuthority ? 'other' : '')),
          issuingAuthorityOther: incomingAuthorityOther || (!isKnownAuthority ? incomingAuthority : ''),
          issuingProvince: record.issuing_province || record.issuingProvince || '',
          issuingCity: record.issuing_city || record.issuingCity || '',
          issueDate: record.issue_date || record.issueDate || '',
          referenceNumber: record.reference_number || record.referenceNumber || undefined,
          file: null,
          existingFileUrl: record.document_file_url || record.file_url || undefined,
          existingFileName: record.document_file_name || record.file_name || undefined,
          existingFileId: record.document_file_id || record.file_id || undefined,
          existingFileMimeType: record.document_file_mime_type || record.file_mime_type || undefined,
          existingFileSize: record.document_file_size || record.file_size || undefined,
          id: stableId
        } as PoliceClearanceRecord;
      });
    } else if (!formData.policeClearances) {
      formData.policeClearances = [];
    }

    const rawTrainingCertificates = (formData as any).training_certificates || formData.trainingCertificates || [];
    if (Array.isArray(rawTrainingCertificates) && rawTrainingCertificates.length > 0) {
      formData.trainingCertificates = rawTrainingCertificates.map((cert: any, index: number) => {
        const backendId = cert.id || cert.certificate_id;
        const stableId = backendId || `training_cert_${cert.certificate_name || 'unknown'}_${index}`;
        const certificateName = this.normalizeOptionValue(
          cert.certificate_name || cert.certificateName || 'basicSecurityTraining',
          this.trainingCertificateOptions
        );
        const incomingIssuer = cert.issuing_organization || cert.issuingOrganization || '';
        const incomingIssuerOther = cert.issuing_organization_other || cert.issuingOrganizationOther || '';
        const issuerOptions = this.getTrainingIssuerOptions(certificateName);
        const knownIssuers = issuerOptions.map(opt => opt.value);
        const normalizedIssuer = this.normalizeOptionValue(incomingIssuer, issuerOptions);
        const isKnownIssuer = knownIssuers.includes(normalizedIssuer);
        return {
          certificateName,
          issuingOrganizationType: incomingIssuerOther
            ? 'other'
            : (isKnownIssuer ? normalizedIssuer : (incomingIssuer ? 'other' : '')),
          issuingOrganizationOther: incomingIssuerOther || (!isKnownIssuer ? incomingIssuer : ''),
          issueDate: cert.issue_date || cert.issueDate || '',
          expiryDate: cert.expiry_date || cert.expiryDate || undefined,
          file: null,
          existingFileUrl: cert.document_file_url || cert.file_url || undefined,
          existingFileName: cert.document_file_name || cert.file_name || undefined,
          existingFileId: cert.document_file_id || cert.file_id || undefined,
          existingFileMimeType: cert.document_file_mime_type || cert.file_mime_type || undefined,
          existingFileSize: cert.document_file_size || cert.file_size || undefined,
          id: stableId
        } as TrainingCertificate;
      });
    } else if (!formData.trainingCertificates) {
      formData.trainingCertificates = [];
    }

    // Transform preferred guard types if they exist
    const rawPreferredGuardTypes = (formData as any).preferred_guard_types || formData.preferredGuardTypes || [];
    if (Array.isArray(rawPreferredGuardTypes)) {
      formData.preferredGuardTypes = rawPreferredGuardTypes.map((guardType: any) => {
        return typeof guardType === 'string' ? guardType : guardType.value || guardType;
      });
    } else if (!formData.preferredGuardTypes) {
      formData.preferredGuardTypes = [];
    }

    return formData;
  }

  hasGuardData(data: Guard): boolean {
    return !!(
      data.name.trim() ||
      data.contact.trim() ||
      data.mobilePhone?.e164 ||
      data.landlinePhone?.e164 ||
      data.dob ||
      data.address.street.trim() ||
      (data.identification.documents && data.identification.documents.length > 0) ||
      data.identification.idNumber?.trim() ||
      (data.securityLicenses && data.securityLicenses.length > 0) ||
      (data.policeClearances && data.policeClearances.length > 0) ||
      (data.trainingCertificates && data.trainingCertificates.length > 0) ||
      data.operationalRadius != null ||
      Object.values(data.weeklyAvailability).some(day => day.enabled && day.timeRanges.length > 0)
    );
  }


  // Add a new identification document to the list
  addIdentificationDocument(): void {
    const newIndex = this.guardFormModel.identification.documents.length;
    const newDoc: IdentificationDocument = {
      documentType: '',
      number: '',
      province: undefined,
      expiryDate: undefined,
      file: null,
      // Use stable ID based on index for new documents (will be replaced by backend ID on save)
      id: `doc_new_${newIndex}_${Date.now()}`
    };
    this.guardFormModel.identification.documents.push(newDoc);
  }

  /**
   * Remove an identification document from the list
   */
  removeIdentificationDocument(index: number): void {
    const doc = this.guardFormModel.identification.documents[index];

    // Clear all errors for this document
    if (doc && doc.id) {
      delete this.guardErrors[`identification_${doc.id}_type`];
      delete this.guardErrors[`identification_${doc.id}_number`];
      delete this.guardErrors[`identification_${doc.id}_province`];
      delete this.guardErrors[`identification_${doc.id}_expiry`];
    }

    // If the removed document was primary, clear the primary selection
    if (
      this.guardFormModel.identification.primaryDocumentId === doc?.id
    ) {
      this.guardFormModel.identification.primaryDocumentId = undefined;
    }

    if (doc?.existingFileId) {
      this.deleteIdentityFile(doc);
    }

    this.guardFormModel.identification.documents.splice(index, 1);
  }

  /**
   * Handle identity document file selection and upload
   */
  onIdentityFileSelected(doc: IdentificationDocument, file: File | null): void {
    if (!doc?.id) {
      return;
    }

    this.identityUploadErrors[doc.id] = '';

    if (!file) {
      if (doc.existingFileId) {
        this.deleteIdentityFile(doc);
      }
      doc.file = null;
      doc.existingFileUrl = undefined;
      doc.existingFileName = undefined;
      doc.existingFileId = undefined;
      doc.existingFileMimeType = undefined;
      doc.existingFileSize = undefined;
      return;
    }

    this.identityUploadInProgress[doc.id] = true;

    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/identity', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.identityUploadInProgress[doc.id as string] = false;
          doc.file = null;
          doc.existingFileId = response?.file_id;
          doc.existingFileUrl = response?.file_url;
          doc.existingFileName = response?.file_name;
          doc.existingFileMimeType = response?.mime_type;
          doc.existingFileSize = response?.size;
        },
        error: (err) => {
          this.identityUploadInProgress[doc.id as string] = false;
          this.identityUploadErrors[doc.id as string] = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  /**
   * Delete uploaded identity document file
   */
  deleteIdentityFile(doc: IdentificationDocument): void {
    if (!doc?.existingFileId) {
      return;
    }

    this.identityUploadInProgress[doc.id as string] = true;

    this.apiService.delete(`tenant/files/identity/${doc.existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.identityUploadInProgress[doc.id as string] = false;
          doc.existingFileId = undefined;
          doc.existingFileUrl = undefined;
          doc.existingFileName = undefined;
          doc.existingFileMimeType = undefined;
          doc.existingFileSize = undefined;
        },
        error: (err) => {
          this.identityUploadInProgress[doc.id as string] = false;
          this.identityUploadErrors[doc.id as string] = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  // ============================================================================
  // Security License Methods
  // ============================================================================

  addSecurityLicense(): void {
    const newIndex = this.guardFormModel.securityLicenses.length;
    const newLicense: SecurityLicenseDocument = {
      fullLegalName: this.guardFormModel.name || '',
      licenseNumber: '',
      licenseType: 'securityGuard',
      issuingProvince: '',
      issuingAuthority: '',
      issueDate: '',
      expiryDate: '',
      file: null,
      id: `sec_license_new_${newIndex}_${Date.now()}`
    };
    this.guardFormModel.securityLicenses.push(newLicense);
  }

  removeSecurityLicense(index: number): void {
    const license = this.guardFormModel.securityLicenses[index];

    if (license?.id) {
      delete this.guardErrors[`security_license_${license.id}_fullLegalName`];
      delete this.guardErrors[`security_license_${license.id}_licenseNumber`];
      delete this.guardErrors[`security_license_${license.id}_licenseType`];
      delete this.guardErrors[`security_license_${license.id}_issuingProvince`];
      delete this.guardErrors[`security_license_${license.id}_issuingAuthority`];
      delete this.guardErrors[`security_license_${license.id}_issueDate`];
      delete this.guardErrors[`security_license_${license.id}_expiryDate`];
    }

    if (license?.existingFileId) {
      this.deleteSecurityLicenseFile(license);
    }

    this.guardFormModel.securityLicenses.splice(index, 1);
  }

  onSecurityLicenseFileSelected(license: SecurityLicenseDocument, file: File | null): void {
    if (!license?.id) {
      return;
    }

    this.securityLicenseUploadErrors[license.id] = '';

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

    this.securityLicenseUploadInProgress[license.id] = true;

    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/security-license', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.securityLicenseUploadInProgress[license.id as string] = false;
          license.file = null;
          license.existingFileId = response?.file_id;
          license.existingFileUrl = response?.file_url;
          license.existingFileName = response?.file_name;
          license.existingFileMimeType = response?.mime_type;
          license.existingFileSize = response?.size;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress[license.id as string] = false;
          this.securityLicenseUploadErrors[license.id as string] = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  deleteSecurityLicenseFile(license: SecurityLicenseDocument): void {
    if (!license?.existingFileId) {
      return;
    }

    this.securityLicenseUploadInProgress[license.id as string] = true;

    this.apiService.delete(`tenant/files/security-license/${license.existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.securityLicenseUploadInProgress[license.id as string] = false;
          license.existingFileId = undefined;
          license.existingFileUrl = undefined;
          license.existingFileName = undefined;
          license.existingFileMimeType = undefined;
          license.existingFileSize = undefined;
        },
        error: (err) => {
          this.securityLicenseUploadInProgress[license.id as string] = false;
          this.securityLicenseUploadErrors[license.id as string] = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  // ============================================================================
  // Police Clearance Methods
  // ============================================================================

  addPoliceClearance(): void {
    const newIndex = this.guardFormModel.policeClearances.length;
    const newRecord: PoliceClearanceRecord = {
      issuingAuthorityType: '',
      issuingAuthorityOther: '',
      issuingProvince: '',
      issuingCity: '',
      issueDate: '',
      referenceNumber: '',
      file: null,
      id: `police_clearance_new_${newIndex}_${Date.now()}`
    };
    this.guardFormModel.policeClearances.push(newRecord);
  }

  removePoliceClearance(index: number): void {
    const record = this.guardFormModel.policeClearances[index];

    if (record?.id) {
      delete this.guardErrors[`police_clearance_${record.id}_issuingAuthorityType`];
      delete this.guardErrors[`police_clearance_${record.id}_issuingAuthorityOther`];
      delete this.guardErrors[`police_clearance_${record.id}_issueDate`];
    }

    if (record?.existingFileId) {
      this.deletePoliceClearanceFile(record);
    }

    this.guardFormModel.policeClearances.splice(index, 1);
  }

  onPoliceClearanceFileSelected(record: PoliceClearanceRecord, file: File | null): void {
    if (!record?.id) {
      return;
    }

    this.policeClearanceUploadErrors[record.id] = '';

    if (!file) {
      if (record.existingFileId) {
        this.deletePoliceClearanceFile(record);
      }
      record.file = null;
      record.existingFileUrl = undefined;
      record.existingFileName = undefined;
      record.existingFileId = undefined;
      record.existingFileMimeType = undefined;
      record.existingFileSize = undefined;
      return;
    }

    this.policeClearanceUploadInProgress[record.id] = true;

    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/police-clearance', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.policeClearanceUploadInProgress[record.id as string] = false;
          record.file = null;
          record.existingFileId = response?.file_id;
          record.existingFileUrl = response?.file_url;
          record.existingFileName = response?.file_name;
          record.existingFileMimeType = response?.mime_type;
          record.existingFileSize = response?.size;
        },
        error: (err) => {
          this.policeClearanceUploadInProgress[record.id as string] = false;
          this.policeClearanceUploadErrors[record.id as string] = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  deletePoliceClearanceFile(record: PoliceClearanceRecord): void {
    if (!record?.existingFileId) {
      return;
    }

    this.policeClearanceUploadInProgress[record.id as string] = true;

    this.apiService.delete(`tenant/files/police-clearance/${record.existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.policeClearanceUploadInProgress[record.id as string] = false;
          record.existingFileId = undefined;
          record.existingFileUrl = undefined;
          record.existingFileName = undefined;
          record.existingFileMimeType = undefined;
          record.existingFileSize = undefined;
        },
        error: (err) => {
          this.policeClearanceUploadInProgress[record.id as string] = false;
          this.policeClearanceUploadErrors[record.id as string] = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  // ============================================================================
  // Training Certificate Methods
  // ============================================================================

  addTrainingCertificate(): void {
    const newIndex = this.guardFormModel.trainingCertificates.length;
    const newCert: TrainingCertificate = {
      certificateName: '',
      issuingOrganizationType: '',
      issuingOrganizationOther: '',
      issueDate: '',
      expiryDate: '',
      file: null,
      id: `training_cert_new_${newIndex}_${Date.now()}`
    };
    this.guardFormModel.trainingCertificates.push(newCert);
  }

  removeTrainingCertificate(index: number): void {
    const cert = this.guardFormModel.trainingCertificates[index];

    if (cert?.id) {
      delete this.guardErrors[`training_certificate_${cert.id}_certificateName`];
      delete this.guardErrors[`training_certificate_${cert.id}_issuingOrganizationType`];
      delete this.guardErrors[`training_certificate_${cert.id}_issuingOrganizationOther`];
      delete this.guardErrors[`training_certificate_${cert.id}_issueDate`];
      delete this.guardErrors[`training_certificate_${cert.id}_expiryDate`];
    }

    if (cert?.existingFileId) {
      this.deleteTrainingCertificateFile(cert);
    }

    this.guardFormModel.trainingCertificates.splice(index, 1);
  }

  onTrainingCertificateFileSelected(cert: TrainingCertificate, file: File | null): void {
    if (!cert?.id) {
      return;
    }

    this.trainingCertificateUploadErrors[cert.id] = '';

    if (!file) {
      if (cert.existingFileId) {
        this.deleteTrainingCertificateFile(cert);
      }
      cert.file = null;
      cert.existingFileUrl = undefined;
      cert.existingFileName = undefined;
      cert.existingFileId = undefined;
      cert.existingFileMimeType = undefined;
      cert.existingFileSize = undefined;
      return;
    }

    this.trainingCertificateUploadInProgress[cert.id] = true;

    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post('tenant/files/training-certificate', formData)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response: any) => {
          this.trainingCertificateUploadInProgress[cert.id as string] = false;
          cert.file = null;
          cert.existingFileId = response?.file_id;
          cert.existingFileUrl = response?.file_url;
          cert.existingFileName = response?.file_name;
          cert.existingFileMimeType = response?.mime_type;
          cert.existingFileSize = response?.size;
        },
        error: (err) => {
          this.trainingCertificateUploadInProgress[cert.id as string] = false;
          this.trainingCertificateUploadErrors[cert.id as string] = err?.error?.detail || 'Failed to upload document.';
        }
      });
  }

  onTrainingCertificateTypeChange(cert: TrainingCertificate): void {
    const options = this.getTrainingIssuerOptions(cert.certificateName);
    const validValues = options.map(opt => opt.value);

    if (!validValues.includes(cert.issuingOrganizationType)) {
      cert.issuingOrganizationType = '';
      cert.issuingOrganizationOther = '';
    }
  }

  deleteTrainingCertificateFile(cert: TrainingCertificate): void {
    if (!cert?.existingFileId) {
      return;
    }

    this.trainingCertificateUploadInProgress[cert.id as string] = true;

    this.apiService.delete(`tenant/files/training-certificate/${cert.existingFileId}`)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.trainingCertificateUploadInProgress[cert.id as string] = false;
          cert.existingFileId = undefined;
          cert.existingFileUrl = undefined;
          cert.existingFileName = undefined;
          cert.existingFileMimeType = undefined;
          cert.existingFileSize = undefined;
        },
        error: (err) => {
          this.trainingCertificateUploadInProgress[cert.id as string] = false;
          this.trainingCertificateUploadErrors[cert.id as string] = err?.error?.detail || 'Failed to delete document.';
        }
      });
  }

  /**
   * Get the document type label
   */
  getDocumentLabel(documentType: string): string {
    const doc = this.documentTypes.find(d => d.value === documentType);
    return doc ? doc.label : documentType;
  }

  /**
   * Check if document type already exists in the list
   */
  hasDuplicateDocumentType(documentType: string, currentDocId?: string): boolean {
    return this.guardFormModel.identification.documents.some(
      doc => doc.documentType === documentType && doc.id !== currentDocId
    );
  }

  /**
   * Validate a single document - returns errors per field
   */
  validateDocument(doc: IdentificationDocument): { valid: boolean; errors: { [key: string]: string } } {
    const errors: { [key: string]: string } = {};

    if (!doc.documentType) {
      errors['type'] = 'Document type is required.';
    } else {
      // Check for duplicate document types
      if (this.hasDuplicateDocumentType(doc.documentType, doc.id)) {
        errors['type'] = 'You have already added this document type.';
      }
    }

    if (!doc.number.trim()) {
      errors['number'] = 'Document number is required.';
    } else if (doc.documentType) {
      // Validate document number format
      const pattern = {
        drivers_license: /^[A-Z0-9\-]{4,20}$/i,
        provincial_id: /^[A-Z0-9\-]{4,20}$/i,
        canadian_passport: /^[A-Z0-9]{6,9}$/i,
        pr_card: /^[A-Z0-9]{8,12}$/i,
        work_permit: /^[A-Z0-9]{8,20}$/i,
        study_permit: /^[A-Z0-9]{8,20}$/i
      };

      const validPattern = pattern[doc.documentType as keyof typeof pattern];
      if (validPattern && !validPattern.test(doc.number)) {
        errors['number'] = `Invalid ${this.getDocumentLabel(doc.documentType)} format.`;
      }
    }

    if (this.requiresProvince(doc.documentType) && !doc.province) {
      errors['province'] = 'Province is required for this document type.';
    }

    if (this.requiresExpiry(doc.documentType) && !doc.expiryDate) {
      errors['expiry'] = 'Expiry date is required for this document type.';
    } else if (doc.expiryDate) {
      const expiryDate = new Date(doc.expiryDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (expiryDate < today) {
        errors['expiry'] = 'Document has expired.';
      }
    }

    return { valid: Object.keys(errors).length === 0, errors };
  }

  validateGuardForm(): boolean {
    this.guardErrors = {};

    // Name
    if (!this.guardFormModel.name.trim()) {
      this.guardErrors['name'] = 'Name is required.';
    } else if (/[^a-zA-Z ]/.test(this.guardFormModel.name)) {
      this.guardErrors['name'] = 'Name can only contain letters and spaces.';
    }

    // Date of Birth
    if (!this.guardFormModel.dob) {
      this.guardErrors['dob'] = 'Date of birth is required.';
    } else {
      const dobDate = new Date(this.guardFormModel.dob);
      const today = new Date();
      today.setHours(0, 0, 0, 0);

      if (dobDate >= today) {
        this.guardErrors['dob'] = 'Date of birth must be in the past.';
      } else {
        // Calculate age
        const age = today.getFullYear() - dobDate.getFullYear();
        const monthDiff = today.getMonth() - dobDate.getMonth();
        const dayDiff = today.getDate() - dobDate.getDate();
        const actualAge = (monthDiff < 0 || (monthDiff === 0 && dayDiff < 0)) ? age - 1 : age;

        if (actualAge < 18) {
          this.guardErrors['dob'] = 'You must be at least 18 years old.';
        } else if (actualAge > 100) {
          this.guardErrors['dob'] = 'Please enter a valid date of birth.';
        }
      }
    }

    // Phone Numbers - At least one required (mobile or landline)
    const hasMobile = this.guardFormModel.mobilePhone && this.guardFormModel.mobilePhone.e164;
    const hasLandline = this.guardFormModel.landlinePhone && this.guardFormModel.landlinePhone.e164;

    // Validate mobile phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasMobile) {
      const mobileE164 = this.guardFormModel.mobilePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(mobileE164)) {
        this.guardErrors['mobilePhone'] = 'Invalid Canadian mobile phone number format.';
      } else if (this.guardFormModel.mobilePhone!.country !== 'CA') {
        // Ensure country is Canada
        this.guardErrors['mobilePhone'] = 'Only Canadian phone numbers are accepted.';
      }
    }

    // Validate landline phone format if provided (Canadian: +1 followed by 10 digits)
    if (hasLandline) {
      const landlineE164 = this.guardFormModel.landlinePhone!.e164;
      const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

      if (!canadianPhonePattern.test(landlineE164)) {
        this.guardErrors['landlinePhone'] = 'Invalid Canadian landline phone number format.';
      } else if (this.guardFormModel.landlinePhone!.country !== 'CA') {
        // Ensure country is Canada
        this.guardErrors['landlinePhone'] = 'Only Canadian phone numbers are accepted.';
      }
    }

    // At least one phone number is required
    if (!hasMobile && !hasLandline) {
      this.guardErrors['phoneNumbers'] = 'At least one phone number (mobile or landline) is required.';
    }

    // If both phone numbers are provided, they must be from the same country
    if (hasMobile && hasLandline) {
      if (this.guardFormModel.mobilePhone?.country !== this.guardFormModel.landlinePhone?.country) {
        this.guardErrors['phoneNumbers'] = 'Mobile and landline phone numbers must be from the same country.';
      }
    }

    // Address
    if (!this.guardFormModel.address.street.trim()) {
      this.guardErrors['addressStreet'] = 'Street address is required.';
    }
    if (!this.guardFormModel.address.city.trim()) {
      this.guardErrors['addressCity'] = 'City is required.';
    }
    if (!this.guardFormModel.address.country.trim()) {
      this.guardErrors['addressCountry'] = 'Country is required.';
    } else {
      // Validate that selected country is from the allowed list
      const validCountries = this.countryOptions.map(c => c.value);
      if (validCountries.length && !validCountries.includes(this.guardFormModel.address.country)) {
        this.guardErrors['addressCountry'] = 'Please select a valid country from the list.';
      }
      // Only allow Canada for postal code validation
      else if (this.guardFormModel.address.country !== 'CA') {
        this.guardErrors['addressCountry'] = 'Only Canadian addresses are accepted.';
      }
    }

    if (!this.guardFormModel.address.province?.trim()) {
      this.guardErrors['addressProvince'] = 'Province is required.';
    } else {
      // Validate that selected province is from the allowed list
      const validProvinces = this.provinceOptions.map(p => p.value);
      if (validProvinces.length && !validProvinces.includes(this.guardFormModel.address.province)) {
        this.guardErrors['addressProvince'] = 'Please select a valid province from the list.';
      }
    }

    // Canadian Postal Code validation (A1A 1A1 format)
    if (!this.guardFormModel.address.postalCode.trim()) {
      this.guardErrors['addressPostalCode'] = 'Postal code is required.';
    } else {
      const postalCodePattern = /^[A-Z]\d[A-Z]\s?\d[A-Z]\d$/i;
      if (!postalCodePattern.test(this.guardFormModel.address.postalCode.trim())) {
        this.guardErrors['addressPostalCode'] = 'Invalid Canadian postal code format (e.g., A1A 1A1).';
      }
    }

    // Identification Documents - at least one required
    if (!this.guardFormModel.identification.documents || this.guardFormModel.identification.documents.length === 0) {
      this.guardErrors['identification'] = 'At least one identification document is required.';
    } else {
      // Validate each document using document ID
      this.guardFormModel.identification.documents.forEach((doc, index) => {
        // First document is required, validate fully
        if (index === 0) {
          const validation = this.validateDocument(doc);
          if (!validation.valid && doc.id) {
            // Store errors per field
            if (validation.errors['type']) {
              this.guardErrors[`identification_${doc.id}_type`] = validation.errors['type'];
            }
            if (validation.errors['number']) {
              this.guardErrors[`identification_${doc.id}_number`] = validation.errors['number'];
            }
            if (validation.errors['province']) {
              this.guardErrors[`identification_${doc.id}_province`] = validation.errors['province'];
            }
            if (validation.errors['expiry']) {
              this.guardErrors[`identification_${doc.id}_expiry`] = validation.errors['expiry'];
            }
          }
        } else {
          // Additional documents are optional, but if partially filled, validate
          const hasAnyData = doc.documentType || doc.number || doc.province || doc.expiryDate;
          if (hasAnyData) {
            const validation = this.validateDocument(doc);
            if (!validation.valid && doc.id) {
              if (validation.errors['type']) {
                this.guardErrors[`identification_${doc.id}_type`] = validation.errors['type'];
              }
              if (validation.errors['number']) {
                this.guardErrors[`identification_${doc.id}_number`] = validation.errors['number'];
              }
              if (validation.errors['province']) {
                this.guardErrors[`identification_${doc.id}_province`] = validation.errors['province'];
              }
              if (validation.errors['expiry']) {
                this.guardErrors[`identification_${doc.id}_expiry`] = validation.errors['expiry'];
              }
            }
          }
        }
      });
    }

    // Security Licenses, Training Certificates (Canada only)
    const isCanadian = this.guardFormModel.address.country === 'CA';
    if (isCanadian) {
      if (!this.guardFormModel.securityLicenses || this.guardFormModel.securityLicenses.length === 0) {
        this.guardErrors['securityLicenses'] = 'At least one security license is required.';
      } else {
        this.guardFormModel.securityLicenses.forEach((license, index) => {
          if (!license.id) {
            return;
          }

          // First license is required, validate fully
          if (index === 0) {
            if (!license.fullLegalName.trim()) {
              this.guardErrors[`security_license_${license.id}_fullLegalName`] = 'Full legal name is required.';
            }
            if (!license.licenseNumber.trim()) {
              this.guardErrors[`security_license_${license.id}_licenseNumber`] = 'License number is required.';
            } else {
              const normalized = license.licenseNumber.replace(/[^A-Za-z0-9]/g, '');
              if (normalized.length < 4 || normalized.length > 32) {
                this.guardErrors[`security_license_${license.id}_licenseNumber`] = 'License number must be 4-32 letters or numbers (hyphens/slashes/spaces allowed).';
              }
            }
            if (!license.licenseType.trim()) {
              this.guardErrors[`security_license_${license.id}_licenseType`] = 'License type is required.';
            }
            if (!license.issuingProvince.trim()) {
              this.guardErrors[`security_license_${license.id}_issuingProvince`] = 'Issuing province is required.';
            } else {
              const validProvinces = this.provinceOptions.map(p => p.value);
              if (validProvinces.length && !validProvinces.includes(license.issuingProvince)) {
                this.guardErrors[`security_license_${license.id}_issuingProvince`] = 'Please select a valid province.';
              }
            }
            if (!license.issuingAuthority.trim()) {
              this.guardErrors[`security_license_${license.id}_issuingAuthority`] = 'Issuing authority is required.';
            }
            if (!license.issueDate) {
              this.guardErrors[`security_license_${license.id}_issueDate`] = 'Issue date is required.';
            } else {
              const issueDate = new Date(license.issueDate);
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              if (issueDate > today) {
                this.guardErrors[`security_license_${license.id}_issueDate`] = 'Issue date cannot be in the future.';
              }
            }
            if (!license.expiryDate) {
              this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Expiry date is required.';
            } else {
              const expiryDate = new Date(license.expiryDate);
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              if (expiryDate < today) {
                this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Security license has expired.';
              }
              if (license.issueDate) {
                const issueDate = new Date(license.issueDate);
                if (expiryDate < issueDate) {
                  this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Expiry date cannot be before issue date.';
                }
              }
            }
          } else {
            // Additional licenses are optional, but if partially filled, validate
            const hasAnyData = license.fullLegalName.trim() || license.licenseNumber.trim() ||
              license.licenseType.trim() || license.issuingProvince.trim() ||
              license.issuingAuthority.trim() || license.issueDate || license.expiryDate;

            if (hasAnyData) {
              if (!license.fullLegalName.trim()) {
                this.guardErrors[`security_license_${license.id}_fullLegalName`] = 'Full legal name is required.';
              }
              if (!license.licenseNumber.trim()) {
                this.guardErrors[`security_license_${license.id}_licenseNumber`] = 'License number is required.';
              } else {
                const normalized = license.licenseNumber.replace(/[^A-Za-z0-9]/g, '');
                if (normalized.length < 4 || normalized.length > 32) {
                  this.guardErrors[`security_license_${license.id}_licenseNumber`] = 'License number must be 4-32 letters or numbers (hyphens/slashes/spaces allowed).';
                }
              }
              if (!license.licenseType.trim()) {
                this.guardErrors[`security_license_${license.id}_licenseType`] = 'License type is required.';
              }
              if (!license.issuingProvince.trim()) {
                this.guardErrors[`security_license_${license.id}_issuingProvince`] = 'Issuing province is required.';
              } else {
                const validProvinces = this.provinceOptions.map(p => p.value);
                if (validProvinces.length && !validProvinces.includes(license.issuingProvince)) {
                  this.guardErrors[`security_license_${license.id}_issuingProvince`] = 'Please select a valid province.';
                }
              }
              if (!license.issuingAuthority.trim()) {
                this.guardErrors[`security_license_${license.id}_issuingAuthority`] = 'Issuing authority is required.';
              }
              if (!license.issueDate) {
                this.guardErrors[`security_license_${license.id}_issueDate`] = 'Issue date is required.';
              }
              if (!license.expiryDate) {
                this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Expiry date is required.';
              } else {
                const expiryDate = new Date(license.expiryDate);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                if (expiryDate < today) {
                  this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Security license has expired.';
                }
                if (license.issueDate) {
                  const issueDate = new Date(license.issueDate);
                  if (expiryDate < issueDate) {
                    this.guardErrors[`security_license_${license.id}_expiryDate`] = 'Expiry date cannot be before issue date.';
                  }
                }
              }
            }
          }
        });
      }

      // Police Clearances
      if (!this.guardFormModel.policeClearances || this.guardFormModel.policeClearances.length === 0) {
        this.guardErrors['policeClearances'] = 'At least one police clearance is required.';
      } else {
        this.guardFormModel.policeClearances.forEach((record, index) => {
          if (!record.id) {
            return;
          }

          // First clearance is required, validate fully
          if (index === 0) {
            if (!record.issuingAuthorityType.trim()) {
              this.guardErrors[`police_clearance_${record.id}_issuingAuthorityType`] = 'Issuing authority type is required.';
            } else if (record.issuingAuthorityType === 'other' && !record.issuingAuthorityOther?.trim()) {
              this.guardErrors[`police_clearance_${record.id}_issuingAuthorityOther`] = 'Please specify the issuing authority.';
            }
            if (!record.issuingProvince.trim()) {
              this.guardErrors[`police_clearance_${record.id}_issuingProvince`] = 'Issuing province is required.';
            } else {
              const validProvinces = this.provinceOptions.map(p => p.value);
              if (validProvinces.length && !validProvinces.includes(record.issuingProvince)) {
                this.guardErrors[`police_clearance_${record.id}_issuingProvince`] = 'Please select a valid province.';
              }
            }
            if (!record.issueDate) {
              this.guardErrors[`police_clearance_${record.id}_issueDate`] = 'Issue date is required.';
            } else {
              const issueDate = new Date(record.issueDate);
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              if (issueDate > today) {
                this.guardErrors[`police_clearance_${record.id}_issueDate`] = 'Issue date cannot be in the future.';
              }
            }
          } else {
            // Additional clearances are optional, but if partially filled, validate
            const hasAnyData = record.issuingAuthorityType.trim() || record.issuingAuthorityOther?.trim() ||
              record.issuingProvince.trim() || record.issuingCity?.trim() ||
              record.issueDate || record.referenceNumber?.trim();

            if (hasAnyData) {
              if (!record.issuingAuthorityType.trim()) {
                this.guardErrors[`police_clearance_${record.id}_issuingAuthorityType`] = 'Issuing authority type is required.';
              } else if (record.issuingAuthorityType === 'other' && !record.issuingAuthorityOther?.trim()) {
                this.guardErrors[`police_clearance_${record.id}_issuingAuthorityOther`] = 'Please specify the issuing authority.';
              }
              if (!record.issuingProvince.trim()) {
                this.guardErrors[`police_clearance_${record.id}_issuingProvince`] = 'Issuing province is required.';
              } else {
                const validProvinces = this.provinceOptions.map(p => p.value);
                if (validProvinces.length && !validProvinces.includes(record.issuingProvince)) {
                  this.guardErrors[`police_clearance_${record.id}_issuingProvince`] = 'Please select a valid province.';
                }
              }
              if (!record.issueDate) {
                this.guardErrors[`police_clearance_${record.id}_issueDate`] = 'Issue date is required.';
              }
            }
          }
        });
      }

      // Training certificates are completely optional
      if (this.guardFormModel.trainingCertificates && this.guardFormModel.trainingCertificates.length > 0) {
        this.guardFormModel.trainingCertificates.forEach((cert) => {
          if (!cert.id) {
            return;
          }

          // Training certificates are optional, but if any field is filled, validate
          const hasAnyData = cert.certificateName.trim() || cert.issuingOrganizationType.trim() ||
            cert.issuingOrganizationOther?.trim() || cert.issueDate || cert.expiryDate;

          if (hasAnyData) {
            if (!cert.certificateName.trim()) {
              this.guardErrors[`training_certificate_${cert.id}_certificateName`] = 'Certificate name is required.';
            }
            if (!cert.issuingOrganizationType.trim()) {
              this.guardErrors[`training_certificate_${cert.id}_issuingOrganizationType`] = 'Issuing organization is required.';
            } else if (cert.issuingOrganizationType === 'other' && !cert.issuingOrganizationOther?.trim()) {
              this.guardErrors[`training_certificate_${cert.id}_issuingOrganizationOther`] = 'Please specify the issuing organization.';
            }
            if (!cert.issueDate) {
              this.guardErrors[`training_certificate_${cert.id}_issueDate`] = 'Issue date is required.';
            } else {
              const issueDate = new Date(cert.issueDate);
              const today = new Date();
              today.setHours(0, 0, 0, 0);
              if (issueDate > today) {
                this.guardErrors[`training_certificate_${cert.id}_issueDate`] = 'Issue date cannot be in the future.';
              }
            }
            if (cert.expiryDate && cert.issueDate) {
              const expiryDate = new Date(cert.expiryDate);
              const issueDate = new Date(cert.issueDate);
              if (expiryDate < issueDate) {
                this.guardErrors[`training_certificate_${cert.id}_expiryDate`] = 'Expiry date cannot be before issue date.';
              }
            }
          }
        });
      }
    }

    // Secondary Contact Validation (optional, but if any field is filled, name and email are required)
    const secondaryContact = this.guardFormModel.secondaryContact;
    const hasSecondaryContactData = secondaryContact && (
      secondaryContact.name?.trim() ||
      secondaryContact.email?.trim() ||
      (secondaryContact.mobilePhone?.e164) ||
      (secondaryContact.landlinePhone?.e164)
    );

    if (hasSecondaryContactData) {
      // If any field is provided, name and email are required
      if (!secondaryContact.name?.trim()) {
        this.guardErrors['secondaryContactName'] = 'Contact name is required if secondary contact is provided.';
      } else if (!/^[a-zA-Z\s]+$/.test(secondaryContact.name)) {
        this.guardErrors['secondaryContactName'] = 'Contact name can only contain letters and spaces.';
      }
      if (!secondaryContact.email?.trim()) {
        this.guardErrors['secondaryContactEmail'] = 'Contact email is required if secondary contact is provided.';
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(secondaryContact.email)) {
        this.guardErrors['secondaryContactEmail'] = 'Please enter a valid email address.';
      }

      // At least one phone required if any field is filled
      const hasSecondaryMobile = secondaryContact.mobilePhone && secondaryContact.mobilePhone.e164;
      const hasSecondaryLandline = secondaryContact.landlinePhone && secondaryContact.landlinePhone.e164;

      // Validate secondary mobile phone format if provided (Canadian: +1 followed by 10 digits)
      if (hasSecondaryMobile) {
        const secondaryMobileE164 = secondaryContact.mobilePhone!.e164;
        const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

        if (!canadianPhonePattern.test(secondaryMobileE164)) {
          this.guardErrors['secondaryContactMobilePhone'] = 'Invalid Canadian mobile phone number format.';
        } else if (secondaryContact.mobilePhone!.country !== 'CA') {
          // Ensure country is Canada
          this.guardErrors['secondaryContactMobilePhone'] = 'Only Canadian phone numbers are accepted.';
        }
      }

      // Validate secondary landline phone format if provided (Canadian: +1 followed by 10 digits)
      if (hasSecondaryLandline) {
        const secondaryLandlineE164 = secondaryContact.landlinePhone!.e164;
        const canadianPhonePattern = /^\+1[2-9]\d{9}$/;

        if (!canadianPhonePattern.test(secondaryLandlineE164)) {
          this.guardErrors['secondaryContactLandlinePhone'] = 'Invalid Canadian landline phone number format.';
        } else if (secondaryContact.landlinePhone!.country !== 'CA') {
          // Ensure country is Canada
          this.guardErrors['secondaryContactLandlinePhone'] = 'Only Canadian phone numbers are accepted.';
        }
      }

      // At least one phone number is required
      if (!hasSecondaryMobile && !hasSecondaryLandline) {
        this.guardErrors['secondaryContactPhoneNumbers'] = 'At least one phone number (mobile or landline) is required.';
      }

      // If both phone numbers are provided, they must be from the same country
      if (hasSecondaryMobile && hasSecondaryLandline) {
        if (secondaryContact.mobilePhone?.country !== secondaryContact.landlinePhone?.country) {
          this.guardErrors['secondaryContactPhoneNumbers'] = 'Mobile and landline phone numbers must be from the same country.';
        }
      }
    }

    // Preferred Guard Types
    if (!this.guardFormModel.preferredGuardTypes || this.guardFormModel.preferredGuardTypes.length === 0) {
      this.guardErrors['preferredGuardTypes'] = 'Select at least one preferred guard type.';
    }

    // Operational Radius
    if (
      this.guardFormModel.operationalRadius != null &&
      (isNaN(this.guardFormModel.operationalRadius) ||
        this.guardFormModel.operationalRadius < 1)
    ) {
      this.guardErrors['operationalRadius'] = 'Operational radius must be at least 1 mile.';
    }

    // Weekly Availability validation
    const hasAtLeastOneDay = Object.keys(this.guardFormModel.weeklyAvailability).some(
      day => this.guardFormModel.weeklyAvailability[day].enabled
    );

    if (!hasAtLeastOneDay) {
      this.guardErrors['weeklyAvailability'] = 'Please select at least one day of availability.';
    } else {
      // Validate that enabled days have at least one complete time range
      let hasIncompleteRanges = false;

      Object.keys(this.guardFormModel.weeklyAvailability).forEach(day => {
        const dayData = this.guardFormModel.weeklyAvailability[day];

        if (dayData.enabled) {
          const hasCompleteRange = dayData.timeRanges.some(range => range.start && range.end);

          if (!hasCompleteRange) {
            hasIncompleteRanges = true;
          }
        }
      });

      if (hasIncompleteRanges) {
        this.guardErrors['weeklyAvailability'] = 'Please complete time ranges for all selected days.';
      }
    }

    return Object.keys(this.guardErrors).length === 0;
  }

  onSecurityLicenseProvinceChange(license: SecurityLicenseDocument, provinceCode: string): void {
    license.issuingProvince = provinceCode;

    // Auto-populate issuing authority based on province
    if (provinceCode) {
      const suggestedAuthority = this.getSuggestedIssuingAuthority(provinceCode);
      if (suggestedAuthority) {
        license.issuingAuthority = suggestedAuthority;
      }
    }
  }

  submitGuardForm(): void {
    if (!this.validateGuardForm() || this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;
    this.guardErrors = {}; // Clear previous errors

    const identificationDocs = this.guardFormModel.identification.documents || [];
    const primaryIdentification = identificationDocs.find(
      doc => doc.id === this.guardFormModel.identification.primaryDocumentId
    ) || identificationDocs[0];

    // Build JSON payload (files already uploaded separately)
    const payload: any = {
      tenant_type: TENANT_TYPES.GUARD,
      status: 'active',
      profile: {
        full_name: this.guardFormModel.name,
        date_of_birth: this.guardFormModel.dob,
        home_address: {
          street: this.guardFormModel.address.street,
          city: this.guardFormModel.address.city,
          country: this.guardFormModel.address.country,
          province: this.guardFormModel.address.province || '',
          postal_code: this.guardFormModel.address.postalCode
        },
        identification: {
          ...(primaryIdentification?.documentType && { id_type: primaryIdentification.documentType }),
          ...(primaryIdentification?.number && { id_number: primaryIdentification.number }),
          ...(primaryIdentification?.existingFileUrl && { document_url: primaryIdentification.existingFileUrl }),
          documents: identificationDocs.map(doc => ({
            document_type: doc.documentType,
            document_number: doc.number,
            ...(doc.province && { province: doc.province }),
            ...(doc.expiryDate && { expiry_date: doc.expiryDate }),
            ...(doc.existingFileId && { document_file_id: doc.existingFileId }),
            ...(doc.existingFileUrl && { document_file_url: doc.existingFileUrl }),
            ...(doc.existingFileName && { document_file_name: doc.existingFileName }),
            ...(doc.existingFileMimeType && { document_file_mime_type: doc.existingFileMimeType }),
            ...(doc.existingFileSize != null && { document_file_size: doc.existingFileSize })
          })),
          ...(this.guardFormModel.identification.primaryDocumentId && {
            primary_document_type: this.guardFormModel.identification.primaryDocumentId
          })
        },
        security_licenses: this.guardFormModel.securityLicenses.map(license => ({
          full_legal_name: license.fullLegalName,
          license_number: license.licenseNumber,
          license_type: license.licenseType,
          issuing_province: license.issuingProvince,
          issuing_authority: license.issuingAuthority,
          issue_date: license.issueDate,
          expiry_date: license.expiryDate,
          ...(license.existingFileId && { document_file_id: license.existingFileId }),
          ...(license.existingFileUrl && { document_file_url: license.existingFileUrl }),
          ...(license.existingFileName && { document_file_name: license.existingFileName }),
          ...(license.existingFileMimeType && { document_file_mime_type: license.existingFileMimeType }),
          ...(license.existingFileSize != null && { document_file_size: license.existingFileSize })
        })),
        police_clearances: this.guardFormModel.policeClearances.map(record => ({
          issuing_authority: record.issuingAuthorityType,
          ...(record.issuingAuthorityType === 'other' && record.issuingAuthorityOther
            ? { issuing_authority_other: record.issuingAuthorityOther }
            : {}),
          issuing_province: record.issuingProvince,
          ...(record.issuingCity && { issuing_city: record.issuingCity }),
          issue_date: record.issueDate,
          ...(record.referenceNumber && { reference_number: record.referenceNumber }),
          ...(record.existingFileId && { document_file_id: record.existingFileId }),
          ...(record.existingFileUrl && { document_file_url: record.existingFileUrl }),
          ...(record.existingFileName && { document_file_name: record.existingFileName }),
          ...(record.existingFileMimeType && { document_file_mime_type: record.existingFileMimeType }),
          ...(record.existingFileSize != null && { document_file_size: record.existingFileSize })
        })),
        training_certificates: this.guardFormModel.trainingCertificates.map(cert => ({
          certificate_name: cert.certificateName,
          issuing_organization: cert.issuingOrganizationType,
          ...(cert.issuingOrganizationType === 'other' && cert.issuingOrganizationOther
            ? { issuing_organization_other: cert.issuingOrganizationOther }
            : {}),
          issue_date: cert.issueDate,
          ...(cert.expiryDate && { expiry_date: cert.expiryDate }),
          ...(cert.existingFileId && { document_file_id: cert.existingFileId }),
          ...(cert.existingFileUrl && { document_file_url: cert.existingFileUrl }),
          ...(cert.existingFileName && { document_file_name: cert.existingFileName }),
          ...(cert.existingFileMimeType && { document_file_mime_type: cert.existingFileMimeType }),
          ...(cert.existingFileSize != null && { document_file_size: cert.existingFileSize })
        })),
        preferred_guard_types: this.guardFormModel.preferredGuardTypes,
        // UPDATED - Use new mapping function
        weekly_availability: this.mapWeeklyAvailabilityToBackend(this.guardFormModel.weeklyAvailability),
      }
    };

    // Add phone numbers if present
    if (this.guardFormModel.mobilePhone?.e164) {
      payload.profile.mobile_phone = this.guardFormModel.mobilePhone.e164;
      payload.profile.mobile_phone_country = this.guardFormModel.mobilePhone.country;
    }
    if (this.guardFormModel.landlinePhone?.e164) {
      payload.profile.landline_phone = this.guardFormModel.landlinePhone.e164;
      payload.profile.landline_phone_country = this.guardFormModel.landlinePhone.country;
    }

    // Add secondary contact if any data is present
    const secondaryContact = this.guardFormModel.secondaryContact;
    if (secondaryContact && (
      secondaryContact.name?.trim() ||
      secondaryContact.email?.trim() ||
      secondaryContact.mobilePhone?.e164 ||
      secondaryContact.landlinePhone?.e164
    )) {
      const secondaryPhone = secondaryContact.mobilePhone?.e164
        || secondaryContact.landlinePhone?.e164
        || '';
      payload.profile.secondary_contact = {
        name: secondaryContact.name || '',
        email: secondaryContact.email || '',
        phone: secondaryPhone
      };
    }

    // Legacy contact field
    const legacyContact = this.guardFormModel.mobilePhone?.national ||
      this.guardFormModel.landlinePhone?.national || '';
    payload.profile.contact = legacyContact;

    // Add operational radius if set
    if (this.guardFormModel.operationalRadius != null) {
      payload.profile.max_travel_radius_km = Math.round(this.guardFormModel.operationalRadius * 1.60934);
    }

    this.apiService.put('tenant', payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.isSubmitting = false;
          this.appService.setTenantStatus('active', false);
          this.router.navigate(['/dashboard/pending-verification']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.guardErrors['submit'] = err?.error?.detail || 'Failed to submit guard profile.';
        }
      });
  }
}