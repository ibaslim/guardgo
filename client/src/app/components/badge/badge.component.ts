import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-badge',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './badge.component.html'
})
export class BadgeComponent {
  @Input() color?: 'primary' | 'secondary' | 'success' | 'danger' | 'warning';
  @Input() label = '';

  private keywordMap(): { [key: string]: ('primary' | 'secondary' | 'success' | 'danger' | 'warning') } {
    return {
      // success-like
      active: 'success',
      enabled: 'success',
      verified: 'success',
      ok: 'success',
      running: 'success',
      // secondary/neutral
      inactive: 'secondary',
      disabled: 'secondary',
      pending: 'secondary',
      draft: 'secondary',
      unverified: 'secondary',
      // danger-like
      banned: 'danger',
      suspended: 'danger',
      error: 'danger',
      failed: 'danger',
      rejected: 'danger',
      denied: 'danger',
      disable: 'danger'
      ,
      // warning-like
      warning: 'warning',
      attention: 'warning',
      caution: 'warning',
      onboarding: 'warning',
    };
  }

  get resolvedColor(): 'primary' | 'secondary' | 'success' | 'danger' | 'warning' {
    if (this.color) return this.color;
    const text = (this.label || '').toString().toLowerCase();
    const map = this.keywordMap();
    for (const key of Object.keys(map)) {
      if (text.includes(key)) return map[key];
    }
    return 'primary';
  }
}
