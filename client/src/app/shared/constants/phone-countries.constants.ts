/**
 * Phone Input Country Data
 * Maps countries to phone country codes and formatting info for libphonenumber-js
 */

export interface PhoneCountry {
  code: string;                    // ISO country code (CA, US, etc.)
  label: string;                   // Display name
  countryCode: number;             // Phone country code (1 for CA/US, 44 for UK, etc.)
  flagEmoji?: string;              // Optional flag emoji
  defaultFormat?: 'INTERNATIONAL' | 'NATIONAL' | 'E164' | 'RFC3966'; // Default formatting
}

export const PHONE_COUNTRIES: PhoneCountry[] = [
  { code: 'CA', label: 'Canada', countryCode: 1, flagEmoji: '🇨🇦', defaultFormat: 'NATIONAL' },
  { code: 'US', label: 'United States', countryCode: 1, flagEmoji: '🇺🇸', defaultFormat: 'NATIONAL' },
  { code: 'GB', label: 'United Kingdom', countryCode: 44, flagEmoji: '🇬🇧', defaultFormat: 'NATIONAL' },
  { code: 'IE', label: 'Ireland', countryCode: 353, flagEmoji: '🇮🇪', defaultFormat: 'NATIONAL' },
  { code: 'FR', label: 'France', countryCode: 33, flagEmoji: '🇫🇷', defaultFormat: 'NATIONAL' },
  { code: 'DE', label: 'Germany', countryCode: 49, flagEmoji: '🇩🇪', defaultFormat: 'NATIONAL' },
  { code: 'IT', label: 'Italy', countryCode: 39, flagEmoji: '🇮🇹', defaultFormat: 'NATIONAL' },
  { code: 'ES', label: 'Spain', countryCode: 34, flagEmoji: '🇪🇸', defaultFormat: 'NATIONAL' },
  { code: 'NL', label: 'Netherlands', countryCode: 31, flagEmoji: '🇳🇱', defaultFormat: 'NATIONAL' },
  { code: 'BE', label: 'Belgium', countryCode: 32, flagEmoji: '🇧🇪', defaultFormat: 'NATIONAL' },
  { code: 'CH', label: 'Switzerland', countryCode: 41, flagEmoji: '🇨🇭', defaultFormat: 'NATIONAL' },
  { code: 'AT', label: 'Austria', countryCode: 43, flagEmoji: '🇦🇹', defaultFormat: 'NATIONAL' },
  { code: 'SE', label: 'Sweden', countryCode: 46, flagEmoji: '🇸🇪', defaultFormat: 'NATIONAL' },
  { code: 'NO', label: 'Norway', countryCode: 47, flagEmoji: '🇳🇴', defaultFormat: 'NATIONAL' },
  { code: 'DK', label: 'Denmark', countryCode: 45, flagEmoji: '🇩🇰', defaultFormat: 'NATIONAL' },
  { code: 'FI', label: 'Finland', countryCode: 358, flagEmoji: '🇫🇮', defaultFormat: 'NATIONAL' },
  { code: 'PL', label: 'Poland', countryCode: 48, flagEmoji: '🇵🇱', defaultFormat: 'NATIONAL' },
  { code: 'CZ', label: 'Czech Republic', countryCode: 420, flagEmoji: '🇨🇿', defaultFormat: 'NATIONAL' },
  { code: 'AU', label: 'Australia', countryCode: 61, flagEmoji: '🇦🇺', defaultFormat: 'NATIONAL' },
  { code: 'NZ', label: 'New Zealand', countryCode: 64, flagEmoji: '🇳🇿', defaultFormat: 'NATIONAL' },
  { code: 'JP', label: 'Japan', countryCode: 81, flagEmoji: '🇯🇵', defaultFormat: 'NATIONAL' },
  { code: 'CN', label: 'China', countryCode: 86, flagEmoji: '🇨🇳', defaultFormat: 'NATIONAL' },
  { code: 'IN', label: 'India', countryCode: 91, flagEmoji: '🇮🇳', defaultFormat: 'NATIONAL' },
  { code: 'SG', label: 'Singapore', countryCode: 65, flagEmoji: '🇸🇬', defaultFormat: 'NATIONAL' },
  { code: 'BR', label: 'Brazil', countryCode: 55, flagEmoji: '🇧🇷', defaultFormat: 'NATIONAL' },
  { code: 'MX', label: 'Mexico', countryCode: 52, flagEmoji: '🇲🇽', defaultFormat: 'NATIONAL' },
  { code: 'ZA', label: 'South Africa', countryCode: 27, flagEmoji: '🇿🇦', defaultFormat: 'NATIONAL' },
];

// Create lookup maps for quick access
export const PHONE_COUNTRY_MAP = new Map(PHONE_COUNTRIES.map(c => [c.code, c]));
export const PHONE_COUNTRY_CODE_MAP = new Map(PHONE_COUNTRIES.map(c => [c.countryCode, c]));

/**
 * Get phone country by ISO code
 */
export function getPhoneCountry(code: string): PhoneCountry | undefined {
  return PHONE_COUNTRY_MAP.get(code.toUpperCase());
}

/**
 * Get country code for a country
 */
export function getCountryCode(countryCode: string): number | undefined {
  return PHONE_COUNTRY_MAP.get(countryCode.toUpperCase())?.countryCode;
}
