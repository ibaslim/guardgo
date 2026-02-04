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
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';
import { CANADIAN_PROVINCES, IDENTITY_DOCUMENT_TYPES, requiresExpiry, requiresProvince } from '../../shared/constants/canadian-identity.constants';
import { COUNTRY_OPTIONS } from '../../shared/constants/countries.constants';
import { TENANT_TYPES } from '../../shared/constants/tenant-types.constants';
import { Guard, GuardErrors, IdentificationDocument } from '../../shared/model/guard';
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
    ProfilePictureUploadComponent
  ],
  templateUrl: './guard-setting.component.html',
  styleUrls: ['./guard-setting.component.css']
})
export class GuardSettingComponent implements OnInit, OnDestroy {

  @Input() guardData?: Guard;

  isEditMode = false;

  // Available options for dropdowns
  identityDocumentTypes = IDENTITY_DOCUMENT_TYPES;
  documentTypes = IDENTITY_DOCUMENT_TYPES;
  canadianProvinces = CANADIAN_PROVINCES;

  // Converted options for select-input component
  documentTypeOptions = IDENTITY_DOCUMENT_TYPES.map(dt => ({ 
    value: dt.value, 
    label: dt.label 
  }));
  
  provinceOptions = CANADIAN_PROVINCES.map(prov => ({ 
    value: prov.code, 
    label: prov.label 
  }));

  countryOptions = COUNTRY_OPTIONS;

