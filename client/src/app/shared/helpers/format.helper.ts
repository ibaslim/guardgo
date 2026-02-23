/**
 * Global formatting helper functions
 */

/**
 * Converts snake_case or kebab-case to Title Case
 * @param value - The string to format (e.g., "drivers_license", "health-card")
 * @returns Formatted string (e.g., "Drivers License", "Health Card")
 */
export function toTitleCase(value: string): string {
  if (!value) return '';
  
  return value
    .replace(/[_-]/g, ' ')  // Replace underscores and hyphens with spaces
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Converts camelCase to Title Case
 * @param value - The string to format (e.g., "firstName")
 * @returns Formatted string (e.g., "First Name")
 */
export function camelToTitleCase(value: string): string {
  if (!value) return '';
  
  return value
    .replace(/([A-Z])/g, ' $1')  // Add space before capital letters
    .replace(/^./, str => str.toUpperCase())  // Capitalize first letter
    .trim();
}

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
 * Produce a readable title from arbitrary strings containing special characters
 * Examples:
 *  - "service_provider" -> "Service Provider"
 *  - "client-type#1" -> "Client Type 1"
 *  - "firstName" -> "First Name"
 */
export function readableTitle(value: string): string {
  if (!value) return '';

  // Normalize common separators to spaces
  let s = value.replace(/[_-]+/g, ' ');

  // Remove any characters that are not letters, numbers or whitespace
  s = s.replace(/[^A-Za-z0-9\s]+/g, ' ');

  // Collapse multiple spaces and trim
  s = s.replace(/\s+/g, ' ').trim();

  // If the string is camelCase, convert to words first
  if (/[a-z][A-Z]/.test(value)) {
    s = camelToTitleCase(s);
  }

  // Finally apply title-casing for readability
  return toTitleCase(s);
}
