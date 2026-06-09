import { Injectable, signal } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { ApiService } from '../../shared/services/api.service';
import { LatestNotificationResponse, NotificationItem, NotificationListResponse } from '../../shared/model/notification/notification.model';
import { MessageNotificationService, ToastType } from '../message_notification/message-notification.service';

@Injectable({ providedIn: 'root' })
export class NotificationsService {
  readonly latestScope = 'notifications:latest';
  readonly pageScope = 'notifications:page';
  readonly markAllScope = 'notifications:mark-all';

  readonly latestItems = signal<NotificationItem[]>([]);
  readonly unreadCount = signal<number>(0);
  readonly latestLoading = signal<boolean>(false);
  readonly pageLoading = signal<boolean>(false);
  private hasInitializedLatest = false;
  private readonly seenNotificationIds = new Set<string>();

  constructor(
    private api: ApiService,
    private messageNotification: MessageNotificationService,
  ) {}

  loadLatest(limit = 5): Observable<LatestNotificationResponse> {
    this.latestLoading.set(true);
    const params = new HttpParams().set('limit', limit);
    return this.api.get<LatestNotificationResponse>('notifications/latest', { params, loadingMode: 'silent', loadingScope: this.latestScope }).pipe(
      tap({
        next: (response) => {
          const nextItems = response.items || [];
          this.maybeShowLiveNotificationToasts(nextItems);
          this.latestItems.set(nextItems);
          this.unreadCount.set(Number(response.unread_count || 0));
          this.latestLoading.set(false);
        },
        error: () => {
          this.latestLoading.set(false);
        }
      })
    );
  }

  loadPage(page = 1, rows = 20, status = 'all'): Observable<NotificationListResponse> {
    this.pageLoading.set(true);
    const params = new HttpParams()
      .set('page', page)
      .set('rows', rows)
      .set('status', status);

    return this.api.get<NotificationListResponse>('notifications', { params, loadingScope: this.pageScope }).pipe(
      tap({
        next: (response) => {
          this.unreadCount.set(Number(response.unread_count || 0));
          this.pageLoading.set(false);
        },
        error: () => {
          this.pageLoading.set(false);
        }
      })
    );
  }

  refreshUnreadCount(): Observable<{ unread_count: number }> {
    return this.api.get<{ unread_count: number }>('notifications/unread-count', { loadingMode: 'silent' }).pipe(
      tap((response) => {
        this.unreadCount.set(Number(response.unread_count || 0));
      })
    );
  }

  markAsRead(notificationId: string): Observable<{ message: string; item: NotificationItem }> {
    return this.api.patch<{ message: string; item: NotificationItem }>(`notifications/${notificationId}/read`).pipe(
      tap((response) => {
        const updatedItem = response.item;
        this.latestItems.update((items) => items.map((item) => item.id === updatedItem.id ? updatedItem : item));
        this.unreadCount.update((count) => Math.max(0, updatedItem.is_read ? count - 1 : count));
      })
    );
  }

  markAllRead(): Observable<{ message: string; unread_count: number }> {
    return this.api.patch<{ message: string; unread_count: number }>('notifications/read-all', undefined, { loadingScope: this.markAllScope }).pipe(
      tap((response) => {
        this.latestItems.update((items) => items.map((item) => ({ ...item, is_read: true, read_at: item.read_at || new Date().toISOString() })));
        this.unreadCount.set(Number(response.unread_count || 0));
      })
    );
  }

  private maybeShowLiveNotificationToasts(items: NotificationItem[]): void {
    const normalizedItems = Array.isArray(items) ? items : [];
    const unseenUnreadItems = normalizedItems.filter((item) => {
      const id = String(item?.id || '').trim();
      return Boolean(id) && !item.is_read && !this.seenNotificationIds.has(id);
    });

    for (const item of normalizedItems) {
      const id = String(item?.id || '').trim();
      if (id) {
        this.seenNotificationIds.add(id);
      }
    }

    if (!this.hasInitializedLatest) {
      this.hasInitializedLatest = true;
      return;
    }

    unseenUnreadItems
      .slice(0, 2)
      .reverse()
      .forEach((item) => {
        this.messageNotification.show(
          item.title || item.message || 'New notification received',
          this.toToastType(item.category),
          4500,
        );
      });
  }

  private toToastType(category: string): ToastType {
    switch (String(category || '').trim().toLowerCase()) {
      case 'success':
        return 'success';
      case 'warning':
        return 'warning';
      case 'error':
        return 'fail';
      default:
        return 'info';
    }
  }
}