  // UI helper methods
  requiresProvince = requiresProvince;
  requiresExpiry = requiresExpiry;
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
    identification: {
      documents: [],
      primaryDocumentId: undefined,
      idType: 'canadian_passport', // Legacy
      idNumber: '',
      document: null
    },
    securityLicense: {
      licenseNumber: '',
      issuingAuthority: '',
      expiryDate: '',
      document: null
    },
    operationalRadius: null,
    weeklyAvailability: {
      Monday: [],
      Tuesday: [],
      Wednesday: [],
      Thursday: [],
      Friday: [],
      Saturday: [],
      Sunday: []
    }
  };


  guardErrors: GuardErrors = {};
  isSubmitting = false;
  private destroy$ = new Subject<void>();

  // Identity document upload state
  identityUploadInProgress: Record<string, boolean> = {};
  identityUploadErrors: Record<string, string> = {};

  constructor(
    private apiService: ApiService,
    private router: Router,
    private appService: AppService
  ) {}

  ngOnInit(): void {
    if (this.guardData && this.hasGuardData(this.guardData)) {
      this.guardFormModel = this.transformBackendDataToForm(this.guardData);
      this.isEditMode = true;
    } else {
      this.isEditMode = false;
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  /**
   * Transform backend data format to frontend form format
   */
  private transformBackendDataToForm(data: Guard): Guard {
    const formData = JSON.parse(JSON.stringify(data));

    // Transform phone numbers from backend
    if ((data as any).mobile_phone) {
      formData.mobilePhone = {
        e164: (data as any).mobile_phone,
        national: (data as any).mobile_phone, // Backend should provide formatted version
        international: (data as any).mobile_phone,
        country: (data as any).mobile_phone_country || 'CA',
        phoneType: 'mobile' as const,
        rawInput: (data as any).mobile_phone
      };
    }
    if ((data as any).landline_phone) {
      formData.landlinePhone = {
        e164: (data as any).landline_phone,
        national: (data as any).landline_phone,
        international: (data as any).landline_phone,
        country: (data as any).landline_phone_country || 'CA',
        phoneType: 'landline' as const,
        rawInput: (data as any).landline_phone
      };
    }

    if (formData.address?.country) {
      const normalizedCountry = String(formData.address.country).trim().toLowerCase();
      if (normalizedCountry === 'canada' || normalizedCountry === 'ca') {
        formData.address.country = 'CA';
      }
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
    } else if (!formData.identification?.documents) {
      // Initialize documents array if it doesn't exist
      if (formData.identification) {
        formData.identification.documents = [];
      }
    }
    
    // Handle security license file metadata
    if (formData.securityLicense) {
      const license = formData.securityLicense as any;
      formData.securityLicense.existingFileUrl = license.document_file_url || license.file_url || undefined;
      formData.securityLicense.existingFileName = license.document_file_name || license.file_name || undefined;
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
      data.securityLicense.licenseNumber.trim() ||
      data.operationalRadius != null ||
      Object.values(data.weeklyAvailability).some(day => day.length > 0)
    );
  }

  /**
   * Add a new identification document to the list
   */
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

    if (requiresProvince(doc.documentType) && !doc.province) {
      errors['province'] = 'Province is required for this document type.';
    }

    if (requiresExpiry(doc.documentType) && !doc.expiryDate) {
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
    
    if (!hasMobile && !hasLandline) {
      this.guardErrors['phoneNumbers'] = 'At least one phone number (mobile or landline) is required.';
    } else if (hasMobile && hasLandline) {
      // If both phone numbers are provided, they must be from the same country
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
      const validCountries = COUNTRY_OPTIONS.map(c => c.value);
      if (!validCountries.includes(this.guardFormModel.address.country)) {
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
      const validProvinces = CANADIAN_PROVINCES.map(p => p.code);
      if (!validProvinces.includes(this.guardFormModel.address.province)) {
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
      this.guardFormModel.identification.documents.forEach((doc) => {
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
      });
    }

    // Security License
    if (!this.guardFormModel.securityLicense.licenseNumber.trim()) {
      this.guardErrors['licenseNumber'] = 'Security License number is required.';
    } else {
      const licenseNormalized = this.guardFormModel.securityLicense.licenseNumber.replace(/[^A-Za-z0-9]/g, '');
      if (licenseNormalized.length < 4 || licenseNormalized.length > 32) {
        this.guardErrors['licenseNumber'] = 'Security License must be 4-32 letters or numbers (hyphens/slashes/spaces allowed).';
      }
    }
    if (!this.guardFormModel.securityLicense.issuingAuthority.trim()) {
      this.guardErrors['issuingAuthority'] = 'Issuing authority is required.';
    }
    if (!this.guardFormModel.securityLicense.expiryDate) {
      this.guardErrors['expiryDate'] = 'Expiry date is required.';
    } else {
      // Check if security license has expired
      const expiryDate = new Date(this.guardFormModel.securityLicense.expiryDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (expiryDate < today) {
        this.guardErrors['expiryDate'] = 'Security license has expired.';
      }
    }

    // Operational Radius
    if (
      this.guardFormModel.operationalRadius != null &&
      (isNaN(this.guardFormModel.operationalRadius) ||
        this.guardFormModel.operationalRadius < 1)
    ) {
      this.guardErrors['operationalRadius'] = 'Operational radius must be at least 1 mile.';
    }

    return Object.keys(this.guardErrors).length === 0;
  }

  submitGuardForm(): void {
    if (!this.validateGuardForm() || this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;
    this.guardErrors = {}; // Clear previous errors

    // Build JSON payload (files already uploaded separately)
    const payload: any = {
      tenant_type: TENANT_TYPES.GUARD,
      status: 'active',
      profile: {
        name: this.guardFormModel.name,
        date_of_birth: this.guardFormModel.dob,
        address: {
          street: this.guardFormModel.address.street,
          city: this.guardFormModel.address.city,
          country: this.guardFormModel.address.country,
          province: this.guardFormModel.address.province || '',
          postal_code: this.guardFormModel.address.postalCode
        },
        identification: {
          documents: this.guardFormModel.identification.documents.map(doc => ({
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
        security_license: {
          license_number: this.guardFormModel.securityLicense.licenseNumber,
          issuing_authority: this.guardFormModel.securityLicense.issuingAuthority,
          expiry_date: this.guardFormModel.securityLicense.expiryDate
        },
        weekly_availability: this.guardFormModel.weeklyAvailability
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
    // Legacy contact field
    const legacyContact = this.guardFormModel.mobilePhone?.national || 
                          this.guardFormModel.landlinePhone?.national || '';
    payload.profile.contact = legacyContact;

    // Add operational radius if set
    if (this.guardFormModel.operationalRadius != null) {
      payload.profile.operational_radius = this.guardFormModel.operationalRadius;
    }

    this.apiService.put('tenant', payload)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.isSubmitting = false;
          this.appService.setTenantStatus('active', false);
          this.router.navigate(['/dashboard']);
        },
        error: (err) => {
          this.isSubmitting = false;
          this.guardErrors['submit'] = err?.error?.detail || 'Failed to submit guard profile.';
        }
      });
  }

  // ============================================================================
  // Identity Document Methods
  // ============================================================================
}