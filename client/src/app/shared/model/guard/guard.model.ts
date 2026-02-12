/**
 * Guard Profile Models
 * Global type definitions for guard onboarding and profile management
 */

export interface PhoneNumber {
  e164: string;
  national: string;
  international: string;
  country: string;
  phoneType: 'mobile' | 'landline';
  rawInput: string;
}

export interface Address {
  street: string;
  city: string;
  country: string;
  province?: string;
  postalCode: string;
}

export interface ContactPerson {
  name: string;
  email: string;
  mobilePhone: PhoneNumber | null;
  landlinePhone: PhoneNumber | null;
}

export interface IdentificationDocument {
  documentType: string;
  number: string;
  province?: string;
  expiryDate?: string;
  file?: File | null;
  id?: string; // unique identifier for UI purposes
  existingFileUrl?: string; // URL to existing uploaded file
  existingFileName?: string; // Name of existing uploaded file
  existingFileId?: string; // Backend file identifier
  existingFileMimeType?: string;
  existingFileSize?: number;
}

export interface Identification {
  documents: IdentificationDocument[];
  primaryDocumentId?: string;
  // Legacy fields for backward compatibility
  idType?: string;
  idNumber?: string;
  document?: File | null;
}

export interface SecurityLicense {
  licenseNumber: string;
  issuingAuthority: string;
  expiryDate: string;
  document?: File | null;
  existingFileUrl?: string; // URL to existing uploaded file
  existingFileName?: string; // Name of existing uploaded file
}

export interface SecurityLicenseDocument {
  fullLegalName: string;
  licenseNumber: string;
  licenseType: string;
  issuingProvince: string;
  issuingAuthority: string;
  issueDate: string;
  expiryDate: string;
  file?: File | null;
  id?: string; // unique identifier for UI purposes
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

export interface PoliceClearanceRecord {
  issuingAuthorityType: string;
  issuingAuthorityOther?: string;
  issuingProvince: string;
  issuingCity?: string;
  issueDate: string;
  referenceNumber?: string;
  file?: File | null;
  id?: string; // unique identifier for UI purposes
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

export interface TrainingCertificate {
  certificateName: string;
  issuingOrganizationType: string;
  issuingOrganizationOther?: string;
  issueDate: string;
  expiryDate?: string;
  file?: File | null;
  id?: string; // unique identifier for UI purposes
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

// export interface WeeklyAvailability {
//   Monday: string[];
//   Tuesday: string[];
//   Wednesday: string[];
//   Thursday: string[];
//   Friday: string[];
//   Saturday: string[];
//   Sunday: string[];
// }

// NEW - Add this
export interface TimeRange {
  start: string;
  end: string;
}

export interface DayAvailability {
  enabled: boolean;
  timeRanges: TimeRange[];
}

export interface WeeklyAvailability {
  [day: string]: DayAvailability;
}

export interface GuardErrors {
  name?: string;
  dob?: string;
  contact?: string;
  mobilePhone?: string;
  landlinePhone?: string;
  phoneNumbers?: string;
  secondaryContactName?: string;
  secondaryContactEmail?: string;
  secondaryContactPhoneNumbers?: string;
  addressStreet?: string;
  addressCity?: string;
  addressCountry?: string;
  addressProvince?: string;
  addressPostalCode?: string;
  identification?: string;
  licenseNumber?: string;
  issuingAuthority?: string;
  expiryDate?: string;
  securityLicenses?: string;
  policeClearances?: string;
  trainingCertificates?: string;
  preferredGuardTypes?: string;
  operationalRadius?: string;
  weeklyAvailability?: string;
  submit?: string;
  [key: string]: string | undefined; // For dynamic identification document errors
}

export interface Guard {
  name: string;
  contact: string; // Legacy field for backward compatibility
  mobilePhone?: PhoneNumber | null;
  landlinePhone?: PhoneNumber | null;
  dob: string;
  address: Address;
  secondaryContact: ContactPerson;
  identification: Identification;
  securityLicense?: SecurityLicense; // Legacy
  securityLicenses: SecurityLicenseDocument[];
  policeClearances: PoliceClearanceRecord[];
  trainingCertificates: TrainingCertificate[];
  preferredGuardTypes: string[];
  operationalRadius: number | null;
  weeklyAvailability: WeeklyAvailability;
}
