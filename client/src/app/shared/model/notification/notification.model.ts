export type NotificationCategory = 'info' | 'success' | 'warning' | 'error';

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  category: NotificationCategory | string;
  source_module?: string | null;
  action_url?: string | null;
  action_label?: string | null;
  metadata?: Record<string, any>;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  pagination: {
    page: number;
    rows: number;
    total_items: number;
    total_pages: number;
  };
  filters: {
    status: string;
  };
  unread_count: number;
}

export interface LatestNotificationResponse {
  items: NotificationItem[];
  unread_count: number;
}
