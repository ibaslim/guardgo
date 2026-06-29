/**
 * Global formatting helper functions
 */

/**
 * Formats a file size in bytes to human-readable format
 * @param bytes - File size in bytes
 * @returns Formatted string (e.g., "1.5 MB")
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Formats a date to locale string
 * @param date - Date object or string
 * @param locale - Locale (default: 'en-CA')
 * @returns Formatted date string
 */
export function formatDate(date: Date | string, locale: string = 'en-CA'): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return dateObj.toLocaleDateString(locale);
}

/**
 * Formats backend date/time values safely for UI display.
 * Returns '-' for empty or invalid values.
 */
export function formatBackendDateTime(
  value: Date | string | null | undefined,
  locale: string = 'en-CA',
  options?: {
    timeZone?: string | null;
    preserveLocalTime?: boolean;
    timeZoneName?: 'short' | 'long';
  },
): string {
  if (!value) return '-';
  const preserveLocalTime = Boolean(options?.preserveLocalTime);
  const dateObj = preserveLocalTime
    ? parseIsoAsLocalWallTime(value)
    : (value instanceof Date ? value : new Date(value));
  if (Number.isNaN(dateObj.getTime())) return '-';

  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: options?.timeZone || undefined,
    timeZoneName: options?.timeZoneName,
  }).format(dateObj);
}

function parseIsoAsLocalWallTime(value: Date | string): Date {
  if (value instanceof Date) {
    return value;
  }
  const raw = String(value || '').trim();
  const match = raw.match(
    /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/,
  );
  if (!match) {
    return new Date(raw);
  }
  const [, year, month, day, hour, minute, second = '00'] = match;
  return new Date(Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  ));
}

/**
 * Produce a readable title from arbitrary strings containing special characters
 * Examples:
 *  - "service_provider" -> "Service Provider"
 *  - "client-type#1" -> "Client Type 1"
 *  - "firstName" -> "First Name"
 */
export function readableTitle(value: string): string {
  if (!value) return '';

  const withCamelSpacing = value.replace(/([a-z0-9])([A-Z])/g, '$1 $2');

  // Normalize common separators to spaces
  let s = withCamelSpacing.replace(/[_-]+/g, ' ');

  // Remove any characters that are not letters, numbers or whitespace
  s = s.replace(/[^A-Za-z0-9\s]+/g, ' ');

  // Collapse multiple spaces and trim
  s = s.replace(/\s+/g, ' ').trim();

  // Apply title-casing for readability
  return s
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}
