import { Injectable, computed, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class LoadingFeedbackService {
  private readonly activeRequestCount = signal(0);
  private readonly activeScopes = signal<Record<string, number>>({});
  private readonly visible = signal(false);

  private showTimer: ReturnType<typeof setTimeout> | null = null;
  private hideTimer: ReturnType<typeof setTimeout> | null = null;
  private lastShownAt = 0;

  readonly isVisible = computed(() => this.visible());
  readonly hasActiveRequests = computed(() => this.activeRequestCount() > 0);

  begin(mode: 'global' | 'silent', scope = ''): void {
    this.updateScope(scope, 1);

    if (mode === 'silent') {
      return;
    }

    this.activeRequestCount.update(count => count + 1);
    this.scheduleShow();
  }

  end(mode: 'global' | 'silent', scope = ''): void {
    this.updateScope(scope, -1);

    if (mode === 'silent') {
      return;
    }

    this.activeRequestCount.update(count => Math.max(0, count - 1));
    this.scheduleHide();
  }

  isScopeLoading(scope: string): boolean {
    return (this.activeScopes()[scope] || 0) > 0;
  }

  private updateScope(scope: string, delta: number): void {
    if (!scope) {
      return;
    }

    this.activeScopes.update(current => {
      const next = { ...current };
      const updated = Math.max(0, (next[scope] || 0) + delta);
      if (updated === 0) {
        delete next[scope];
      } else {
        next[scope] = updated;
      }
      return next;
    });
  }

  private scheduleShow(): void {
    if (this.visible()) {
      return;
    }
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
    if (this.showTimer) {
      return;
    }

    this.showTimer = setTimeout(() => {
      this.showTimer = null;
      if (this.activeRequestCount() > 0) {
        this.lastShownAt = Date.now();
        this.visible.set(true);
      }
    }, 120);
  }

  private scheduleHide(): void {
    if (this.activeRequestCount() > 0) {
      return;
    }
    if (this.showTimer) {
      clearTimeout(this.showTimer);
      this.showTimer = null;
    }
    if (!this.visible()) {
      return;
    }
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
    }

    const elapsed = Date.now() - this.lastShownAt;
    const remaining = Math.max(0, 320 - elapsed);
    this.hideTimer = setTimeout(() => {
      this.hideTimer = null;
      if (this.activeRequestCount() === 0) {
        this.visible.set(false);
      }
    }, remaining);
  }
}
