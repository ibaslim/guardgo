import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { formatBackendDateTime, readableTitle } from '../../shared/helpers/format.helper';
import { ClientRequestItem, RequestAssignmentItem, RequestAssignmentStatus } from '../../shared/model/request/client-request.model';
import { BannerComponent } from '../banner/banner.component';
import { ButtonComponent } from '../button/button.component';
import { CardComponent } from '../card/card.component';
import { SelectInputComponent } from '../form/select-input/select-input.component';
import { SummaryMetricCardComponent } from '../summary-metric-card/summary-metric-card.component';

type RequestInsight = {
  tone: 'info' | 'success' | 'warning' | 'danger' | 'neutral';
  title: string;
  message: string;
};

@Component({
  selector: 'app-request-list-card',
  standalone: true,
  host: {
    class: 'block'
  },
  imports: [
    CommonModule,
    FormsModule,
    BannerComponent,
    ButtonComponent,
    CardComponent,
    SelectInputComponent,
    SummaryMetricCardComponent,
  ],
  templateUrl: './request-list-card.component.html',
})
export class RequestListCardComponent {
  @Input({ required: true }) request!: ClientRequestItem;
  @Input() canEdit = false;
  @Input() canPublishUpdate = false;
  @Input() canRequestAdditionalCoverage = false;
  @Input() canPublish = false;
  @Input() canShowStatusActions = false;
  @Input() canSoftDelete = false;
  @Input() canShowAssignmentActions = false;
  @Input() selectedCandidateId = '';
  @Input() candidateOptions: Array<{ label: string; value: string }> = [];
  @Input() requestStatusScope = '';
  @Input() assignScope = '';
  @Input() showClientTenant = false;
  @Input() clientTenantLabel = '';
  @Input() viewerAssignment: RequestAssignmentItem | null = null;
  @Input() viewerAssignmentActions: Array<{ label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' }> = [];
  @Input() viewerAssignmentLoadingScope = '';

  @Output() selectedCandidateIdChange = new EventEmitter<string>();
  @Output() details = new EventEmitter<void>();
  @Output() edit = new EventEmitter<void>();
  @Output() publishUpdate = new EventEmitter<void>();
  @Output() requestAdditionalCoverage = new EventEmitter<void>();
  @Output() publish = new EventEmitter<void>();
  @Output() cancel = new EventEmitter<void>();
  @Output() close = new EventEmitter<void>();
  @Output() softDelete = new EventEmitter<void>();
  @Output() assign = new EventEmitter<void>();
  @Output() viewerAssignmentAction = new EventEmitter<RequestAssignmentStatus>();

  readonly statCardContainerClass =
    'rounded-xl border border-slate-200/80 bg-slate-50/95 px-4 py-3 shadow-sm dark:border-slate-700/80 dark:bg-slate-900/70';
  readonly statCardValueClass = 'mt-1 text-sm font-semibold text-gray-900 dark:text-gray-100';
  readonly miniMetricContainerClass =
    'rounded-lg border border-slate-200/80 bg-white/90 px-3 py-2 dark:border-slate-700/80 dark:bg-slate-950/80';
  readonly miniMetricLabelClass =
    'text-[10px] font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-gray-500';
  readonly miniMetricValueClass = 'mt-1 text-base font-semibold text-gray-900 dark:text-gray-100';

  readonly formatBackendDateTime = formatBackendDateTime;

  get statusClass(): string {
    return this.getStatusClasses(this.request?.request_status || '');
  }

  get cardContainerClass(): string {
    return 'overflow-hidden rounded-[1.35rem] border border-slate-200/80 bg-white shadow-[0_14px_34px_rgba(15,23,42,0.08)] ring-1 ring-slate-200/70 dark:border-slate-800 dark:bg-slate-950 dark:ring-slate-800';
  }

  get headerSurfaceClass(): string {
    switch (this.visualTone) {
      case 'success':
        return 'rounded-2xl border border-emerald-200/80 bg-emerald-50/80 p-4 dark:border-emerald-900/40 dark:bg-emerald-950/20';
      case 'warning':
        return 'rounded-2xl border border-amber-200/80 bg-amber-50/80 p-4 dark:border-amber-900/40 dark:bg-amber-950/20';
      case 'danger':
        return 'rounded-2xl border border-rose-200/80 bg-rose-50/80 p-4 dark:border-rose-900/40 dark:bg-rose-950/20';
      case 'neutral':
        return 'rounded-2xl border border-slate-200/80 bg-slate-50/90 p-4 dark:border-slate-800 dark:bg-slate-900/70';
      default:
        return 'rounded-2xl border border-sky-200/80 bg-sky-50/75 p-4 dark:border-sky-900/40 dark:bg-sky-950/20';
    }
  }

  get progressSurfaceClass(): string {
    return 'rounded-2xl border border-slate-200/80 bg-slate-50/85 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/75';
  }

  get actionSurfaceClass(): string {
    switch (this.visualTone) {
      case 'success':
        return 'rounded-2xl border border-emerald-200/80 bg-white p-4 shadow-sm dark:border-emerald-900/40 dark:bg-slate-900';
      case 'warning':
        return 'rounded-2xl border border-amber-200/80 bg-white p-4 shadow-sm dark:border-amber-900/40 dark:bg-slate-900';
      case 'danger':
        return 'rounded-2xl border border-rose-200/80 bg-white p-4 shadow-sm dark:border-rose-900/40 dark:bg-slate-900';
      case 'neutral':
        return 'rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900';
      default:
        return 'rounded-2xl border border-sky-200/80 bg-white p-4 shadow-sm dark:border-sky-900/40 dark:bg-slate-900';
    }
  }

  get manualAssignmentPanelClass(): string {
    switch (this.visualTone) {
      case 'warning':
        return 'rounded-2xl border border-amber-200/80 bg-amber-50/80 p-4 dark:border-amber-900/40 dark:bg-amber-950/20';
      case 'danger':
        return 'rounded-2xl border border-rose-200/80 bg-rose-50/75 p-4 dark:border-rose-900/40 dark:bg-rose-950/20';
      default:
        return 'rounded-2xl border border-blue-200/80 bg-blue-50/75 p-4 dark:border-blue-900/40 dark:bg-blue-950/20';
    }
  }

  get staffingStatusClass(): string {
    const staffingStatus = this.request?.staffing_status || '';
    if (!staffingStatus) {
      return '';
    }
    switch (staffingStatus) {
      case 'filled':
        return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300';
      case 'expired':
      case 'review_returned':
        return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
      case 'pending_review':
      case 'partially_filled':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300';
      default:
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    }
  }

  get fulfillmentLabel(): string {
    switch (this.request?.fulfillment_mode) {
      case 'service_provider_only':
        return 'Service Providers';
      case 'hybrid':
        return 'Hybrid Coverage';
      default:
        return 'Individual Guards';
    }
  }

  get coverageAccepted(): number {
    const explicitAccepted = Number(this.request?.accepted_slots);
    if (Number.isFinite(explicitAccepted) && explicitAccepted >= 0) {
      return explicitAccepted;
    }
    const required = this.coverageRequired;
    const open = Number(this.request?.open_slots);
    if (Number.isFinite(open) && open >= 0) {
      return Math.max(0, required - open);
    }
    return 0;
  }

  get coverageRequired(): number {
    return Math.max(0, Number(this.request?.guards_required || 0));
  }

  get coverageOpen(): number {
    const open = Number(this.request?.open_slots);
    if (Number.isFinite(open) && open >= 0) {
      return open;
    }
    return Math.max(0, this.coverageRequired - this.coverageAccepted);
  }

  get coveragePercent(): number {
    if (this.coverageRequired <= 0) {
      return 0;
    }
    return Math.min(100, Math.round((this.coverageAccepted / this.coverageRequired) * 100));
  }

  get coverageSummaryValue(): string {
    return `${this.coverageAccepted}/${this.coverageRequired} accepted`;
  }

  get coverageHelperText(): string {
    return `${this.coverageOpen} open slot${this.coverageOpen === 1 ? '' : 's'} remaining`;
  }

  get requestedWindowLabel(): string {
    const start = this.request?.requested_start_at;
    const end = this.request?.requested_end_at;
    if (start && end) {
      if (this.isSameCalendarDate(start, end)) {
        return `${this.formatDisplayDate(start)} to ${this.formatDisplayTime(end)}`;
      }
      return `${this.formatDisplayDate(start)} to ${this.formatDisplayDate(end)}`;
    }
    if (start) {
      return `Starts ${this.formatDisplayDate(start)}`;
    }
    if (end) {
      return `Ends ${this.formatDisplayDate(end)}`;
    }
    return 'Window not set';
  }

  get requestedWindowHelperText(): string {
    return this.request?.requested_guard_type || 'Guard type not specified';
  }

  get titleSupportingLabel(): string {
    return this.request?.requested_guard_type || '';
  }

  get expiryLabel(): string {
    return this.request?.request_expires_at ? this.formatDisplayDate(this.request.request_expires_at) : 'No expiry set';
  }

  get expiryHelperText(): string {
    if (this.request?.staffing_status === 'expired') {
      return 'Request is read-only';
    }
    if (this.request?.lock_reason === 'filled') {
      return 'All vacancies are currently covered';
    }
    return this.request?.published_at ? `Published ${formatBackendDateTime(this.request.published_at)}` : 'Not published yet';
  }

  get siteValue(): string {
    return this.request?.site_snapshot?.site_name || 'Unnamed site';
  }

  get siteHelperText(): string {
    const city = this.request?.site_snapshot?.site_address?.city;
    const province = this.request?.site_snapshot?.site_address?.province;
    const parts = [city, province].filter(Boolean);
    return parts.length ? parts.join(', ') : 'Address details pending';
  }

  get insight(): RequestInsight | null {
    if (!this.request) {
      return null;
    }
    if (this.request.request_status === 'draft') {
      return {
        tone: 'neutral',
        title: 'Draft Request',
        message: 'Review the request details, timing, and site information before publishing it to candidates.',
      };
    }
    if (this.request.staffing_status === 'pending_review') {
      return {
        tone: 'info',
        title: 'Awaiting Platform Review',
        message: 'This request is published, but the broadcast is being held until a platform admin approves it.',
      };
    }
    if (this.request.staffing_status === 'review_returned') {
      return {
        tone: 'warning',
        title: 'Client Update Required',
        message: 'The last broadcast wave was returned for changes. Update the request details and publish again.',
      };
    }
    if (this.request.staffing_status === 'expired') {
      return {
        tone: 'danger',
        title: 'Request Expired',
        message: 'The request deadline has passed. Existing accepted work can continue, but no new waves can be issued.',
      };
    }
    if (this.request.staffing_status === 'filled') {
      return {
        tone: 'success',
        title: 'Coverage Filled',
        message: 'All currently required slots are covered. Keep this request open only if more coverage may be needed later.',
      };
    }
    if (this.request.staffing_status === 'partially_filled') {
      return {
        tone: 'info',
        title: 'Still Staffing',
        message: `${this.coverageOpen} slot${this.coverageOpen === 1 ? '' : 's'} remain open. You can issue additional coverage without disrupting accepted work.`,
      };
    }
    if (this.request.request_status === 'in_progress') {
      return {
        tone: 'info',
        title: 'Active Operations',
        message: 'Accepted coverage has moved into live shift operations. Use the Shifts tab for attendance and exception handling.',
      };
    }
    return null;
  }

  get insightContainerClass(): string {
    if (this.request?.request_status === 'draft') {
      return 'mt-2 rounded-2xl px-4 py-3';
    }
    return 'rounded-2xl px-4 py-3';
  }

  get primaryActionLabel(): string {
    if (this.canPublish) {
      return 'Publish';
    }
    if (this.canPublishUpdate) {
      return 'Publish Update';
    }
    if (this.canRequestAdditionalCoverage) {
      return 'Add Coverage';
    }
    return '';
  }

  get primaryActionType(): 'primary' | 'secondary' {
    return this.canPublish ? 'primary' : 'secondary';
  }

  get showPrimaryAction(): boolean {
    return Boolean(this.primaryActionLabel);
  }

  get visualTone(): RequestInsight['tone'] {
    if (this.request?.staffing_status === 'filled' || this.request?.request_status === 'closed') {
      return 'success';
    }
    if (this.request?.staffing_status === 'expired' || this.request?.staffing_status === 'review_returned' || this.request?.request_status === 'cancelled') {
      return 'danger';
    }
    if (this.request?.staffing_status === 'pending_review' || this.request?.staffing_status === 'partially_filled' || this.request?.request_status === 'in_progress') {
      return 'warning';
    }
    if (this.request?.request_status === 'draft') {
      return 'neutral';
    }
    return 'info';
  }

  get showSecondaryCoverageAction(): boolean {
    return this.canRequestAdditionalCoverage && !this.showCoverageAsPrimary;
  }

  get hasViewerAssignmentActions(): boolean {
    return Array.isArray(this.viewerAssignmentActions) && this.viewerAssignmentActions.length > 0;
  }

  get showCoverageAsPrimary(): boolean {
    return !this.canPublish && !this.canPublishUpdate && this.canRequestAdditionalCoverage;
  }

  get eligibleMatchCount(): number {
    return this.getMatchCount('eligible_count');
  }

  get missingGeoCount(): number {
    return this.getMatchCount('missing_geo_count');
  }

  get outsideRadiusCount(): number {
    return this.getMatchCount('outside_radius_count');
  }

  get hasManualAssignmentPanel(): boolean {
    return this.canShowAssignmentActions && this.candidateOptions.length > 0;
  }

  emitPrimaryAction(): void {
    if (this.canPublish) {
      this.publish.emit();
      return;
    }
    if (this.canPublishUpdate) {
      this.publishUpdate.emit();
      return;
    }
    if (this.canRequestAdditionalCoverage) {
      this.requestAdditionalCoverage.emit();
    }
  }

  onCandidateSelectionChange(value: string): void {
    this.selectedCandidateIdChange.emit(value);
  }

  onViewerAssignmentAction(status: RequestAssignmentStatus): void {
    this.viewerAssignmentAction.emit(status);
  }

  trackByViewerAssignmentActionStatus(
    _index: number,
    action: { label: string; status: RequestAssignmentStatus; type: 'primary' | 'secondary' | 'danger' },
  ): string {
    return action.status;
  }

  formatTokenLabel(value: string): string {
    return readableTitle(String(value || '').trim());
  }

  formatDisplayDate(value?: string | null): string {
    return value ? formatBackendDateTime(value) : '-';
  }

  formatDisplayTime(value?: string | null): string {
    if (!value) {
      return '-';
    }

    const dateObj = new Date(value);
    if (Number.isNaN(dateObj.getTime())) {
      return '-';
    }

    return new Intl.DateTimeFormat('en-CA', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(dateObj);
  }

  private isSameCalendarDate(startValue: string, endValue: string): boolean {
    const start = new Date(startValue);
    const end = new Date(endValue);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return false;
    }

    return start.getFullYear() === end.getFullYear()
      && start.getMonth() === end.getMonth()
      && start.getDate() === end.getDate();
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

  private getMatchCount(key: 'eligible_count' | 'missing_geo_count' | 'outside_radius_count'): number {
    return Number(this.request?.match_summary?.[key] || 0);
  }
}
