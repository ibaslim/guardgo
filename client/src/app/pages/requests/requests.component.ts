import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription, forkJoin, interval } from 'rxjs';

import { ButtonComponent } from '../../components/button/button.component';
import { CardComponent } from '../../components/card/card.component';
import { DrawerActionRowComponent } from '../../components/drawer-action-row/drawer-action-row.component';
import { DrawerTitleBlockComponent } from '../../components/drawer-title-block/drawer-title-block.component';
import { EventTimelineComponent } from '../../components/event-timeline/event-timeline.component';
import { FilterActionBarComponent } from '../../components/filter-action-bar/filter-action-bar.component';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { SelectInputComponent } from '../../components/form/select-input/select-input.component';
import { TextareaComponent } from '../../components/form/textarea/textarea.component';
import { GeoLocationPickerComponent } from '../../components/geo-location-picker/geo-location-picker.component';
import { ListStatePanelComponent } from '../../components/list-state-panel/list-state-panel.component';
import { ListToolbarComponent } from '../../components/list-toolbar/list-toolbar.component';
import { PageComponent } from '../../components/page/page.component';
import { PaginationFooterComponent } from '../../components/pagination-footer/pagination-footer.component';
import { RecordListItemComponent } from '../../components/record-list-item/record-list-item.component';
import { RequestListCardComponent } from '../../components/request-list-card/request-list-card.component';
import { SectionComponent } from '../../components/section/section.component';
import { ShiftSlotCardComponent } from '../../components/shift-slot-card/shift-slot-card.component';
import { SideDrawerComponent } from '../../components/side-drawer/side-drawer.component';
import { ShiftCalendarComponent } from '../../components/shift-calendar/shift-calendar.component';
import { SummaryMetricCardComponent } from '../../components/summary-metric-card/summary-metric-card.component';
import { ValidationMessageComponent } from '../../components/validation-message/validation-message.component';
import { BannerComponent } from '../../components/banner/banner.component';
import { ApiService } from '../../shared/services/api.service';
import { RequestService } from '../../shared/services/request.service';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';
import {
  ClientRequestFulfillmentMode,
  ClientRequestItem,
  ClientRequestStatus,
  ProviderRosterPayload,
  RequestAssignmentItem,
  RequestAssignmentStatus,
  RequestBroadcastWaveItem,
  RequestScheduleItem,
  RequestScheduleType,
  ServiceProviderGuardSummaryItem,
  ShiftExceptionItem,
  ShiftInstanceItem,
  ShiftSlotDetailResponse,
  ShiftSlotItem,
  ShiftSlotSummary,
} from '../../shared/model/request/client-request.model';
import { formatBackendDateTime } from '../../shared/helpers/format.helper';
import { AppService } from '../../services/core/app/app.service';
import { normalizeRole } from '../../shared/helpers/access-control.helper';
import { GoogleMapsAddressConsistencyService } from '../../shared/services/google-maps-address-consistency.service';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';

type RequestSiteSourceMode = 'manual' | 'saved';

interface SavedClientSiteRecord {
  index: number;
  siteId: string;
  siteName: string;
  siteManagerContact: string;
  managerEmail: string;
  numberOfGuardsRequired: number | null;
  siteType: string;
  googleMapsUrl: string;
  siteAddress: {
    street: string;
    city: string;
    country: string;
    province: string;
    postalCode: string;
    latitude: string;
    longitude: string;
  };
  hasCoordinates: boolean;
}

interface RequestClientTenantOption {
  value: string;
  label: string;
  siteCount: number;
}

@Component({
  selector: 'app-requests',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    PageComponent,
    RecordListItemComponent,
    RequestListCardComponent,
    SectionComponent,
    CardComponent,
    ButtonComponent,
    DrawerActionRowComponent,
    DrawerTitleBlockComponent,
    EventTimelineComponent,
    FilterActionBarComponent,
    BaseInputComponent,
    SelectInputComponent,
    TextareaComponent,
    GeoLocationPickerComponent,
    SideDrawerComponent,
    ListStatePanelComponent,
    ListToolbarComponent,
    PaginationFooterComponent,
    ShiftCalendarComponent,
    ShiftSlotCardComponent,
    SummaryMetricCardComponent,
    ValidationMessageComponent,
    BannerComponent,
  ],
  templateUrl: './requests.component.html',
})
export class RequestsComponent implements OnInit, OnDestroy {
  readonly requestListScope = 'requests:list';
  readonly jobListScope = 'requests:jobs';
  readonly metadataScope = 'requests:metadata';
  readonly saveRequestScope = 'requests:save';
  readonly reviewListScope = 'requests:review:list';
  readonly requestScheduleScope = 'requests:detail:schedule';
  readonly saveRequestScheduleScope = 'requests:detail:schedule:save';
  readonly shiftListScope = 'requests:shifts:list';
  readonly shiftCalendarScope = 'requests:shifts:calendar';
  readonly shiftDetailScope = 'requests:shifts:detail';
  readonly shiftSlotDetailScope = 'requests:shifts:slot:detail';
  readonly shiftProviderGuardsScope = 'requests:shifts:provider-guards';
  readonly shiftRosterPatternScope = 'requests:shifts:roster-pattern';
  readonly exceptionListScope = 'requests:exceptions:list';
  readonly exceptionDetailScope = 'requests:exceptions:detail';
  readonly requestWavesScope = 'requests:detail:waves';
  readonly jobDetailRequestScope = 'requests:job:detail';
  readonly jobDetailWavesScope = 'requests:job:waves';
  readonly metricCompactContainerClass =
    'rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-700 dark:bg-gray-800/70 dark:text-gray-200';
  readonly metricCompactValueClass = 'mt-1 font-semibold text-gray-900 dark:text-gray-100';
  readonly metricCountLabelClass = 'text-[11px] font-semibold text-gray-500 dark:text-gray-400';
  readonly metricCountValueClass = 'mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100';
  readonly requestSummaryMetricContainerClass =
    'rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm dark:border-gray-800 dark:bg-gray-900/80';
  readonly requestSummaryMetricValueClass = 'mt-1 text-base font-semibold text-gray-900 dark:text-gray-100';
  readonly drawerSectionContainerClass = 'rounded-md border border-gray-100 p-4 dark:border-gray-800';
  readonly drawerSectionHeaderClass = 'flex items-start justify-between gap-3';
  readonly drawerSectionTitleClass = 'text-sm font-semibold text-gray-900 dark:text-gray-100';
  readonly drawerSectionSubtitleClass = 'mt-1 text-xs text-gray-500 dark:text-gray-400';
  readonly listToolbarControlsThreeColumnClass =
    'grid grid-cols-1 gap-3 rounded-md bg-gray-50/70 p-3 sm:grid-cols-2 xl:grid-cols-3 xl:items-end dark:bg-gray-800/50';
  readonly listToolbarControlsFourColumnClass =
    'grid grid-cols-1 gap-3 rounded-md bg-gray-50/70 p-3 sm:grid-cols-2 xl:grid-cols-4 xl:items-end dark:bg-gray-800/50';
  readonly listToolbarControlsFiveColumnClass =
    'grid grid-cols-1 gap-3 rounded-md bg-gray-50/70 p-3 sm:grid-cols-2 xl:grid-cols-5 xl:items-end dark:bg-gray-800/50';
  readonly listToolbarFooterClass = 'mt-4 flex flex-wrap items-center justify-between gap-3';
  readonly requestToolbarSummaryFooterClass = 'mt-5 grid grid-cols-2 gap-3 xl:grid-cols-4';
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

  activeTab: 'requests' | 'jobs' | 'review' | 'exceptions' | 'shifts' = 'requests';
  shiftViewMode: 'calendar' | 'list' = 'calendar';

  items: ClientRequestItem[] = [];
  jobs: RequestAssignmentItem[] = [];
  reviewWaves: RequestBroadcastWaveItem[] = [];
  shifts: ShiftInstanceItem[] = [];
  shiftCalendarItems: ShiftInstanceItem[] = [];
  shiftExceptions: ShiftExceptionItem[] = [];
  selectedRequestWaves: RequestBroadcastWaveItem[] = [];
  shiftRequestSummaries: Record<string, { title: string; siteName: string }> = {};

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

  shiftPage = 1;
  shiftRows = 10;
  shiftTotalPages = 1;
  shiftTotalItems = 0;
  shiftCalendarMonthAnchor = this.getStartOfMonth(new Date());

  exceptionPage = 1;
  exceptionRows = 10;
  exceptionTotalPages = 1;
  exceptionTotalItems = 0;

  keyword = '';
  requestStatusFilter = '';
  fulfillmentModeFilter = '';
  requestClientTenantFilter = '';

  jobKeyword = '';
  jobStatusFilter = '';

  reviewStatusFilter = 'pending_review';
  reviewTriggerFilter = '';

  shiftStatusFilter = '';
  shiftDateFrom = '';
  shiftDateTo = '';

  exceptionStatusFilter = '';
  exceptionDateFrom = '';
  exceptionDateTo = '';

  requestErrors: Record<string, string> = {};

  selectedRequest: ClientRequestItem | null = null;
  selectedRequestSchedule: RequestScheduleItem | null = null;
  selectedWave: RequestBroadcastWaveItem | null = null;
  selectedJob: RequestAssignmentItem | null = null;
  selectedJobRequest: ClientRequestItem | null = null;
  selectedJobWaves: RequestBroadcastWaveItem[] = [];
  selectedShift: ShiftInstanceItem | null = null;
  selectedShiftSlots: ShiftSlotItem[] = [];
  selectedShiftSlotSummary: ShiftSlotSummary | null = null;
  selectedShiftSlot: ShiftSlotItem | null = null;
  selectedShiftSlotDetail: ShiftSlotDetailResponse | null = null;
  selectedException: ShiftExceptionItem | null = null;
  selectedExceptionDetail: ShiftSlotDetailResponse | null = null;
  selectedScheduleRequest: ClientRequestItem | null = null;
  selectedBulkConfirmShift: ShiftInstanceItem | null = null;
  bulkConfirmShiftSlots: ShiftSlotItem[] = [];
  showRequestDrawer = false;
  showRequestFormDrawer = false;
  showScheduleDrawer = false;
  showWaveDrawer = false;
  showJobDrawer = false;
  showShiftDrawer = false;
  showShiftSlotDrawer = false;
  showExceptionDrawer = false;
  showCoverageDrawer = false;
  showReturnWaveDrawer = false;
  showAcceptJobDrawer = false;
  showRosterDrawer = false;
  showReasonDrawer = false;
  showShiftActionDrawer = false;
  showReopenExceptionDrawer = false;
  showBulkConfirmDrawer = false;
  requestFormMode: 'create' | 'edit' | 'publish_update' = 'create';
  editingRequestId = '';
  requestScheduleSetupEnabled = false;

  selectedCandidateByRequestId: Record<string, string> = {};
  assigningRequestId = '';
  updatingJobId = '';
  reviewingWaveId = '';
  selectedCoverageRequest: ClientRequestItem | null = null;
  returnWaveTarget: RequestBroadcastWaveItem | null = null;
  selectedAcceptJob: RequestAssignmentItem | null = null;
  selectedRosterShift: ShiftInstanceItem | null = null;
  rosterShiftSlots: ShiftSlotItem[] = [];
  rosterPatternFutureShifts: ShiftInstanceItem[] = [];
  shiftActionTarget: ShiftSlotItem | null = null;
  shiftActionType: 'report_unavailable' | 'check_in' | 'client_confirm' | 'start' | 'check_out' | null = null;
  reopenExceptionTarget: ShiftExceptionItem | null = null;
  reasonRequestTarget: ClientRequestItem | null = null;
  reasonJobTarget: RequestAssignmentItem | null = null;
  reasonRequestStatus: ClientRequestStatus | null = null;
  reasonRequestSoftDelete = false;
  reasonJobStatus: RequestAssignmentStatus | null = null;
  coverageErrors: Record<string, string> = {};
  returnWaveErrors: Record<string, string> = {};
  acceptJobErrors: Record<string, string> = {};
  rosterErrors: Record<string, string> = {};
  reasonErrors: Record<string, string> = {};
  shiftActionErrors: Record<string, string> = {};
  reopenExceptionErrors: Record<string, string> = {};
  scheduleErrors: Record<string, string> = {};
  bulkConfirmErrors: Record<string, string> = {};
  shiftActionLocationError = '';
  shiftActionLocationMessage = '';
  capturingShiftActionLocation = false;

  providerGuards: ServiceProviderGuardSummaryItem[] = [];
  rosterSelections: Record<string, string> = {};
  bulkConfirmSelections: Record<string, boolean> = {};

  rosterPatternForm = {
    applyToFutureShifts: false,
  };

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

  shiftActionForm = {
    latitude: '',
    longitude: '',
    note: '',
  };

  scheduleForm = {
    timezone: 'UTC',
    scheduleType: 'one_time' as RequestScheduleType,
    startDate: '',
    endDate: '',
    startTimeLocal: '08:00',
    endTimeLocal: '17:00',
    recurrenceDays: [] as string[],
    generationHorizonDays: 30,
    rosterDueOffsetMinutes: 120,
    unavailableCutoffMinutes: 120,
    lateGraceMinutes: 15,
    noShowCutoffMinutes: 30,
    checkinGeofenceMeters: 200,
    active: true,
  };

  bulkConfirmForm = {
    note: '',
  };

  reasonForm = {
    note: '',
  };
  reopenExceptionForm = {
    note: '',
    maxMatchResults: 25,
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
    requestedStartDate: '',
    requestedStartTime: '',
    requestedEndDate: '',
    requestedEndTime: '',
    requestExpiresDate: '',
    requestExpiresTime: '',
    specialInstructions: '',
  };
  requestSiteSourceMode: RequestSiteSourceMode = 'manual';
  selectedSavedSiteIndex = '';
  clientSavedSites: SavedClientSiteRecord[] = [];
  savedClientSitesMissingGeoCount = 0;
  requestClientTenantOptions: RequestClientTenantOption[] = [];
  selectedRequestClientTenantId = '';
  selectedRequestClientTenantLabel = '';

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

  shiftStatusOptions = [
    { label: 'All Shift States', value: '' },
    { label: 'Scheduled', value: 'scheduled' },
    { label: 'Partially Staffed', value: 'partially_staffed' },
    { label: 'Staffed', value: 'staffed' },
    { label: 'In Progress', value: 'in_progress' },
    { label: 'Completed', value: 'completed' },
    { label: 'Cancelled', value: 'cancelled' },
    { label: 'Expired', value: 'expired' },
  ];

  scheduleTypeOptions = [
    { label: 'One-Time Shift', value: 'one_time' },
    { label: 'Date Range', value: 'date_range' },
    { label: 'Recurring Weekly', value: 'recurring_weekly' },
  ];

  scheduleWeekdayOptions = [
    { label: 'Mon', value: 'mon' },
    { label: 'Tue', value: 'tue' },
    { label: 'Wed', value: 'wed' },
    { label: 'Thu', value: 'thu' },
    { label: 'Fri', value: 'fri' },
    { label: 'Sat', value: 'sat' },
    { label: 'Sun', value: 'sun' },
  ];

  exceptionStatusOptions = [
    { label: 'All Exceptions', value: '' },
    { label: 'Unavailable', value: 'unavailable' },
    { label: 'Late Risk', value: 'late_risk' },
    { label: 'No-Show Suspected', value: 'no_show_suspected' },
    { label: 'No-Show Confirmed', value: 'no_show_confirmed' },
    { label: 'Replacement Required', value: 'replacement_required' },
  ];

