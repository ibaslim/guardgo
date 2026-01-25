export interface userSessionData {
    user: UserDataModel;
    tenant: TenantDataModel;
    alerts: AlertModel[];
}

export interface UserDataModel {
    email: string;
    twofa_enabled: boolean;
    username: string;
    role: string;
    status: string;
    subscription: boolean;
    verificationDate: string;
    license: string[];
    image?: string;
    preferences?: {
        [key: string]: any;
    };
}

export interface TenantDataModel {
    id: string;
    name: string;
    phone: string;
    country: string;
    city: string;
    postal_code: string;
    has_onboarding: boolean;
    is_default: boolean;
    tax_id: string;
    user_id: string;
    licenses: string[];
    assigned_quota: string;
    quota_exceeded: boolean;
    image?: string;
    tenant_type?: string;
    status?: string;
}

export interface AlertAllIoc {
    name: string;
    values: string[];
}

export interface AlertModel {
    alert_id?: string;
    report_seen?: boolean;
    custom_alert?: boolean;
    type?: string;
    ioc_type?: string;
    ioc_value?: string;
    data_hash?: string;
    title?: string;
    description?: string;
    url?: string;
    source?: string;
    all_ioc?: AlertAllIoc[];
    content_types?: string[];
    status?: 'ignore' | 'active';
    first_seen?: Date;
    last_seen?: Date;
}
