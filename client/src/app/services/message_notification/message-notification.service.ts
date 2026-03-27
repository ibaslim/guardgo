import { Injectable, computed, signal } from '@angular/core';

export type ToastType = 'success' | 'fail' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
  createdAt: number;
}

@Injectable({ providedIn: 'root' })
export class MessageNotificationService {
  private toastsSignal = signal<ToastItem[]>([]);
  private timeouts = new Map<string, ReturnType<typeof setTimeout>>();

  toasts = computed(() => this.toastsSignal());

  // Backward compatibility with legacy single-message API consumers
  message = computed(() => this.toastsSignal()[0]?.message || null);
  type = computed<ToastType>(() => this.toastsSignal()[0]?.type || 'fail');

  show(message: string, type: ToastType = 'fail', duration: number = 3000): string {
    const trimmed = String(message || '').trim();
    if (!trimmed) return '';

    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const toast: ToastItem = {
      id,
      message: trimmed,
      type,
      duration: Math.max(1200, Number(duration) || 3000),
      createdAt: Date.now()
    };

    this.toastsSignal.update((prev) => [toast, ...prev].slice(0, 5));

    const timeout = setTimeout(() => {
      this.dismiss(id);
    }, toast.duration);
    this.timeouts.set(id, timeout);

    return id;
  }

  success(message: string, duration: number = 3000): string {
    return this.show(message, 'success', duration);
  }

  error(message: string, duration: number = 4000): string {
    return this.show(message, 'fail', duration);
  }

  info(message: string, duration: number = 3000): string {
    return this.show(message, 'info', duration);
  }

  warning(message: string, duration: number = 3500): string {
    return this.show(message, 'warning', duration);
  }

  dismiss(id: string): void {
    const handle = this.timeouts.get(id);
    if (handle) {
      clearTimeout(handle);
      this.timeouts.delete(id);
    }
    this.toastsSignal.update((prev) => prev.filter((toast) => toast.id !== id));
  }

  clear(): void {
    this.timeouts.forEach((handle) => clearTimeout(handle));
    this.timeouts.clear();
    this.toastsSignal.set([]);
  }
}
