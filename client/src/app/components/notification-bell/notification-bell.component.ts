import { CommonModule } from '@angular/common';
import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { Router, RouterModule } from '@angular/router';
import { Subscription, interval } from 'rxjs';

import { IconComponent } from '../icon/icon.component';
import { NotificationsService } from '../../services/notifications/notifications.service';
import { NotificationItem } from '../../shared/model/notification/notification.model';
import { AppService } from '../../services/core/app/app.service';
import { ButtonComponent } from '../button/button.component';

@Component({
  selector: 'app-notification-bell',
  standalone: true,
  imports: [CommonModule, RouterModule, IconComponent, ButtonComponent],
  templateUrl: './notification-bell.component.html'
})
export class NotificationBellComponent implements OnInit, OnDestroy {
  isOpen = false;
  private refreshSubscription: Subscription | null = null;

  constructor(
    protected notificationsService: NotificationsService,
    protected appService: AppService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    if (!this.canUseNotifications()) return;
    this.notificationsService.loadLatest(6).subscribe();
    this.refreshSubscription = interval(10000).subscribe(() => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      this.notificationsService.loadLatest(6).subscribe();
    });
  }

  ngOnDestroy(): void {
    this.refreshSubscription?.unsubscribe();
    this.refreshSubscription = null;
  }

  toggleMenu(event: MouseEvent): void {
    if (!this.canUseNotifications()) return;
    event.stopPropagation();
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.notificationsService.loadLatest(6).subscribe();
    }
  }

  closeMenu(): void {
    this.isOpen = false;
  }

  @HostListener('document:mousedown', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.notification-bell-container')) {
      this.closeMenu();
    }
  }

  onOpenNotification(item: NotificationItem, event?: MouseEvent): void {
    event?.stopPropagation();
    const navigate = () => {
      if (item.action_url) {
        this.router.navigateByUrl(item.action_url).then();
      } else {
        this.router.navigate(['/dashboard/notifications']).then();
      }
      this.closeMenu();
    };

    if (!item.is_read) {
      this.notificationsService.markAsRead(item.id).subscribe({ next: () => navigate(), error: () => navigate() });
      return;
    }

    navigate();
  }

  markAllRead(event: Event): void {
    if (!this.canUseNotifications()) return;
    event.stopPropagation();
    this.notificationsService.markAllRead().subscribe();
  }

  viewAll(event: MouseEvent): void {
    event.stopPropagation();
    this.router.navigate(['/dashboard/notifications']).then(() => this.closeMenu());
  }

  trackById(_index: number, item: NotificationItem): string {
    return item.id;
  }

  getCategoryClasses(category: string): string {
    switch ((category || '').toLowerCase()) {
      case 'success':
        return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300';
      case 'warning':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300';
      case 'error':
        return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300';
      default:
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300';
    }
  }

  formatRelativeDate(value: string): string {
    const date = new Date(value);
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.max(1, Math.floor(diffMs / 60000));
    if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    }
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) {
      return `${diffHours}h ago`;
    }
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) {
      return `${diffDays}d ago`;
    }
    return date.toLocaleDateString();
  }

  private canUseNotifications(): boolean {
    const roleRaw = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = roleRaw.includes('.') ? (roleRaw.split('.').pop() || '') : roleRaw;
    const tenantStatus = String(this.appService.userSessionData()?.tenant?.status || '').trim().toLowerCase();
    const tenantAdminRoles = new Set(['guard_admin', 'client_admin', 'sp_admin']);
    if (!tenantAdminRoles.has(role)) return true;
    return tenantStatus === 'active';
  }
}
