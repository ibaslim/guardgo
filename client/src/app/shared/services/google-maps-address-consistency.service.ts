import { Injectable } from '@angular/core';

import { mapGoogleAddressResultToSelection } from '../helpers/google-maps-address.helper';
import { parseCoordinate } from '../helpers/location.helper';
import { GoogleMapsLoaderService } from './google-maps-loader.service';

export interface AddressConsistencyInput {
  latitude: string | number;
  longitude: string | number;
  expectedCountryCode?: string;
  expectedCountryName?: string;
  expectedProvinceCode?: string;
  expectedProvinceName?: string;
  expectedCity?: string;
  expectedPostalCode?: string;
}

export interface AddressConsistencyResult {
  ok: boolean;
  message?: string;
}

@Injectable({
  providedIn: 'root',
})
export class GoogleMapsAddressConsistencyService {
  constructor(private readonly mapsLoader: GoogleMapsLoaderService) {}

  async validate(input: AddressConsistencyInput): Promise<AddressConsistencyResult> {
    const latitude = parseCoordinate(input.latitude);
    const longitude = parseCoordinate(input.longitude);
    if (latitude == null || longitude == null) {
      return {
        ok: false,
        message: 'Coordinates must be valid before address consistency can be verified.',
      };
    }

    let googleApi: any;
    try {
      googleApi = (await this.mapsLoader.load()).google;
    } catch {
      return {
        ok: false,
        message: 'Coordinates could not be verified because Google Maps is unavailable in this environment.',
      };
    }

    const geocoder = new googleApi.maps.Geocoder();
    const selection = await new Promise<any | null>((resolve) => {
      geocoder.geocode({ location: { lat: latitude, lng: longitude } }, (results: any[], status: string) => {
        const okStatus = googleApi?.maps?.GeocoderStatus?.OK || 'OK';
        const result = Array.isArray(results) ? results[0] : null;
        if (status !== okStatus || !result) {
          resolve(null);
          return;
        }
        resolve(mapGoogleAddressResultToSelection(result, latitude, longitude));
      });
    });

    if (!selection) {
      return {
        ok: false,
        message: 'Coordinates could not be reverse-geocoded. Please reselect the location on Google Maps.',
      };
    }

    const mismatchParts: string[] = [];

    if (!this.areLocationTokensConsistent(
      input.expectedCountryCode,
      input.expectedCountryName,
      selection.countryCode,
      selection.countryName,
    )) {
      mismatchParts.push(`country resolves to ${selection.countryCode || selection.countryName}`);
    }

    if (!this.areLocationTokensConsistent(
      input.expectedProvinceCode,
      input.expectedProvinceName,
      selection.provinceCode,
      selection.provinceName,
    )) {
      mismatchParts.push(`province resolves to ${selection.provinceCode || selection.provinceName}`);
    }

    if (!this.areFreeformLocationsConsistent(input.expectedCity, selection.city)) {
      mismatchParts.push(`city resolves to ${selection.city}`);
    }

    if (!this.arePostalCodesConsistent(input.expectedPostalCode, selection.postalCode)) {
      mismatchParts.push(`postal code resolves to ${selection.postalCode}`);
    }

    if (!mismatchParts.length) {
      return { ok: true };
    }

    return {
      ok: false,
      message: `The selected coordinates do not match the manual address: ${mismatchParts.join(', ')}.`,
    };
  }

  private normalizeToken(value: unknown): string {
    return String(value || '').trim().toUpperCase();
  }

  private normalizeText(value: unknown): string {
    return String(value || '').trim().toLowerCase();
  }

