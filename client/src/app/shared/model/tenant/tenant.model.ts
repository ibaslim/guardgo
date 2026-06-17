export interface IocCategory {
  ioc_id: string;
  name: string;
  values: string[];
}

export type TenantStatus = 'onboarding' | 'pending_activation' | 'active' | 'disable';

export const TenantStatusValues = {
  ONBOARDING: 'onboarding' as TenantStatus,
  PENDING_ACTIVATION: 'pending_activation' as TenantStatus,
  ACTIVE: 'active' as TenantStatus,
  DISABLE: 'disable' as TenantStatus,
};

export interface TenantModel {
  id?: string;
  name: string;
  iocs: IocCategory[];
  phone?: string;
  country?: string;
  city?: string;
  subscription?: boolean;
  postal_code?: string;
  verified?: boolean;
  user_quota?: number;
  status?: TenantStatus;
  licenses?: string[];
  quota_exceeded?: boolean;
  email?: string;
}

export interface TenantUpdateResponse {
  message: string;
  id: string;
  tenant_type?: string;
  status?: string;
  approvals_required?: number;
  approvals_done?: number;
  approvals_remaining?: number;
  profile?: Record<string, unknown>;
  tenant?: {
    name?: string;
    iocs?: IocCategory[];
  };
  alerts?: unknown[];
}
