export interface IocCategory {
  ioc_id: string;
  name: string;
  values: string[];
}

export type TenantStatus = 'onboarding' | 'active' | 'disable';

export const TenantStatusValues = {
  ONBOARDING: 'onboarding' as TenantStatus,
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
  quotaExceeded?: boolean;
  email?: string;
}