import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription, interval } from 'rxjs';

import { ButtonComponent } from '../../components/button/button.component';
import { CardComponent } from '../../components/card/card.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { IconComponent } from '../../components/icon/icon.component';
import { PageComponent } from '../../components/page/page.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { ApiService } from '../../shared/services/api.service';
import { RequestService } from '../../shared/services/request.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import {
  ClientRequestFulfillmentMode,
  ClientRequestItem,
  ClientRequestStatus,
  RequestAssignmentItem,
  RequestAssignmentStatus,
  RequestBroadcastWaveItem,
} from '../../shared/model/request/client-request.model';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { AppService } from '../../services/core/app/app.service';
import { normalizeRole } from '../../shared/helpers/access-control.helper';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';

@Component({
  selector: 'app-requests',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PageComponent,
    CardComponent,
    ButtonComponent,
    BaseInputComponent,
    SelectInputComponent,
    TextareaComponent,
    SideDrawerComponent,
    IconComponent,
  ],
  templateUrl: './requests.component.html',
})
export class RequestsComponent implements OnInit, OnDestroy {
  readonly requestListScope = 'requests:list';
  readonly jobListScope = 'requests:jobs';
  readonly metadataScope = 'requests:metadata';
  readonly saveRequestScope = 'requests:save';
  readonly reviewListScope = 'requests:review:list';
  readonly requestWavesScope = 'requests:detail:waves';
  readonly jobDetailRequestScope = 'requests:job:detail';
  readonly jobDetailWavesScope = 'requests:job:waves';
  loading = false;
  saving = false;
  jobsLoading = false;
  reviewLoading = false;
  requestWavesLoading = false;
  private readonly loadingFeedback = inject(LoadingFeedbackService);
  private autoRefreshSubscription: Subscription | null = null;
  private routeQuerySubscription: Subscription | null = null;
  private lastHandledRouteFocus = '';

  role = '';
  tenantType = '';

  activeTab: 'requests' | 'jobs' | 'review' = 'requests';

  items: ClientRequestItem[] = [];
  jobs: RequestAssignmentItem[] = [];
  reviewWaves: RequestBroadcastWaveItem[] = [];
  selectedRequestWaves: RequestBroadcastWaveItem[] = [];

  page = 1;
  rows = 10;
  totalPages = 1;
  totalItems = 0;

  jobPage = 1;
  jobRows = 10;
  jobTotalPages = 1;
  jobTotalItems = 0;

  reviewPage = 1;
  reviewRows = 10;
  reviewTotalPages = 1;
  reviewTotalItems = 0;

  keyword = '';
  requestStatusFilter = '';
  fulfillmentModeFilter = '';

  jobKeyword = '';
  jobStatusFilter = '';

  reviewStatusFilter = 'pending_review';
  reviewTriggerFilter = '';

  requestErrors: Record<string, string> = {};

  selectedRequest: ClientRequestItem | null = null;
  selectedWave: RequestBroadcastWaveItem | null = null;
  selectedJob: RequestAssignmentItem | null = null;
  selectedJobRequest: ClientRequestItem | null = null;
  selectedJobWaves: RequestBroadcastWaveItem[] = [];
  showRequestDrawer = false;
  showRequestFormDrawer = false;
  showWaveDrawer = false;
  showJobDrawer = false;
  showCoverageDrawer = false;
  showReturnWaveDrawer = false;
  showAcceptJobDrawer = false;
  showReasonDrawer = false;
  requestFormMode: 'create' | 'edit' | 'publish_update' = 'create';
  editingRequestId = '';

  selectedCandidateByRequestId: Record<string, string> = {};
  assigningRequestId = '';
  updatingJobId = '';
  reviewingWaveId = '';
  selectedCoverageRequest: ClientRequestItem | null = null;
  returnWaveTarget: RequestBroadcastWaveItem | null = null;
  selectedAcceptJob: RequestAssignmentItem | null = null;
  reasonRequestTarget: ClientRequestItem | null = null;
  reasonJobTarget: RequestAssignmentItem | null = null;
  reasonRequestStatus: ClientRequestStatus | null = null;
  reasonJobStatus: RequestAssignmentStatus | null = null;
  coverageErrors: Record<string, string> = {};
  returnWaveErrors: Record<string, string> = {};
  acceptJobErrors: Record<string, string> = {};
  reasonErrors: Record<string, string> = {};

  coverageForm = {
    additionalSlots: 1,
    requestExpiresAt: '',
  };

  returnWaveForm = {
    note: '',
  };

  acceptJobForm = {
    slotsCommitted: 1,
  };

  reasonForm = {
    note: '',
  };

  requestForm = {
    title: '',
    fulfillmentMode: 'individual_only' as ClientRequestFulfillmentMode,
    siteName: '',
    siteStreet: '',
    siteCity: '',
    siteProvince: '',
    sitePostalCode: '',
    siteCountry: 'CA',
    siteManagerContact: '',
    managerEmail: '',
    googleMapsUrl: '',
    latitude: '',
    longitude: '',
    requestedGuardType: '',
    guardsRequired: 1,
    requestedStartAt: '',
    requestedEndAt: '',
    requestExpiresAt: '',
    specialInstructions: '',
  };

  fulfillmentModeOptions = [
    { label: 'Individual Guards', value: 'individual_only' },
    { label: 'Service Providers', value: 'service_provider_only' },
    { label: 'Hybrid Coverage', value: 'hybrid' },
  ];

