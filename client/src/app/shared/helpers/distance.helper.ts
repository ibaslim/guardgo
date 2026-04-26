export type DistanceUnit = 'km' | 'mi';

export const KM_PER_MILE = 1.60934;
export const STORAGE_KM_PRECISION = 2;
export const DISPLAY_PRECISION = 1;

export function milesToKm(miles: number, precision = STORAGE_KM_PRECISION): number {
  return roundTo(Number(miles) * KM_PER_MILE, precision);
}

export function kmToMiles(km: number, precision = DISPLAY_PRECISION): number {
  return roundTo(Number(km) / KM_PER_MILE, precision);
}

export function normalizeKmForStorage(km: number): number {
  return roundTo(Number(km), STORAGE_KM_PRECISION);
}

export function formatDistance(value: number, unit: DistanceUnit = 'km', precision = DISPLAY_PRECISION): string {
  return `${roundTo(Number(value), precision)} ${unit}`;
}

function roundTo(value: number, precision: number): number {
  if (!Number.isFinite(value)) return 0;
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
}
