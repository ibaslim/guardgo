export type RoleMetadataModel = {
  platformRoles: string[];
  tenantSettingsRoles: string[];
  tenantManagementRoles: string[];
  platformUserManagementRoles: string[];
};

export type AccessPolicy =
  | 'platform'
  | 'tenantSettings'
  | 'tenantManagement'
  | 'platformUserManagement'
  | 'billingConfigurations'
  | 'clientRequests';

type AccessPolicyRule = {
  metadataKey?: keyof RoleMetadataModel;
  allowedRoles?: string[];
};

const policyRules: Record<AccessPolicy, AccessPolicyRule> = {
  platform: { metadataKey: 'platformRoles' },
  tenantSettings: { metadataKey: 'tenantSettingsRoles' },
  tenantManagement: { metadataKey: 'tenantManagementRoles' },
  platformUserManagement: { allowedRoles: ['admin'] },
  billingConfigurations: { allowedRoles: ['admin'] },
  clientRequests: {
    allowedRoles: [
      'admin',
      'ops_admin',
      'support_admin',
      'compliance_admin',
      'read_only_admin',
      'client_admin',
      'guard_admin',
      'sp_admin'
    ]
  }
};

const routePolicyMap: Record<string, AccessPolicy> = {
  '/dashboard/admin-users': 'platformUserManagement',
  '/dashboard/billing-configurations': 'billingConfigurations',
  '/dashboard/requests': 'clientRequests'
};

export const normalizeRole = (role: string | undefined | null): string => {
  const rawRole = String(role || '').trim().toLowerCase();
  return rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
};

export const isServiceProviderOwnedGuardTenant = (
  tenant: { tenant_type?: string | null; ownership_type?: string | null } | undefined | null
): boolean => {
  const tenantType = String(tenant?.tenant_type || '').trim().toLowerCase();
  const ownershipType = String(tenant?.ownership_type || '').trim().toLowerCase();
  return tenantType === 'guard' && ownershipType === 'service_provider';
};

export const canAccessPolicy = (
  policy: AccessPolicy,
  role: string | undefined | null,
  metadata: Partial<RoleMetadataModel> | undefined | null
): boolean => {
  const normalizedRole = normalizeRole(role);
  if (!normalizedRole) return false;

  const rule = policyRules[policy];
  if (Array.isArray(rule.allowedRoles) && rule.allowedRoles.length > 0) {
    return rule.allowedRoles.includes(normalizedRole);
  }

  const metadataKey = rule.metadataKey;
  const allowedRoles = metadataKey && Array.isArray(metadata?.[metadataKey]) ? metadata?.[metadataKey] || [] : [];
  return allowedRoles.includes(normalizedRole);
};

export const canAccessRoute = (
  route: string,
  role: string | undefined | null,
  metadata: Partial<RoleMetadataModel> | undefined | null
): boolean => {
  const policy = routePolicyMap[route];
  if (!policy) return true;
  return canAccessPolicy(policy, role, metadata);
};
