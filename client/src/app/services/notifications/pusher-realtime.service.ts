import { Injectable } from '@angular/core';
import Pusher from 'pusher-js';
import type { Channel } from 'pusher-js';
import { BehaviorSubject, Subject } from 'rxjs';

import { ApiService } from '../../shared/services/api.service';
import { PUSHER_CONFIG } from '../../config/pusher.config';

export interface PusherNotificationEvent {
  id: string;
  source_module?: string | null;
  event_type: 'created' | 'updated' | 'read-all';
}

@Injectable({ providedIn: 'root' })
export class PusherRealtimeService {
  private client: Pusher | null = null;
  private channel: Channel | null = null;
  private channelRequestPending = false;
  private lifecycleVersion = 0;
  private readonly notificationEvents = new Subject<PusherNotificationEvent>();
  private readonly subscriptionRestored = new Subject<void>();
  private readonly connectionState = new BehaviorSubject<boolean>(false);

  readonly notificationEvents$ = this.notificationEvents.asObservable();
  readonly subscriptionRestored$ = this.subscriptionRestored.asObservable();
  readonly connectionState$ = this.connectionState.asObservable();

  constructor(private api: ApiService) {}

  isConfigured(): boolean {
    return Boolean(PUSHER_CONFIG.key.trim() && PUSHER_CONFIG.cluster.trim());
  }

  isConnected(): boolean {
    return this.connectionState.value;
  }

  start(): void {
    if (!this.isConfigured() || this.client || this.channelRequestPending) return;

    const lifecycleVersion = this.lifecycleVersion;
    this.channelRequestPending = true;
    this.api.get<{ channel_name: string }>('pusher/channel', { loadingMode: 'silent' }).subscribe({
      next: ({ channel_name }) => {
        if (lifecycleVersion !== this.lifecycleVersion) return;
        this.channelRequestPending = false;
        if (!channel_name || this.client) return;

        this.client = new Pusher(PUSHER_CONFIG.key, {
          cluster: PUSHER_CONFIG.cluster,
          channelAuthorization: {
            endpoint: '/api/pusher/auth',
            transport: 'ajax',
            headersProvider: () => {
              const token = localStorage.getItem('token');
              return token ? { Authorization: `Bearer ${token}` } : {};
            },
          },
        });

        this.client.connection.bind('state_change', (states: { current: string }) => {
          if (states.current !== 'connected') {
            this.connectionState.next(false);
          }
        });

        this.channel = this.client.subscribe(channel_name);
        this.channel.bind('notification-created', (event: Omit<PusherNotificationEvent, 'event_type'>) => {
          this.notificationEvents.next({ ...event, event_type: 'created' });
        });
        this.channel.bind('notification-updated', (event: Omit<PusherNotificationEvent, 'event_type'>) => {
          this.notificationEvents.next({ ...event, event_type: 'updated' });
        });
        this.channel.bind('notifications-read-all', () => {
          this.notificationEvents.next({ id: '', event_type: 'read-all' });
        });
        this.channel.bind('pusher:subscription_succeeded', () => {
          this.connectionState.next(true);
          // Refresh after reconnect so persisted events missed while offline are recovered.
          this.subscriptionRestored.next();
        });
        this.channel.bind('pusher:subscription_error', () => this.connectionState.next(false));
      },
      error: () => {
        if (lifecycleVersion !== this.lifecycleVersion) return;
        this.channelRequestPending = false;
      },
    });
  }

  stop(): void {
    this.lifecycleVersion += 1;
    if (this.channel) {
      this.channel.unbind_all();
      this.client?.unsubscribe(this.channel.name);
      this.channel = null;
    }
    this.client?.disconnect();
    this.client = null;
    this.channelRequestPending = false;
    this.connectionState.next(false);
  }
}
