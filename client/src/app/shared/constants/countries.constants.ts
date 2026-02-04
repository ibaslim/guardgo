/**
 * Global Countries List
 * Comprehensive list of countries for use in dropdowns and forms
 */

export interface CountryOption {
  code: string;
  label: string;
}

export const COUNTRIES: CountryOption[] = [
  { code: 'CA', label: 'Canada' },
  { code: 'US', label: 'United States' },
  { code: 'MX', label: 'Mexico' },
  { code: 'GB', label: 'United Kingdom' },
  { code: 'IE', label: 'Ireland' },
  { code: 'FR', label: 'France' },
  { code: 'DE', label: 'Germany' },
  { code: 'IT', label: 'Italy' },
  { code: 'ES', label: 'Spain' },
  { code: 'NL', label: 'Netherlands' },
  { code: 'BE', label: 'Belgium' },
  { code: 'CH', label: 'Switzerland' },
  { code: 'AT', label: 'Austria' },
  { code: 'SE', label: 'Sweden' },
  { code: 'NO', label: 'Norway' },
  { code: 'DK', label: 'Denmark' },
  { code: 'FI', label: 'Finland' },
  { code: 'PL', label: 'Poland' },
  { code: 'CZ', label: 'Czech Republic' },
  { code: 'HU', label: 'Hungary' },
  { code: 'RO', label: 'Romania' },
  { code: 'GR', label: 'Greece' },
  { code: 'PT', label: 'Portugal' },
  { code: 'JP', label: 'Japan' },
  { code: 'CN', label: 'China' },
  { code: 'IN', label: 'India' },
  { code: 'KR', label: 'South Korea' },
  { code: 'SG', label: 'Singapore' },
  { code: 'AU', label: 'Australia' },
  { code: 'NZ', label: 'New Zealand' },
  { code: 'BR', label: 'Brazil' },
  { code: 'AR', label: 'Argentina' },
  { code: 'ZA', label: 'South Africa' },
];

export const COUNTRY_OPTIONS = COUNTRIES.map(country => ({
  value: country.code,
  label: country.label
}));