  requestStatusOptions = [
    { label: 'All Statuses', value: '' },
    { label: 'Draft', value: 'draft' },
    { label: 'Submitted', value: 'submitted' },
    { label: 'Assigned', value: 'assigned' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Cancelled', value: 'cancelled' },
    { label: 'Closed', value: 'closed' },
  ];

  jobStatusOptions = [
    { label: 'All Jobs', value: '' },
    { label: 'Offered', value: 'offered' },
    { label: 'Accepted', value: 'accepted' },
    { label: 'Reconfirmation Required', value: 'reconfirmation_required' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Completed', value: 'completed' },
    { label: 'Declined', value: 'declined' },
    { label: 'Expired', value: 'expired' },
    { label: 'Closed Filled', value: 'closed_filled' },
    { label: 'Cancelled', value: 'cancelled' },
  ];

  reviewStatusOptions = [
    { label: 'All Review States', value: '' },
    { label: 'Pending Review', value: 'pending_review' },
    { label: 'Active', value: 'active' },
    { label: 'Returned', value: 'returned' },
    { label: 'Filled', value: 'filled' },
    { label: 'Expired', value: 'expired' },
    { label: 'Superseded', value: 'superseded' },
    { label: 'Cancelled', value: 'cancelled' },
  ];

  reviewTriggerOptions = [
    { label: 'All Triggers', value: '' },
    { label: 'Initial Publish', value: 'initial_publish' },
    { label: 'Publish Update', value: 'publish_update' },
    { label: 'Additional Coverage', value: 'additional_coverage' },
    { label: 'Capacity Reopened', value: 'capacity_reopened' },
  ];

  fulfillmentModeFilterOptions = [
    { label: 'All Modes', value: '' },
    ...this.fulfillmentModeOptions,
  ];

  guardTypeOptions: { label: string; value: string }[] = [];

  constructor(
    private api: ApiService,
    private requestService: RequestService,
    private notification: MessageNotificationService,
    private appService: AppService,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  formatBackendDateTime = formatBackendDateTime;

  isScopeLoading(scope: string): boolean {
    return this.loadingFeedback.isScopeLoading(scope);
  }

  getRequestStatusScope(requestId: string): string {
    return `requests:status:${requestId}`;
  }

  getAssignScope(requestId: string): string {
    return `requests:assign:${requestId}`;
  }

  getJobUpdateScope(jobId: string): string {
    return `requests:job:${jobId}`;
  }

  get isPlatformAdmin(): boolean {
    return ['admin', 'ops_admin', 'support_admin', 'compliance_admin'].includes(this.role);
  }

  get canReviewBroadcastWaves(): boolean {
    return ['admin', 'ops_admin'].includes(this.role);
  }

  get isClientAdmin(): boolean {
    return this.role === 'client_admin' && this.tenantType === 'client';
  }

  get isGuardOrProvider(): boolean {
    return (this.role === 'guard_admin' && this.tenantType === 'guard') || (this.role === 'sp_admin' && this.tenantType === 'service_provider');
  }

  get canAssignRequests(): boolean {
    return this.isPlatformAdmin || this.isClientAdmin;
  }

  ngOnInit(): void {
    const session = this.appService.userSessionData();
    this.role = normalizeRole(session?.user?.role);
    this.tenantType = String(session?.tenant?.tenant_type || '').trim().toLowerCase();

    this.activeTab = this.isGuardOrProvider ? 'jobs' : 'requests';

    this.loadMetadata();

    this.loadRequests(1);
    this.loadJobs(1);
    if (this.canReviewBroadcastWaves) {
      this.loadReviewWaves(1);
    }
    this.routeQuerySubscription = this.route.queryParams.subscribe((params) => {
      this.handleRouteFocusParams(params || {});
    });
    this.startAutoRefresh();
  }

  ngOnDestroy(): void {
    this.autoRefreshSubscription?.unsubscribe();
    this.autoRefreshSubscription = null;
    this.routeQuerySubscription?.unsubscribe();
    this.routeQuerySubscription = null;
  }

  startAutoRefresh(): void {
    this.autoRefreshSubscription?.unsubscribe();
    this.autoRefreshSubscription = interval(30000).subscribe(() => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      this.refreshVisibleDataSilently();
    });
  }

  refreshVisibleDataSilently(): void {
    if (this.activeTab === 'requests') {
      this.loadRequests(this.page, { silent: true, suppressError: true });
      if (this.showRequestDrawer && this.selectedRequest?.id) {
        this.openRequestById(this.selectedRequest.id, { silent: true, suppressError: true });
      } else if (this.selectedRequest?.id) {
        this.loadRequestWaves(this.selectedRequest.id, { silent: true, suppressError: true });
      }
      return;
    }

    if (this.activeTab === 'jobs') {
      this.loadJobs(this.jobPage, { silent: true, suppressError: true });
      if (this.showJobDrawer && this.selectedJob?.id) {
        this.openJobById(this.selectedJob.id, { silent: true, suppressError: true });
      } else if (this.selectedJob) {
        this.loadJobDetails(this.selectedJob, { silent: true, suppressError: true });
      }
      return;
    }

    if (this.activeTab === 'review' && this.canReviewBroadcastWaves) {
      this.loadReviewWaves(this.reviewPage, { silent: true, suppressError: true });
      if (this.showWaveDrawer && this.selectedWave?.id) {
        this.openWaveById(this.selectedWave.id, { silent: true, suppressError: true });
      }
    }
  }

  handleRouteFocusParams(params: Record<string, any>): void {
    const tab = String(params['tab'] || '').trim().toLowerCase();
    if (tab === 'jobs' || tab === 'requests' || (tab === 'review' && this.canReviewBroadcastWaves)) {
      this.activeTab = tab as 'requests' | 'jobs' | 'review';
    }

    const requestId = String(params['request'] || '').trim();
    const jobId = String(params['job'] || '').trim();
    const waveId = String(params['wave'] || '').trim();
    const focusKey = `${tab}|${requestId}|${jobId}|${waveId}`;

    if (!requestId && !jobId && !waveId) {
      this.lastHandledRouteFocus = '';
      return;
    }

    if (focusKey === this.lastHandledRouteFocus) {
      return;
    }
    this.lastHandledRouteFocus = focusKey;

    if (jobId) {
      this.openJobById(jobId);
      return;
    }
    if (waveId) {
      this.openWaveById(waveId);
      return;
    }
    if (requestId) {
      this.openRequestById(requestId);
    }
  }

  clearRouteFocusParams(keys: Array<'request' | 'job' | 'wave'>): void {
    const queryParams: Record<string, null> = {};
    for (const key of keys) {
      queryParams[key] = null;
    }
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge',
      replaceUrl: true,
    }).then();
  }

  loadMetadata(): void {
    this.api.get<any>('public/client-metadata', { loadingScope: this.metadataScope }).subscribe({
      next: (response) => {
        this.guardTypeOptions = Array.isArray(response?.guardTypeOptions) ? response.guardTypeOptions : [];
      }
    });
  }

