export type ClientRequestStatus = 'draft' | 'submitted' | 'assigned' | 'in_progress' | 'cancelled' | 'closed';
export type ClientRequestTargetType = 'guard' | 'service_provider';
export type ClientRequestFulfillmentMode = 'individual_only' | 'service_provider_only' | 'hybrid';
export type RequestStaffingStatus = 'pending_review' | 'review_returned' | 'open' | 'partially_filled' | 'filled' | 'expired';
export type RequestLockReason = 'review_pending' | 'filled' | 'request_expired' | 'request_cancelled' | 'request_closed';
export type RequestAssignmentStatus =
  | 'offered'
  | 'accepted'
  | 'reconfirmation_required'
  | 'declined'
  | 'expired'
  | 'closed_filled'
  | 'superseded'
  | 'in_progress'
  | 'completed'
  | 'cancelled';
export type RequestAssignmentOrigin = 'manual' | 'broadcast';
export type RequestAssignmentScope = 'request' | 'shift_replacement';
export type RequestAssignmentLockReason = 'filled' | 'wave_expired' | 'request_expired' | 'superseded' | 'request_cancelled';
export type RequestWaveTrigger = 'initial_publish' | 'publish_update' | 'additional_coverage' | 'capacity_reopened';
export type RequestWaveStatus = 'pending_review' | 'active' | 'returned' | 'filled' | 'expired' | 'superseded' | 'cancelled';
export type RequestScheduleType = 'one_time' | 'date_range' | 'recurring_weekly';
export type ShiftInstanceStatus =
  | 'scheduled'
  | 'partially_staffed'
  | 'staffed'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'expired';
export type ShiftSlotStatus =
  | 'open'
  | 'reserved'
  | 'rostered'
  | 'unavailable'
  | 'late_risk'
  | 'arrival_pending'
  | 'client_confirmation_pending'
  | 'in_progress'
  | 'completed'
  | 'no_show_suspected'
  | 'no_show_confirmed'
  | 'replacement_required'
  | 'cancelled';
export type ShiftAttendanceEventType =
  | 'unavailable_reported'
  | 'leave_reported'
  | 'leave_returned'
  | 'late_arrival'
  | 'checkin_attempted'
  | 'arrived'
  | 'geo_failed'
  | 'client_confirmed'
  | 'ops_start_override'
  | 'started'
  | 'checkout'
  | 'completed'
  | 'no_show_suspected'
  | 'no_show_confirmed'
  | 'replacement_requested'
  | 'replacement_assigned';

export interface ClientRequestItem {
  id: string;
  client_tenant_id: string;
  client_tenant_label?: string | null;
  created_by_user_id: string;
  created_by_username: string;
  title: string;
  fulfillment_mode: ClientRequestFulfillmentMode;
  target_type: ClientRequestTargetType;
  requested_guard_type?: string | null;
  guards_required: number;
  request_status: ClientRequestStatus;
  staffing_status?: RequestStaffingStatus | null;
  lock_reason?: RequestLockReason | null;
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
  request_expires_at?: string | null;
  published_at?: string | null;
  published_by_user_id?: string | null;
  published_by_username?: string | null;
  request_revision?: number;
  accepted_slots?: number;
  open_slots?: number;
  active_wave_id?: string | null;
  last_wave_number?: number;
  expired_at?: string | null;
  match_summary?: Record<string, any>;
  matched_candidates?: Array<Record<string, any>>;
  cancelled_at?: string | null;
  closed_at?: string | null;
  deleted_at?: string | null;
  deleted_by_user_id?: string | null;
  deleted_by_username?: string | null;
  deleted_reason?: string | null;
  created_at: string;
  updated_at: string;
  viewer_assignment?: RequestAssignmentItem | null;
}

