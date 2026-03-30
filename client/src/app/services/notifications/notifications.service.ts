import { Injectable, signal } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { ApiService } from '../../shared/services/api.service';
import { LatestNotificationResponse, NotificationItem, NotificationListResponse } from '../../shared/model/notification/notification.model';

@Injectable({ providedIn: 'root' })
export class NotificationsService {
  readonly latestItems = signal<NotificationItem[]>([]);
  readonly unreadCount = signal<number>(0);
  readonly latestLoading = signal<boolean>(false);
  readonly pageLoading = signal<boolean>(false);

  constructor(private api: ApiService) {}

  loadLatest(limit = 5): Observable<LatestNotificationResponse> {
    this.latestLoading.set(true);
    const params = new HttpParams().set('limit', limit);
    return this.api.get<LatestNotificationResponse>('notifications/latest', { params }).pipe(
      tap({
        next: (response) => {
          this.latestItems.set(response.items || []);
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

    return this.api.get<NotificationListResponse>('notifications', { params }).pipe(
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
    return this.api.get<{ unread_count: number }>('notifications/unread-count').pipe(
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
    return this.api.patch<{ message: string; unread_count: number }>('notifications/read-all').pipe(
      tap((response) => {
        this.latestItems.update((items) => items.map((item) => ({ ...item, is_read: true, read_at: item.read_at || new Date().toISOString() })));
        this.unreadCount.set(Number(response.unread_count || 0));
      })
    );
  }
}
