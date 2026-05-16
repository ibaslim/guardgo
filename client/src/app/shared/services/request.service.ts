import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';

import { ApiRequestOptions, ApiService } from './api.service';
import {
  ClientRequestCreatePayload,
  ClientRequestItem,
  ClientRequestListResponse,
  ClientRequestStatus,
  ClientRequestUpdatePayload,
  RequestScheduleResponse,
  RequestScheduleUpsertPayload,
  RequestAdditionalCoveragePayload,
  RequestAssignmentListResponse,
  RequestAssignmentItem,
  RequestAssignmentStatus,
  RequestBroadcastWaveItem,
  RequestPublishPayload,
  RequestPublishUpdatePayload,
  RequestReviewWaveListResponse,
  ProviderRosterPayload,
  ServiceProviderGuardListResponse,
  ShiftDetailResponse,
  ShiftExceptionListResponse,
  ShiftListResponse,
  ShiftSlotCheckInPayload,
  ShiftSlotCheckOutPayload,
  ShiftSlotClientConfirmPayload,
  ShiftSlotDetailResponse,
  ShiftSlotStartPayload,
  ShiftSlotUnavailablePayload,
  ShiftSlotReopenPayload,
  ShiftSlotReopenResponse,
  RequestWaveListResponse,
  RequestWaveReviewPayload,
} from '../model/request/client-request.model';

@Injectable({ providedIn: 'root' })
export class RequestService {
  constructor(private api: ApiService) {}

  private withOptionalParam(params: HttpParams, key: string, value: string | number | null | undefined): HttpParams {
    if (value === null || value === undefined) {
      return params;
    }
    if (typeof value === 'string') {
      const normalized = value.trim();
      return normalized ? params.set(key, normalized) : params;
    }
    return params.set(key, value);
  }

  listRequests(page = 1, rows = 20, keyword = '', requestStatus = '', fulfillmentMode = '', options?: ApiRequestOptions) {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('keyword', keyword)
      .set('request_status', requestStatus)
      .set('fulfillment_mode', fulfillmentMode);
    return this.api.get<ClientRequestListResponse>('requests', { ...options, params });
  }

