import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { SectionComponent } from '../section/section.component';

@Component({
  selector: 'app-tenant-admin-user-summary',
  standalone: true,
  imports: [CommonModule, SectionComponent],
  templateUrl: './tenant-admin-user-summary.component.html',
})
export class TenantAdminUserSummaryComponent {
  @Input() fullName = '';
  @Input() email = '';
  @Input() username = '';

  get displayName(): string {
    const fullName = (this.fullName || '').trim();
    if (fullName) {
      return fullName;
    }
    const username = (this.username || '').trim();
    if (username) {
      return username;
    }
    return 'Tenant admin user';
  }

  get displayEmail(): string {
    return (this.email || '').trim() || 'No email available';
  }
}
