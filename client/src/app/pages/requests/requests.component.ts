import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

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
  ClientRequestItem,
  ClientRequestStatus,
  ClientRequestTargetType,
  RequestAssignmentItem,
  RequestAssignmentStatus,
} from '../../shared/model/request/client-request.model';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { AppService } from '../../services/core/app/app.service';
import { normalizeRole } from '../../shared/helpers/access-control.helper';

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
export class RequestsComponent implements OnInit {
  loading = false;
  saving = false;
  jobsLoading = false;

  role = '';
  tenantType = '';

  activeTab: 'requests' | 'jobs' = 'requests';

  items: ClientRequestItem[] = [];
  jobs: RequestAssignmentItem[] = [];

  page = 1;
  rows = 10;
  totalPages = 1;
  totalItems = 0;

  jobPage = 1;
  jobRows = 10;
  jobTotalPages = 1;
  jobTotalItems = 0;

  keyword = '';
  requestStatusFilter = '';
  targetTypeFilter = '';

  jobKeyword = '';
  jobStatusFilter = '';

  requestErrors: Record<string, string> = {};

  selectedRequest: ClientRequestItem | null = null;
  showRequestDrawer = false;
  showRequestFormDrawer = false;
  requestFormMode: 'create' | 'edit' = 'create';
  editingRequestId = '';

  selectedCandidateByRequestId: Record<string, string> = {};
  assigningRequestId = '';
  updatingJobId = '';

  requestForm = {
    title: '',
    targetType: 'guard' as ClientRequestTargetType,
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
    specialInstructions: '',
  };

  targetTypeOptions = [
    { label: 'Guard', value: 'guard' },
    { label: 'Service Provider', value: 'service_provider' },
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
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Completed', value: 'completed' },
    { label: 'Declined', value: 'declined' },
    { label: 'Cancelled', value: 'cancelled' },
  ];

  targetTypeFilterOptions = [
    { label: 'All Targets', value: '' },
    ...this.targetTypeOptions,
  ];

  guardTypeOptions: { label: string; value: string }[] = [];

  constructor(
    private api: ApiService,
    private requestService: RequestService,
    private notification: MessageNotificationService,
    private appService: AppService,
  ) {}

  formatBackendDateTime = formatBackendDateTime;

  get isPlatformAdmin(): boolean {
    return ['admin', 'ops_admin', 'support_admin', 'compliance_admin'].includes(this.role);
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
  }

  loadMetadata(): void {
    this.api.get<any>('public/client-metadata').subscribe({
      next: (response) => {
        this.guardTypeOptions = Array.isArray(response?.guardTypeOptions) ? response.guardTypeOptions : [];
      }
    });
  }

  loadRequests(page: number): void {
    this.loading = true;
    this.requestService.listRequests(page, this.rows, this.keyword, this.requestStatusFilter, this.targetTypeFilter).subscribe({
      next: (response) => {
        this.items = response.items || [];
        this.page = response.pagination?.page || page;
        this.totalPages = response.pagination?.total_pages || 1;
        this.totalItems = response.pagination?.total_items || 0;
        this.loading = false;
      },
      error: (error) => {
        this.loading = false;
        this.notification.show(error?.error?.detail || 'Failed to load requests', 'fail', 5000);
      }
    });
  }

  loadJobs(page: number): void {
    this.jobsLoading = true;
    this.requestService.listJobs(page, this.jobRows, this.jobStatusFilter, this.jobKeyword).subscribe({
      next: (response) => {
        this.jobs = response.items || [];
        this.jobPage = response.pagination?.page || page;
        this.jobTotalPages = response.pagination?.total_pages || 1;
        this.jobTotalItems = response.pagination?.total_items || 0;
        this.jobsLoading = false;
      },
      error: (error) => {
        this.jobsLoading = false;
        this.notification.show(error?.error?.detail || 'Failed to load jobs', 'fail', 5000);
      }
    });
  }

  validateRequestForm(): boolean {
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

    return Object.keys(this.requestErrors).length === 0;
  }