export interface RequestAssignmentItem {
  id: string;
  request_id: string;
  client_tenant_id: string;
  assignee_tenant_id: string;
  assignee_tenant_type: ClientRequestTargetType;
  assignment_status: RequestAssignmentStatus;
  assignment_origin?: RequestAssignmentOrigin | null;
  assignment_scope?: RequestAssignmentScope | null;
  broadcast_wave_id?: string | null;
  shift_instance_id?: string | null;
  shift_slot_id?: string | null;
  request_revision_at_offer?: number;
  slots_committed?: number | null;
  response_due_at?: string | null;
  reconfirmation_due_at?: string | null;
  lock_reason?: RequestAssignmentLockReason | null;
  candidate_snapshot?: Record<string, any>;
  assigned_by_user_id: string;
  assigned_by_username: string;
  note?: string | null;
  offered_at?: string | null;
  accepted_at?: string | null;
  declined_at?: string | null;
  expired_at?: string | null;
  reconfirmation_requested_at?: string | null;
  reconfirmed_at?: string | null;
  closed_filled_at?: string | null;
  superseded_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
  request?: {
    id?: string;
    title?: string;
    request_status?: ClientRequestStatus | string;
    staffing_status?: RequestStaffingStatus | string;
    fulfillment_mode?: ClientRequestFulfillmentMode | string;
    target_type?: ClientRequestTargetType | string;
    requested_guard_type?: string | null;
    site_name?: string;
    requested_start_at?: string | null;
    requested_end_at?: string | null;
    request_revision?: number;
    request_expires_at?: string | null;
    accepted_slots?: number;
    open_slots?: number;
    has_schedule?: boolean;
  };
}

export interface RequestBroadcastWaveItem {
  id: string;
  request_id: string;
  client_tenant_id: string;
  request_revision: number;
  wave_number: number;
  trigger: RequestWaveTrigger;
  wave_status: RequestWaveStatus;
  request_snapshot?: Record<string, any>;
  match_summary_snapshot?: Record<string, any>;
  candidate_snapshots?: Array<Record<string, any>>;
  review_reason_codes?: string[];
  review_findings?: Array<Record<string, any>>;
  review_note?: string | null;
  reviewed_by_user_id?: string | null;
  reviewed_by_username?: string | null;
  review_requested_at?: string | null;
  reviewed_at?: string | null;
  returned_at?: string | null;
  activated_at?: string | null;
  wave_expires_at?: string | null;
  filled_at?: string | null;
  expired_at?: string | null;
  superseded_at?: string | null;
  cancelled_at?: string | null;
  open_slots_at_send?: number;
  offer_count?: number;
  accepted_slots_at_close?: number;
  created_at: string;
  updated_at: string;
}

