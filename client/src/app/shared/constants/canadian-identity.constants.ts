/**
 * Canadian Identity Document Types and Validation Constants
 * Specific to Canadian provinces and territories
 */

export enum CanadianDocumentType {
  DRIVERS_LICENSE = 'drivers_license',
  PROVINCIAL_ID = 'provincial_id',
  CANADIAN_PASSPORT = 'canadian_passport',
  PR_CARD = 'pr_card',
  WORK_PERMIT = 'work_permit',
  STUDY_PERMIT = 'study_permit'
}

export enum CanadianProvince {
  AB = 'AB',
  BC = 'BC',
  MB = 'MB',
  NB = 'NB',
  NL = 'NL',
  NS = 'NS',
  NT = 'NT',
  NU = 'NU',
  ON = 'ON',
  PE = 'PE',
  QC = 'QC',
  SK = 'SK',
  YT = 'YT'
}

export const CANADIAN_PROVINCES: { code: string; label: string }[] = [
  { code: 'AB', label: 'Alberta' },
  { code: 'BC', label: 'British Columbia' },
  { code: 'MB', label: 'Manitoba' },
  { code: 'NB', label: 'New Brunswick' },
  { code: 'NL', label: 'Newfoundland and Labrador' },
  { code: 'NS', label: 'Nova Scotia' },
  { code: 'NT', label: 'Northwest Territories' },
  { code: 'NU', label: 'Nunavut' },
  { code: 'ON', label: 'Ontario' },
  { code: 'PE', label: 'Prince Edward Island' },
  { code: 'QC', label: 'Quebec' },
  { code: 'SK', label: 'Saskatchewan' },
  { code: 'YT', label: 'Yukon' }
];

export const IDENTITY_DOCUMENT_TYPES: { value: string; label: string; requiresProvince: boolean; requiresExpiry: boolean; mandatory: boolean }[] = [
  {
    value: CanadianDocumentType.DRIVERS_LICENSE,
    label: "Driver's License (Provincial)",
    requiresProvince: true,
    requiresExpiry: true,
    mandatory: false
  },
  {
    value: CanadianDocumentType.PROVINCIAL_ID,
    label: 'Provincial Photo ID Card',
    requiresProvince: true,
    requiresExpiry: true,
    mandatory: false
  },
  {
    value: CanadianDocumentType.CANADIAN_PASSPORT,
    label: 'Canadian Passport',
    requiresProvince: false,
    requiresExpiry: true,
    mandatory: false
  },
  {
    value: CanadianDocumentType.PR_CARD,
    label: 'Permanent Resident (PR) Card',
    requiresProvince: false,
    requiresExpiry: true,
    mandatory: false
  },
  {
    value: CanadianDocumentType.WORK_PERMIT,
    label: 'Work Permit (Photo Version)',
    requiresProvince: false,
    requiresExpiry: true,
    mandatory: false
  },
  {
    value: CanadianDocumentType.STUDY_PERMIT,
    label: 'Study Permit (Photo Version)',
    requiresProvince: false,
    requiresExpiry: true,
    mandatory: false
  }
];

/**
 * Validation patterns for document numbers
 * These are general patterns; actual validation may vary by province
 */
export const DOCUMENT_NUMBER_PATTERNS: { [key in CanadianDocumentType]: RegExp } = {
  [CanadianDocumentType.DRIVERS_LICENSE]: /^[A-Z0-9\-]{4,20}$/i,
  [CanadianDocumentType.PROVINCIAL_ID]: /^[A-Z0-9\-]{4,20}$/i,
  [CanadianDocumentType.CANADIAN_PASSPORT]: /^[A-Z0-9]{6,9}$/i,
  [CanadianDocumentType.PR_CARD]: /^[A-Z0-9]{8,12}$/i,
  [CanadianDocumentType.WORK_PERMIT]: /^[A-Z0-9]{8,20}$/i,
  [CanadianDocumentType.STUDY_PERMIT]: /^[A-Z0-9]{8,20}$/i
};

/**
 * Helper function to get document type label
 */
export function getDocumentTypeLabel(type: string): string {
  const doc = IDENTITY_DOCUMENT_TYPES.find(d => d.value === type);
  return doc ? doc.label : type;
}

/**
 * Helper function to check if document type requires province selection
 */
export function requiresProvince(type: string): boolean {
  const doc = IDENTITY_DOCUMENT_TYPES.find(d => d.value === type);
  return doc ? doc.requiresProvince : false;
}

/**
 * Helper function to check if document type requires expiry date
 */
export function requiresExpiry(type: string): boolean {
  const doc = IDENTITY_DOCUMENT_TYPES.find(d => d.value === type);
  return doc ? doc.requiresExpiry : false;
}
