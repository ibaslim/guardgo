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

export interface GuardEmergencyContact {
  name: string;
  email: string;
  phone: PhoneNumber | null;
  landlinePhone?: PhoneNumber | null;
}

export interface IdentificationDocument {
  documentType: string;
  number: string;
  province?: string;
  expiryDate?: string;
  file?: File | null;
  id?: string;
  existingFileUrl?: string;
  existingFileName?: string;
  existingFileId?: string;
  existingFileMimeType?: string;
  existingFileSize?: number;
}

export interface Identification {
  documents: IdentificationDocument[];
  primaryDocumentId?: string;
  idType?: string;
  idNumber?: string;
  document?: File | null;
}

export interface SecurityLicense {
  licenseNumber: string;
  issuingAuthority: string;
  expiryDate: string;
  document?: File | null;
  existingFileUrl?: string;
  existingFileName?: string;
}

export interface WeeklyAvailability {
  Monday: string[];
  Tuesday: string[];
  Wednesday: string[];
  Thursday: string[];
  Friday: string[];
  Saturday: string[];
  Sunday: string[];
}

export interface GuardErrors {
  name?: string;
  dob?: string;
  contact?: string;
  mobilePhone?: string;
  landlinePhone?: string;
  phoneNumbers?: string;
  emergencyContactName?: string;
  emergencyContactEmail?: string;
  emergencyContactPhone?: string;
  emergencyContactLandlinePhone?: string;
  addressStreet?: string;
  addressCity?: string;
  addressCountry?: string;
  addressProvince?: string;
  addressPostalCode?: string;
  identification?: string;
  licenseNumber?: string;
  issuingAuthority?: string;
  expiryDate?: string;
  operationalRadius?: string;
  submit?: string;
  [key: string]: string | undefined;
}

export interface Guard {
  name: string;
  contact: string;
  mobilePhone?: PhoneNumber | null;
  landlinePhone?: PhoneNumber | null;
  dob: string;
  emergencyContact: GuardEmergencyContact;
  address: Address;
  identification: Identification;
  securityLicense: SecurityLicense;
  operationalRadius: number | null;
  weeklyAvailability: WeeklyAvailability;
}
