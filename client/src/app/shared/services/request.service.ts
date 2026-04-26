import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';

import { ApiRequestOptions, ApiService } from './api.service';
import {
  ClientRequestCreatePayload,
  ClientRequestItem,
  ClientRequestListResponse,
  ClientRequestStatus,
  ClientRequestUpdatePayload,
  RequestAssignmentListResponse,
  RequestAssignmentItem,
  RequestAssignmentStatus,
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

  updateRequest(requestId: string, payload: ClientRequestUpdatePayload, options?: ApiRequestOptions) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}`, payload, options);
  }

  updateRequestStatus(requestId: string, requestStatus: ClientRequestStatus, reason?: string, options?: ApiRequestOptions) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}/status`, {
      request_status: requestStatus,
      reason: reason || null,
    }, options);
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

  updateJobStatus(assignmentId: string, assignmentStatus: RequestAssignmentStatus, reason?: string, options?: ApiRequestOptions) {
    return this.api.patch<{ message: string; item: RequestAssignmentItem }>(`jobs/${assignmentId}/status`, {
      assignment_status: assignmentStatus,
      reason: reason || null,
    }, options);
  }
}