  submitRequest(commit: boolean): void {
    if (!this.isClientAdmin) {
      return;
    }
    if (!this.validateRequestForm()) {
      this.notification.show('Please fix the highlighted request fields.', 'fail', 4000);
      return;
    }

    this.saving = true;
    const payload = this.buildRequestPayload();

    if (this.requestFormMode === 'create') {
      this.requestService.createRequest({ ...payload, commit }).subscribe({
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

    this.requestService.updateRequest(this.editingRequestId, payload).subscribe({
      next: () => {
        if (!commit) {
          this.saving = false;
          this.notification.show('Request draft updated', 'success', 3500);
          this.closeRequestFormDrawer();
          this.loadRequests(this.page);
          return;
        }

        this.requestService.updateRequestStatus(this.editingRequestId, 'submitted').subscribe({
          next: (response) => {
            this.saving = false;
            this.notification.show(response.message || 'Request submitted', 'success', 3500);
            this.closeRequestFormDrawer();
            this.loadRequests(this.page);
          },
          error: (error) => {
            this.saving = false;
            this.notification.show(error?.error?.detail || 'Draft updated but failed to submit request', 'fail', 5000);
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
      targetType: 'guard',
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
      targetType: 'guard',
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
      specialInstructions: picked.specialInstructions,
    };
    this.requestErrors = {};
  }

  populateFormFromRequest(item: ClientRequestItem): void {
    const address = item.site_snapshot?.site_address || {};
    this.requestForm = {
      title: item.title || '',
      targetType: (item.target_type || 'guard') as ClientRequestTargetType,
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
      specialInstructions: item.special_instructions || '',
    };
    this.requestErrors = {};
  }

  buildRequestPayload() {
    const latitude = this.parseCoordinate(this.requestForm.latitude);
    const longitude = this.parseCoordinate(this.requestForm.longitude);

    return {
      title: this.requestForm.title.trim(),
      target_type: this.requestForm.targetType,
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
      special_instructions: this.requestForm.specialInstructions.trim() || null,
      max_match_results: 25,
    };
  }

  commitDraft(item: ClientRequestItem): void {
    if (!this.canCommitRequest(item)) {
      return;
    }

    this.requestService.updateRequestStatus(item.id, 'submitted').subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Request submitted', 'success', 3500);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to submit request', 'fail', 5000);
      }
    });
  }

  openRequestDetails(item: ClientRequestItem): void {
    this.selectedRequest = item;
    this.showRequestDrawer = true;
  }

  closeRequestDrawer(): void {
    this.showRequestDrawer = false;
    this.selectedRequest = null;
  }

  applyFilters(): void {
    this.loadRequests(1);
  }

  clearFilters(): void {
    this.keyword = '';
    this.requestStatusFilter = '';
    this.targetTypeFilter = '';
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

  updateStatus(item: ClientRequestItem, status: ClientRequestStatus): void {
    const reason = this.isPlatformAdmin
      ? (window.prompt('Reason for override is required:') || '').trim()
      : undefined;

    if (this.isPlatformAdmin && !reason) {
      this.notification.show('Reason is required for platform admin override.', 'fail', 4000);
      return;
    }

    this.requestService.updateRequestStatus(item.id, status, reason).subscribe({
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

  assignSelectedCandidate(item: ClientRequestItem): void {
    const candidateId = this.selectedCandidateByRequestId[item.id];
    if (!candidateId) {
      this.notification.show('Select an eligible candidate first.', 'fail', 4000);
      return;
    }

    this.assigningRequestId = item.id;
    this.requestService.assignRequest(item.id, candidateId).subscribe({
      next: (response) => {
        this.assigningRequestId = '';
        this.notification.show(response.message || 'Request assigned', 'success', 3500);
        this.loadJobs(1);
      },
      error: (error) => {
        this.assigningRequestId = '';
        this.notification.show(error?.error?.detail || 'Failed to assign request', 'fail', 5000);
      }
    });
  }

  updateJobStatus(job: RequestAssignmentItem, status: RequestAssignmentStatus): void {
    const requiresReason = status === 'declined' || status === 'cancelled';
    const reason = requiresReason ? (window.prompt('Reason is required:') || '').trim() : undefined;
    if (requiresReason && !reason) {
      this.notification.show('Reason is required.', 'fail', 4000);
      return;
    }

    this.updatingJobId = job.id;
    this.requestService.updateJobStatus(job.id, status, reason).subscribe({
      next: (response) => {
        this.updatingJobId = '';
        this.notification.show(response.message || 'Job updated', 'success', 3500);
        this.loadJobs(this.jobPage);
        this.loadRequests(this.page);
      },
      error: (error) => {
        this.updatingJobId = '';
        this.notification.show(error?.error?.detail || 'Failed to update job', 'fail', 5000);
      }
    });
  }

  canShowRequestStatusActions(item: ClientRequestItem): boolean {
    return (this.isClientAdmin || this.isPlatformAdmin) && item.request_status === 'submitted';
  }

  canEditRequest(item: ClientRequestItem): boolean {
    return this.isClientAdmin && item.request_status === 'draft';
  }

  canCommitRequest(item: ClientRequestItem): boolean {
    return this.isClientAdmin && item.request_status === 'draft';
  }

  canShowAssignmentActions(item: ClientRequestItem): boolean {
    return this.canAssignRequests && item.request_status === 'submitted' && this.getEligibleCandidates(item).length > 0;
  }

  canShowJobActions(job: RequestAssignmentItem): boolean {
    if (this.isPlatformAdmin) {
      return true;
    }
    return this.isGuardOrProvider && ['offered', 'accepted', 'in_progress'].includes(job.assignment_status);
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
      label: `${candidate['candidate_name'] || candidate['candidate_id']} (${Math.round(Number(candidate['distance_km'] || 0) * 10) / 10} km)`,
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
}
