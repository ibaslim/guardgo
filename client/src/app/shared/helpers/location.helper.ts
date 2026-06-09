export type CoordinatePair = [number, number];

export function parseCoordinate(value: unknown): number | null {
  const trimmed = String(value ?? '').trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatCoordinateInput(value: unknown, digits = 6): string {
  const parsed = parseCoordinate(value);
  return parsed === null ? '' : parsed.toFixed(digits);
}

export function isLatitudeInRange(value: number | null): value is number {
  return value !== null && value >= -90 && value <= 90;
}

export function isLongitudeInRange(value: number | null): value is number {
  return value !== null && value >= -180 && value <= 180;
}

export function extractCoordinatesFromMapUrl(value: string): CoordinatePair | null {
  const url = String(value || '').trim();
  if (!url) {
    return null;
  }

  const patterns = [
    /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
    /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,
    /[?&](?:q|ll)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
    /[?&]mlat=(-?\d+(?:\.\d+)?).*?[?&]mlon=(-?\d+(?:\.\d+)?)/,
    /#map=\d+\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/,
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (!match) {
      continue;
    }

    const latitude = Number(match[1]);
    const longitude = Number(match[2]);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
      return [latitude, longitude];
    }
  }

  return null;
}

export function buildOpenStreetMapSearchUrl(query: string): string | null {
  const trimmed = String(query || '').trim();
  if (!trimmed) {
    return null;
  }

  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(trimmed)}`;
}

export function buildOpenStreetMapViewUrl(latitude: number, longitude: number, zoom = 15): string {
  return `https://www.openstreetmap.org/#map=${zoom}/${latitude}/${longitude}`;
}

export function buildOpenStreetMapEmbedUrl(latitude: number, longitude: number, delta = 0.01): string {
  const left = longitude - delta;
  const right = longitude + delta;
  const top = latitude + delta;
  const bottom = latitude - delta;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${latitude}%2C${longitude}`;
}
