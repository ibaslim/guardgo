export type SelectOption = { value: string; label: string };
export type CityOptionsByProvince = Record<string, SelectOption[]>;
let dummySeedCounter = 0;

export const isLocalhostForDummyData = (): boolean => {
  if (typeof window === 'undefined') return false;
  const host = String(window.location.hostname || '').trim().toLowerCase();
  return host === 'localhost' || host === '127.0.0.1' || host === '::1';
};

export const isoDateYearsAgo = (yearsAgo: number): string => {
  const date = new Date();
  date.setFullYear(date.getFullYear() - yearsAgo);
  return date.toISOString().slice(0, 10);
};

export const isoDateYearsAhead = (yearsAhead: number): string => {
  const date = new Date();
  date.setFullYear(date.getFullYear() + yearsAhead);
  return date.toISOString().slice(0, 10);
};

export const buildCaPhone = (
  e164: string,
  phoneType: 'mobile' | 'landline'
): {
  e164: string;
  national: string;
  international: string;
  country: string;
  phoneType: 'mobile' | 'landline';
  rawInput: string;
} => ({
  e164,
  national: e164,
  international: e164,
  country: 'CA',
  phoneType,
  rawInput: e164,
});

export const pickFirstOptionValue = (options: SelectOption[], fallback = ''): string =>
  options?.[0]?.value || fallback;

export const pickPreferredOptionValue = (
  options: SelectOption[],
  preferredValues: string[],
  fallback = ''
): string => {
  const normalizedPreferred = preferredValues.map(value => String(value || '').trim().toLowerCase());
  const matched = options.find(option => normalizedPreferred.includes(String(option.value || '').trim().toLowerCase()));
  return matched?.value || pickFirstOptionValue(options, fallback);
};

export const pickCityValueForProvince = (
  citiesByProvince: CityOptionsByProvince,
  provinceCode: string,
  fallback = ''
): string => {
  const key = String(provinceCode || '').trim().toUpperCase();
  const list = citiesByProvince?.[key] || [];
  return list?.[0]?.value || fallback;
};

export const nextDummySeed = (): { sequence: number; suffix: string; phoneSuffix: string } => {
  dummySeedCounter += 1;
  const sequence = dummySeedCounter;
  const timestampSuffix = String(Date.now()).slice(-4);
  const suffix = `${sequence}${timestampSuffix}`;
  const phoneSuffix = String(2000 + sequence).padStart(4, '0').slice(-4);
  return { sequence, suffix, phoneSuffix };
};

export const buildAlphabeticDummyTag = (sequence: number): string => {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  let index = Math.max(1, Number(sequence || 1));
  let result = '';

  while (index > 0) {
    index -= 1;
    result = alphabet[index % 26] + result;
    index = Math.floor(index / 26);
  }

  return result;
};

export const buildSeededCaPhone = (
  phoneSuffix: string,
  offset: number,
  phoneType: 'mobile' | 'landline'
): {
  e164: string;
  national: string;
  international: string;
  country: string;
  phoneType: 'mobile' | 'landline';
  rawInput: string;
} => {
  const base = 2000 + Number(phoneSuffix || '0') + offset;
  const local = String(base).padStart(4, '0').slice(-4);
  return buildCaPhone(`+1416555${local}`, phoneType);
};