  loadRequests(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.loading = true;
    this.requestService.listRequests(page, this.rows, this.keyword, this.requestStatusFilter, this.fulfillmentModeFilter, {
      loadingScope: this.requestListScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.items = response.items || [];
        this.page = response.pagination?.page || page;
        this.totalPages = response.pagination?.total_pages || 1;
        this.totalItems = response.pagination?.total_items || 0;
        if (this.selectedRequest?.id) {
          const refreshed = this.items.find((item) => item.id === this.selectedRequest?.id);
          if (refreshed) {
            this.selectedRequest = refreshed;
          }
        }
        this.loading = false;
      },
      error: (error) => {
        this.loading = false;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load requests', 'fail', 5000);
        }
      }
    });
  }

  loadJobs(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.jobsLoading = true;
    this.requestService.listJobs(page, this.jobRows, this.jobStatusFilter, this.jobKeyword, {
      loadingScope: this.jobListScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.jobs = response.items || [];
        this.jobPage = response.pagination?.page || page;
        this.jobTotalPages = response.pagination?.total_pages || 1;
        this.jobTotalItems = response.pagination?.total_items || 0;
        if (this.selectedJob?.id) {
          const refreshed = this.jobs.find((item) => item.id === this.selectedJob?.id);
          if (refreshed) {
            this.selectedJob = refreshed;
          }
        }
        this.jobsLoading = false;
      },
      error: (error) => {
        this.jobsLoading = false;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load jobs', 'fail', 5000);
        }
      }
    });
  }

  loadReviewWaves(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    if (!this.canReviewBroadcastWaves) {
      return;
    }

    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.reviewLoading = true;
    this.requestService.listRequestReviewWaves(
      page,
      this.reviewRows,
      this.reviewStatusFilter,
      this.reviewTriggerFilter,
      '',
      '',
      {
        loadingScope: this.reviewListScope,
        loadingMode: silent ? 'silent' : undefined,
      },
    ).subscribe({
      next: (response) => {
        this.reviewWaves = response.items || [];
        this.reviewPage = response.pagination?.page || page;
        this.reviewTotalPages = response.pagination?.total_pages || 1;
        this.reviewTotalItems = response.pagination?.total_items || 0;
        if (this.selectedWave?.id) {
          const refreshed = this.reviewWaves.find((item) => item.id === this.selectedWave?.id);
          if (refreshed) {
            this.selectedWave = refreshed;
          }
        }
        this.reviewLoading = false;
      },
      error: (error) => {
        this.reviewLoading = false;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load request review queue', 'fail', 5000);
        }
      }
    });
  }

  loadRequestWaves(requestId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestWavesLoading = true;
    this.requestService.listRequestWaves(requestId, 1, 20, {
      loadingScope: this.requestWavesScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedRequestWaves = response.items || [];
        this.requestWavesLoading = false;
      },
      error: (error) => {
        this.selectedRequestWaves = [];
        this.requestWavesLoading = false;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load request waves', 'fail', 5000);
        }
      }
    });
  }

  validateRequestForm(requirePublishFields = false): boolean {
    this.requestErrors = {};

    this.applyGoogleMapsCoordinates();

    if (!this.requestForm.title.trim()) {
      this.requestErrors['title'] = 'Request title is required.';
    }
    if (!this.requestForm.siteName.trim()) {
      this.requestErrors['siteName'] = 'Site name is required.';
    }
    if (!this.requestForm.siteCity.trim()) {
      this.requestErrors['siteCity'] = 'City is required.';
    }
    if (!this.requestForm.siteProvince.trim()) {
      this.requestErrors['siteProvince'] = 'Province/state is required.';
    }
    if (!this.requestForm.guardsRequired || this.requestForm.guardsRequired < 1) {
      this.requestErrors['guardsRequired'] = 'Guard count must be at least 1.';
    }
    if (this.requestForm.managerEmail.trim() && !this.isValidEmail(this.requestForm.managerEmail)) {
      this.requestErrors['managerEmail'] = 'Manager email is invalid.';
    }

    const latitude = this.parseCoordinate(this.requestForm.latitude);
    const longitude = this.parseCoordinate(this.requestForm.longitude);
    const hasLatitude = this.requestForm.latitude.trim() !== '';
    const hasLongitude = this.requestForm.longitude.trim() !== '';

    if (hasLatitude !== hasLongitude) {
      this.requestErrors['coordinates'] = 'Provide both latitude and longitude or leave both empty.';
    }
    if (hasLatitude && latitude === null) {
      this.requestErrors['latitude'] = 'Latitude must be a valid number.';
    }
    if (hasLongitude && longitude === null) {
      this.requestErrors['longitude'] = 'Longitude must be a valid number.';
    }
    if (latitude !== null && (latitude < -90 || latitude > 90)) {
      this.requestErrors['latitude'] = 'Latitude must be between -90 and 90.';
    }
    if (longitude !== null && (longitude < -180 || longitude > 180)) {
      this.requestErrors['longitude'] = 'Longitude must be between -180 and 180.';
    }

    if (this.requestForm.requestedEndAt && this.requestForm.requestedStartAt) {
      const start = new Date(this.requestForm.requestedStartAt);
      const end = new Date(this.requestForm.requestedEndAt);
      if (end <= start) {
        this.requestErrors['requestedEndAt'] = 'End time must be after start time.';
      }
    }

    if (requirePublishFields) {
      if (!this.requestForm.requestExpiresAt) {
        this.requestErrors['requestExpiresAt'] = 'Request expiry is required before publishing.';
      } else {
        const expiry = new Date(this.requestForm.requestExpiresAt);
        if (Number.isNaN(expiry.getTime()) || expiry <= new Date()) {
          this.requestErrors['requestExpiresAt'] = 'Request expiry must be in the future.';
        } else if (this.requestForm.requestedStartAt) {
          const requestedStartAt = new Date(this.requestForm.requestedStartAt);
          if (expiry > requestedStartAt) {
            this.requestErrors['requestExpiresAt'] = 'Request expiry cannot be after the requested start date.';
          }
        }
      }
    }

    return Object.keys(this.requestErrors).length === 0;
  }

  submitRequest(commit: boolean): void {
    if (!(this.isClientAdmin || this.isPlatformAdmin)) {
      return;
    }
    if (!this.validateRequestForm(commit)) {
      this.notification.show('Please fix the highlighted request fields.', 'fail', 4000);
      return;
    }

    this.saving = true;
    const payload = this.buildRequestPayload();

    if (this.requestFormMode === 'create') {
      this.requestService.createRequest({ ...payload, commit }, { loadingScope: this.saveRequestScope }).subscribe({
        next: (response) => {
          this.saving = false;
          this.notification.show(response.message || (commit ? 'Request created' : 'Request draft saved'), 'success', 4000);
          this.closeRequestFormDrawer();
          this.loadRequests(1);
        },
        error: (error) => {
          this.saving = false;
          this.notification.show(error?.error?.detail || 'Failed to create request', 'fail', 5000);
        }
      });
      return;
    }

    if (!this.editingRequestId) {
      this.saving = false;
      this.notification.show('No request selected for edit.', 'fail', 4000);
      return;
    }

    if (this.requestFormMode === 'publish_update') {
      this.requestService.publishRequestUpdate(
        this.editingRequestId,
        this.buildPublishUpdatePayload(),
        { loadingScope: this.saveRequestScope },
      ).subscribe({
        next: (response) => {
          this.saving = false;
          this.notification.show(response.message || 'Request update published', 'success', 3500);
          this.closeRequestFormDrawer();
          this.loadRequests(this.page);
          if (this.canReviewBroadcastWaves) {
            this.loadReviewWaves(this.reviewPage);
          }
        },
        error: (error) => {
          this.saving = false;
          this.notification.show(error?.error?.detail || 'Failed to publish request update', 'fail', 5000);
        }
      });
      return;
    }

    this.requestService.updateRequest(this.editingRequestId, payload, { loadingScope: this.saveRequestScope }).subscribe({
      next: () => {
        if (!commit) {
          this.saving = false;
          this.notification.show('Request draft updated', 'success', 3500);
          this.closeRequestFormDrawer();
          this.loadRequests(this.page);
          return;
        }

        this.requestService.publishRequest(this.editingRequestId, { max_match_results: 25 }, { loadingScope: this.saveRequestScope }).subscribe({
          next: (response) => {
            this.saving = false;
            this.notification.show(response.message || 'Request published', 'success', 3500);
            this.closeRequestFormDrawer();
            this.loadRequests(this.page);
          },
          error: (error) => {
            this.saving = false;
            this.notification.show(error?.error?.detail || 'Draft updated but failed to publish request', 'fail', 5000);
            this.loadRequests(this.page);
          }
        });
      },
      error: (error) => {
        this.saving = false;
        this.notification.show(error?.error?.detail || 'Failed to update request draft', 'fail', 5000);
      }
    });
  }

  resetForm(): void {
    this.requestForm = {
      title: '',
      fulfillmentMode: 'individual_only',
      siteName: '',
      siteStreet: '',
      siteCity: '',
      siteProvince: '',
      sitePostalCode: '',
      siteCountry: 'CA',
      siteManagerContact: '',
      managerEmail: '',
      googleMapsUrl: '',
      latitude: '',
      longitude: '',
      requestedGuardType: '',
      guardsRequired: 1,
      requestedStartAt: '',
      requestedEndAt: '',
      requestExpiresAt: '',
      specialInstructions: '',
    };
    this.requestErrors = {};
  }

  openCreateRequestDrawer(): void {
    this.requestFormMode = 'create';
    this.editingRequestId = '';
    this.resetForm();
    this.showRequestFormDrawer = true;
  }

  openEditRequestDrawer(item: ClientRequestItem): void {
    if (!this.canEditRequest(item)) {
      this.notification.show('Only draft requests are editable.', 'fail', 3500);
      return;
    }

    this.requestFormMode = 'edit';
    this.editingRequestId = item.id;
    this.populateFormFromRequest(item);
    this.showRequestFormDrawer = true;
  }

  openPublishUpdateDrawer(item: ClientRequestItem): void {
    if (!this.canPublishUpdate(item)) {
      this.notification.show('This request cannot be updated from the current state.', 'fail', 3500);
      return;
    }

    if (this.selectedRequest?.id === item.id) {
      this.closeRequestDrawer();
    }
    this.requestFormMode = 'publish_update';
    this.editingRequestId = item.id;
    this.populateFormFromRequest(item);
    this.showRequestFormDrawer = true;
  }

  closeRequestFormDrawer(): void {
    this.showRequestFormDrawer = false;
    this.editingRequestId = '';
    this.requestFormMode = 'create';
    this.resetForm();
  }

  fillDummyData(): void {
    const samples = [
      {
        title: 'Overnight Warehouse Security – Toronto',
        siteName: 'Maple Leaf Logistics Centre',
        siteStreet: '120 Interchange Way',
        siteCity: 'Toronto',
        siteProvince: 'Ontario',
        sitePostalCode: 'M9W 6G9',
        siteCountry: 'CA',
        latitude: '43.7315',
        longitude: '-79.5700',
        siteManagerContact: '+1 416-555-0192',
        managerEmail: 'ops@mapleloglistics.ca',
        requestedGuardType: 'armed',
        guardsRequired: 3,
        specialInstructions: 'Guards must be licensed under Ontario Security Guard Act. Night shift from 22:00–06:00. Check-in every 2 hours via radio.',
      },
      {
        title: 'Construction Site Patrol – Calgary',
        siteName: 'Bow River Towers – Phase 2',
        siteStreet: '4500 Bow Trail SW',
        siteCity: 'Calgary',
        siteProvince: 'Alberta',
        sitePostalCode: 'T3C 3K3',
        siteCountry: 'CA',
        latitude: '51.0423',
        longitude: '-114.1341',
        siteManagerContact: '+1 403-555-0147',
        managerEmail: 'site.manager@bowrivertowers.ca',
        requestedGuardType: 'unarmed',
        guardsRequired: 2,
        specialInstructions: 'Patrol perimeter every 90 minutes. No public access after 20:00. Incident log required.',
      },
      {
        title: 'Retail Event Security – Vancouver',
        siteName: 'Pacific Centre Mall – West Wing',
        siteStreet: '701 W Georgia St',
        siteCity: 'Vancouver',
        siteProvince: 'British Columbia',
        sitePostalCode: 'V7Y 1G5',
        siteCountry: 'CA',
        latitude: '49.2827',
        longitude: '-123.1207',
        siteManagerContact: '+1 604-555-0211',
        managerEmail: 'events@pacificcentre.ca',
        requestedGuardType: 'unarmed',
        guardsRequired: 4,
        specialInstructions: 'Flash sale event. High foot traffic expected. Guards to manage crowd at entrance and cashier area.',
      },
      {
        title: 'Corporate Campus Patrol – Ottawa',
        siteName: 'Parliament Hill Campus Annex',
        siteStreet: '180 Wellington St',
        siteCity: 'Ottawa',
        siteProvince: 'Ontario',
        sitePostalCode: 'K1A 0A9',
        siteCountry: 'CA',
        latitude: '45.4253',
        longitude: '-75.7009',
        siteManagerContact: '+1 613-555-0099',
        managerEmail: 'facilities@gov-annex.ca',
        requestedGuardType: 'tactical',
        guardsRequired: 5,
        specialInstructions: 'High-profile government facility. Security clearance preferred. Strict access control at all three entry points.',
      },
      {
        title: 'Hospital Entrance Security – Montreal',
        siteName: 'Montréal General Hospital',
        siteStreet: '1650 Cedar Ave',
        siteCity: 'Montreal',
        siteProvince: 'Quebec',
        sitePostalCode: 'H3G 1A4',
        siteCountry: 'CA',
        latitude: '45.4974',
        longitude: '-73.5872',
        siteManagerContact: '+1 514-555-0312',
        managerEmail: 'security@mgh-montreal.ca',
        requestedGuardType: 'unarmed',
        guardsRequired: 2,
        specialInstructions: 'De-escalation training required. Bilingual (EN/FR) preferred. Must follow hospital visitor policy.',
      },
    ];

    const picked = samples[Math.floor(Math.random() * samples.length)];

    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() + 7);
    const endDate = new Date(startDate);
    endDate.setDate(startDate.getDate() + 30);

    const toDateInput = (d: Date) => d.toISOString().slice(0, 10);

    this.requestForm = {
      ...this.requestForm,
      title: picked.title,
      fulfillmentMode: 'individual_only',
      siteName: picked.siteName,
      siteStreet: picked.siteStreet,
      siteCity: picked.siteCity,
      siteProvince: picked.siteProvince,
      sitePostalCode: picked.sitePostalCode,
      siteCountry: picked.siteCountry,
      latitude: picked.latitude,
      longitude: picked.longitude,
      googleMapsUrl: '',
      siteManagerContact: picked.siteManagerContact,
      managerEmail: picked.managerEmail,
        requestedGuardType: picked.requestedGuardType,
        guardsRequired: picked.guardsRequired,
        requestedStartAt: toDateInput(startDate),
        requestedEndAt: toDateInput(endDate),
        requestExpiresAt: toDateInput(startDate),
        specialInstructions: picked.specialInstructions,
      };
    this.requestErrors = {};
  }

  populateFormFromRequest(item: ClientRequestItem): void {
    const address = item.site_snapshot?.site_address || {};
    this.requestForm = {
      title: item.title || '',
      fulfillmentMode: (item.fulfillment_mode || this.targetTypeToFulfillmentMode(item.target_type || 'guard')) as ClientRequestFulfillmentMode,
      siteName: item.site_snapshot?.site_name || '',
      siteStreet: String(address['street'] || ''),
      siteCity: String(address['city'] || ''),
      siteProvince: String(address['province'] || ''),
      sitePostalCode: String(address['postal_code'] || ''),
      siteCountry: String(address['country'] || 'CA'),
      siteManagerContact: item.site_snapshot?.site_manager_contact || '',
      managerEmail: item.site_snapshot?.manager_email || '',
      googleMapsUrl: item.site_snapshot?.google_maps_url || '',
      latitude: address['latitude'] != null ? String(address['latitude']) : '',
      longitude: address['longitude'] != null ? String(address['longitude']) : '',
      requestedGuardType: item.requested_guard_type || '',
      guardsRequired: Number(item.guards_required || 1),
      requestedStartAt: item.requested_start_at ? String(item.requested_start_at).slice(0, 10) : '',
      requestedEndAt: item.requested_end_at ? String(item.requested_end_at).slice(0, 10) : '',
      requestExpiresAt: item.request_expires_at ? String(item.request_expires_at).slice(0, 10) : '',
      specialInstructions: item.special_instructions || '',
    };
    this.requestErrors = {};
  }

  buildRequestPayload() {
    const latitude = this.parseCoordinate(this.requestForm.latitude);
    const longitude = this.parseCoordinate(this.requestForm.longitude);

    return {
      title: this.requestForm.title.trim(),
      fulfillment_mode: this.requestForm.fulfillmentMode,
      site: {
        site_name: this.requestForm.siteName.trim(),
        site_manager_contact: this.requestForm.siteManagerContact.trim() || null,
        manager_email: this.requestForm.managerEmail.trim() || null,
        google_maps_url: this.requestForm.googleMapsUrl.trim() || null,
        site_address: {
          street: this.requestForm.siteStreet.trim() || null,
          city: this.requestForm.siteCity.trim(),
          country: this.requestForm.siteCountry.trim() || 'CA',
          province: this.requestForm.siteProvince.trim(),
          postal_code: this.requestForm.sitePostalCode.trim() || null,
          latitude,
          longitude,
        },
      },
      requested_guard_type: this.requestForm.requestedGuardType || null,
      guards_required: Number(this.requestForm.guardsRequired || 1),
      requested_start_at: this.requestForm.requestedStartAt || null,
      requested_end_at: this.requestForm.requestedEndAt || null,
      request_expires_at: this.requestForm.requestExpiresAt || null,
      special_instructions: this.requestForm.specialInstructions.trim() || null,
      max_match_results: 25,
    };
  }

  buildPublishUpdatePayload() {
    const payload = this.buildRequestPayload();
    return {
      fulfillment_mode: payload.fulfillment_mode,
      site: payload.site,
      requested_guard_type: payload.requested_guard_type,
      requested_start_at: payload.requested_start_at,
      requested_end_at: payload.requested_end_at,
      request_expires_at: payload.request_expires_at,
      special_instructions: payload.special_instructions,
      max_match_results: payload.max_match_results,
    };
  }

  commitDraft(item: ClientRequestItem): void {
    if (!this.canCommitRequest(item)) {
      return;
    }
    if (!item.request_expires_at) {
      this.notification.show('Set a request expiry in the draft before publishing.', 'fail', 4000);
      return;
    }

    this.requestService.publishRequest(item.id, { max_match_results: 25 }, { loadingScope: this.getRequestStatusScope(item.id) }).subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Request published', 'success', 3500);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to publish request', 'fail', 5000);
      }
    });
  }

  openRequestDetails(item: ClientRequestItem): void {
    this.selectedRequest = item;
    this.selectedRequestWaves = [];
    this.showRequestDrawer = true;
    this.loadRequestWaves(item.id);
  }

  openRequestById(requestId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getRequest(requestId, {
      loadingScope: this.requestWavesScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        if (this.selectedWave) {
          this.closeWaveDrawer();
        }
        if (this.selectedJob) {
          this.closeJobDrawer();
        }
        this.selectedRequest = response;
        this.selectedRequestWaves = [];
        this.showRequestDrawer = true;
        this.loadRequestWaves(requestId, options);
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open request details', 'fail', 5000);
        }
      }
    });
  }

  closeRequestDrawer(): void {
    this.showRequestDrawer = false;
    this.selectedRequest = null;
    this.selectedRequestWaves = [];
    this.clearRouteFocusParams(['request']);
  }

  openWaveDetails(wave: RequestBroadcastWaveItem): void {
    if (this.selectedRequest) {
      this.closeRequestDrawer();
    }
    this.selectedWave = wave;
    this.showWaveDrawer = true;
  }

  openWaveById(waveId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getRequestWave(waveId, {
      loadingScope: this.reviewListScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        if (this.selectedRequest) {
          this.closeRequestDrawer();
        }
        if (this.selectedJob) {
          this.closeJobDrawer();
        }
        this.selectedWave = response;
        this.showWaveDrawer = true;
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open request wave', 'fail', 5000);
        }
      }
    });
  }

  closeWaveDrawer(): void {
    this.showWaveDrawer = false;
    this.selectedWave = null;
    this.clearRouteFocusParams(['wave']);
  }

  openJobDetails(job: RequestAssignmentItem): void {
    this.selectedJob = job;
    this.selectedJobRequest = null;
    this.selectedJobWaves = [];
    this.showJobDrawer = true;
    this.loadJobDetails(job);
  }

  openJobById(jobId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getJob(jobId, {
      loadingScope: this.jobListScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        if (this.selectedRequest) {
          this.closeRequestDrawer();
        }
        if (this.selectedWave) {
          this.closeWaveDrawer();
        }
        this.selectedJob = response;
        this.selectedJobRequest = null;
        this.selectedJobWaves = [];
        this.showJobDrawer = true;
        this.loadJobDetails(response, options);
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open job details', 'fail', 5000);
        }
      }
    });
  }

  closeJobDrawer(): void {
    this.showJobDrawer = false;
    this.selectedJob = null;
    this.selectedJobRequest = null;
    this.selectedJobWaves = [];
    this.clearRouteFocusParams(['job']);
  }

  loadJobDetails(job: RequestAssignmentItem, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getRequest(job.request_id, {
      loadingScope: this.jobDetailRequestScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedJobRequest = response;
      },
      error: (error) => {
        this.selectedJobRequest = null;
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load request details', 'fail', 5000);
        }
      }
    });

    this.requestService.listRequestWaves(job.request_id, 1, 20, {
      loadingScope: this.jobDetailWavesScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedJobWaves = response.items || [];
      },
      error: (error) => {
        this.selectedJobWaves = [];
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load broadcast waves', 'fail', 5000);
        }
      }
    });
  }

  openCoverageDrawer(item: ClientRequestItem): void {
    if (!this.canRequestAdditionalCoverage(item)) {
      this.notification.show('Additional coverage is not available for this request state.', 'fail', 3500);
      return;
    }

    if (this.selectedRequest?.id === item.id) {
      this.closeRequestDrawer();
    }
    this.selectedCoverageRequest = item;
    this.coverageErrors = {};
    this.coverageForm = {
      additionalSlots: 1,
      requestExpiresAt: item.request_expires_at ? String(item.request_expires_at).slice(0, 10) : '',
    };
    this.showCoverageDrawer = true;
  }

  closeCoverageDrawer(): void {
    this.showCoverageDrawer = false;
    this.selectedCoverageRequest = null;
    this.coverageErrors = {};
    this.coverageForm = {
      additionalSlots: 1,
      requestExpiresAt: '',
    };
  }

  openReturnWaveDrawer(wave: RequestBroadcastWaveItem): void {
    this.returnWaveTarget = wave;
    this.returnWaveErrors = {};
    this.returnWaveForm = { note: '' };
    if (this.selectedWave?.id === wave.id) {
      this.closeWaveDrawer();
    }
    this.showReturnWaveDrawer = true;
  }

  closeReturnWaveDrawer(): void {
    this.showReturnWaveDrawer = false;
    this.returnWaveTarget = null;
    this.returnWaveErrors = {};
    this.returnWaveForm = { note: '' };
  }

  openAcceptJobDrawer(job: RequestAssignmentItem): void {
    if (this.selectedJob?.id === job.id) {
      this.closeJobDrawer();
    }
    this.selectedAcceptJob = job;
    this.acceptJobErrors = {};
    this.acceptJobForm = {
      slotsCommitted: Number(job.slots_committed || 1),
    };
    this.showAcceptJobDrawer = true;
  }

  closeAcceptJobDrawer(): void {
    this.showAcceptJobDrawer = false;
    this.selectedAcceptJob = null;
    this.acceptJobErrors = {};
    this.acceptJobForm = {
      slotsCommitted: 1,
    };
  }

  openRequestReasonDrawer(item: ClientRequestItem, status: ClientRequestStatus): void {
    if (this.selectedRequest?.id === item.id) {
      this.closeRequestDrawer();
    }
    this.reasonRequestTarget = item;
    this.reasonJobTarget = null;
    this.reasonRequestStatus = status;
    this.reasonJobStatus = null;
    this.reasonErrors = {};
    this.reasonForm = { note: '' };
    this.showReasonDrawer = true;
  }

  openJobReasonDrawer(job: RequestAssignmentItem, status: RequestAssignmentStatus): void {
    if (this.selectedJob?.id === job.id) {
      this.closeJobDrawer();
    }
    this.reasonRequestTarget = null;
    this.reasonJobTarget = job;
    this.reasonRequestStatus = null;
    this.reasonJobStatus = status;
    this.reasonErrors = {};
    this.reasonForm = { note: '' };
    this.showReasonDrawer = true;
  }

  closeReasonDrawer(): void {
    this.showReasonDrawer = false;
    this.reasonRequestTarget = null;
    this.reasonJobTarget = null;
    this.reasonRequestStatus = null;
    this.reasonJobStatus = null;
    this.reasonErrors = {};
    this.reasonForm = { note: '' };
  }

  applyFilters(): void {
    this.loadRequests(1);
  }

  clearFilters(): void {
    this.keyword = '';
    this.requestStatusFilter = '';
    this.fulfillmentModeFilter = '';
    this.loadRequests(1);
  }

  applyJobFilters(): void {
    this.loadJobs(1);
  }

  clearJobFilters(): void {
    this.jobKeyword = '';
    this.jobStatusFilter = '';
    this.loadJobs(1);
  }

  applyReviewFilters(): void {
    this.loadReviewWaves(1);
  }

  clearReviewFilters(): void {
    this.reviewStatusFilter = 'pending_review';
    this.reviewTriggerFilter = '';
    this.loadReviewWaves(1);
  }

  updateStatus(item: ClientRequestItem, status: ClientRequestStatus): void {
    if (this.isPlatformAdmin) {
      this.openRequestReasonDrawer(item, status);
      return;
    }

    this.requestService.updateRequestStatus(item.id, status, undefined, { loadingScope: this.getRequestStatusScope(item.id) }).subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Request updated', 'success', 3500);
        this.loadRequests(this.page);
        if (this.selectedRequest?.id === item.id) {
          this.selectedRequest = { ...this.selectedRequest, request_status: status };
        }
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to update request', 'fail', 5000);
      }
    });
  }

  requestAdditionalCoverage(item: ClientRequestItem): void {
    this.openCoverageDrawer(item);
  }

  submitAdditionalCoverage(): void {
    const item = this.selectedCoverageRequest;
    if (!item) {
      return;
    }

    this.coverageErrors = {};
    const additionalSlots = Number(this.coverageForm.additionalSlots);
    if (!Number.isInteger(additionalSlots) || additionalSlots < 1) {
      this.coverageErrors['additionalSlots'] = 'Provide a valid whole number of additional slots.';
    }

    if (this.coverageForm.requestExpiresAt) {
      const expiry = new Date(this.coverageForm.requestExpiresAt);
      if (Number.isNaN(expiry.getTime()) || expiry <= new Date()) {
        this.coverageErrors['requestExpiresAt'] = 'Request expiry must be in the future.';
      } else if (item.requested_start_at) {
        const requestedStartAt = new Date(item.requested_start_at);
        if (expiry > requestedStartAt) {
          this.coverageErrors['requestExpiresAt'] = 'Request expiry cannot be after the requested start date.';
        }
      }
    }

    if (Object.keys(this.coverageErrors).length) {
      this.notification.show('Please fix the additional coverage fields.', 'fail', 4000);
      return;
    }

    const payload: { additional_slots: number; max_match_results: number; request_expires_at?: string } = {
      additional_slots: additionalSlots,
      max_match_results: 25,
    };
    if (this.coverageForm.requestExpiresAt.trim()) {
      payload.request_expires_at = this.coverageForm.requestExpiresAt.trim();
    }

    this.requestService.requestAdditionalCoverage(item.id, payload, { loadingScope: this.getRequestStatusScope(item.id) }).subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Additional coverage requested', 'success', 3500);
        this.closeCoverageDrawer();
        this.loadRequests(this.page);
        if (this.canReviewBroadcastWaves) {
          this.loadReviewWaves(this.reviewPage);
        }
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to request additional coverage', 'fail', 5000);
      }
    });
  }

  approveWave(wave: RequestBroadcastWaveItem): void {
    this.reviewingWaveId = wave.id;
    this.requestService.approveRequestWave(wave.id, { note: null }, { loadingScope: this.getReviewActionScope(wave.id) }).subscribe({
      next: (response) => {
        this.reviewingWaveId = '';
        this.notification.show(response.message || 'Broadcast approved', 'success', 3500);
        if (this.selectedWave?.id === wave.id) {
          this.closeWaveDrawer();
        }
        this.loadReviewWaves(this.reviewPage);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.reviewingWaveId = '';
        this.notification.show(error?.error?.detail || 'Failed to approve broadcast wave', 'fail', 5000);
      }
    });
  }

  returnWave(wave: RequestBroadcastWaveItem): void {
    this.openReturnWaveDrawer(wave);
  }

  submitReturnWave(): void {
    const wave = this.returnWaveTarget;
    if (!wave) {
      return;
    }

    const note = this.returnWaveForm.note.trim();
    this.returnWaveErrors = {};
    if (!note) {
      this.returnWaveErrors['note'] = 'A return note is required.';
      this.notification.show('A return note is required.', 'fail', 4000);
      return;
    }

    this.reviewingWaveId = wave.id;
    this.requestService.returnRequestWave(wave.id, { note }, { loadingScope: this.getReviewActionScope(wave.id) }).subscribe({
      next: (response) => {
        this.reviewingWaveId = '';
        this.notification.show(response.message || 'Broadcast returned to client', 'success', 3500);
        this.closeReturnWaveDrawer();
        this.loadReviewWaves(this.reviewPage);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.reviewingWaveId = '';
        this.notification.show(error?.error?.detail || 'Failed to return broadcast wave', 'fail', 5000);
      }
    });
  }

  assignSelectedCandidate(item: ClientRequestItem): void {
    const candidateId = this.selectedCandidateByRequestId[item.id];
    if (!candidateId) {
      this.notification.show('Select an eligible candidate first.', 'fail', 4000);
      return;
    }

    this.assigningRequestId = item.id;
    this.requestService.assignRequest(item.id, candidateId, undefined, { loadingScope: this.getAssignScope(item.id) }).subscribe({
      next: (response) => {
        this.assigningRequestId = '';
        this.notification.show(response.message || 'Request assigned', 'success', 3500);
        this.loadJobs(1);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.assigningRequestId = '';
        this.notification.show(error?.error?.detail || 'Failed to assign request', 'fail', 5000);
      }
    });
  }

  updateJobStatus(job: RequestAssignmentItem, status: RequestAssignmentStatus): void {
    const requiresReason = status === 'declined' || status === 'cancelled';
    if (requiresReason) {
      this.openJobReasonDrawer(job, status);
      return;
    }

    if (status === 'accepted' && job.assignee_tenant_type === 'service_provider') {
      this.openAcceptJobDrawer(job);
      return;
    }

    this.updatingJobId = job.id;
    this.requestService.updateJobStatus(job.id, status, undefined, { loadingScope: this.getJobUpdateScope(job.id) }, null).subscribe({
      next: (response) => {
        this.updatingJobId = '';
        this.notification.show(response.message || 'Job updated', 'success', 3500);
        if (this.selectedJob?.id === job.id) {
          this.closeJobDrawer();
        }
        this.loadJobs(this.jobPage);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.updatingJobId = '';
        this.notification.show(error?.error?.detail || 'Failed to update job', 'fail', 5000);
      }
    });
  }

  submitReasonAction(): void {
    const note = this.reasonForm.note.trim();
    this.reasonErrors = {};

    if (!note) {
      this.reasonErrors['note'] = 'A reason is required.';
      this.notification.show('A reason is required.', 'fail', 4000);
      return;
    }

    if (this.reasonRequestTarget && this.reasonRequestStatus) {
      const item = this.reasonRequestTarget;
      const status = this.reasonRequestStatus;
      this.requestService.updateRequestStatus(item.id, status, note, { loadingScope: this.getRequestStatusScope(item.id) }).subscribe({
        next: (response) => {
          this.notification.show(response.message || 'Request updated', 'success', 3500);
          this.closeReasonDrawer();
          this.loadRequests(this.page);
          if (this.selectedRequest?.id === item.id) {
            this.selectedRequest = { ...this.selectedRequest, request_status: status };
          }
        },
        error: (error) => {
          this.notification.show(error?.error?.detail || 'Failed to update request', 'fail', 5000);
        }
      });
      return;
    }

    if (this.reasonJobTarget && this.reasonJobStatus) {
      const job = this.reasonJobTarget;
      const status = this.reasonJobStatus;
      this.updatingJobId = job.id;
      this.requestService.updateJobStatus(job.id, status, note, { loadingScope: this.getJobUpdateScope(job.id) }, null).subscribe({
        next: (response) => {
          this.updatingJobId = '';
          this.notification.show(response.message || 'Job updated', 'success', 3500);
          if (this.selectedJob?.id === job.id) {
            this.closeJobDrawer();
          }
          this.closeReasonDrawer();
          this.loadJobs(this.jobPage);
          this.loadRequests(this.page);
        },
        error: (error) => {
          this.updatingJobId = '';
          this.notification.show(error?.error?.detail || 'Failed to update job', 'fail', 5000);
        }
      });
    }
  }

  submitAcceptJob(): void {
    const job = this.selectedAcceptJob;
    if (!job) {
      return;
    }

    this.acceptJobErrors = {};
    const slotsCommitted = Number(this.acceptJobForm.slotsCommitted);
    if (!Number.isInteger(slotsCommitted) || slotsCommitted < 1) {
      this.acceptJobErrors['slotsCommitted'] = 'Provide a valid whole number of committed slots.';
      this.notification.show('Please fix the acceptance fields.', 'fail', 4000);
      return;
    }

    this.updatingJobId = job.id;
    this.requestService.updateJobStatus(job.id, 'accepted', undefined, { loadingScope: this.getJobUpdateScope(job.id) }, slotsCommitted).subscribe({
      next: (response) => {
        this.updatingJobId = '';
        this.notification.show(response.message || 'Job accepted', 'success', 3500);
        if (this.selectedJob?.id === job.id) {
          this.closeJobDrawer();
        }
        this.closeAcceptJobDrawer();
        this.loadJobs(this.jobPage);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.updatingJobId = '';
        this.notification.show(error?.error?.detail || 'Failed to accept job', 'fail', 5000);
      }
    });
  }

  canShowRequestStatusActions(item: ClientRequestItem): boolean {
    return (this.isClientAdmin || this.isPlatformAdmin) && ['submitted', 'assigned', 'in_progress'].includes(item.request_status);
  }

  canEditRequest(item: ClientRequestItem): boolean {
    return this.isClientAdmin && item.request_status === 'draft';
  }

  canCommitRequest(item: ClientRequestItem): boolean {
    return this.isClientAdmin && item.request_status === 'draft';
  }

  canShowAssignmentActions(item: ClientRequestItem): boolean {
    return this.canAssignRequests
      && ['submitted', 'assigned'].includes(item.request_status)
      && Number(item.open_slots ?? item.guards_required ?? 0) > 0
      && this.getEligibleCandidates(item).length > 0;
  }

  canPublishUpdate(item: ClientRequestItem): boolean {
    return (this.isClientAdmin || this.isPlatformAdmin)
      && ['submitted', 'assigned'].includes(item.request_status)
      && item.staffing_status !== 'expired';
  }

  canRequestAdditionalCoverage(item: ClientRequestItem): boolean {
    return (this.isClientAdmin || this.isPlatformAdmin)
      && ['submitted', 'assigned'].includes(item.request_status)
      && item.staffing_status !== 'expired';
  }

  canShowJobActions(job: RequestAssignmentItem): boolean {
    if (this.isPlatformAdmin) {
      return true;
    }
    return this.isGuardOrProvider && ['offered', 'accepted', 'reconfirmation_required', 'in_progress'].includes(job.assignment_status);
  }

  getJobActions(job: RequestAssignmentItem): Array<{ label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' }> {
    switch (job.assignment_status) {
      case 'offered':
        return [
          { label: 'Accept', status: 'accepted', type: 'primary' },
          { label: 'Decline', status: 'declined', type: 'danger' },
        ];
      case 'accepted':
        return [
          { label: 'Start', status: 'in_progress', type: 'primary' },
          { label: 'Cancel', status: 'cancelled', type: 'danger' },
        ];
      case 'reconfirmation_required':
        return [
          { label: 'Reconfirm', status: 'accepted', type: 'primary' },
          { label: 'Decline', status: 'declined', type: 'danger' },
        ];
      case 'in_progress':
        return [
          { label: 'Complete', status: 'completed', type: 'primary' },
          { label: 'Cancel', status: 'cancelled', type: 'danger' },
        ];
      default:
        return [];
    }
  }

  getEligibleCandidates(item: ClientRequestItem): Array<Record<string, any>> {
    const candidates = Array.isArray(item.matched_candidates) ? item.matched_candidates : [];
    return candidates.filter((candidate) => Boolean(candidate?.['eligible']));
  }

  getEligibleCandidateOptions(item: ClientRequestItem): Array<{ label: string; value: string }> {
    return this.getEligibleCandidates(item).map((candidate) => ({
      label: `${candidate['candidate_name'] || candidate['candidate_id']} • ${this.getTargetTypeLabel(String(candidate['target_type'] || 'guard'))} (${Math.round(Number(candidate['distance_km'] || 0) * 10) / 10} km)`,
      value: String(candidate['candidate_id'] || ''),
    })).filter((candidate) => candidate.value);
  }

  trackByRequestId(_index: number, item: ClientRequestItem): string {
    return item.id;
  }

  trackByJobId(_index: number, item: RequestAssignmentItem): string {
    return item.id;
  }

  getStatusClasses(status: string): string {
    switch ((status || '').toLowerCase()) {
      case 'draft':
        return 'bg-slate-100 text-slate-700 dark:bg-slate-900/40 dark:text-slate-300';
      case 'closed':
      case 'completed':
        return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300';
      case 'cancelled':
      case 'declined':
        return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
      case 'in_progress':
      case 'accepted':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300';
      default:
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    }
  }

  getTargetTypeLabel(targetType: string): string {
    return targetType === 'service_provider' ? 'Service Provider' : 'Guard';
  }

  getRequestFormHeading(): string {
    if (this.requestFormMode === 'publish_update') {
      return 'Publish Request Update';
    }
    return this.requestFormMode === 'create' ? 'Add Request' : 'Edit Request Draft';
  }

  getRequestFormSubtitle(): string {
    if (this.requestFormMode === 'publish_update') {
      return 'Update the live request details and issue a fresh broadcast wave.';
    }
    return 'Capture site details, staffing needs, and publish when ready.';
  }

  getFulfillmentModeHelperText(): string {
    switch (this.requestForm.fulfillmentMode) {
      case 'hybrid':
        return 'Hybrid broadcasts the request to both matching individual guards and service providers in the same staffing flow.';
      case 'service_provider_only':
        return 'Only matching service providers will receive this request.';
      default:
        return 'Only matching individual guards will receive this request.';
    }
  }

  getRequestFormPrimaryActionLabel(): string {
    return this.requestFormMode === 'publish_update' ? 'Publish Update' : 'Publish Request';
  }

  getReviewActionScope(waveId: string): string {
    return `requests:review:${waveId}`;
  }

  getWaveTitle(item: RequestBroadcastWaveItem): string {
    return String(item.request_snapshot?.['title'] || 'Request');
  }

  getWaveSiteName(item: RequestBroadcastWaveItem): string {
    return String(item.request_snapshot?.['site_name'] || 'Unknown site');
  }

  getWaveReasonCodes(item: RequestBroadcastWaveItem): string[] {
    return Array.isArray(item.review_reason_codes) ? item.review_reason_codes : [];
  }

  getWaveCandidateSnapshots(item: RequestBroadcastWaveItem): Array<Record<string, any>> {
    return Array.isArray(item.candidate_snapshots) ? item.candidate_snapshots : [];
  }

  getWaveReviewFindings(item: RequestBroadcastWaveItem): Array<Record<string, any>> {
    return Array.isArray(item.review_findings) ? item.review_findings : [];
  }

  getWaveBroadcastCandidateCount(item: RequestBroadcastWaveItem, outcome: 'auto_broadcast' | 'pending_review' | 'outside_policy'): number {
    return this.getWaveCandidateSnapshots(item).filter((candidate) => candidate?.['broadcast_outcome'] === outcome).length;
  }

  getWaveCandidateName(candidate: Record<string, any>): string {
    return String(candidate?.['candidate_name'] || candidate?.['candidate_id'] || 'Candidate');
  }

  getWaveFindingLabel(finding: Record<string, any>): string {
    const candidateId = String(finding?.['candidate_id'] || '').trim();
    const prefix = candidateId ? `Candidate ${candidateId}` : 'Request';
    return `${prefix}: ${this.formatTokenLabel(String(finding?.['reason_code'] || 'review_required'))}`;
  }

  getWaveReviewSummary(item: RequestBroadcastWaveItem): string {
    const codes = this.getWaveReasonCodes(item);
    if (!codes.length) {
      return 'Auto-broadcasted without review blockers.';
    }
    return codes.map((code) => this.formatTokenLabel(code)).join(', ');
  }

  getAcceptJobDrawerTitle(): string {
    if (!this.selectedAcceptJob) {
      return 'Accept Job Offer';
    }
    return this.selectedAcceptJob.assignment_status === 'reconfirmation_required' ? 'Reconfirm Coverage' : 'Accept Job Offer';
  }

  getAcceptJobDrawerSubtitle(): string {
    const requestTitle = this.selectedAcceptJob?.request?.title || 'Request';
    return `${requestTitle} • Service provider coverage response`;
  }

  getSelectedJobWave(): RequestBroadcastWaveItem | null {
    if (!this.selectedJob?.broadcast_wave_id) {
      return null;
    }
    return this.selectedJobWaves.find((wave) => wave.id === this.selectedJob?.broadcast_wave_id) || null;
  }

  openSelectedJobWaveDetails(): void {
    const wave = this.getSelectedJobWave();
    if (!wave) {
      return;
    }
    this.closeJobDrawer();
    this.openWaveDetails(wave);
  }

  getJobStateMessage(job: RequestAssignmentItem): string {
    switch (job.assignment_status) {
      case 'reconfirmation_required':
        return 'This request changed after your earlier acceptance. Review the updated request details and reconfirm only if you can still cover the assignment.';
      case 'closed_filled':
        return 'All required slots have already been filled. This offer remains visible for history but no longer accepts responses.';
      case 'expired':
        return 'This offer expired before a response was received.';
      case 'superseded':
        return 'This offer was replaced by a newer broadcast wave after the request changed.';
      case 'cancelled':
        return 'This assignment was cancelled and is no longer actionable.';
      case 'accepted':
        return 'You have already accepted this assignment. Review the request details below before starting work.';
      case 'offered':
        return job.response_due_at
          ? `Review the full request before responding. This offer closes at ${this.formatBackendDateTime(job.response_due_at)}.`
          : 'Review the full request before responding to this offer.';
      default:
        return '';
    }
  }

  getJobStateMessageClasses(job: RequestAssignmentItem): string {
    switch (job.assignment_status) {
      case 'reconfirmation_required':
        return 'rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200';
      case 'closed_filled':
      case 'expired':
      case 'superseded':
      case 'cancelled':
        return 'rounded-md border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-800/60 dark:text-gray-200';
      default:
        return 'rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-900/40 dark:bg-blue-950/20 dark:text-blue-200';
    }
  }

  getReasonDrawerTitle(): string {
    if (this.reasonRequestTarget && this.reasonRequestStatus) {
      return `${this.formatTokenLabel(this.reasonRequestStatus)} Request`;
    }
    if (this.reasonJobTarget && this.reasonJobStatus) {
      return `${this.formatTokenLabel(this.reasonJobStatus)} Job`;
    }
    return 'Provide Reason';
  }

  getReasonDrawerSubtitle(): string {
    if (this.reasonRequestTarget) {
      return `${this.reasonRequestTarget.title} • Reason is required for this request action`;
    }
    if (this.reasonJobTarget) {
      return `${this.reasonJobTarget.request?.title || 'Request'} • Reason is required for this assignment action`;
    }
    return 'Add the required note to continue.';
  }

  getReasonDrawerActionLabel(): string {
    if (this.reasonRequestStatus) {
      return `Confirm ${this.formatTokenLabel(this.reasonRequestStatus)}`;
    }
    if (this.reasonJobStatus) {
      return `Confirm ${this.formatTokenLabel(this.reasonJobStatus)}`;
    }
    return 'Submit';
  }

  formatTokenLabel(value: string): string {
    return String(value || '')
      .split('_')
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  getFulfillmentModeLabel(fulfillmentMode: string): string {
    switch (fulfillmentMode) {
      case 'service_provider_only':
        return 'Service Providers';
      case 'hybrid':
        return 'Hybrid Coverage';
      default:
        return 'Individual Guards';
    }
  }

  private targetTypeToFulfillmentMode(targetType: string): ClientRequestFulfillmentMode {
    return targetType === 'service_provider' ? 'service_provider_only' : 'individual_only';
  }

  getTopCandidateNames(item: ClientRequestItem): string[] {
    const candidates = this.getEligibleCandidates(item);
    return candidates
      .slice(0, 3)
      .map((candidate) => String(candidate['candidate_name'] || candidate['candidate_id'] || 'Candidate'));
  }

  getSiteAddressField(item: ClientRequestItem, key: string): string {
    return String(item.site_snapshot?.site_address?.[key] || '');
  }

  getMatchCount(item: ClientRequestItem, key: 'eligible_count' | 'missing_geo_count' | 'outside_radius_count'): number {
    return Number(item.match_summary?.[key] || 0);
  }

  parseCoordinate(value: string): number | null {
    const trimmed = String(value || '').trim();
    if (!trimmed) {
      return null;
    }

    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  applyGoogleMapsCoordinates(): void {
    const coordinates = this.extractCoordinatesFromMapsUrl(this.requestForm.googleMapsUrl);
    if (!coordinates) {
      return;
    }

    const [latitude, longitude] = coordinates;
    if (!this.requestForm.latitude.trim()) {
      this.requestForm.latitude = String(latitude);
    }
    if (!this.requestForm.longitude.trim()) {
      this.requestForm.longitude = String(longitude);
    }
  }

  extractCoordinatesFromMapsUrl(value: string): [number, number] | null {
    const url = String(value || '').trim();
    if (!url) {
      return null;
    }

    const patterns = [
      /@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
      /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,
      /[?&](?:q|ll)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,
    ];

    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (!match) {
        continue;
      }

      const latitude = Number(match[1]);
      const longitude = Number(match[2]);
      if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
        return [latitude, longitude];
      }
    }

    return null;
  }

  isValidEmail(value: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
  }

  getPageLabel(pageNumber: number): string {
    return String(pageNumber);
  }

  get paginationPages(): number[] {
    if (this.totalPages <= 1) {
      return [];
    }
    const start = Math.max(1, this.page - 2);
    const end = Math.min(this.totalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }

  get jobPaginationPages(): number[] {
    if (this.jobTotalPages <= 1) {
      return [];
    }
    const start = Math.max(1, this.jobPage - 2);
    const end = Math.min(this.jobTotalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }

  get reviewPaginationPages(): number[] {
    if (this.reviewTotalPages <= 1) {
      return [];
    }
    const start = Math.max(1, this.reviewPage - 2);
    const end = Math.min(this.reviewTotalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }

  trackByWaveId(_index: number, item: RequestBroadcastWaveItem): string {
    return item.id;
  }
}
