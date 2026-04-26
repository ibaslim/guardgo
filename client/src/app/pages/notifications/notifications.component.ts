import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import { CardComponent } from '../../components/card/card.component';
import { ButtonComponent } from '../../components/button/button.component';
import { IconComponent } from '../../components/icon/icon.component';
import { PageComponent } from '../../components/page/page.component';
import { NotificationsService } from '../../services/notifications/notifications.service';
import { NotificationItem, NotificationListResponse } from '../../shared/model/notification/notification.model';
import { MessageNotificationService } from '../../services/message_notification/message-notification.service';

@Component({
  selector: 'app-notifications-page',
  standalone: true,
  imports: [CommonModule, PageComponent, CardComponent, ButtonComponent, IconComponent],
  templateUrl: './notifications.component.html'
})
export class NotificationsComponent implements OnInit {
  items: NotificationItem[] = [];
  currentPage = 1;
  rows = 12;
  totalPages = 0;
  totalItems = 0;
  selectedStatus: 'all' | 'unread' | 'read' = 'all';

  constructor(
    protected notificationsService: NotificationsService,
    private messageNotification: MessageNotificationService,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.loadNotifications();
  }

  loadNotifications(page = this.currentPage): void {
    this.currentPage = page;
    this.notificationsService.loadPage(this.currentPage, this.rows, this.selectedStatus).subscribe({
      next: (response: NotificationListResponse) => {
        this.items = response.items || [];
        this.totalPages = Number(response.pagination?.total_pages || 0);
        this.totalItems = Number(response.pagination?.total_items || 0);
        this.notificationsService.loadLatest(6).subscribe();
      },
      error: (error) => {
        this.messageNotification.show(error?.error?.detail || 'Failed to load notifications', 'fail', 5000);
      }
    });
  }

  setStatusFilter(status: 'all' | 'unread' | 'read'): void {
    if (this.selectedStatus === status) {
      return;
    }
    this.selectedStatus = status;
    this.loadNotifications(1);
  }

  markAllRead(): void {
    this.notificationsService.markAllRead().subscribe({
      next: () => {
        this.messageNotification.show('All notifications marked as read', 'success', 3000);
        this.loadNotifications(this.currentPage);
      },
      error: (error) => {
        this.messageNotification.show(error?.error?.detail || 'Failed to mark notifications as read', 'fail', 5000);
      }
    });
  }

  openNotification(item: NotificationItem): void {
    const navigate = () => {
      if (item.action_url) {
        this.router.navigateByUrl(item.action_url).then();
      }
    };

    if (!item.is_read) {
      this.notificationsService.markAsRead(item.id).subscribe({
        next: () => {
          this.items = this.items.map((entry) => entry.id === item.id ? { ...entry, is_read: true, read_at: new Date().toISOString() } : entry);
          navigate();
        },
        error: () => navigate(),
      });
      return;
    }

    navigate();
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

  formatDisplayDate(value: string): string {
    return new Date(value).toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
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

  get paginationWindow(): number[] {
    if (this.totalPages <= 1) {
      return [];
    }
    const start = Math.max(1, this.currentPage - 2);
    const end = Math.min(this.totalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }
}