  private normalizeSlug(value: unknown): string {
    return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '');
  }

  private normalizePostalCode(value: unknown): string {
    return String(value || '').trim().replace(/\s+/g, '').toUpperCase();
  }

  private areLocationTokensConsistent(
    expectedCode: unknown,
    expectedName: unknown,
    actualCode: unknown,
    actualName: unknown,
  ): boolean {
    const expectedTokens = this.buildLocationTokenSet(expectedCode, expectedName);
    const actualTokens = this.buildLocationTokenSet(actualCode, actualName);

    if (!expectedTokens.size || !actualTokens.size) {
      return true;
    }

    for (const token of expectedTokens) {
      if (actualTokens.has(token)) {
        return true;
      }
    }

    return false;
  }

  private buildLocationTokenSet(code: unknown, name: unknown): Set<string> {
    const tokens = new Set<string>();
    const normalizedCode = this.normalizeToken(code);
    const normalizedName = this.normalizeText(name);
    const normalizedCodeSlug = this.normalizeSlug(code);
    const normalizedNameSlug = this.normalizeSlug(name);

    if (normalizedCode) {
      tokens.add(normalizedCode);
    }
    if (normalizedName) {
      tokens.add(normalizedName);
    }
    if (normalizedCodeSlug) {
      tokens.add(normalizedCodeSlug);
    }
    if (normalizedNameSlug) {
      tokens.add(normalizedNameSlug);
    }

    const provinceAlias = this.getCanadianProvinceAlias(normalizedCode || normalizedName);
    if (provinceAlias) {
      tokens.add(this.normalizeToken(provinceAlias.code));
      tokens.add(this.normalizeText(provinceAlias.name));
      tokens.add(this.normalizeSlug(provinceAlias.code));
      tokens.add(this.normalizeSlug(provinceAlias.name));
    }

    const countryAlias = this.getCountryAlias(normalizedCode || normalizedName);
    if (countryAlias) {
      tokens.add(this.normalizeToken(countryAlias.code));
      tokens.add(this.normalizeText(countryAlias.name));
      tokens.add(this.normalizeSlug(countryAlias.code));
      tokens.add(this.normalizeSlug(countryAlias.name));
    }

    return tokens;
  }

  private areFreeformLocationsConsistent(expected: unknown, actual: unknown): boolean {
    const expectedText = this.normalizeText(expected);
    const actualText = this.normalizeText(actual);
    const expectedSlug = this.normalizeSlug(expected);
    const actualSlug = this.normalizeSlug(actual);

    if ((!expectedText && !expectedSlug) || (!actualText && !actualSlug)) {
      return true;
    }

    return expectedText === actualText || (!!expectedSlug && expectedSlug === actualSlug);
  }

  private arePostalCodesConsistent(expected: unknown, actual: unknown): boolean {
    const expectedPostalCode = this.normalizePostalCode(expected);
    const actualPostalCode = this.normalizePostalCode(actual);

    if (!expectedPostalCode || !actualPostalCode) {
      return true;
    }

    return (
      expectedPostalCode === actualPostalCode
      || expectedPostalCode.startsWith(actualPostalCode)
      || actualPostalCode.startsWith(expectedPostalCode)
    );
  }

  private getCanadianProvinceAlias(value: string): { code: string; name: string } | null {
    const aliases: Record<string, { code: string; name: string }> = {
      AB: { code: 'AB', name: 'Alberta' },
      ALBERTA: { code: 'AB', name: 'Alberta' },
      BC: { code: 'BC', name: 'British Columbia' },
      BRITISHCOLUMBIA: { code: 'BC', name: 'British Columbia' },
      MB: { code: 'MB', name: 'Manitoba' },
      MANITOBA: { code: 'MB', name: 'Manitoba' },
      NB: { code: 'NB', name: 'New Brunswick' },
      NEWBRUNSWICK: { code: 'NB', name: 'New Brunswick' },
      NL: { code: 'NL', name: 'Newfoundland and Labrador' },
      NEWFOUNDLANDANDLABRADOR: { code: 'NL', name: 'Newfoundland and Labrador' },
      NS: { code: 'NS', name: 'Nova Scotia' },
      NOVASCOTIA: { code: 'NS', name: 'Nova Scotia' },
      NT: { code: 'NT', name: 'Northwest Territories' },
      NORTHWESTTERRITORIES: { code: 'NT', name: 'Northwest Territories' },
      NU: { code: 'NU', name: 'Nunavut' },
      NUNAVUT: { code: 'NU', name: 'Nunavut' },
      ON: { code: 'ON', name: 'Ontario' },
      ONTARIO: { code: 'ON', name: 'Ontario' },
      PE: { code: 'PE', name: 'Prince Edward Island' },
      PRINCEEDWARDISLAND: { code: 'PE', name: 'Prince Edward Island' },
      QC: { code: 'QC', name: 'Quebec' },
      QUEBEC: { code: 'QC', name: 'Quebec' },
      SK: { code: 'SK', name: 'Saskatchewan' },
      SASKATCHEWAN: { code: 'SK', name: 'Saskatchewan' },
      YT: { code: 'YT', name: 'Yukon' },
      YUKON: { code: 'YT', name: 'Yukon' },
    };

    return aliases[this.normalizeSlug(value).toUpperCase()] || aliases[this.normalizeToken(value)] || null;
  }

  private getCountryAlias(value: string): { code: string; name: string } | null {
    const aliases: Record<string, { code: string; name: string }> = {
      CA: { code: 'CA', name: 'Canada' },
      CANADA: { code: 'CA', name: 'Canada' },
      US: { code: 'US', name: 'United States' },
      USA: { code: 'US', name: 'United States' },
      UNITEDSTATES: { code: 'US', name: 'United States' },
    };

    return aliases[this.normalizeSlug(value).toUpperCase()] || aliases[this.normalizeToken(value)] || null;
  }
}
