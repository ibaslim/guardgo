import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';

import { ApiRequestOptions, ApiService } from './api.service';
import {
  ClientRequestCreatePayload,
  ClientRequestItem,
  ClientRequestListResponse,
  ClientRequestStatus,
  ClientRequestUpdatePayload,
  RequestAdditionalCoveragePayload,
  RequestAssignmentListResponse,
  RequestAssignmentItem,
  RequestAssignmentStatus,
  RequestBroadcastWaveItem,
  RequestPublishPayload,
  RequestPublishUpdatePayload,
  RequestReviewWaveListResponse,
  RequestWaveListResponse,
  RequestWaveReviewPayload,
} from '../model/request/client-request.model';

@Injectable({ providedIn: 'root' })
export class RequestService {
  constructor(private api: ApiService) {}

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

  listRequestWaves(requestId: string, page = 1, rows = 20, options?: ApiRequestOptions) {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows);
    return this.api.get<RequestWaveListResponse>(`requests/${requestId}/waves`, { ...options, params });
  }

  getRequestWave(waveId: string, options?: ApiRequestOptions) {
    return this.api.get<RequestBroadcastWaveItem>(`request-waves/${waveId}`, options);
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
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('wave_status', waveStatus)
      .set('trigger', trigger)
      .set('request_id', requestId)
      .set('client_tenant_id', clientTenantId);
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
