export interface GeoLocationSelection {
  latitude: string;
  longitude: string;
  formattedAddress: string;
  street: string;
  city: string;
  provinceCode: string;
  provinceName: string;
  countryCode: string;
  countryName: string;
  postalCode: string;
  placeId: string;
  mapUrl: string;
}

function getComponent(components: any[], type: string, useShortName = false): string {
  const match = Array.isArray(components)
    ? components.find((component) => Array.isArray(component?.types) && component.types.includes(type))
    : null;
  const value = useShortName
    ? (match?.short_name ?? match?.shortText)
    : (match?.long_name ?? match?.longText);
  return String(value || '').trim();
}

function resolveCity(components: any[]): string {
  return (
    getComponent(components, 'locality')
    || getComponent(components, 'postal_town')
    || getComponent(components, 'administrative_area_level_3')
    || getComponent(components, 'administrative_area_level_2')
    || getComponent(components, 'sublocality')
  );
}

function resolveStreet(components: any[]): string {
  const streetNumber = getComponent(components, 'street_number');
  const route = getComponent(components, 'route');
  const premise = getComponent(components, 'premise');
  const subpremise = getComponent(components, 'subpremise');

  const line = [streetNumber, route].filter((part) => !!part).join(' ').trim();
  if (line) {
    return line;
  }

  return [premise, subpremise].filter((part) => !!part).join(' ').trim();
}

export function buildGoogleMapsLocationUrl(latitude: number, longitude: number, placeId?: string): string {
  const query = `${latitude},${longitude}`;
  const placeIdPart = String(placeId || '').trim();
  if (placeIdPart) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}&query_place_id=${encodeURIComponent(placeIdPart)}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}

export function mapGoogleAddressResultToSelection(source: any, latitude: number, longitude: number, explicitPlaceId?: string): GeoLocationSelection {
  const components = Array.isArray(source?.address_components)
    ? source.address_components
    : (Array.isArray(source?.addressComponents) ? source.addressComponents : []);
  const provinceCode = getComponent(components, 'administrative_area_level_1', true);
  const provinceName = getComponent(components, 'administrative_area_level_1');
  const countryCode = getComponent(components, 'country', true);
  const countryName = getComponent(components, 'country');
  const city = resolveCity(components);
  const street = resolveStreet(components);
  const postalCode = getComponent(components, 'postal_code');
  const placeId = String(explicitPlaceId || source?.place_id || source?.placeId || source?.id || '').trim();
  const formattedAddress = String(source?.formatted_address || source?.formattedAddress || source?.name || source?.displayName || '').trim()
    || [street, city, provinceName, countryName].filter((part) => !!part).join(', ');
  const mapUrl = String(source?.googleMapsURI || source?.google_maps_uri || '').trim()
    || buildGoogleMapsLocationUrl(latitude, longitude, placeId);

  return {
    latitude: latitude.toFixed(6),
    longitude: longitude.toFixed(6),
    formattedAddress,
    street,
    city,
    provinceCode,
    provinceName,
    countryCode,
    countryName,
    postalCode,
    placeId,
    mapUrl,
  };
}