  fulfillmentModeFilterOptions = [
    { label: 'All Modes', value: '' },
    ...this.fulfillmentModeOptions,
  ];

  countryOptions: { value: string; label: string }[] = [];
  provinceOptions: { value: string; label: string }[] = [];
  canadianCitiesByProvinceOptions: Record<string, { value: string; label: string }[]> = {};

  guardTypeOptions: { label: string; value: string }[] = [];

  constructor(
    private api: ApiService,
    private requestService: RequestService,
    private notification: MessageNotificationService,
    private appService: AppService,
    private addressConsistencyService: GoogleMapsAddressConsistencyService,
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

  get hasPlatformRequestScope(): boolean {
    return this.isPlatformAdmin || this.role === 'read_only_admin';
  }

  get requestListToolbarControlsClass(): string {
    return this.hasPlatformRequestScope ? this.listToolbarControlsFiveColumnClass : this.listToolbarControlsFourColumnClass;
  }

  get requestClientTenantFilterOptions(): Array<{ value: string; label: string }> {
    const options = [
      { value: '', label: 'All Client Tenants' },
      ...this.requestClientTenantOptions.map((option) => ({
        value: option.value,
        label: option.label,
      })),
    ];

    const currentFilter = String(this.requestClientTenantFilter || '').trim();
    if (currentFilter && !options.some((option) => option.value === currentFilter)) {
      options.push({ value: currentFilter, label: currentFilter });
    }

    return options;
  }

  getCountSummary(count: number, singularLabel: string, scopeLabel: string): string {
    return `${count} ${singularLabel}${count === 1 ? '' : 's'} ${scopeLabel}`;
  }

  get visibleDraftRequestCount(): number {
    return this.items.filter((item) => item.request_status === 'draft').length;
  }

  get visibleNeedsReviewRequestCount(): number {
    return this.items.filter((item) => ['pending_review', 'review_returned'].includes(String(item.staffing_status || ''))).length;
  }

  get visibleOpenCoverageRequestCount(): number {
    return this.items.filter((item) => ['open', 'partially_filled'].includes(String(item.staffing_status || ''))).length;
  }

  get visibleFilledRequestCount(): number {
    return this.items.filter((item) => item.staffing_status === 'filled').length;
  }

  get canReviewBroadcastWaves(): boolean {
    return ['admin', 'ops_admin'].includes(this.role);
  }

  get canViewShifts(): boolean {
    return [
      'admin',
      'ops_admin',
      'support_admin',
      'compliance_admin',
      'read_only_admin',
      'client_admin',
      'guard_admin',
      'sp_admin',
    ].includes(this.role);
  }

  get canViewShiftExceptions(): boolean {
    return ['admin', 'ops_admin', 'support_admin', 'compliance_admin', 'read_only_admin'].includes(this.role);
  }

  get canReopenShiftExceptions(): boolean {
    return ['admin', 'ops_admin', 'support_admin', 'compliance_admin'].includes(this.role);
  }

  get isClientAdmin(): boolean {
    return this.role === 'client_admin' && this.tenantType === 'client';
  }

  get isGuardOrProvider(): boolean {
    return (this.role === 'guard_admin' && this.tenantType === 'guard') || (this.role === 'sp_admin' && this.tenantType === 'service_provider');
  }

  get canManageProviderRoster(): boolean {
    return this.role === 'sp_admin' && this.tenantType === 'service_provider';
  }

  get canManageShiftAttendance(): boolean {
    return this.isPlatformAdmin || (this.role === 'guard_admin' && this.tenantType === 'guard');
  }

  get canConfirmShiftArrivals(): boolean {
    return this.isPlatformAdmin || this.isClientAdmin;
  }

  get canAssignRequests(): boolean {
    return this.isPlatformAdmin || this.isClientAdmin;
  }

  get canCreateRequests(): boolean {
    return this.isPlatformAdmin || this.isClientAdmin;
  }

  get requestTimingStartLabel(): string {
    return this.requestScheduleSetupEnabled ? 'First Shift Start' : 'Job Start';
  }

  get requestTimingEndLabel(): string {
    return this.requestScheduleSetupEnabled ? 'First Shift End' : 'Job End';
  }

  get requestTimingStartHelperText(): string {
    return this.requestScheduleSetupEnabled
      ? 'Use the exact local start time for the first shift in this longer-term coverage pattern.'
      : 'Same-day and short-duration jobs are supported. Use the exact local start time.';
  }

  get requestTimingEndHelperText(): string {
    return this.requestScheduleSetupEnabled
      ? 'Use the exact local end time for the first shift, even if later shifts repeat under the coverage pattern below.'
      : 'Use the exact local end time, even if the job ends on the same day.';
  }

  ngOnInit(): void {
    const session = this.appService.userSessionData();
    this.role = normalizeRole(session?.user?.role);
    this.tenantType = String(session?.tenant?.tenant_type || '').trim().toLowerCase();
    this.scheduleForm.timezone = this.getDefaultScheduleTimezone();

    this.activeTab = 'requests';

    this.loadMetadata();
    this.loadRequestClientTenants({ silent: true });
    this.loadClientSites({ silent: true });

    this.loadRequests(1);
    this.loadJobs(1);
    if (this.canReviewBroadcastWaves) {
      this.loadReviewWaves(1);
    }
    if (this.canViewShifts) {
      this.loadShifts(1);
      this.loadShiftCalendar(this.shiftCalendarMonthAnchor);
    }
    if (this.canViewShiftExceptions) {
      this.loadShiftExceptions(1);
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
      return;
    }

    if (this.activeTab === 'shifts' && this.canViewShifts) {
      this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
      this.loadShiftCalendar(this.shiftCalendarMonthAnchor, { silent: true, suppressError: true });
      if (this.showShiftDrawer && this.selectedShift?.id) {
        this.openShiftById(this.selectedShift.id, { silent: true, suppressError: true });
      }
      if (this.showShiftSlotDrawer && this.selectedShiftSlot?.id) {
        this.openShiftSlotById(this.selectedShiftSlot.id, { silent: true, suppressError: true });
      }
      return;
    }

    if (this.activeTab === 'exceptions' && this.canViewShiftExceptions) {
      this.loadShiftExceptions(this.exceptionPage, { silent: true, suppressError: true });
      if (this.showExceptionDrawer && this.selectedException?.slot?.id) {
        this.openExceptionBySlotId(this.selectedException.slot.id, { silent: true, suppressError: true });
      }
    }
  }

  handleRouteFocusParams(params: Record<string, any>): void {
    const tab = String(params['tab'] || '').trim().toLowerCase();
    if (
      tab === 'jobs'
      || tab === 'requests'
      || (tab === 'shifts' && this.canViewShifts)
      || (tab === 'review' && this.canReviewBroadcastWaves)
      || (tab === 'exceptions' && this.canViewShiftExceptions)
    ) {
      this.activeTab = tab as 'requests' | 'jobs' | 'review' | 'exceptions' | 'shifts';
    }

    const requestId = String(params['request'] || '').trim();
    const jobId = String(params['job'] || '').trim();
    const waveId = String(params['wave'] || '').trim();
    const shiftId = String(params['shift'] || '').trim();
    const slotId = String(params['slot'] || '').trim();
    const focusKey = `${tab}|${requestId}|${jobId}|${waveId}|${shiftId}|${slotId}`;

    if (!requestId && !jobId && !waveId && !shiftId && !slotId) {
      this.lastHandledRouteFocus = '';
      if (!tab) {
        this.activeTab = 'requests';
      }
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
    if (slotId && this.canViewShifts) {
      this.activeTab = 'shifts';
      this.openShiftSlotById(slotId);
      return;
    }
    if (shiftId && this.canViewShifts) {
      this.activeTab = 'shifts';
      this.openShiftById(shiftId);
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

  clearRouteFocusParams(keys: Array<'request' | 'job' | 'wave' | 'shift' | 'slot'>): void {
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
        this.countryOptions = Array.isArray(response?.countries) ? response.countries : [];
        this.provinceOptions = Array.isArray(response?.canadianProvinces) ? response.canadianProvinces : [];
        this.canadianCitiesByProvinceOptions = response?.canadianCitiesByProvince || {};
      }
    });
  }

  loadRequestClientTenants(options?: { silent?: boolean }): void {
    if (!this.hasPlatformRequestScope) {
      this.requestClientTenantOptions = [];
      return;
    }

    const params = new HttpParams().set('rows', '200');
    this.api.get<any>('request-client-tenants', {
      params,
      loadingMode: options?.silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        const items = Array.isArray(response?.items) ? response.items : [];
        this.requestClientTenantOptions = items.map((item: any) => ({
          value: String(item?.id || '').trim(),
          label: String(item?.label || item?.id || '').trim(),
          siteCount: Number(item?.site_count || 0),
        })).filter((item: RequestClientTenantOption) => item.value && item.label);

        if (this.requestFormMode === 'create' && this.isPlatformAdmin) {
          const selectedExists = this.requestClientTenantOptions.some((option) => option.value === this.selectedRequestClientTenantId);
          if (!selectedExists) {
            if (this.requestClientTenantOptions.length === 1) {
              this.onRequestClientTenantChange(this.requestClientTenantOptions[0].value);
            } else if (!this.selectedRequestClientTenantId) {
              this.selectedRequestClientTenantLabel = '';
              this.clientSavedSites = [];
              this.savedClientSitesMissingGeoCount = 0;
            }
          } else {
            this.selectedRequestClientTenantLabel = this.requestClientTenantOptions.find((option) => option.value === this.selectedRequestClientTenantId)?.label || this.selectedRequestClientTenantLabel;
          }
        }
      },
      error: () => {
        this.requestClientTenantOptions = [];
      },
    });
  }

