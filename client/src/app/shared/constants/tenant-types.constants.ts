/**
 * Tenant Type Constants
 * Defines all available tenant/user types in the system
 */

export const TENANT_TYPES = {
  GUARD: 'guard',
  CLIENT: 'client',
  SERVICE_PROVIDER: 'service_provider'
} as const;

export type TenantType = typeof TENANT_TYPES[keyof typeof TENANT_TYPES];

/**
 * Display labels for tenant types
 */
export const TENANT_TYPE_LABELS: Record<string, string> = {
  [TENANT_TYPES.GUARD]: 'Guard',
  [TENANT_TYPES.CLIENT]: 'Client',
  [TENANT_TYPES.SERVICE_PROVIDER]: 'Service Provider'
};

/**
 * Helper function to validate tenant type
 */
export function isValidTenantType(type: string): type is TenantType {
  return Object.values(TENANT_TYPES).includes(type as TenantType);
}

/**
 * Helper function to get tenant type label
 */
export function getTenantTypeLabel(type: string): string {
  return TENANT_TYPE_LABELS[type] || type;
}