  createRequest(payload: ClientRequestCreatePayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: ClientRequestItem }>('requests', payload, options);
  }

  getRequest(requestId: string, options?: ApiRequestOptions) {
    return this.api.get<ClientRequestItem>(`requests/${requestId}`, options);
  }

  getRequestSchedule(requestId: string, options?: ApiRequestOptions) {
    return this.api.get<RequestScheduleResponse>(`requests/${requestId}/schedule`, options);
  }

  createRequestSchedule(requestId: string, payload: RequestScheduleUpsertPayload, options?: ApiRequestOptions) {
    return this.api.post<RequestScheduleResponse>(`requests/${requestId}/schedule`, payload, options);
  }

  updateRequestSchedule(requestId: string, payload: RequestScheduleUpsertPayload, options?: ApiRequestOptions) {
    return this.api.patch<RequestScheduleResponse>(`requests/${requestId}/schedule`, payload, options);
  }

  updateRequest(requestId: string, payload: ClientRequestUpdatePayload, options?: ApiRequestOptions) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}`, payload, options);
  }

  publishRequest(requestId: string, payload: RequestPublishPayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: ClientRequestItem; wave?: RequestBroadcastWaveItem | null }>(
      `requests/${requestId}/publish`,
      payload,
      options,
    );
  }

  publishRequestUpdate(requestId: string, payload: RequestPublishUpdatePayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: ClientRequestItem; wave?: RequestBroadcastWaveItem | null }>(
      `requests/${requestId}/publish-update`,
      payload,
      options,
    );
  }

  requestAdditionalCoverage(requestId: string, payload: RequestAdditionalCoveragePayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: ClientRequestItem; wave?: RequestBroadcastWaveItem | null }>(
      `requests/${requestId}/additional-coverage`,
      payload,
      options,
    );
  }

  updateRequestStatus(requestId: string, requestStatus: ClientRequestStatus, reason?: string, options?: ApiRequestOptions) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}/status`, {
      request_status: requestStatus,
      reason: reason || null,
    }, options);
  }

  softDeleteRequest(requestId: string, reason: string, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: ClientRequestItem }>(`requests/${requestId}/soft-delete`, {
      reason,
    }, options);
  }

  listRequestWaves(requestId: string, page = 1, rows = 20, options?: ApiRequestOptions) {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    return this.api.get<RequestWaveListResponse>(`requests/${requestId}/waves`, { ...options, params });
  }

  getRequestWave(waveId: string, options?: ApiRequestOptions) {
    return this.api.get<RequestBroadcastWaveItem>(`request-waves/${waveId}`, options);
  }

  listShifts(
    page = 1,
    rows = 20,
    requestId = '',
    instanceStatus = '',
    dateFrom = '',
    dateTo = '',
    options?: ApiRequestOptions,
  ) {
    let params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    params = this.withOptionalParam(params, 'request_id', requestId);
    params = this.withOptionalParam(params, 'instance_status', instanceStatus);
    params = this.withOptionalParam(params, 'date_from', dateFrom);
    params = this.withOptionalParam(params, 'date_to', dateTo);
    return this.api.get<ShiftListResponse>('shifts', { ...options, params });
  }

  getShift(shiftId: string, options?: ApiRequestOptions) {
    return this.api.get<ShiftDetailResponse>(`shifts/${shiftId}`, options);
  }

  listShiftExceptions(
    page = 1,
    rows = 20,
    exceptionStatus = '',
    requestId = '',
    dateFrom = '',
    dateTo = '',
    options?: ApiRequestOptions,
  ) {
    let params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    params = this.withOptionalParam(params, 'exception_status', exceptionStatus);
    params = this.withOptionalParam(params, 'request_id', requestId);
    params = this.withOptionalParam(params, 'date_from', dateFrom);
    params = this.withOptionalParam(params, 'date_to', dateTo);
    return this.api.get<ShiftExceptionListResponse>('shift-exceptions', { ...options, params });
  }

  getShiftSlot(slotId: string, options?: ApiRequestOptions) {
    return this.api.get<ShiftSlotDetailResponse>(`shift-slots/${slotId}`, options);
  }

  reopenShiftSlot(slotId: string, payload: ShiftSlotReopenPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotReopenResponse>(`shift-slots/${slotId}/reopen`, payload, options);
  }

  rosterShift(shiftId: string, payload: ProviderRosterPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftDetailResponse>(`shifts/${shiftId}/roster`, payload, options);
  }

  reportShiftSlotUnavailable(slotId: string, payload: ShiftSlotUnavailablePayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotDetailResponse>(`shift-slots/${slotId}/report-unavailable`, payload, options);
  }

  checkInShiftSlot(slotId: string, payload: ShiftSlotCheckInPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotDetailResponse>(`shift-slots/${slotId}/check-in`, payload, options);
  }

  confirmShiftSlotArrival(slotId: string, payload: ShiftSlotClientConfirmPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotDetailResponse>(`shift-slots/${slotId}/client-confirm`, payload, options);
  }

  startShiftSlot(slotId: string, payload: ShiftSlotStartPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotDetailResponse>(`shift-slots/${slotId}/start`, payload, options);
  }

  checkOutShiftSlot(slotId: string, payload: ShiftSlotCheckOutPayload, options?: ApiRequestOptions) {
    return this.api.post<ShiftSlotDetailResponse>(`shift-slots/${slotId}/check-out`, payload, options);
  }

  listServiceProviderGuards(page = 1, rows = 100, options?: ApiRequestOptions) {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    return this.api.get<ServiceProviderGuardListResponse>('sp/guards', { ...options, params });
  }

  listRequestReviewWaves(
    page = 1,
    rows = 20,
    waveStatus = '',
    trigger = '',
    requestId = '',
    clientTenantId = '',
    options?: ApiRequestOptions,
  ) {
    let params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    params = this.withOptionalParam(params, 'wave_status', waveStatus);
    params = this.withOptionalParam(params, 'trigger', trigger);
    params = this.withOptionalParam(params, 'request_id', requestId);
    params = this.withOptionalParam(params, 'client_tenant_id', clientTenantId);
    return this.api.get<RequestReviewWaveListResponse>('request-review-waves', { ...options, params });
  }

  approveRequestWave(waveId: string, payload: RequestWaveReviewPayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: RequestBroadcastWaveItem }>(
      `request-review-waves/${waveId}/approve`,
      payload,
      options,
    );
  }

  returnRequestWave(waveId: string, payload: RequestWaveReviewPayload, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: RequestBroadcastWaveItem }>(
      `request-review-waves/${waveId}/return`,
      payload,
      options,
    );
  }

  assignRequest(requestId: string, candidateTenantId: string, note?: string, options?: ApiRequestOptions) {
    return this.api.post<{ message: string; item: RequestAssignmentItem }>(`requests/${requestId}/assign`, {
      candidate_tenant_id: candidateTenantId,
      note: note || null,
    }, options);
  }

  listJobs(page = 1, rows = 20, assignmentStatus = '', keyword = '', options?: ApiRequestOptions) {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('assignment_status', assignmentStatus)
      .set('keyword', keyword);
    return this.api.get<RequestAssignmentListResponse>('jobs', { ...options, params });
  }

  getJob(assignmentId: string, options?: ApiRequestOptions) {
    return this.api.get<RequestAssignmentItem>(`jobs/${assignmentId}`, options);
  }

  updateJobStatus(
    assignmentId: string,
    assignmentStatus: RequestAssignmentStatus,
    reason?: string,
    options?: ApiRequestOptions,
    slotsCommitted?: number | null,
  ) {
    return this.api.patch<{ message: string; item: RequestAssignmentItem }>(`jobs/${assignmentId}/status`, {
      assignment_status: assignmentStatus,
      reason: reason || null,
      slots_committed: slotsCommitted ?? null,
    }, options);
  }
}