export interface RequestScheduleItem {
  id: string;
  request_id: string;
  client_tenant_id: string;
  timezone: string;
  schedule_type: RequestScheduleType;
  start_date: string;
  end_date?: string | null;
  start_time_local: string;
  end_time_local: string;
  is_overnight: boolean;
  recurrence_days: string[];
  generation_horizon_days: number;
  roster_due_offset_minutes: number;
  unavailable_cutoff_minutes: number;
  late_grace_minutes: number;
  no_show_cutoff_minutes: number;
  checkin_geofence_meters: number;
  active: boolean;
  generated_shift_count?: number;
  generated_slot_count?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ShiftSlotItem {
  id: string;
  shift_instance_id: string;
  request_id: string;
  client_tenant_id: string;
  parent_assignment_id?: string | null;
  slot_number: number;
  coverage_slot_index?: number;
  coverage_source_type?: ClientRequestTargetType | null;
  coverage_tenant_id?: string | null;
  service_provider_tenant_id?: string | null;
  assigned_guard_tenant_id?: string | null;
  slot_status: ShiftSlotStatus;
  replacement_of_slot_id?: string | null;
  rostered_at?: string | null;
  roster_due_at?: string | null;
  guard_unavailable_reported_at?: string | null;
  arrived_at?: string | null;
  client_confirmed_at?: string | null;
  started_at?: string | null;
  checked_out_at?: string | null;
  completed_at?: string | null;
  no_show_confirmed_at?: string | null;
  geo_check_passed?: boolean | null;
  actual_start_at?: string | null;
  actual_end_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShiftAttendanceEventItem {
  id: string;
  shift_slot_id: string;
  shift_instance_id: string;
  request_id: string;
  event_type: ShiftAttendanceEventType | string;
  actor_user_id?: string | null;
  actor_role?: string | null;
  guard_tenant_id?: string | null;
  service_provider_tenant_id?: string | null;
  client_tenant_id?: string | null;
  timestamp: string;
  latitude?: number | null;
  longitude?: number | null;
  distance_meters?: number | null;
  note?: string | null;
  metadata?: Record<string, any>;
}

export interface ShiftInstanceItem {
  id: string;
  request_id: string;
  request_title?: string | null;
  site_name?: string | null;
  client_tenant_id: string;
  schedule_template_id: string;
  shift_date_local: string;
  shift_start_at_utc: string;
  shift_end_at_utc: string;
  timezone: string;
  instance_status: ShiftInstanceStatus | string;
  slots_required: number;
  slots_staffed: number;
  slots_checked_in: number;
  slots_completed: number;
  client_action_required: boolean;
  roster_due_at?: string | null;
  created_from_revision?: number;
  cancel_reason?: string | null;
  reduction_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ShiftExceptionItem {
  slot: ShiftSlotItem;
  shift: ShiftInstanceItem;
  request: {
    id: string;
    title: string;
    client_tenant_id: string;
  };
}

export interface ShiftExceptionListResponse {
  items: ShiftExceptionItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
}

export interface ShiftSlotDetailResponse {
  slot: ShiftSlotItem;
  events: ShiftAttendanceEventItem[];
}

export interface ShiftSlotSummary {
  total_visible_slots: number;
  open_slots: number;
  reserved_slots: number;
  rostered_slots: number;
}

export interface ShiftDetailResponse {
  shift: ShiftInstanceItem;
  slots: ShiftSlotItem[];
  slot_summary: ShiftSlotSummary;
}

export interface ShiftSlotReopenPayload {
  note?: string | null;
  max_match_results: number;
}

export interface ShiftSlotReopenResponse {
  message: string;
  original_slot: ShiftSlotItem;
  replacement_slot: ShiftSlotItem;
  wave?: RequestBroadcastWaveItem | null;
}

export interface RequestScheduleResponse {
  schedule: RequestScheduleItem;
}

export interface RequestScheduleUpsertPayload {
  timezone: string;
  schedule_type: RequestScheduleType;
  start_date: string;
  end_date?: string | null;
  start_time_local: string;
  end_time_local: string;
  recurrence_days: string[];
  generation_horizon_days: number;
  roster_due_offset_minutes: number;
  unavailable_cutoff_minutes: number;
  late_grace_minutes: number;
  no_show_cutoff_minutes: number;
  checkin_geofence_meters: number;
  active: boolean;
}

export interface ShiftListResponse {
  items: ShiftInstanceItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
}

export interface ProviderRosterSelectionPayload {
  slot_id: string;
  guard_tenant_id: string;
}

export interface ProviderRosterPayload {
  assignments: ProviderRosterSelectionPayload[];
}

export interface ShiftSlotCheckInPayload {
  latitude: number;
  longitude: number;
  note?: string | null;
  timezone?: string | null;
}

export interface ShiftSlotClientConfirmPayload {
  note?: string | null;
}

export interface ShiftSlotStartPayload {
  note?: string | null;
  timezone?: string | null;
}

export interface ShiftSlotCheckOutPayload {
  note?: string | null;
}

export interface ShiftSlotUnavailablePayload {
  note?: string | null;
}

export type ShiftGuardLeaveStatus = 'active' | 'returned_early' | 'completed' | 'cancelled';

export interface ShiftGuardLeaveItem {
  id: string;
  guard_tenant_id: string;
  service_provider_tenant_id?: string | null;
  leave_status: ShiftGuardLeaveStatus | string;
  start_at_utc: string;
  end_at_utc: string;
  effective_end_at_utc?: string | null;
  reason?: string | null;
  affected_slot_ids: string[];
  replacement_slot_ids: string[];
  requested_by_user_id?: string | null;
  requested_by_username?: string | null;
  requested_by_role?: string | null;
  returned_early_at?: string | null;
  returned_early_by_user_id?: string | null;
  returned_early_by_username?: string | null;
  return_note?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ShiftGuardLeaveListResponse {
  items: ShiftGuardLeaveItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
  filters: {
    guard_tenant_id?: string;
    leave_status?: string;
  };
}

export interface ShiftGuardLeaveCreatePayload {
  guard_tenant_id?: string | null;
  start_at_utc: string;
  end_at_utc: string;
  reason?: string | null;
}

export interface ShiftGuardLeaveReturnPayload {
  note?: string | null;
}

export type ShiftGuardLeaveReturnDecisionAction = 'restore_original' | 'keep_replacement';
export type ShiftGuardLeaveReturnReviewMode = 'auto_restore' | 'manual_review' | 'keep_history';

export interface ShiftGuardLeaveReturnReviewItem {
  original_slot_id: string;
  original_slot_status: ShiftSlotStatus | string;
  shift_id: string;
  request_id: string;
  request_title: string;
  shift_date_local: string;
  shift_start_at_utc: string;
  shift_end_at_utc: string;
  replacement_slot_id?: string | null;
  replacement_slot_status?: ShiftSlotStatus | string | null;
  replacement_assignment_id?: string | null;
  replacement_assignment_status?: RequestAssignmentStatus | string | null;
  replacement_assignee_tenant_id?: string | null;
  replacement_assignee_tenant_type?: ClientRequestTargetType | string | null;
  replacement_assigned_guard_tenant_id?: string | null;
  review_mode: ShiftGuardLeaveReturnReviewMode | string;
  recommended_action: ShiftGuardLeaveReturnDecisionAction | string;
  can_restore_original: boolean;
  can_keep_replacement: boolean;
}

export interface ShiftGuardLeaveReturnReviewResponse {
  leave: ShiftGuardLeaveItem;
  items: ShiftGuardLeaveReturnReviewItem[];
  summary: {
    total_items: number;
    auto_restore_count: number;
    decision_required_count: number;
    locked_history_count: number;
  };
}

export interface ShiftGuardLeaveReturnDecisionPayload {
  original_slot_id: string;
  action: ShiftGuardLeaveReturnDecisionAction;
}

export interface ShiftGuardLeaveReconcilePayload {
  note?: string | null;
  decisions: ShiftGuardLeaveReturnDecisionPayload[];
}

export interface ServiceProviderGuardSummaryItem {
  id: string;
  name?: string | null;
  status?: string | null;
  ownership_type?: string | null;
  service_provider_tenant_id?: string | null;
  invite_status?: string | null;
  invite_expires_at?: string | null;
  email?: string | null;
  verified?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ServiceProviderGuardListResponse {
  items: ServiceProviderGuardSummaryItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
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
    fulfillment_mode: string;
    client_tenant_id?: string;
  };
}

export interface ClientRequestCreatePayload {
  title: string;
  timezone?: string | null;
  fulfillment_mode: ClientRequestFulfillmentMode;
  client_tenant_id?: string | null;
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
  request_expires_at?: string | null;
  special_instructions?: string | null;
  max_match_results: number;
  commit?: boolean;
}

export interface ClientRequestUpdatePayload {
  title?: string | null;
  timezone?: string | null;
  fulfillment_mode?: ClientRequestFulfillmentMode;
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
  request_expires_at?: string | null;
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

export interface RequestWaveListResponse {
  items: RequestBroadcastWaveItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
}

export interface RequestReviewWaveListResponse extends RequestWaveListResponse {
  filters: {
    wave_status: string;
    trigger: string;
    request_id: string;
    client_tenant_id: string;
  };
}

export interface RequestPublishPayload {
  max_match_results: number;
}

export interface RequestPublishUpdatePayload {
  timezone?: string | null;
  fulfillment_mode?: ClientRequestFulfillmentMode;
  site?: ClientRequestUpdatePayload['site'];
  requested_guard_type?: string | null;
  requested_start_at?: string | null;
  requested_end_at?: string | null;
  request_expires_at?: string | null;
  special_instructions?: string | null;
  max_match_results: number;
}

export interface RequestAdditionalCoveragePayload {
  additional_slots: number;
  request_expires_at?: string | null;
  max_match_results: number;
}

export interface RequestWaveReviewPayload {
  note?: string | null;
}
