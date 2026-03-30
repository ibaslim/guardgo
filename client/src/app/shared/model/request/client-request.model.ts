export type ClientRequestStatus = 'draft' | 'submitted' | 'cancelled' | 'closed';
export type ClientRequestTargetType = 'guard' | 'service_provider';
export type RequestAssignmentStatus = 'offered' | 'accepted' | 'declined' | 'in_progress' | 'completed' | 'cancelled';

export interface ClientRequestItem {
  id: string;
  client_tenant_id: string;
  created_by_user_id: string;
  created_by_username: string;
  title: string;
  target_type: ClientRequestTargetType;
  requested_guard_type?: string | null;
  guards_required: number;
  request_status: ClientRequestStatus;
  site_snapshot: {
    site_index: number;
    site_source?: string;
    site_id?: string;
    site_name: string;
    site_manager_contact?: string;
    manager_email?: string;
    number_of_guards_required?: number | null;
    site_type?: string | null;
    google_maps_url?: string;
    site_address?: {
      street?: string;
      city?: string;
      country?: string;
      province?: string;
      postal_code?: string;
      latitude?: number | null;
      longitude?: number | null;
      [key: string]: any;
    };
  };
  special_instructions?: string | null;
  requested_start_at?: string | null;
  requested_end_at?: string | null;
  match_summary?: Record<string, any>;
  matched_candidates?: Array<Record<string, any>>;
  cancelled_at?: string | null;
  closed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequestAssignmentItem {
  id: string;
  request_id: string;
  client_tenant_id: string;
  assignee_tenant_id: string;
  assignee_tenant_type: ClientRequestTargetType;
  assignment_status: RequestAssignmentStatus;
  candidate_snapshot?: Record<string, any>;
  assigned_by_user_id: string;
  assigned_by_username: string;
  note?: string | null;
  offered_at?: string | null;
  accepted_at?: string | null;
  declined_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
  request?: {
    id?: string;
    title?: string;
    request_status?: ClientRequestStatus | string;
    target_type?: ClientRequestTargetType | string;
    site_name?: string;
    requested_start_at?: string | null;
    requested_end_at?: string | null;
  };
}

export interface ClientRequestListResponse {
  items: ClientRequestItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
  filters: {
    keyword: string;
    request_status: string;
    target_type: string;
  };
}

export interface ClientRequestCreatePayload {
  title: string;
  target_type: ClientRequestTargetType;
  site_index?: number | null;
  site?: {
    site_name: string;
    site_manager_contact?: string | null;
    manager_email?: string | null;
    site_type?: string | null;
    google_maps_url?: string | null;
    site_address: {
      street?: string | null;
      city: string;
      country?: string | null;
      province: string;
      postal_code?: string | null;
      latitude?: number | null;
      longitude?: number | null;
    };
  } | null;
  requested_guard_type?: string | null;
  guards_required: number;
  requested_start_at?: string | null;
  requested_end_at?: string | null;
  special_instructions?: string | null;
  max_match_results: number;
  commit?: boolean;
}

export interface ClientRequestUpdatePayload {
  title?: string | null;
  target_type?: ClientRequestTargetType;
  site?: {
    site_name: string;
    site_manager_contact?: string | null;
    manager_email?: string | null;
    site_type?: string | null;
    google_maps_url?: string | null;
    site_address: {
      street?: string | null;
      city: string;
      country?: string | null;
      province: string;
      postal_code?: string | null;
      latitude?: number | null;
      longitude?: number | null;
    };
  } | null;
  requested_guard_type?: string | null;
  guards_required?: number;
  requested_start_at?: string | null;
  requested_end_at?: string | null;
  special_instructions?: string | null;
  max_match_results?: number;
}

export interface RequestAssignmentListResponse {
  items: RequestAssignmentItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
  filters: {
    assignment_status: string;
    keyword: string;
  };
}
