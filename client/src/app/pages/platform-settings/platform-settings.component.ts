import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { BaseInputComponent } from '../../components/form/base-input/base-input.component';
import { PageComponent } from '../../components/page/page.component';
import { ButtonComponent } from '../../components/button/button.component';
import { CardComponent } from '../../components/card/card.component';
import { ApiService } from '../../shared/services/api.service';
import { AppService } from '../../services/core/app/app.service';

@Component({
  selector: 'app-platform-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, PageComponent, CardComponent, BaseInputComponent, ButtonComponent],
  templateUrl: './platform-settings.component.html'
})
export class PlatformSettingsComponent implements OnInit {
  model = {
    full_name: '',
    username: ''
  };
  email = '';
  isSaving = false;
  successMessage = '';
  errorMessage = '';

  constructor(
    private apiService: ApiService,
    private appService: AppService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.initialize();
  }

  private normalizeRole(role: string | undefined | null): string {
    const raw = String(role || '').trim().toLowerCase();
    if (!raw) return '';
    return raw.includes('.') ? (raw.split('.').pop() || '') : raw;
  }

  private async initialize(): Promise<void> {
    await this.appService.loadRoleMetadata();
    await this.appService.loadSession(true);
    const session = this.appService.userSessionData();
    const role = this.normalizeRole(session?.user?.role);
    const platformRoles = this.appService.roleMetadata().platformRoles;
    if (!platformRoles.includes(role)) {
      this.router.navigate(['/dashboard']).then();
      return;
    }

    this.model.full_name = (session?.user as any)?.full_name || '';
    this.model.username = session?.user?.username || '';
    this.email = session?.user?.email || '';
  }

  get usernameError(): string {
    const value = (this.model.username || '').trim();
    if (!value) return 'Username is required.';
    const valid = /^[A-Za-z][A-Za-z0-9_-]{7,19}$/.test(value);
    return valid ? '' : 'Username must be 8-20 characters, start with a letter, and use letters, numbers, _ or -.';
  }

  get fullNameError(): string {
    const value = (this.model.full_name || '').trim();
    return value ? '' : 'Full name is required.';
  }

  get canSubmit(): boolean {
    return !this.usernameError && !this.fullNameError && !this.isSaving;
  }

  async save(): Promise<void> {
    this.successMessage = '';
    this.errorMessage = '';

    if (!this.canSubmit) return;

    this.isSaving = true;
    const payload = {
      username: this.model.username.trim(),
      full_name: this.model.full_name.trim()
    };

    try {
      await firstValueFrom(this.apiService.put('me', payload));
      await this.appService.loadSession(true);
      this.successMessage = 'Settings updated successfully.';
    } catch (error: any) {
      this.errorMessage = error?.error?.detail || 'Failed to update settings.';
    } finally {
      this.isSaving = false;
    }
  }
}