  loadClientSites(options?: { silent?: boolean; tenantId?: string }): void {
    if (!this.isClientAdmin && !this.isPlatformAdmin) {
      this.clientSavedSites = [];
      this.savedClientSitesMissingGeoCount = 0;
      return;
    }

    const targetTenantId = String(options?.tenantId || this.selectedRequestClientTenantId || '').trim();
    if (this.isPlatformAdmin && !targetTenantId) {
      this.clientSavedSites = [];
      this.savedClientSitesMissingGeoCount = 0;
      return;
    }

    const endpoint = this.isPlatformAdmin ? `request-client-tenants/${targetTenantId}` : 'tenant';
    this.api.get<any>(endpoint, {
      loadingMode: options?.silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        if (this.isPlatformAdmin) {
          this.selectedRequestClientTenantLabel = String(response?.label || this.requestClientTenantOptions.find((option) => option.value === targetTenantId)?.label || targetTenantId).trim();
        }
        const profile = response?.profile || response || {};
        const rawSites = Array.isArray(profile?.sites) ? profile.sites : [];
        let missingGeoCount = 0;
        const reusableSites: SavedClientSiteRecord[] = rawSites.reduce((acc: SavedClientSiteRecord[], rawSite: any, index: number) => {
          const siteAddress = rawSite?.site_address || rawSite?.siteAddress || {};
          const latitudeText = siteAddress?.latitude != null ? String(siteAddress.latitude) : '';
          const longitudeText = siteAddress?.longitude != null ? String(siteAddress.longitude) : '';
          const hasCoordinates = this.parseCoordinate(latitudeText) !== null && this.parseCoordinate(longitudeText) !== null;
          if (!hasCoordinates) {
            missingGeoCount += 1;
            return acc;
          }

          acc.push({
            index,
            siteId: String(rawSite?.site_id || rawSite?.siteId || '').trim(),
            siteName: String(rawSite?.site_name || rawSite?.siteName || '').trim(),
            siteManagerContact: String(rawSite?.site_manager_contact || rawSite?.siteManagerContact || '').trim(),
            managerEmail: String(rawSite?.manager_email || rawSite?.managerEmail || '').trim(),
            numberOfGuardsRequired: rawSite?.number_of_guards_required ?? rawSite?.numberOfGuardsRequired ?? null,
            siteType: String(rawSite?.site_type || rawSite?.siteType || '').trim(),
            googleMapsUrl: String(rawSite?.google_maps_url || rawSite?.googleMapsUrl || '').trim(),
            siteAddress: {
              street: String(siteAddress?.street || '').trim(),
              city: String(siteAddress?.city || '').trim(),
              country: String(siteAddress?.country || 'CA').trim() || 'CA',
              province: String(siteAddress?.province || '').trim(),
              postalCode: String(siteAddress?.postal_code || siteAddress?.postalCode || '').trim(),
              latitude: latitudeText,
              longitude: longitudeText,
            },
            hasCoordinates,
          });
          return acc;
        }, []);

        this.clientSavedSites = reusableSites;
        this.savedClientSitesMissingGeoCount = missingGeoCount;

        if (this.requestFormMode === 'create' && this.requestSiteSourceMode === 'saved') {
          if (!this.selectedSavedSiteIndex && this.clientSavedSites.length) {
            this.selectedSavedSiteIndex = String(this.clientSavedSites[0].index);
          }
          const selectedSite = this.selectedSavedClientSite;
          if (selectedSite) {
            this.applySavedSiteToRequestForm(selectedSite);
          }
        }
      },
      error: () => {
        this.clientSavedSites = [];
        this.savedClientSitesMissingGeoCount = 0;
        if (this.isPlatformAdmin) {
          this.selectedRequestClientTenantLabel = this.requestClientTenantOptions.find((option) => option.value === targetTenantId)?.label || '';
        }
      }
    });
  }

  loadRequests(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.loading = true;
    this.requestService.listRequests(
      page,
      this.rows,
      this.keyword,
      this.requestStatusFilter,
      this.fulfillmentModeFilter,
      this.hasPlatformRequestScope ? this.requestClientTenantFilter : '',
      {
        loadingScope: this.requestListScope,
        loadingMode: silent ? 'silent' : undefined,
      },
    ).subscribe({
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

  loadShifts(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    if (!this.canViewShifts) {
      return;
    }

    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.listShifts(
      page,
      this.shiftRows,
      '',
      this.shiftStatusFilter,
      this.shiftDateFrom,
      this.shiftDateTo,
      {
        loadingScope: this.shiftListScope,
        loadingMode: silent ? 'silent' : undefined,
      },
    ).subscribe({
      next: (response) => {
        this.shifts = response.items || [];
        this.shiftPage = response.pagination?.page || page;
        this.shiftTotalPages = response.pagination?.total_pages || 1;
        this.shiftTotalItems = response.pagination?.total_items || 0;
        if (this.selectedShift?.id) {
          const refreshed = this.shifts.find((item) => item.id === this.selectedShift?.id);
          if (refreshed) {
            this.selectedShift = refreshed;
          }
        }
        this.ensureShiftRequestSummaries(this.shifts);
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load shifts', 'fail', 5000);
        }
      }
    });
  }

  loadShiftCalendar(monthAnchor?: Date, options?: { silent?: boolean; suppressError?: boolean }): void {
    if (!this.canViewShifts) {
      return;
    }

    const anchor = monthAnchor ? this.getStartOfMonth(monthAnchor) : this.shiftCalendarMonthAnchor;
    this.shiftCalendarMonthAnchor = anchor;
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    const monthStart = this.formatDateInput(anchor);
    const monthEnd = this.formatDateInput(this.getEndOfMonth(anchor));

    this.requestService.listShifts(
      1,
      500,
      '',
      this.shiftStatusFilter,
      monthStart,
      monthEnd,
      {
        loadingScope: this.shiftCalendarScope,
        loadingMode: silent ? 'silent' : undefined,
      },
    ).subscribe({
      next: (response) => {
        this.shiftCalendarItems = response.items || [];
        this.ensureShiftRequestSummaries(this.shiftCalendarItems);
      },
      error: (error) => {
        this.shiftCalendarItems = [];
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load shift calendar', 'fail', 5000);
        }
      }
    });
  }

  loadShiftExceptions(page: number, options?: { silent?: boolean; suppressError?: boolean }): void {
    if (!this.canViewShiftExceptions) {
      return;
    }

    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.listShiftExceptions(
      page,
      this.exceptionRows,
      this.exceptionStatusFilter,
      '',
      this.exceptionDateFrom,
      this.exceptionDateTo,
      {
        loadingScope: this.exceptionListScope,
        loadingMode: silent ? 'silent' : undefined,
      },
    ).subscribe({
      next: (response) => {
        this.shiftExceptions = response.items || [];
        this.exceptionPage = response.pagination?.page || page;
        this.exceptionTotalPages = response.pagination?.total_pages || 1;
        this.exceptionTotalItems = response.pagination?.total_items || 0;
        if (this.selectedException?.slot?.id) {
          const refreshed = this.shiftExceptions.find((item) => item.slot?.id === this.selectedException?.slot?.id);
          if (refreshed) {
            this.selectedException = refreshed;
          }
        }
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to load shift exception queue', 'fail', 5000);
        }
      }
    });
  }

  ensureShiftRequestSummaries(items: ShiftInstanceItem[]): void {
    const missingRequestIds = items
      .map((item) => String(item.request_id || '').trim())
      .filter((requestId) => requestId && !this.shiftRequestSummaries[requestId]);

    for (const requestId of missingRequestIds) {
      this.requestService.getRequest(requestId, { loadingMode: 'silent' }).subscribe({
        next: (response) => {
          this.shiftRequestSummaries[requestId] = {
            title: String(response.title || 'Client request'),
            siteName: String(response.site_snapshot?.site_name || 'Unknown site'),
          };
        },
        error: () => {
          this.shiftRequestSummaries[requestId] = {
            title: `Request ${requestId.slice(0, 8)}`,
            siteName: 'Unknown site',
          };
        }
      });
    }
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

  loadRequestSchedule(requestId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getRequestSchedule(requestId, {
      loadingScope: this.requestScheduleScope,
      loadingMode: silent ? 'silent' : undefined,
      suppressErrorStatuses: [404],
    }).subscribe({
      next: (response) => {
        this.selectedRequestSchedule = response.schedule || null;
      },
      error: (error) => {
        this.selectedRequestSchedule = null;
        const status = Number(error?.status || error?.statusCode || 0);
        if (!suppressError && status !== 404) {
          this.notification.show(error?.error?.detail || 'Failed to load request schedule', 'fail', 5000);
        }
      }
    });
  }

  getDefaultScheduleTimezone(): string {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  }

  resetScheduleForm(): void {
    this.scheduleForm = {
      timezone: this.getDefaultScheduleTimezone(),
      scheduleType: 'one_time',
      startDate: '',
      endDate: '',
      startTimeLocal: '08:00',
      endTimeLocal: '17:00',
      recurrenceDays: [],
      generationHorizonDays: 30,
      rosterDueOffsetMinutes: 120,
      unavailableCutoffMinutes: 120,
      lateGraceMinutes: 15,
      noShowCutoffMinutes: 30,
      checkinGeofenceMeters: 200,
      active: true,
    };
  }

  populateScheduleForm(request: ClientRequestItem, schedule: RequestScheduleItem | null): void {
    if (schedule) {
      this.scheduleForm = {
        timezone: schedule.timezone || this.getDefaultScheduleTimezone(),
        scheduleType: schedule.schedule_type || 'one_time',
        startDate: schedule.start_date || '',
        endDate: schedule.end_date || '',
        startTimeLocal: schedule.start_time_local || '08:00',
        endTimeLocal: schedule.end_time_local || '17:00',
        recurrenceDays: Array.isArray(schedule.recurrence_days) ? [...schedule.recurrence_days] : [],
        generationHorizonDays: Number(schedule.generation_horizon_days || 30),
        rosterDueOffsetMinutes: Number(schedule.roster_due_offset_minutes || 120),
        unavailableCutoffMinutes: Number(schedule.unavailable_cutoff_minutes || 120),
        lateGraceMinutes: Number(schedule.late_grace_minutes || 15),
        noShowCutoffMinutes: Number(schedule.no_show_cutoff_minutes || 30),
        checkinGeofenceMeters: Number(schedule.checkin_geofence_meters || 200),
        active: Boolean(schedule.active),
      };
      return;
    }

    const requestStartAt = this.formatDateTimeLocalInput(request.requested_start_at);
    const requestEndAt = this.formatDateTimeLocalInput(request.requested_end_at);
    const [requestStartDate = '', requestStartTime = ''] = requestStartAt.split('T');
    const [, requestEndTime = ''] = requestEndAt.split('T');
    this.scheduleForm = {
      timezone: this.getDefaultScheduleTimezone(),
      scheduleType: 'one_time',
      startDate: requestStartDate,
      endDate: requestStartDate,
      startTimeLocal: requestStartTime || '08:00',
      endTimeLocal: requestEndTime || '17:00',
      recurrenceDays: [],
      generationHorizonDays: 30,
      rosterDueOffsetMinutes: 120,
      unavailableCutoffMinutes: 120,
      lateGraceMinutes: 15,
      noShowCutoffMinutes: 30,
      checkinGeofenceMeters: 200,
      active: true,
    };
  }

  onScheduleTypeChange(): void {
    if (this.scheduleForm.scheduleType === 'one_time') {
      this.scheduleForm.endDate = this.scheduleForm.startDate;
      this.scheduleForm.recurrenceDays = [];
      return;
    }
    if (!this.scheduleForm.endDate) {
      this.scheduleForm.endDate = this.scheduleForm.startDate;
    }
    if (this.scheduleForm.scheduleType === 'date_range') {
      this.scheduleForm.recurrenceDays = [];
    }
  }

  toggleScheduleRecurrenceDay(day: string, checked: boolean): void {
    const normalized = String(day || '').trim().toLowerCase();
    const current = [...this.scheduleForm.recurrenceDays];
    if (checked) {
      if (!current.includes(normalized)) {
        current.push(normalized);
      }
    } else {
      const next = current.filter((item) => item !== normalized);
      this.scheduleForm.recurrenceDays = next;
      return;
    }
    this.scheduleForm.recurrenceDays = current;
  }

  isScheduleRecurrenceDaySelected(day: string): boolean {
    return this.scheduleForm.recurrenceDays.includes(String(day || '').trim().toLowerCase());
  }

  validateScheduleForm(): boolean {
    this.scheduleErrors = {};
    const startDate = String(this.scheduleForm.startDate || '').trim();
    const endDate = String(this.scheduleForm.endDate || '').trim();
    const timezone = String(this.scheduleForm.timezone || '').trim();
    const startTimeLocal = String(this.scheduleForm.startTimeLocal || '').trim();
    const endTimeLocal = String(this.scheduleForm.endTimeLocal || '').trim();

    if (!timezone) {
      this.scheduleErrors['timezone'] = 'Timezone is required.';
    }
    if (!startDate) {
      this.scheduleErrors['startDate'] = 'Start date is required.';
    }
    if (!startTimeLocal) {
      this.scheduleErrors['startTimeLocal'] = 'Start time is required.';
    }
    if (!endTimeLocal) {
      this.scheduleErrors['endTimeLocal'] = 'End time is required.';
    }

    if (this.scheduleForm.scheduleType !== 'one_time') {
      if (!endDate) {
        this.scheduleErrors['endDate'] = 'End date is required for this schedule type.';
      } else if (startDate && endDate < startDate) {
        this.scheduleErrors['endDate'] = 'End date must be on or after the start date.';
      }
    } else if (startDate && endDate && endDate !== startDate) {
      this.scheduleErrors['endDate'] = 'One-time schedules cannot end on a different date.';
    }

    if (this.scheduleForm.scheduleType === 'recurring_weekly' && !this.scheduleForm.recurrenceDays.length) {
      this.scheduleErrors['recurrenceDays'] = 'Select at least one weekday for recurring schedules.';
    }

    const numericFields: Array<{ key: string; value: number; label: string; min: number }> = [
      { key: 'generationHorizonDays', value: Number(this.scheduleForm.generationHorizonDays), label: 'Generation horizon', min: 1 },
      { key: 'rosterDueOffsetMinutes', value: Number(this.scheduleForm.rosterDueOffsetMinutes), label: 'Roster due offset', min: 0 },
      { key: 'unavailableCutoffMinutes', value: Number(this.scheduleForm.unavailableCutoffMinutes), label: 'Unavailable cutoff', min: 0 },
      { key: 'lateGraceMinutes', value: Number(this.scheduleForm.lateGraceMinutes), label: 'Late grace', min: 0 },
      { key: 'noShowCutoffMinutes', value: Number(this.scheduleForm.noShowCutoffMinutes), label: 'No-show cutoff', min: 0 },
      { key: 'checkinGeofenceMeters', value: Number(this.scheduleForm.checkinGeofenceMeters), label: 'Check-in geofence', min: 1 },
    ];

    for (const field of numericFields) {
      if (!Number.isFinite(field.value) || field.value < field.min) {
        this.scheduleErrors[field.key] = `${field.label} must be ${field.min === 0 ? 'zero or more' : `${field.min} or more`}.`;
      }
    }

    return Object.keys(this.scheduleErrors).length === 0;
  }

  buildSchedulePayload() {
    const endDate =
      this.scheduleForm.scheduleType === 'one_time'
        ? (this.scheduleForm.startDate || null)
        : (this.scheduleForm.endDate || null);

    return {
      timezone: this.scheduleForm.timezone.trim(),
      schedule_type: this.scheduleForm.scheduleType,
      start_date: this.scheduleForm.startDate,
      end_date: endDate,
      start_time_local: this.scheduleForm.startTimeLocal,
      end_time_local: this.scheduleForm.endTimeLocal,
      recurrence_days: this.scheduleForm.scheduleType === 'recurring_weekly' ? [...this.scheduleForm.recurrenceDays] : [],
      generation_horizon_days: Number(this.scheduleForm.generationHorizonDays),
      roster_due_offset_minutes: Number(this.scheduleForm.rosterDueOffsetMinutes),
      unavailable_cutoff_minutes: Number(this.scheduleForm.unavailableCutoffMinutes),
      late_grace_minutes: Number(this.scheduleForm.lateGraceMinutes),
      no_show_cutoff_minutes: Number(this.scheduleForm.noShowCutoffMinutes),
      checkin_geofence_meters: Number(this.scheduleForm.checkinGeofenceMeters),
      active: Boolean(this.scheduleForm.active),
    };
  }

  shouldPersistInlineSchedule(): boolean {
    return this.shouldShowInlineScheduleSetup && this.requestScheduleSetupEnabled;
  }

  loadRequestScheduleIntoForm(request: ClientRequestItem): void {
    this.selectedRequestSchedule = null;
    this.requestScheduleSetupEnabled = false;
    this.resetScheduleForm();
    this.scheduleErrors = {};

    this.requestService.getRequestSchedule(request.id, {
      loadingMode: 'silent',
      suppressErrorStatuses: [404],
    }).subscribe({
      next: (response) => {
        const schedule = response.schedule || null;
        if (!schedule) {
          this.seedInlineScheduleFromRequestForm();
          return;
        }
        this.selectedRequestSchedule = schedule;
        this.requestScheduleSetupEnabled = true;
        this.populateScheduleForm(request, schedule);
      },
      error: (error) => {
        const status = Number(error?.status || error?.statusCode || 0);
        if (status === 404) {
          this.seedInlineScheduleFromRequestForm();
          return;
        }
        this.notification.show(error?.error?.detail || 'Failed to load request schedule into the request form', 'fail', 5000);
      }
    });
  }

  persistInlineSchedule(
    requestId: string,
    callbacks: {
      onSuccess: () => void;
      onError: (error: any) => void;
    },
  ): void {
    const payload = this.buildSchedulePayload();
    const action = this.selectedRequestSchedule?.id
      ? this.requestService.updateRequestSchedule(requestId, payload, { loadingScope: this.saveRequestScope })
      : this.requestService.createRequestSchedule(requestId, payload, { loadingScope: this.saveRequestScope });

    action.subscribe({
      next: (response) => {
        this.selectedRequestSchedule = response.schedule || null;
        callbacks.onSuccess();
      },
      error: (error) => {
        callbacks.onError(error);
      },
    });
  }

  validateRequestForm(requirePublishFields = false): boolean {
    this.requestErrors = {};

    if (!this.requestForm.title.trim()) {
      this.requestErrors['title'] = 'Request title is required.';
    }
    if (this.isPlatformAdmin && this.requestFormMode === 'create' && !this.selectedRequestClientTenantId) {
      this.requestErrors['clientTenant'] = 'Select the client tenant that owns this request.';
    }
    if (this.requestSiteSourceMode === 'saved' && !this.selectedSavedSiteIndex) {
      this.requestErrors['savedSite'] = 'Select a saved client site.';
    }
    if (!this.requestForm.siteName.trim()) {
      this.requestErrors['siteName'] = 'Site name is required.';
    }
    if (!this.requestForm.siteCity.trim()) {
      this.requestErrors['siteCity'] = 'City is required.';
    } else {
      const cityOptions = this.getRequestSiteCityOptions();
      if (cityOptions.length && !cityOptions.some((city) => city.value === this.requestForm.siteCity)) {
        this.requestErrors['siteCity'] = 'Please select a valid city for the selected province.';
      }
    }
    if (!this.requestForm.siteProvince.trim()) {
      this.requestErrors['siteProvince'] = 'Province/state is required.';
    } else {
      const validProvinces = this.provinceOptions.map((province) => province.value);
      if (validProvinces.length && !validProvinces.includes(this.requestForm.siteProvince)) {
        this.requestErrors['siteProvince'] = 'Please select a valid province from the list.';
      }
    }
    if (!this.requestForm.siteCountry.trim()) {
      this.requestErrors['siteCountry'] = 'Country is required.';
    } else {
      const validCountries = this.countryOptions.map((country) => country.value);
      if (validCountries.length && !validCountries.includes(this.requestForm.siteCountry)) {
        this.requestErrors['siteCountry'] = 'Please select a valid country from the list.';
      } else if (this.requestForm.siteCountry !== 'CA') {
        this.requestErrors['siteCountry'] = 'Only Canadian addresses are accepted.';
      }
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

    if (!hasLatitude && !hasLongitude) {
      this.requestErrors['coordinates'] = 'Site coordinates are required. Select the site on Google Maps.';
    } else if (hasLatitude !== hasLongitude) {
      this.requestErrors['coordinates'] = 'Provide both latitude and longitude.';
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

    const requestedStartAt = this.combineDateAndTime(this.requestForm.requestedStartDate, this.requestForm.requestedStartTime);
    const requestedEndAt = this.combineDateAndTime(this.requestForm.requestedEndDate, this.requestForm.requestedEndTime);
    const requestExpiresAt = this.combineDateAndTime(this.requestForm.requestExpiresDate, this.requestForm.requestExpiresTime);

    const hasRequestedStartDate = this.requestForm.requestedStartDate.trim() !== '';
    const hasRequestedStartTime = this.requestForm.requestedStartTime.trim() !== '';
    const hasRequestedEndDate = this.requestForm.requestedEndDate.trim() !== '';
    const hasRequestedEndTime = this.requestForm.requestedEndTime.trim() !== '';
    const hasRequestExpiryDate = this.requestForm.requestExpiresDate.trim() !== '';
    const hasRequestExpiryTime = this.requestForm.requestExpiresTime.trim() !== '';

    const hasRequestedStartAt = hasRequestedStartDate || hasRequestedStartTime;
    const hasRequestedEndAt = hasRequestedEndDate || hasRequestedEndTime;

    if (hasRequestedStartAt !== hasRequestedEndAt) {
      if (!hasRequestedStartAt) {
        this.requestErrors['requestedStartAt'] = 'Start date and time is required when an end date and time is provided.';
      }
      if (!hasRequestedEndAt) {
        this.requestErrors['requestedEndAt'] = 'End date and time is required when a start date and time is provided.';
      }
    }

    if (hasRequestedStartAt && hasRequestedStartDate !== hasRequestedStartTime) {
      this.requestErrors['requestedStartAt'] = 'Provide both a requested start date and time.';
    }
    if (hasRequestedEndAt && hasRequestedEndDate !== hasRequestedEndTime) {
      this.requestErrors['requestedEndAt'] = 'Provide both a requested end date and time.';
    }
    if ((hasRequestExpiryDate || hasRequestExpiryTime) && hasRequestExpiryDate !== hasRequestExpiryTime) {
      this.requestErrors['requestExpiresAt'] = 'Provide both an expiry date and time.';
    }

    if (requestedEndAt && requestedStartAt) {
      const start = new Date(requestedStartAt);
      const end = new Date(requestedEndAt);
      if (Number.isNaN(start.getTime())) {
        this.requestErrors['requestedStartAt'] = 'Start date and time is invalid.';
      }
      if (Number.isNaN(end.getTime())) {
        this.requestErrors['requestedEndAt'] = 'End date and time is invalid.';
      } else if (!Number.isNaN(start.getTime()) && end <= start) {
        this.requestErrors['requestedEndAt'] = 'End time must be after start time.';
      }
    }

    if (requirePublishFields) {
      if (!requestedStartAt) {
        this.requestErrors['requestedStartAt'] = 'Requested start date and time is required before publishing.';
      }
      if (!requestedEndAt) {
        this.requestErrors['requestedEndAt'] = 'Requested end date and time is required before publishing.';
      }
      if (!requestExpiresAt) {
        this.requestErrors['requestExpiresAt'] = 'Request expiry is required before publishing.';
      } else {
        const expiry = new Date(requestExpiresAt);
        if (Number.isNaN(expiry.getTime()) || expiry <= new Date()) {
          this.requestErrors['requestExpiresAt'] = 'Request expiry must be in the future.';
        } else if (requestedStartAt) {
          const requestedStartDateTime = new Date(requestedStartAt);
          if (expiry > requestedStartDateTime) {
            this.requestErrors['requestExpiresAt'] = 'Request expiry cannot be after the requested start date and time.';
          }
        }
      }
    }

    return Object.keys(this.requestErrors).length === 0;
  }

  async submitRequest(commit: boolean): Promise<void> {
    if (!(this.isClientAdmin || this.isPlatformAdmin)) {
      return;
    }
    if (!this.validateRequestForm(commit)) {
      this.notification.show('Please fix the highlighted request fields.', 'fail', 4000);
      return;
    }

    if (this.shouldPersistInlineSchedule() && !this.validateScheduleForm()) {
      this.notification.show('Please fix the coverage pattern fields before saving the request.', 'fail', 4000);
      return;
    }

    const addressConsistent = await this.validateRequestAddressConsistency();
    if (!addressConsistent) {
      this.notification.show('Please reconcile the site coordinates and manual address.', 'fail', 4500);
      return;
    }

    this.saving = true;
    const payload = this.buildRequestPayload();

    if (this.requestFormMode === 'create') {
      const shouldPersistSchedule = this.shouldPersistInlineSchedule();
      const createAsDraftFirst = commit && shouldPersistSchedule;
      this.requestService.createRequest({ ...payload, commit: createAsDraftFirst ? false : commit }, { loadingScope: this.saveRequestScope }).subscribe({
        next: (response) => {
          const createdRequest = response.item;
          if (!createdRequest?.id) {
            this.saving = false;
            this.notification.show('Request was created but no request id was returned.', 'fail', 5000);
            this.loadRequests(1);
            return;
          }

          const finishCreate = (message: string, tone: 'success' | 'fail' = 'success') => {
            this.saving = false;
            this.notification.show(message, tone, 4000);
            this.closeRequestFormDrawer();
            this.loadRequests(1);
          };

          const publishCreatedRequest = () => {
            this.requestService.publishRequest(createdRequest.id, { max_match_results: 25 }, { loadingScope: this.saveRequestScope }).subscribe({
              next: (publishResponse) => {
                finishCreate(publishResponse.message || 'Request published', 'success');
              },
              error: (publishError) => {
                finishCreate(publishError?.error?.detail || 'Request draft saved and schedule saved, but publish failed', 'fail');
              }
            });
          };

          if (!shouldPersistSchedule) {
            finishCreate(response.message || (commit ? 'Request created' : 'Request draft saved'), 'success');
            return;
          }

          this.persistInlineSchedule(createdRequest.id, {
            onSuccess: () => {
              if (commit) {
                publishCreatedRequest();
                return;
              }
              finishCreate('Request draft and coverage pattern saved', 'success');
            },
            onError: (scheduleError) => {
              if (commit) {
                finishCreate(scheduleError?.error?.detail || 'Request draft saved, but coverage pattern failed to save so it was not published', 'fail');
                return;
              }
              finishCreate(scheduleError?.error?.detail || 'Request draft saved, but coverage pattern failed to save', 'fail');
            },
          });
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
        const finishUpdate = (message: string, tone: 'success' | 'fail' = 'success') => {
          this.saving = false;
          this.notification.show(message, tone, 3500);
          this.closeRequestFormDrawer();
          this.loadRequests(this.page);
        };

        const publishUpdatedRequest = () => {
          this.requestService.publishRequest(this.editingRequestId, { max_match_results: 25 }, { loadingScope: this.saveRequestScope }).subscribe({
            next: (response) => {
              finishUpdate(response.message || 'Request published', 'success');
            },
            error: (error) => {
              finishUpdate(error?.error?.detail || 'Draft updated but failed to publish request', 'fail');
            }
          });
        };

        const continueAfterSchedule = () => {
          if (!commit) {
            this.saving = false;
            this.notification.show('Request draft updated', 'success', 3500);
            this.closeRequestFormDrawer();
            this.loadRequests(this.page);
            return;
          }
          publishUpdatedRequest();
        };

        if (!this.shouldPersistInlineSchedule()) {
          continueAfterSchedule();
          return;
        }

        this.persistInlineSchedule(this.editingRequestId, {
          onSuccess: continueAfterSchedule,
          onError: (scheduleError) => {
            finishUpdate(scheduleError?.error?.detail || 'Request draft updated, but coverage pattern failed to save', 'fail');
          },
        });
      },
      error: (error) => {
        this.saving = false;
        this.notification.show(error?.error?.detail || 'Failed to update request draft', 'fail', 5000);
      }
    });
  }

  resetForm(): void {
    const preservedClientTenantId = this.isPlatformAdmin && this.requestFormMode === 'create'
      ? this.selectedRequestClientTenantId
      : '';
    const preservedClientTenantLabel = this.isPlatformAdmin && this.requestFormMode === 'create'
      ? this.requestClientTenantDisplayValue
      : '';
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
      requestedStartDate: '',
      requestedStartTime: '',
      requestedEndDate: '',
      requestedEndTime: '',
      requestExpiresDate: '',
      requestExpiresTime: '',
      specialInstructions: '',
    };
    this.requestSiteSourceMode = 'manual';
    this.selectedSavedSiteIndex = '';
    this.requestScheduleSetupEnabled = false;
    this.selectedRequestSchedule = null;
    this.resetScheduleForm();
    this.scheduleErrors = {};
    if (preservedClientTenantId) {
      this.selectedRequestClientTenantId = preservedClientTenantId;
      this.selectedRequestClientTenantLabel = preservedClientTenantLabel;
    } else if (!this.isPlatformAdmin || this.requestFormMode !== 'create') {
      this.selectedRequestClientTenantId = '';
      this.selectedRequestClientTenantLabel = '';
    }
    this.requestErrors = {};
  }

  openCreateRequestDrawer(): void {
    this.requestFormMode = 'create';
    this.editingRequestId = '';
    this.resetForm();
    this.loadRequestClientTenants({ silent: true });
    this.loadClientSites({ silent: true });
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
    this.loadRequestScheduleIntoForm(item);
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
    this.requestScheduleSetupEnabled = false;
    this.selectedRequestSchedule = null;
    this.showRequestFormDrawer = true;
  }

  closeRequestFormDrawer(): void {
    this.showRequestFormDrawer = false;
    this.editingRequestId = '';
    this.requestFormMode = 'create';
    this.resetForm();
  }

  fillDummyData(): void {
    this.requestSiteSourceMode = 'manual';
    this.selectedSavedSiteIndex = '';
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
    startDate.setHours(18, 0, 0, 0);
    const endDate = new Date(startDate);
    endDate.setHours(startDate.getHours() + 2, 0, 0, 0);
    const expiryDate = new Date(startDate);
    expiryDate.setHours(startDate.getHours() - 2, 0, 0, 0);

    this.requestForm = {
      ...this.requestForm,
      title: picked.title,
      fulfillmentMode: 'individual_only',
      siteName: picked.siteName,
      siteStreet: picked.siteStreet,
      siteCity: this.resolveCityCodeForProvince(
        this.resolveProvinceCode(picked.siteProvince),
        picked.siteCity,
      ) || picked.siteCity,
      siteProvince: this.resolveProvinceCode(picked.siteProvince) || picked.siteProvince,
      sitePostalCode: picked.sitePostalCode,
      siteCountry: picked.siteCountry,
      latitude: picked.latitude,
      longitude: picked.longitude,
      googleMapsUrl: '',
      siteManagerContact: picked.siteManagerContact,
      managerEmail: picked.managerEmail,
      requestedGuardType: picked.requestedGuardType,
      guardsRequired: picked.guardsRequired,
      requestedStartDate: this.formatDateInput(startDate),
      requestedStartTime: this.formatTimeInput(startDate),
      requestedEndDate: this.formatDateInput(endDate),
      requestedEndTime: this.formatTimeInput(endDate),
      requestExpiresDate: this.formatDateInput(expiryDate),
      requestExpiresTime: this.formatTimeInput(expiryDate),
      specialInstructions: picked.specialInstructions,
    };
    if (this.requestScheduleSetupEnabled && !this.selectedRequestSchedule?.id) {
      this.seedInlineScheduleFromRequestForm();
    }
    this.requestErrors = {};
  }

  populateFormFromRequest(item: ClientRequestItem): void {
    const address = item.site_snapshot?.site_address || {};
    const countryCode = String(address['country'] || 'CA').trim() || 'CA';
    const provinceCode = this.resolveProvinceCode(String(address['province'] || ''));
    const cityCode = this.resolveCityCodeForProvince(provinceCode, String(address['city'] || ''));
    this.requestForm = {
      title: item.title || '',
      fulfillmentMode: (item.fulfillment_mode || this.targetTypeToFulfillmentMode(item.target_type || 'guard')) as ClientRequestFulfillmentMode,
      siteName: item.site_snapshot?.site_name || '',
      siteStreet: String(address['street'] || ''),
      siteCity: cityCode || String(address['city'] || ''),
      siteProvince: provinceCode || String(address['province'] || ''),
      sitePostalCode: String(address['postal_code'] || ''),
      siteCountry: countryCode,
      siteManagerContact: item.site_snapshot?.site_manager_contact || '',
      managerEmail: item.site_snapshot?.manager_email || '',
      googleMapsUrl: item.site_snapshot?.google_maps_url || '',
      latitude: address['latitude'] != null ? String(address['latitude']) : '',
      longitude: address['longitude'] != null ? String(address['longitude']) : '',
      requestedGuardType: item.requested_guard_type || '',
      guardsRequired: Number(item.guards_required || 1),
      requestedStartDate: this.formatDateInput(item.requested_start_at),
      requestedStartTime: this.formatTimeInput(item.requested_start_at),
      requestedEndDate: this.formatDateInput(item.requested_end_at),
      requestedEndTime: this.formatTimeInput(item.requested_end_at),
      requestExpiresDate: this.formatDateInput(item.request_expires_at),
      requestExpiresTime: this.formatTimeInput(item.request_expires_at),
      specialInstructions: item.special_instructions || '',
    };
    this.requestSiteSourceMode = item.site_snapshot?.site_source === 'saved' ? 'saved' : 'manual';
    this.selectedSavedSiteIndex = Number.isInteger(item.site_snapshot?.site_index) && Number(item.site_snapshot?.site_index) >= 0
      ? String(item.site_snapshot?.site_index)
      : '';
    if (this.isPlatformAdmin) {
      this.selectedRequestClientTenantId = String(item.client_tenant_id || '').trim();
      this.selectedRequestClientTenantLabel = this.requestClientTenantOptions.find((option) => option.value === this.selectedRequestClientTenantId)?.label || this.selectedRequestClientTenantId;
      if (this.selectedRequestClientTenantId) {
        this.loadClientSites({ silent: true, tenantId: this.selectedRequestClientTenantId });
      }
    }
    this.requestErrors = {};
  }

  buildRequestPayload() {
    const useSavedSiteIndex = this.requestSiteSourceMode === 'saved'
      && this.requestFormMode === 'create'
      && this.selectedSavedSiteIndex !== '';
    const latitude = this.parseCoordinate(this.requestForm.latitude);
    const longitude = this.parseCoordinate(this.requestForm.longitude);
    const requestedStartAt = this.combineDateAndTime(this.requestForm.requestedStartDate, this.requestForm.requestedStartTime);
    const requestedEndAt = this.combineDateAndTime(this.requestForm.requestedEndDate, this.requestForm.requestedEndTime);
    const requestExpiresAt = this.combineDateAndTime(this.requestForm.requestExpiresDate, this.requestForm.requestExpiresTime);

    return {
      title: this.requestForm.title.trim(),
      fulfillment_mode: this.requestForm.fulfillmentMode,
      client_tenant_id: this.isPlatformAdmin && this.requestFormMode === 'create'
        ? (this.selectedRequestClientTenantId || null)
        : null,
      site_index: useSavedSiteIndex ? Number(this.selectedSavedSiteIndex) : null,
      site: useSavedSiteIndex ? null : {
        site_name: this.requestForm.siteName.trim(),
        site_manager_contact: this.requestForm.siteManagerContact.trim() || null,
        manager_email: this.requestForm.managerEmail.trim() || null,
        google_maps_url: this.requestForm.googleMapsUrl.trim() || null,
        site_address: {
          street: this.requestForm.siteStreet.trim() || null,
          city: this.getRequestSiteCityLabel(this.requestForm.siteProvince, this.requestForm.siteCity),
          country: this.requestForm.siteCountry.trim() || 'CA',
          province: this.getRequestProvinceLabel(this.requestForm.siteProvince),
          postal_code: this.requestForm.sitePostalCode.trim() || null,
          latitude,
          longitude,
        },
      },
      requested_guard_type: this.requestForm.requestedGuardType || null,
      guards_required: Number(this.requestForm.guardsRequired || 1),
      requested_start_at: requestedStartAt || null,
      requested_end_at: requestedEndAt || null,
      request_expires_at: requestExpiresAt || null,
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
    this.selectedRequestSchedule = null;
    this.selectedRequestWaves = [];
    this.showRequestDrawer = true;
    this.loadRequestSchedule(item.id);
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
        this.selectedRequestSchedule = null;
        this.selectedRequestWaves = [];
        this.showRequestDrawer = true;
        this.loadRequestSchedule(requestId, options);
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
    this.selectedRequestSchedule = null;
    this.selectedRequestWaves = [];
    this.clearRouteFocusParams(['request']);
  }

  openScheduleDrawer(request?: ClientRequestItem | null): void {
    const targetRequest = request || this.selectedRequest;
    if (!targetRequest || !this.canManageRequestSchedule(targetRequest)) {
      this.notification.show('Schedule management is not available for this request.', 'fail', 3500);
      return;
    }
    const existingSchedule = this.selectedRequest?.id === targetRequest.id ? this.selectedRequestSchedule : null;
    const openDrawer = (schedule: RequestScheduleItem | null) => {
      if (this.selectedRequest?.id === targetRequest.id) {
        this.closeRequestDrawer();
      }
      this.selectedScheduleRequest = targetRequest;
      this.selectedRequestSchedule = schedule;
      this.scheduleErrors = {};
      this.populateScheduleForm(targetRequest, schedule);
      this.showScheduleDrawer = true;
    };

    if (existingSchedule) {
      openDrawer(existingSchedule);
      return;
    }

    this.requestService.getRequestSchedule(targetRequest.id, {
      loadingScope: this.requestScheduleScope,
      loadingMode: 'silent',
      suppressErrorStatuses: [404],
    }).subscribe({
      next: (response) => {
        openDrawer(response.schedule || null);
      },
      error: (error) => {
        const status = Number(error?.status || error?.statusCode || 0);
        if (status === 404) {
          openDrawer(null);
          return;
        }
        this.notification.show(error?.error?.detail || 'Failed to load request schedule', 'fail', 5000);
      }
    });
  }

  closeScheduleDrawer(): void {
    this.showScheduleDrawer = false;
    this.selectedScheduleRequest = null;
    this.scheduleErrors = {};
    this.resetScheduleForm();
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

  openShiftDetails(item: ShiftInstanceItem): void {
    this.openShiftById(item.id);
  }

  openShiftById(shiftId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getShift(shiftId, {
      loadingScope: this.shiftDetailScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedShift = response.shift;
        this.selectedShiftSlots = response.slots || [];
        this.selectedShiftSlotSummary = response.slot_summary || null;
        this.ensureShiftRequestSummaries([response.shift]);
        this.showShiftDrawer = true;
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open shift details', 'fail', 5000);
        }
      }
    });
  }

  closeShiftDrawer(): void {
    this.showShiftDrawer = false;
    this.selectedShift = null;
    this.selectedShiftSlots = [];
    this.selectedShiftSlotSummary = null;
    this.clearRouteFocusParams(['shift']);
  }

  openBulkConfirmDrawer(shift?: ShiftInstanceItem | null): void {
    const targetShift = shift || this.selectedShift;
    if (!targetShift) {
      return;
    }

    const slotSource = targetShift.id === this.selectedShift?.id ? this.selectedShiftSlots : [];
    const confirmableSlots = slotSource.filter((slot) => this.canConfirmShiftSlotArrival(slot));
    if (!confirmableSlots.length) {
      this.notification.show('No arrived guards are waiting for client confirmation on this shift.', 'fail', 3500);
      return;
    }

    if (this.selectedShift?.id === targetShift.id) {
      this.closeShiftDrawer();
    }

    this.selectedBulkConfirmShift = targetShift;
    this.bulkConfirmShiftSlots = confirmableSlots;
    this.bulkConfirmSelections = confirmableSlots.reduce<Record<string, boolean>>((accumulator, slot) => {
      accumulator[slot.id] = true;
      return accumulator;
    }, {});
    this.bulkConfirmErrors = {};
    this.bulkConfirmForm = { note: '' };
    this.showBulkConfirmDrawer = true;
  }

  closeBulkConfirmDrawer(): void {
    this.showBulkConfirmDrawer = false;
    this.selectedBulkConfirmShift = null;
    this.bulkConfirmShiftSlots = [];
    this.bulkConfirmSelections = {};
    this.bulkConfirmErrors = {};
    this.bulkConfirmForm = { note: '' };
  }

  openShiftSlotDetails(slot: ShiftSlotItem): void {
    if (this.selectedShift?.id === slot.shift_instance_id) {
      this.closeShiftDrawer();
    }
    this.openShiftSlotById(slot.id);
  }

  openShiftSlotById(slotId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getShiftSlot(slotId, {
      loadingScope: this.shiftSlotDetailScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedShiftSlot = response.slot;
        this.selectedShiftSlotDetail = response;
        this.showShiftSlotDrawer = true;
        if (this.selectedShift?.id !== response.slot.shift_instance_id) {
          this.selectedShift = null;
          this.selectedShiftSlots = [];
          this.selectedShiftSlotSummary = null;
          this.requestService.getShift(response.slot.shift_instance_id, {
            loadingScope: this.shiftDetailScope,
            loadingMode: 'silent',
          }).subscribe({
            next: (shiftResponse) => {
              this.selectedShift = shiftResponse.shift;
              this.selectedShiftSlots = shiftResponse.slots || [];
              this.selectedShiftSlotSummary = shiftResponse.slot_summary || null;
              this.ensureShiftRequestSummaries([shiftResponse.shift]);
            },
            error: () => {}
          });
        }
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open shift slot', 'fail', 5000);
        }
      }
    });
  }

  closeShiftSlotDrawer(): void {
    this.showShiftSlotDrawer = false;
    this.selectedShiftSlot = null;
    this.selectedShiftSlotDetail = null;
    this.clearRouteFocusParams(['slot']);
  }

  openExceptionDetails(item: ShiftExceptionItem): void {
    this.selectedException = item;
    this.selectedExceptionDetail = null;
    this.showExceptionDrawer = true;
    this.openExceptionBySlotId(item.slot.id);
  }

  openExceptionBySlotId(slotId: string, options?: { silent?: boolean; suppressError?: boolean }): void {
    const silent = Boolean(options?.silent);
    const suppressError = Boolean(options?.suppressError);
    this.requestService.getShiftSlot(slotId, {
      loadingScope: this.exceptionDetailScope,
      loadingMode: silent ? 'silent' : undefined,
    }).subscribe({
      next: (response) => {
        this.selectedExceptionDetail = response;
        const refreshed = this.shiftExceptions.find((item) => item.slot?.id === slotId);
        if (refreshed) {
          this.selectedException = refreshed;
        }
        this.showExceptionDrawer = true;
      },
      error: (error) => {
        if (!suppressError) {
          this.notification.show(error?.error?.detail || 'Failed to open shift exception', 'fail', 5000);
        }
      }
    });
  }

  closeExceptionDrawer(): void {
    this.showExceptionDrawer = false;
    this.selectedException = null;
    this.selectedExceptionDetail = null;
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
      requestExpiresAt: this.formatDateTimeLocalInput(item.request_expires_at),
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

  openRosterDrawer(shift?: ShiftInstanceItem | null): void {
    const targetShift = shift || this.selectedShift;
    if (!targetShift) {
      return;
    }

    const slotSource = targetShift.id === this.selectedShift?.id ? this.selectedShiftSlots : [];
    const rosterableSlots = slotSource.filter((slot) => this.isRosterableProviderSlot(slot));
    if (!this.canManageProviderRoster || !rosterableSlots.length) {
      this.notification.show('There are no provider-backed slots ready for rostering on this shift.', 'fail', 3500);
      return;
    }

    if (this.selectedShift?.id === targetShift.id) {
      this.closeShiftDrawer();
    }
    this.selectedRosterShift = targetShift;
    this.rosterShiftSlots = rosterableSlots;
    this.rosterErrors = {};
    this.rosterSelections = {};
    this.rosterPatternForm = {
      applyToFutureShifts: false,
    };
    this.rosterPatternFutureShifts = [];
    for (const slot of rosterableSlots) {
      if (slot.assigned_guard_tenant_id) {
        this.rosterSelections[slot.id] = slot.assigned_guard_tenant_id;
      }
    }
    this.providerGuards = [];
    this.showRosterDrawer = true;
    this.requestService.listServiceProviderGuards(1, 100, {
      loadingScope: this.shiftProviderGuardsScope,
      loadingMode: 'silent',
    }).subscribe({
      next: (response) => {
        this.providerGuards = (response.items || []).filter((guard) => {
          const status = String(guard.status || '').trim().toLowerCase();
          const inviteStatus = String(guard.invite_status || '').trim().toLowerCase();
          return status === 'active' && inviteStatus !== 'expired';
        });
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to load provider guards', 'fail', 5000);
      }
    });

    this.requestService.listShifts(1, 100, targetShift.request_id, '', targetShift.shift_date_local, '', {
      loadingScope: this.shiftRosterPatternScope,
      loadingMode: 'silent',
    }).subscribe({
      next: (response) => {
        const currentStartAt = String(targetShift.shift_start_at_utc || '');
        this.rosterPatternFutureShifts = (response.items || []).filter((item) => {
          if (item.id === targetShift.id) {
            return false;
          }
          if (String(item.request_id || '') !== String(targetShift.request_id || '')) {
            return false;
          }
          return String(item.shift_start_at_utc || '') >= currentStartAt;
        });
      },
      error: () => {
        this.rosterPatternFutureShifts = [];
      }
    });
  }

  closeRosterDrawer(): void {
    this.showRosterDrawer = false;
    this.selectedRosterShift = null;
    this.rosterShiftSlots = [];
    this.rosterPatternFutureShifts = [];
    this.rosterErrors = {};
    this.rosterSelections = {};
    this.rosterPatternForm = {
      applyToFutureShifts: false,
    };
    this.providerGuards = [];
  }

  openReopenExceptionDrawer(item: ShiftExceptionItem): void {
    if (!this.canReopenException(item)) {
      this.notification.show('This shift exception cannot be reopened from its current state.', 'fail', 3500);
      return;
    }
    if (this.selectedException?.slot?.id === item.slot.id) {
      this.closeExceptionDrawer();
    }
    this.reopenExceptionTarget = item;
    this.reopenExceptionErrors = {};
    this.reopenExceptionForm = {
      note: '',
      maxMatchResults: 25,
    };
    this.showReopenExceptionDrawer = true;
  }

  closeReopenExceptionDrawer(): void {
    this.showReopenExceptionDrawer = false;
    this.reopenExceptionTarget = null;
    this.reopenExceptionErrors = {};
    this.reopenExceptionForm = {
      note: '',
      maxMatchResults: 25,
    };
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

  openShiftActionDrawer(slot: ShiftSlotItem, action: 'report_unavailable' | 'check_in' | 'client_confirm' | 'start' | 'check_out'): void {
    this.shiftActionTarget = slot;
    this.shiftActionType = action;
    this.shiftActionErrors = {};
    this.shiftActionLocationError = '';
    this.shiftActionLocationMessage = '';
    this.capturingShiftActionLocation = false;
    this.shiftActionForm = {
      latitude: '',
      longitude: '',
      note: '',
    };
    if (this.selectedShiftSlot?.id === slot.id) {
      this.closeShiftSlotDrawer();
    }
    this.showShiftActionDrawer = true;
    if (action === 'check_in') {
      this.captureShiftActionLocation(true);
    }
  }

  closeShiftActionDrawer(): void {
    this.showShiftActionDrawer = false;
    this.shiftActionTarget = null;
    this.shiftActionType = null;
    this.shiftActionErrors = {};
    this.shiftActionLocationError = '';
    this.shiftActionLocationMessage = '';
    this.capturingShiftActionLocation = false;
    this.shiftActionForm = {
      latitude: '',
      longitude: '',
      note: '',
    };
  }

  openRequestReasonDrawer(item: ClientRequestItem, status: ClientRequestStatus): void {
    if (this.selectedRequest?.id === item.id) {
      this.closeRequestDrawer();
    }
    this.reasonRequestTarget = item;
    this.reasonJobTarget = null;
    this.reasonRequestStatus = status;
    this.reasonRequestSoftDelete = false;
    this.reasonJobStatus = null;
    this.reasonErrors = {};
    this.reasonForm = { note: '' };
    this.showReasonDrawer = true;
  }

  openRequestSoftDeleteDrawer(item: ClientRequestItem): void {
    if (this.selectedRequest?.id === item.id) {
      this.closeRequestDrawer();
    }
    this.reasonRequestTarget = item;
    this.reasonJobTarget = null;
    this.reasonRequestStatus = null;
    this.reasonRequestSoftDelete = true;
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
    this.reasonRequestSoftDelete = false;
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
    this.reasonRequestSoftDelete = false;
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
    this.requestClientTenantFilter = '';
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

  applyShiftFilters(): void {
    this.loadShifts(1);
    this.loadShiftCalendar(this.shiftCalendarMonthAnchor);
  }

  clearShiftFilters(): void {
    this.shiftStatusFilter = '';
    this.shiftDateFrom = '';
    this.shiftDateTo = '';
    this.loadShifts(1);
    this.loadShiftCalendar(this.shiftCalendarMonthAnchor);
  }

  applyExceptionFilters(): void {
    this.loadShiftExceptions(1);
  }

  clearExceptionFilters(): void {
    this.exceptionStatusFilter = '';
    this.exceptionDateFrom = '';
    this.exceptionDateTo = '';
    this.loadShiftExceptions(1);
  }

  setShiftViewMode(mode: 'calendar' | 'list'): void {
    this.shiftViewMode = mode;
    if (mode === 'calendar' && !this.shiftCalendarItems.length) {
      this.loadShiftCalendar(this.shiftCalendarMonthAnchor, { silent: true, suppressError: true });
    }
  }

  goToPreviousShiftCalendarMonth(): void {
    this.loadShiftCalendar(this.addMonths(this.shiftCalendarMonthAnchor, -1));
  }

  goToNextShiftCalendarMonth(): void {
    this.loadShiftCalendar(this.addMonths(this.shiftCalendarMonthAnchor, 1));
  }

  goToCurrentShiftCalendarMonth(): void {
    this.loadShiftCalendar(this.getStartOfMonth(new Date()));
  }

  focusShiftCalendarDate(isoDate: string): void {
    this.shiftDateFrom = isoDate;
    this.shiftDateTo = isoDate;
    this.shiftViewMode = 'list';
    this.loadShifts(1);
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
          this.coverageErrors['requestExpiresAt'] = 'Request expiry cannot be after the requested start date and time.';
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

  submitRequestSchedule(): void {
    const request = this.selectedScheduleRequest;
    if (!request) {
      return;
    }

    if (!this.validateScheduleForm()) {
      this.notification.show('Please fix the schedule fields before saving.', 'fail', 4000);
      return;
    }

    const payload = this.buildSchedulePayload();
    const action = this.selectedRequestSchedule?.id
      ? this.requestService.updateRequestSchedule(request.id, payload, { loadingScope: this.saveRequestScheduleScope })
      : this.requestService.createRequestSchedule(request.id, payload, { loadingScope: this.saveRequestScheduleScope });

    action.subscribe({
      next: (response) => {
        this.selectedRequestSchedule = response.schedule || null;
        this.notification.show('Request schedule saved', 'success', 3500);
        this.closeScheduleDrawer();
        this.openRequestById(request.id, { silent: true, suppressError: true });
        if (this.canViewShifts) {
          this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
        }
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to save request schedule', 'fail', 5000);
      }
    });
  }

  submitBulkConfirmArrivals(): void {
    const shift = this.selectedBulkConfirmShift;
    if (!shift) {
      return;
    }

    const selectedSlotIds = this.getSelectedBulkConfirmSlotIds();
    this.bulkConfirmErrors = {};
    if (!selectedSlotIds.length) {
      this.bulkConfirmErrors['slots'] = 'Select at least one arrived slot to confirm.';
      this.notification.show('Select at least one slot to confirm.', 'fail', 4000);
      return;
    }

    const note = this.bulkConfirmForm.note.trim() || null;
    const loadingScope = this.getShiftBulkConfirmScope(shift.id);
    forkJoin(
      selectedSlotIds.map((slotId) =>
        this.requestService.confirmShiftSlotArrival(slotId, { note }, {
          loadingScope,
          loadingMode: 'silent',
        }),
      ),
    ).subscribe({
      next: () => {
        this.notification.show(
          `${selectedSlotIds.length} shift slot${selectedSlotIds.length === 1 ? '' : 's'} confirmed`,
          'success',
          3500,
        );
        this.closeBulkConfirmDrawer();
        this.openShiftById(shift.id, { silent: true, suppressError: true });
        this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
      },
      error: (error) => {
        this.notification.show(
          error?.error?.detail || 'Bulk confirmation did not fully complete. The shift state has been refreshed.',
          'fail',
          5000,
        );
        this.closeBulkConfirmDrawer();
        this.openShiftById(shift.id, { silent: true, suppressError: true });
      }
    });
  }

  submitRosterAssignments(): void {
    const shift = this.selectedRosterShift;
    if (!shift) {
      return;
    }

    this.rosterErrors = {};
    const selectedAssignments = this.buildRosterAssignmentsForSlots(this.rosterShiftSlots);
    const assignments: ProviderRosterPayload['assignments'] = selectedAssignments.assignments;

    if (!assignments.length) {
      this.rosterErrors['assignments'] = 'Select at least one guard assignment before rostering the shift.';
      this.notification.show('Select at least one provider guard before saving the roster.', 'fail', 4000);
      return;
    }

    const loadingScope = this.getShiftRosterScope(shift.id);

    if (!this.rosterPatternForm.applyToFutureShifts || !this.rosterPatternFutureShifts.length) {
      this.requestService.rosterShift(shift.id, { assignments }, { loadingScope }).subscribe({
        next: (response) => {
          this.notification.show('Shift roster updated', 'success', 3500);
          this.closeRosterDrawer();
          this.selectedShift = response.shift;
          this.selectedShiftSlots = response.slots || [];
          this.selectedShiftSlotSummary = response.slot_summary || null;
          this.showShiftDrawer = true;
          this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
        },
        error: (error) => {
          this.notification.show(error?.error?.detail || 'Failed to roster provider guards', 'fail', 5000);
        }
      });
      return;
    }

    const futureShiftIds = this.rosterPatternFutureShifts.map((item) => item.id);
    const guardByPatternKey = selectedAssignments.guardByPatternKey;
    forkJoin(
      [shift.id, ...futureShiftIds].map((shiftId) =>
        this.requestService.getShift(shiftId, {
          loadingScope,
          loadingMode: 'silent',
        }),
      ),
    ).subscribe({
      next: (shiftResponses) => {
        const rosterPayloads = shiftResponses
          .map((response) => {
            const shiftAssignments = response.shift.id === shift.id
              ? assignments
              : this.buildRosterPatternAssignments(response.slots || [], guardByPatternKey);
            if (!shiftAssignments.length) {
              return null;
            }
            return {
              shiftId: response.shift.id,
              assignments: shiftAssignments,
            };
          })
          .filter((item): item is { shiftId: string; assignments: ProviderRosterPayload['assignments'] } => Boolean(item));

        if (!rosterPayloads.length) {
          this.notification.show('No matching provider-backed slots were found for the future roster pattern.', 'fail', 4000);
          return;
        }

        forkJoin(
          rosterPayloads.map((item) =>
            this.requestService.rosterShift(item.shiftId, { assignments: item.assignments }, {
              loadingScope,
              loadingMode: 'silent',
            }),
          ),
        ).subscribe({
          next: (responses) => {
            const currentResponse = responses.find((item) => item.shift.id === shift.id) || responses[0];
            const affectedShiftCount = responses.length;
            this.notification.show(
              affectedShiftCount === 1
                ? 'Shift roster updated'
                : `Roster pattern applied to ${affectedShiftCount} shifts`,
              'success',
              3500,
            );
            this.closeRosterDrawer();
            this.selectedShift = currentResponse.shift;
            this.selectedShiftSlots = currentResponse.slots || [];
            this.selectedShiftSlotSummary = currentResponse.slot_summary || null;
            this.showShiftDrawer = true;
            this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
          },
          error: (error) => {
            this.notification.show(error?.error?.detail || 'Failed to apply the roster pattern to future shifts', 'fail', 5000);
          }
        });
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to load future shift details for the roster pattern', 'fail', 5000);
      }
    });
  }

  submitReopenException(): void {
    const item = this.reopenExceptionTarget;
    if (!item) {
      return;
    }

    this.reopenExceptionErrors = {};
    const maxMatchResults = Number(this.reopenExceptionForm.maxMatchResults);
    if (!Number.isInteger(maxMatchResults) || maxMatchResults < 1) {
      this.reopenExceptionErrors['maxMatchResults'] = 'Provide a valid whole number of match results.';
    }
    if (Object.keys(this.reopenExceptionErrors).length) {
      this.notification.show('Please fix the replacement fields.', 'fail', 4000);
      return;
    }

    this.requestService.reopenShiftSlot(
      item.slot.id,
      {
        note: this.reopenExceptionForm.note.trim() || null,
        max_match_results: maxMatchResults,
      },
      { loadingScope: this.getExceptionActionScope(item.slot.id) },
    ).subscribe({
      next: (response) => {
        this.notification.show(response.message || 'Shift slot reopened for replacement', 'success', 3500);
        this.closeReopenExceptionDrawer();
        this.loadShiftExceptions(this.exceptionPage);
        if (this.selectedException?.slot?.id === item.slot.id) {
          this.openExceptionBySlotId(item.slot.id, { silent: true, suppressError: true });
        }
        if (this.canReviewBroadcastWaves) {
          this.loadReviewWaves(this.reviewPage, { silent: true, suppressError: true });
        }
        this.loadJobs(this.jobPage, { silent: true, suppressError: true });
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to reopen shift slot', 'fail', 5000);
      }
    });
  }

  submitShiftAction(): void {
    const slot = this.shiftActionTarget;
    const action = this.shiftActionType;
    if (!slot || !action) {
      return;
    }

    this.shiftActionErrors = {};
    const note = this.shiftActionForm.note.trim() || null;

    if (action === 'check_in') {
      const latitude = Number(this.shiftActionForm.latitude);
      const longitude = Number(this.shiftActionForm.longitude);
      if (!Number.isFinite(latitude)) {
        this.shiftActionErrors['latitude'] = 'Latitude is required.';
      }
      if (!Number.isFinite(longitude)) {
        this.shiftActionErrors['longitude'] = 'Longitude is required.';
      }
      if (Object.keys(this.shiftActionErrors).length) {
        this.notification.show('Please fix the shift action fields.', 'fail', 4000);
        return;
      }
      this.requestService.checkInShiftSlot(
        slot.id,
        { latitude, longitude, note },
        { loadingScope: this.getShiftSlotActionScope(slot.id) },
      ).subscribe({
        next: (response) => {
          this.notification.show('Shift slot checked in', 'success', 3500);
          this.closeShiftActionDrawer();
          this.handleShiftSlotActionSuccess(slot.id, response);
        },
        error: (error) => {
          this.notification.show(error?.error?.detail || 'Failed to check in to shift slot', 'fail', 5000);
        }
      });
      return;
    }

    const actionCall =
      action === 'report_unavailable'
        ? this.requestService.reportShiftSlotUnavailable(slot.id, { note }, { loadingScope: this.getShiftSlotActionScope(slot.id) })
        : action === 'client_confirm'
          ? this.requestService.confirmShiftSlotArrival(slot.id, { note }, { loadingScope: this.getShiftSlotActionScope(slot.id) })
          : action === 'start'
            ? this.requestService.startShiftSlot(slot.id, { note }, { loadingScope: this.getShiftSlotActionScope(slot.id) })
            : this.requestService.checkOutShiftSlot(slot.id, { note }, { loadingScope: this.getShiftSlotActionScope(slot.id) });

    actionCall.subscribe({
      next: (response) => {
        this.notification.show(this.getShiftActionSuccessMessage(action), 'success', 3500);
        this.closeShiftActionDrawer();
        this.handleShiftSlotActionSuccess(slot.id, response);
      },
      error: (error) => {
        this.notification.show(error?.error?.detail || 'Failed to update shift slot', 'fail', 5000);
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
        if (status === 'accepted' && this.isGuardOrProvider) {
          this.activeTab = 'jobs';
          this.jobStatusFilter = '';
        }
        if (this.selectedJob?.id === job.id) {
          this.closeJobDrawer();
        }
        if (this.selectedRequest?.viewer_assignment?.id === job.id) {
          this.closeRequestDrawer();
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
      const message = this.reasonRequestSoftDelete ? 'A delete reason is required.' : 'A reason is required.';
      this.reasonErrors['note'] = message;
      this.notification.show(message, 'fail', 4000);
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

    if (this.reasonRequestTarget && this.reasonRequestSoftDelete) {
      const item = this.reasonRequestTarget;
      this.requestService.softDeleteRequest(item.id, note, { loadingScope: this.getRequestStatusScope(item.id) }).subscribe({
        next: (response) => {
          this.notification.show(response.message || 'Request removed from dashboard', 'success', 3500);
          this.closeReasonDrawer();
          if (this.selectedRequest?.id === item.id) {
            this.closeRequestDrawer();
          }
          this.loadRequests(this.page);
        },
        error: (error) => {
          this.notification.show(error?.error?.detail || 'Failed to remove request from dashboard', 'fail', 5000);
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
          if (this.selectedRequest?.viewer_assignment?.id === job.id) {
            this.closeRequestDrawer();
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
        if (this.isGuardOrProvider) {
          this.activeTab = 'jobs';
          this.jobStatusFilter = '';
        }
        if (this.selectedJob?.id === job.id) {
          this.closeJobDrawer();
        }
        if (this.selectedRequest?.viewer_assignment?.id === job.id) {
          this.closeRequestDrawer();
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

  canSoftDeleteRequest(item: ClientRequestItem): boolean {
    return this.isPlatformAdmin && ['draft', 'cancelled', 'closed'].includes(item.request_status);
  }

  canManageRequestSchedule(item: ClientRequestItem | null): boolean {
    if (!item) {
      return false;
    }
    return (
      ['admin', 'ops_admin', 'support_admin', 'compliance_admin'].includes(this.role)
      || this.isClientAdmin
    ) && !['cancelled', 'closed'].includes(item.request_status) && item.staffing_status !== 'expired';
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

  getViewerAssignment(item: ClientRequestItem | null): RequestAssignmentItem | null {
    return item?.viewer_assignment || null;
  }

  getRequestViewerActions(item: ClientRequestItem | null): Array<{ label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' }> {
    const assignment = this.getViewerAssignment(item);
    return assignment ? this.getJobActions(assignment) : [];
  }

  trackByJobActionStatus(
    _index: number,
    action: { label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' },
  ): string {
    return action.status;
  }

  trackByRequestViewerActionStatus(
    _index: number,
    action: { label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' },
  ): string {
    return action.status;
  }

  hasRequestViewerActions(item: ClientRequestItem | null): boolean {
    return this.getRequestViewerActions(item).length > 0;
  }

  updateRequestViewerAssignmentStatus(item: ClientRequestItem, status: RequestAssignmentStatus): void {
    const assignment = this.getViewerAssignment(item);
    if (!assignment) {
      this.notification.show('No active offer is available for this request.', 'fail', 4000);
      return;
    }
    this.updateJobStatus(assignment, status);
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
    if (job.assignment_scope === 'shift_replacement' && ['accepted', 'in_progress', 'completed', 'cancelled'].includes(job.assignment_status)) {
      return [];
    }
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

  getShiftRosterScope(shiftId: string): string {
    return `requests:shift:roster:${shiftId}`;
  }

  getShiftSlotActionScope(slotId: string): string {
    return `requests:shift-slot:${slotId}`;
  }

  getExceptionActionScope(slotId: string): string {
    return `requests:exception:${slotId}`;
  }

  getShiftRequestTitle(shift: ShiftInstanceItem | null): string {
    if (!shift) {
      return 'Shift';
    }
    return this.shiftRequestSummaries[shift.request_id]?.title || `Request ${shift.request_id.slice(0, 8)}`;
  }

  getShiftRequestSiteName(shift: ShiftInstanceItem | null): string {
    if (!shift) {
      return 'Unknown site';
    }
    return this.shiftRequestSummaries[shift.request_id]?.siteName || 'Unknown site';
  }

  getShiftStatusSummary(shift: ShiftInstanceItem): string {
    return `${shift.slots_staffed}/${shift.slots_required} staffed • ${shift.slots_checked_in} checked in • ${shift.slots_completed} completed`;
  }

  getShiftSlotLabel(slot: ShiftSlotItem): string {
    return `Slot ${slot.slot_number}`;
  }

  getShiftSlotReplacementBadges(slot: ShiftSlotItem): Array<{ label: string; className: string }> {
    if (!slot.replacement_of_slot_id) {
      return [];
    }
    return [
      {
        label: 'Replacement Slot',
        className: 'inline-flex rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-300',
      },
    ];
  }

  getShiftSlotCoverageLabel(slot: ShiftSlotItem): string {
    const source = slot.coverage_source_type || 'guard';
    return this.getTargetTypeLabel(source);
  }

  getShiftSlotTenantLabel(slot: ShiftSlotItem): string {
    if (slot.assigned_guard_tenant_id) {
      return slot.assigned_guard_tenant_id;
    }
    if (slot.coverage_tenant_id) {
      return slot.coverage_tenant_id;
    }
    return 'Unassigned';
  }

  getShiftSlotMetaItems(slot: ShiftSlotItem): string[] {
    const items = [
      `Coverage: ${this.getShiftSlotCoverageLabel(slot)}`,
      `Guard / Tenant: ${this.getShiftSlotTenantLabel(slot)}`,
    ];
    if (slot.roster_due_at) {
      items.push(`Roster due ${this.formatBackendDateTime(slot.roster_due_at)}`);
    }
    return items;
  }

  getShiftSlotDetailItems(slot: ShiftSlotItem): string[] {
    const items: string[] = [];
    if (slot.arrived_at) {
      items.push(`Arrived ${this.formatBackendDateTime(slot.arrived_at)}`);
    }
    if (slot.client_confirmed_at) {
      items.push(`Confirmed ${this.formatBackendDateTime(slot.client_confirmed_at)}`);
    }
    if (slot.started_at) {
      items.push(`Started ${this.formatBackendDateTime(slot.started_at)}`);
    }
    if (slot.completed_at) {
      items.push(`Completed ${this.formatBackendDateTime(slot.completed_at)}`);
    }
    return items;
  }

  getRosterSlotMetaItems(slot: ShiftSlotItem): string[] {
    return [`Coverage owner: ${this.getShiftSlotTenantLabel(slot)}`];
  }

  getBulkConfirmSlotMetaItems(slot: ShiftSlotItem): string[] {
    return [
      `Coverage: ${this.getShiftSlotCoverageLabel(slot)}`,
      `Guard / Tenant: ${this.getShiftSlotTenantLabel(slot)}`,
    ];
  }

  getBulkConfirmSlotDetailItems(slot: ShiftSlotItem): string[] {
    return [`Arrived ${slot.arrived_at ? this.formatBackendDateTime(slot.arrived_at) : 'Not recorded'}`];
  }

  isRosterableProviderSlot(slot: ShiftSlotItem): boolean {
    return this.canManageProviderRoster
      && slot.coverage_source_type === 'service_provider'
      && slot.coverage_tenant_id === this.appService.userSessionData()?.tenant?.id
      && ['reserved', 'rostered'].includes(String(slot.slot_status || ''));
  }

  canOpenRosterForSelectedShift(): boolean {
    return this.selectedShiftSlots.some((slot) => this.isRosterableProviderSlot(slot));
  }

  canOpenBulkConfirmForSelectedShift(): boolean {
    return this.selectedShiftSlots.some((slot) => this.canConfirmShiftSlotArrival(slot));
  }

  canReportShiftSlotUnavailable(slot: ShiftSlotItem | null): boolean {
    return this.canManageShiftAttendance
      && Boolean(slot?.assigned_guard_tenant_id)
      && ['reserved', 'rostered'].includes(String(slot?.slot_status || ''))
      && !slot?.started_at;
  }

  canCheckInShiftSlot(slot: ShiftSlotItem | null): boolean {
    return this.canManageShiftAttendance
      && Boolean(slot?.assigned_guard_tenant_id)
      && ['reserved', 'rostered'].includes(String(slot?.slot_status || ''))
      && !slot?.arrived_at
      && !slot?.started_at;
  }

  canConfirmShiftSlotArrival(slot: ShiftSlotItem | null): boolean {
    return this.canConfirmShiftArrivals
      && Boolean(slot?.arrived_at)
      && !slot?.client_confirmed_at
      && !slot?.started_at;
  }

  canStartShiftSlot(slot: ShiftSlotItem | null): boolean {
    return this.canManageShiftAttendance
      && Boolean(slot?.arrived_at)
      && !slot?.started_at
      && (Boolean(slot?.client_confirmed_at) || this.isPlatformAdmin);
  }

  canCheckOutShiftSlot(slot: ShiftSlotItem | null): boolean {
    return this.canManageShiftAttendance
      && String(slot?.slot_status || '') === 'in_progress'
      && Boolean(slot?.started_at);
  }

  canUseBrowserGeolocation(): boolean {
    return typeof navigator !== 'undefined' && 'geolocation' in navigator;
  }

  captureShiftActionLocation(silent = false): void {
    if (this.shiftActionType !== 'check_in') {
      return;
    }

    this.shiftActionLocationError = '';
    this.shiftActionLocationMessage = '';

    if (!this.canUseBrowserGeolocation()) {
      if (!silent) {
        this.shiftActionLocationError = 'Browser geolocation is not available on this device. Enter coordinates manually to continue.';
      }
      return;
    }

    this.capturingShiftActionLocation = true;
    this.shiftActionLocationMessage = silent ? 'Requesting device location...' : 'Fetching current device location...';

    navigator.geolocation.getCurrentPosition(
      (position) => {
        this.capturingShiftActionLocation = false;
        this.shiftActionForm.latitude = position.coords.latitude.toFixed(6);
        this.shiftActionForm.longitude = position.coords.longitude.toFixed(6);
        delete this.shiftActionErrors['latitude'];
        delete this.shiftActionErrors['longitude'];
        this.shiftActionLocationError = '';
        this.shiftActionLocationMessage = 'Current device location captured. You can still adjust the coordinates manually if needed.';
      },
      (error) => {
        this.capturingShiftActionLocation = false;
        this.shiftActionLocationMessage = '';
        this.shiftActionLocationError = this.getGeolocationErrorMessage(error);
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      },
    );
  }

  getGeolocationErrorMessage(error: GeolocationPositionError): string {
    switch (error.code) {
      case error.PERMISSION_DENIED:
        return 'Location access was denied. Allow location access in the browser or enter coordinates manually.';
      case error.POSITION_UNAVAILABLE:
        return 'Current location could not be determined on this device. Enter coordinates manually or try again.';
      case error.TIMEOUT:
        return 'Location request timed out. Try again or enter coordinates manually.';
      default:
        return 'Unable to fetch current device location. Enter coordinates manually or try again.';
    }
  }

  getShiftActionLocationButtonLabel(): string {
    if (this.capturingShiftActionLocation) {
      return 'Locating...';
    }
    return this.shiftActionForm.latitude.trim() && this.shiftActionForm.longitude.trim()
      ? 'Refresh Current Location'
      : 'Use Current Location';
  }

  getShiftSlotPrimaryAction(slot: ShiftSlotItem): { label: string; action: 'report_unavailable' | 'check_in' | 'client_confirm' | 'start' | 'check_out'; type: 'primary' | 'secondary' | 'danger' } | null {
    if (this.canConfirmShiftSlotArrival(slot)) {
      return { label: 'Confirm Arrival', action: 'client_confirm', type: 'primary' };
    }
    if (this.canCheckInShiftSlot(slot)) {
      return { label: 'Check In', action: 'check_in', type: 'primary' };
    }
    if (this.canStartShiftSlot(slot)) {
      return { label: 'Start Shift', action: 'start', type: 'primary' };
    }
    if (this.canCheckOutShiftSlot(slot)) {
      return { label: 'Check Out', action: 'check_out', type: 'primary' };
    }
    if (this.canReportShiftSlotUnavailable(slot)) {
      return { label: 'Report Unavailable', action: 'report_unavailable', type: 'danger' };
    }
    return null;
  }

  getShiftActionDrawerTitle(): string {
    switch (this.shiftActionType) {
      case 'report_unavailable':
        return 'Report Shift Unavailable';
      case 'check_in':
        return 'Check In To Shift';
      case 'client_confirm':
        return 'Confirm Guard Arrival';
      case 'start':
        return 'Start Shift';
      case 'check_out':
        return 'Check Out From Shift';
      default:
        return 'Shift Action';
    }
  }

  getShiftActionDrawerSubtitle(): string {
    const slot = this.shiftActionTarget;
    if (!slot) {
      return 'Update the selected shift slot.';
    }
    const shift = this.selectedShift;
    return `${this.getShiftSlotLabel(slot)} • ${shift ? this.getShiftRequestTitle(shift) : 'Shift slot'}`;
  }

  getShiftActionButtonLabel(): string {
    switch (this.shiftActionType) {
      case 'report_unavailable':
        return 'Report Unavailable';
      case 'check_in':
        return 'Confirm Check-In';
      case 'client_confirm':
        return 'Confirm Arrival';
      case 'start':
        return 'Start Shift';
      case 'check_out':
        return 'Check Out';
      default:
        return 'Submit';
    }
  }

  getShiftActionSuccessMessage(action: 'report_unavailable' | 'check_in' | 'client_confirm' | 'start' | 'check_out'): string {
    switch (action) {
      case 'report_unavailable':
        return 'Shift unavailability reported';
      case 'check_in':
        return 'Shift check-in recorded';
      case 'client_confirm':
        return 'Guard arrival confirmed';
      case 'start':
        return 'Shift started';
      case 'check_out':
        return 'Shift checked out';
      default:
        return 'Shift updated';
    }
  }

  getProviderGuardOptions(): Array<{ label: string; value: string }> {
    return this.providerGuards.map((guard) => ({
      label: `${guard.name || guard.id} • ${guard.email || 'No email'}`,
      value: guard.id,
    }));
  }

  buildRosterAssignmentsForSlots(slots: ShiftSlotItem[]): {
    assignments: ProviderRosterPayload['assignments'];
    guardByPatternKey: Record<string, string>;
  } {
    const assignments: ProviderRosterPayload['assignments'] = [];
    const guardByPatternKey: Record<string, string> = {};

    for (const slot of slots) {
      const guardTenantId = String(this.rosterSelections[slot.id] || '').trim();
      if (!guardTenantId) {
        continue;
      }
      assignments.push({
        slot_id: slot.id,
        guard_tenant_id: guardTenantId,
      });
      guardByPatternKey[this.getRosterPatternKey(slot)] = guardTenantId;
    }

    return { assignments, guardByPatternKey };
  }

  buildRosterPatternAssignments(
    slots: ShiftSlotItem[],
    guardByPatternKey: Record<string, string>,
  ): ProviderRosterPayload['assignments'] {
    return slots
      .filter((slot) => this.isRosterableProviderSlot(slot))
      .map((slot) => {
        const guardTenantId = guardByPatternKey[this.getRosterPatternKey(slot)];
        if (!guardTenantId) {
          return null;
        }
        return {
          slot_id: slot.id,
          guard_tenant_id: guardTenantId,
        };
      })
      .filter((item): item is ProviderRosterPayload['assignments'][number] => Boolean(item));
  }

  getRosterPatternKey(slot: ShiftSlotItem): string {
    return `${slot.parent_assignment_id || 'open'}:${slot.coverage_slot_index || 0}`;
  }

  getRosterPatternPreviewText(): string {
    const count = this.rosterPatternFutureShifts.length;
    if (!count) {
      return 'No future visible shifts are currently available for this request.';
    }
    if (count === 1) {
      return 'This pattern can be copied to 1 future shift in the current generated window.';
    }
    return `This pattern can be copied to ${count} future shifts in the current generated window.`;
  }

  getShiftBulkConfirmScope(shiftId: string): string {
    return `requests:shift:bulk-confirm:${shiftId}`;
  }

  getSelectedBulkConfirmSlotIds(): string[] {
    return this.bulkConfirmShiftSlots
      .filter((slot) => Boolean(this.bulkConfirmSelections[slot.id]))
      .map((slot) => slot.id);
  }

  toggleBulkConfirmSlot(slotId: string, checked: boolean): void {
    this.bulkConfirmSelections = {
      ...this.bulkConfirmSelections,
      [slotId]: checked,
    };
  }

  isBulkConfirmSlotSelected(slotId: string): boolean {
    return Boolean(this.bulkConfirmSelections[slotId]);
  }

  getScheduleTypeLabel(scheduleType: RequestScheduleType | string): string {
    switch (scheduleType) {
      case 'date_range':
        return 'Date Range';
      case 'recurring_weekly':
        return 'Recurring Weekly';
      default:
        return 'One-Time Shift';
    }
  }

  getScheduleDateRangeLabel(schedule: RequestScheduleItem | null): string {
    if (!schedule) {
      return 'Not configured';
    }
    if (schedule.schedule_type === 'one_time') {
      return schedule.start_date || 'Not set';
    }
    return `${schedule.start_date || 'Not set'} to ${schedule.end_date || 'Not set'}`;
  }

  getScheduleTimeWindowLabel(schedule: RequestScheduleItem | null): string {
    if (!schedule) {
      return 'Not configured';
    }
    const suffix = schedule.is_overnight ? ' (overnight)' : '';
    return `${schedule.start_time_local} to ${schedule.end_time_local}${suffix}`;
  }

  getScheduleRecurrenceLabel(schedule: RequestScheduleItem | null): string {
    if (!schedule) {
      return 'No recurrence';
    }
    if (schedule.schedule_type !== 'recurring_weekly') {
      return 'No recurrence';
    }
    if (!schedule.recurrence_days.length) {
      return 'No weekdays selected';
    }
    return schedule.recurrence_days.map((day) => this.formatTokenLabel(day)).join(', ');
  }

  getStartOfMonth(value: Date): Date {
    return new Date(value.getFullYear(), value.getMonth(), 1);
  }

  getEndOfMonth(value: Date): Date {
    return new Date(value.getFullYear(), value.getMonth() + 1, 0);
  }

  addMonths(value: Date, delta: number): Date {
    return new Date(value.getFullYear(), value.getMonth() + delta, 1);
  }

  formatDateInput(value: string | Date | null | undefined): string {
    if (!value) {
      return '';
    }

    if (value instanceof Date) {
      const year = value.getFullYear();
      const month = String(value.getMonth() + 1).padStart(2, '0');
      const day = String(value.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    }

    const normalized = this.formatDateTimeLocalInput(value);
    if (!normalized) {
      return '';
    }
    return normalized.slice(0, 10);
  }

  handleShiftSlotActionSuccess(slotId: string, response: ShiftSlotDetailResponse): void {
    this.selectedShiftSlot = response.slot;
    this.selectedShiftSlotDetail = response;
    this.showShiftSlotDrawer = true;
    if (this.selectedShift?.id === response.slot.shift_instance_id) {
      this.requestService.getShift(response.slot.shift_instance_id, {
        loadingScope: this.shiftDetailScope,
        loadingMode: 'silent',
      }).subscribe({
        next: (shiftResponse) => {
          this.selectedShift = shiftResponse.shift;
          this.selectedShiftSlots = shiftResponse.slots || [];
          this.selectedShiftSlotSummary = shiftResponse.slot_summary || null;
          this.ensureShiftRequestSummaries([shiftResponse.shift]);
        },
        error: () => {}
      });
    } else {
      this.openShiftById(response.slot.shift_instance_id, { silent: true, suppressError: true });
    }
    this.loadShifts(this.shiftPage, { silent: true, suppressError: true });
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
    if (job.assignment_scope === 'shift_replacement') {
      switch (job.assignment_status) {
        case 'accepted':
          return 'This is a shift replacement assignment. Slot execution now moves to shift attendance actions rather than generic job status updates.';
        case 'offered':
          return job.response_due_at
            ? `This is a shift replacement offer for a specific uncovered slot. Review the replacement context before responding. Offer closes at ${this.formatBackendDateTime(job.response_due_at)}.`
            : 'This is a shift replacement offer for a specific uncovered slot. Review the replacement context before responding.';
        case 'reconfirmation_required':
          return 'This replacement offer changed after your earlier acceptance. Review the updated shift context before reconfirming.';
        default:
          break;
      }
    }
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
    if (this.reasonRequestTarget && this.reasonRequestSoftDelete) {
      return 'Remove Request';
    }
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
      if (this.reasonRequestSoftDelete) {
        return `${this.reasonRequestTarget.title} • This will remove the request from dashboard listings without hard deleting it.`;
      }
      return `${this.reasonRequestTarget.title} • Reason is required for this request action`;
    }
    if (this.reasonJobTarget) {
      return `${this.reasonJobTarget.request?.title || 'Request'} • Reason is required for this assignment action`;
    }
    return 'Add the required note to continue.';
  }

  getReasonFieldLabel(): string {
    if (this.reasonRequestSoftDelete) {
      return 'Delete Reason';
    }
    return 'Reason';
  }

  getReasonFieldHelperText(): string {
    if (this.reasonRequestSoftDelete) {
      return 'Explain why this request is being removed from the dashboard. This note will be saved for audit history.';
    }
    return 'This note will be saved with the action for audit and visibility.';
  }

  getReasonDrawerActionLabel(): string {
    if (this.reasonRequestSoftDelete) {
      return 'Confirm Remove';
    }
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

  getExceptionTitle(item: ShiftExceptionItem): string {
    return item.request?.title || 'Shift exception';
  }

  getExceptionSubtitle(item: ShiftExceptionItem): string {
    return `${item.shift?.shift_date_local || 'Shift'} • Slot ${item.slot?.slot_number || 0}`;
  }

  getExceptionGuardLabel(item: ShiftExceptionItem): string {
    if (item.slot?.assigned_guard_tenant_id) {
      return item.slot.assigned_guard_tenant_id;
    }
    if (item.slot?.coverage_tenant_id) {
      return item.slot.coverage_tenant_id;
    }
    return 'Unassigned';
  }

  canReopenException(item: ShiftExceptionItem | null): boolean {
    const status = item?.slot?.slot_status || '';
    return this.canReopenShiftExceptions && ['unavailable', 'late_risk', 'no_show_suspected', 'no_show_confirmed'].includes(status);
  }

  getExceptionSummary(item: ShiftExceptionItem): string {
    const shiftStart = item.shift?.shift_start_at_utc ? this.formatBackendDateTime(item.shift.shift_start_at_utc) : 'Unknown start';
    return `${this.formatTokenLabel(item.slot.slot_status)} • Shift starts ${shiftStart}`;
  }

  getSiteAddressField(item: ClientRequestItem, key: string): string {
    return String(item.site_snapshot?.site_address?.[key] || '');
  }

  getRequestSiteLatitude(item: ClientRequestItem): string {
    const value = item.site_snapshot?.site_address?.latitude;
    return value === null || value === undefined ? '' : String(value);
  }

  getRequestSiteLongitude(item: ClientRequestItem): string {
    const value = item.site_snapshot?.site_address?.longitude;
    return value === null || value === undefined ? '' : String(value);
  }

  getRequestClientTenantLabel(item: Pick<ClientRequestItem, 'client_tenant_id' | 'client_tenant_label'> | null | undefined): string {
    const explicitLabel = String(item?.client_tenant_label || '').trim();
    if (explicitLabel) {
      return explicitLabel;
    }

    const tenantId = String(item?.client_tenant_id || '').trim();
    if (!tenantId) {
      return '';
    }

    return this.requestClientTenantOptions.find((option) => option.value === tenantId)?.label || tenantId;
  }

  get canUseSavedSiteMode(): boolean {
    return this.clientSavedSites.length > 0 || this.requestSiteSourceMode === 'saved';
  }

  get requestClientTenantDisplayValue(): string {
    return this.getRequestClientTenantLabel({
      client_tenant_id: this.selectedRequestClientTenantId,
      client_tenant_label: this.selectedRequestClientTenantLabel,
    });
  }

  get shouldShowInlineScheduleSetup(): boolean {
    return this.requestFormMode !== 'publish_update';
  }

  get requestSiteSourceOptions(): Array<{ value: RequestSiteSourceMode; label: string }> {
    const options: Array<{ value: RequestSiteSourceMode; label: string }> = [
      { value: 'manual', label: 'Manual Site Entry' },
    ];
    if (this.canUseSavedSiteMode) {
      options.unshift({ value: 'saved', label: 'Saved Client Site' });
    }
    return options;
  }

  get savedClientSiteOptions(): Array<{ value: string; label: string }> {
    return this.clientSavedSites.map((site) => {
      const locality = [site.siteAddress.city, site.siteAddress.province].filter(Boolean).join(', ');
      return {
        value: String(site.index),
        label: locality ? `${site.siteName} • ${locality}` : site.siteName,
      };
    });
  }

  get selectedSavedClientSite(): SavedClientSiteRecord | null {
    return this.clientSavedSites.find((site) => String(site.index) === String(this.selectedSavedSiteIndex || '')) || null;
  }

  get requestSitePreview(): {
    siteName: string;
    addressLine: string;
    contactLine: string;
    coordinatesLine: string;
    siteType: string;
    recommendedGuards: string;
  } | null {
    if (this.requestSiteSourceMode !== 'saved') {
      return null;
    }

    const site = this.selectedSavedClientSite;
    const siteName = site?.siteName || this.requestForm.siteName.trim();
    if (!siteName) {
      return null;
    }

    const street = site?.siteAddress.street || this.requestForm.siteStreet.trim();
    const city = site?.siteAddress.city || this.getRequestSiteCityLabel(this.requestForm.siteProvince, this.requestForm.siteCity);
    const province = site?.siteAddress.province || this.getRequestProvinceLabel(this.requestForm.siteProvince);
    const postalCode = site?.siteAddress.postalCode || this.requestForm.sitePostalCode.trim();
    const latitude = site?.siteAddress.latitude || this.requestForm.latitude.trim();
    const longitude = site?.siteAddress.longitude || this.requestForm.longitude.trim();
    const contact = site?.siteManagerContact || this.requestForm.siteManagerContact.trim();
    const email = site?.managerEmail || this.requestForm.managerEmail.trim();
    const siteType = site?.siteType || '';
    const recommendedCount = site?.numberOfGuardsRequired != null ? String(site.numberOfGuardsRequired) : '';

    return {
      siteName,
      addressLine: [street, city, province, postalCode].filter(Boolean).join(' • '),
      contactLine: [contact || 'No site manager contact', email].filter(Boolean).join(' • '),
      coordinatesLine: latitude && longitude ? `${latitude}, ${longitude}` : 'Coordinates unavailable',
      siteType: siteType || 'Not specified',
      recommendedGuards: recommendedCount || 'Not specified',
    };
  }

  onRequestSiteSourceModeChange(nextMode: RequestSiteSourceMode | string): void {
    const normalizedMode = String(nextMode || '').trim().toLowerCase() === 'saved' && this.canUseSavedSiteMode
      ? 'saved'
      : 'manual';
    this.requestSiteSourceMode = normalizedMode;
    delete this.requestErrors['savedSite'];
    delete this.requestErrors['coordinates'];
    delete this.requestErrors['latitude'];
    delete this.requestErrors['longitude'];

    if (normalizedMode === 'saved') {
      if (!this.selectedSavedSiteIndex && this.clientSavedSites.length) {
        this.selectedSavedSiteIndex = String(this.clientSavedSites[0].index);
      }
      const selectedSite = this.selectedSavedClientSite;
      if (selectedSite) {
        this.applySavedSiteToRequestForm(selectedSite);
      }
    }
  }

  onRequestClientTenantChange(nextTenantId: string): void {
    this.selectedRequestClientTenantId = String(nextTenantId || '').trim();
    this.selectedRequestClientTenantLabel = this.requestClientTenantOptions.find((option) => option.value === this.selectedRequestClientTenantId)?.label || '';
    this.requestSiteSourceMode = 'manual';
    this.selectedSavedSiteIndex = '';
    this.clientSavedSites = [];
    this.savedClientSitesMissingGeoCount = 0;
    this.requestForm = {
      ...this.requestForm,
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
    };
    delete this.requestErrors['clientTenant'];
    delete this.requestErrors['savedSite'];
    delete this.requestErrors['siteName'];
    delete this.requestErrors['siteProvince'];
    delete this.requestErrors['siteCity'];
    delete this.requestErrors['managerEmail'];
    delete this.requestErrors['coordinates'];
    delete this.requestErrors['latitude'];
    delete this.requestErrors['longitude'];

    if (!this.selectedRequestClientTenantId) {
      return;
    }

    this.loadClientSites({ silent: true, tenantId: this.selectedRequestClientTenantId });
  }

  onSavedSiteSelectionChange(nextIndex: string): void {
    this.selectedSavedSiteIndex = String(nextIndex || '').trim();
    delete this.requestErrors['savedSite'];
    const selectedSite = this.selectedSavedClientSite;
    if (selectedSite) {
      this.applySavedSiteToRequestForm(selectedSite);
    }
  }

  onRequestScheduleSetupToggle(checked: boolean): void {
    this.requestScheduleSetupEnabled = Boolean(checked);
    this.scheduleErrors = {};
    if (!this.requestScheduleSetupEnabled) {
      return;
    }

    if (!this.selectedRequestSchedule?.id) {
      this.seedInlineScheduleFromRequestForm();
    }
  }

  useFirstShiftTimingForSchedule(): void {
    this.seedInlineScheduleFromRequestForm();
    this.scheduleErrors = {};
  }

  getRequestSiteCityOptions(): { value: string; label: string }[] {
    const provinceCode = String(this.requestForm.siteProvince || '').trim().toUpperCase();
    const canonical = this.canadianCitiesByProvinceOptions[provinceCode] || [];
    const current = String(this.requestForm.siteCity || '').trim();
    if (!current) {
      return canonical;
    }

    const exists = canonical.some((option) => option.value === current);
    if (exists) {
      return canonical;
    }

    return [...canonical, { value: current, label: current }];
  }

  onRequestSiteProvinceChange(nextProvinceCode: string): void {
    this.requestForm.siteProvince = String(nextProvinceCode || '').trim().toUpperCase();
    const options = this.getRequestSiteCityOptions();
    const isCurrentValid = options.some((option) => option.value === this.requestForm.siteCity);
    if (!isCurrentValid) {
      this.requestForm.siteCity = '';
    }
  }

  getRequestProvinceLabel(value: string): string {
    const normalized = String(value || '').trim().toUpperCase();
    if (!normalized) {
      return '';
    }
    return this.provinceOptions.find((option) => option.value === normalized)?.label || String(value || '').trim();
  }

  getRequestSiteCityLabel(provinceCode: string, value: string): string {
    const normalizedProvince = String(provinceCode || '').trim().toUpperCase();
    const normalizedValue = String(value || '').trim().toUpperCase();
    if (!normalizedValue) {
      return '';
    }

    const options = this.canadianCitiesByProvinceOptions[normalizedProvince] || [];
    return options.find((option) => option.value === normalizedValue)?.label || String(value || '').trim();
  }

  resolveProvinceCode(value: string): string {
    const normalized = String(value || '').trim();
    if (!normalized) {
      return '';
    }

    const byValue = this.provinceOptions.find((option) => option.value === normalized.toUpperCase());
    if (byValue) {
      return byValue.value;
    }

    const byLabel = this.provinceOptions.find((option) => option.label.toLowerCase() === normalized.toLowerCase());
    return byLabel?.value || '';
  }

  resolveCityCodeForProvince(provinceCode: string, value: string): string {
    const normalizedProvince = String(provinceCode || '').trim().toUpperCase();
    const normalizedValue = String(value || '').trim();
    if (!normalizedProvince || !normalizedValue) {
      return '';
    }

    const options = this.canadianCitiesByProvinceOptions[normalizedProvince] || [];
    const byValue = options.find((option) => option.value === normalizedValue.toUpperCase());
    if (byValue) {
      return byValue.value;
    }

    const byLabel = options.find((option) => option.label.toLowerCase() === normalizedValue.toLowerCase());
    return byLabel?.value || '';
  }

  parseCoordinate(value: string): number | null {
    const trimmed = String(value || '').trim();
    if (!trimmed) {
      return null;
    }

    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private applySavedSiteToRequestForm(site: SavedClientSiteRecord): void {
    const provinceCode = this.resolveProvinceCode(site.siteAddress.province) || site.siteAddress.province;
    const cityCode = this.resolveCityCodeForProvince(provinceCode, site.siteAddress.city) || site.siteAddress.city;
    this.requestForm = {
      ...this.requestForm,
      siteName: site.siteName,
      siteStreet: site.siteAddress.street,
      siteCity: cityCode,
      siteProvince: provinceCode,
      sitePostalCode: site.siteAddress.postalCode,
      siteCountry: site.siteAddress.country || 'CA',
      siteManagerContact: site.siteManagerContact,
      managerEmail: site.managerEmail,
      googleMapsUrl: site.googleMapsUrl,
      latitude: site.siteAddress.latitude,
      longitude: site.siteAddress.longitude,
    };
  }

  private seedInlineScheduleFromRequestForm(): void {
    const requestedStartAt = this.combineDateAndTime(this.requestForm.requestedStartDate, this.requestForm.requestedStartTime);
    const requestedEndAt = this.combineDateAndTime(this.requestForm.requestedEndDate, this.requestForm.requestedEndTime);
    const startDate = this.formatDateInput(requestedStartAt);
    const startTime = this.formatTimeInput(requestedStartAt);
    const endTime = this.formatTimeInput(requestedEndAt);

    this.scheduleForm = {
      ...this.scheduleForm,
      timezone: this.scheduleForm.timezone || this.getDefaultScheduleTimezone(),
      startDate: startDate || this.scheduleForm.startDate,
      endDate: startDate || this.scheduleForm.endDate,
      startTimeLocal: startTime || this.scheduleForm.startTimeLocal,
      endTimeLocal: endTime || this.scheduleForm.endTimeLocal,
    };
  }

  private combineDateAndTime(dateValue: string | null | undefined, timeValue: string | null | undefined): string {
    const normalizedDate = String(dateValue || '').trim();
    const normalizedTime = String(timeValue || '').trim();
    if (!normalizedDate || !normalizedTime) {
      return '';
    }
    return `${normalizedDate}T${normalizedTime}`;
  }

  private formatTimeInput(value: string | Date | null | undefined): string {
    const normalized = this.formatDateTimeLocalInput(value);
    if (!normalized || normalized.length < 16) {
      return '';
    }
    return normalized.slice(11, 16);
  }

  private formatDateTimeLocalInput(value: string | Date | null | undefined): string {
    if (!value) {
      return '';
    }

    if (value instanceof Date) {
      const year = value.getFullYear();
      const month = String(value.getMonth() + 1).padStart(2, '0');
      const day = String(value.getDate()).padStart(2, '0');
      const hours = String(value.getHours()).padStart(2, '0');
      const minutes = String(value.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    const text = String(value || '').trim();
    if (!text) {
      return '';
    }

    const normalized = text.replace(' ', 'T');
    const match = normalized.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/);
    if (match) {
      return `${match[1]}T${match[2]}:${match[3]}`;
    }

    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) {
      return '';
    }

    return this.formatDateTimeLocalInput(parsed);
  }

  private async validateRequestAddressConsistency(): Promise<boolean> {
    const result = await this.addressConsistencyService.validate({
      latitude: this.requestForm.latitude,
      longitude: this.requestForm.longitude,
      expectedCountryCode: this.requestForm.siteCountry,
      expectedProvinceCode: this.requestForm.siteProvince,
      expectedProvinceName: this.getRequestProvinceLabel(this.requestForm.siteProvince),
      expectedCity: this.getRequestSiteCityLabel(this.requestForm.siteProvince, this.requestForm.siteCity),
      expectedPostalCode: this.requestForm.sitePostalCode,
    });

    if (!result.ok) {
      this.requestErrors['coordinates'] = result.message || 'Site coordinates do not match the manual address.';
      return false;
    }

    return true;
  }

  isValidEmail(value: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || '').trim());
  }

  get paginationPages(): number[] {
    return this.buildPaginationPages(this.page, this.totalPages);
  }

  get jobPaginationPages(): number[] {
    return this.buildPaginationPages(this.jobPage, this.jobTotalPages);
  }

  get reviewPaginationPages(): number[] {
    return this.buildPaginationPages(this.reviewPage, this.reviewTotalPages);
  }

  get shiftPaginationPages(): number[] {
    return this.buildPaginationPages(this.shiftPage, this.shiftTotalPages);
  }

  get exceptionPaginationPages(): number[] {
    return this.buildPaginationPages(this.exceptionPage, this.exceptionTotalPages);
  }

  buildPaginationPages(currentPage: number, totalPages: number): number[] {
    if (totalPages <= 1) {
      return [];
    }
    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }

  trackByWaveId(_index: number, item: RequestBroadcastWaveItem): string {
    return item.id;
  }

  trackByShiftId(_index: number, item: ShiftInstanceItem): string {
    return item.id;
  }

  trackByShiftSlotId(_index: number, item: ShiftSlotItem): string {
    return item.id;
  }

  trackByProviderGuardId(_index: number, item: ServiceProviderGuardSummaryItem): string {
    return item.id;
  }

  trackByExceptionSlotId(_index: number, item: ShiftExceptionItem): string {
    return item.slot.id;
  }
}
