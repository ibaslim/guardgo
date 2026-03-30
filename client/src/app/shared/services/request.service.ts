import { Injectable } from '@angular/core';
import { HttpParams } from '@angular/common/http';

import { ApiService } from './api.service';
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

  listRequests(page = 1, rows = 20, keyword = '', requestStatus = '', targetType = '') {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('keyword', keyword)
      .set('request_status', requestStatus)
      .set('target_type', targetType);
    return this.api.get<ClientRequestListResponse>('requests', { params });
  }

  createRequest(payload: ClientRequestCreatePayload) {
    return this.api.post<{ message: string; item: ClientRequestItem }>('requests', payload);
  }

  updateRequest(requestId: string, payload: ClientRequestUpdatePayload) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}`, payload);
  }

  updateRequestStatus(requestId: string, requestStatus: ClientRequestStatus, reason?: string) {
    return this.api.patch<{ message: string; item: ClientRequestItem }>(`requests/${requestId}/status`, {
      request_status: requestStatus,
      reason: reason || null,
    });
  }

  assignRequest(requestId: string, candidateTenantId: string, note?: string) {
    return this.api.post<{ message: string; item: RequestAssignmentItem }>(`requests/${requestId}/assign`, {
      candidate_tenant_id: candidateTenantId,
      note: note || null,
    });
  }

  listJobs(page = 1, rows = 20, assignmentStatus = '', keyword = '') {
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('assignment_status', assignmentStatus)
      .set('keyword', keyword);
    return this.api.get<RequestAssignmentListResponse>('jobs', { params });
  }

  updateJobStatus(assignmentId: string, assignmentStatus: RequestAssignmentStatus, reason?: string) {
    return this.api.patch<{ message: string; item: RequestAssignmentItem }>(`jobs/${assignmentId}/status`, {
      assignment_status: assignmentStatus,
      reason: reason || null,
    });
  }
}
