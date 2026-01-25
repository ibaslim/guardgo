import { CommonModule } from '@angular/common';
import { Component, HostListener } from '@angular/core';
import { Router } from '@angular/router';
import { AvatarComponent } from '../avatar/avatar.component';
import { AppService } from '../../services/core/app/app.service';
import { AuthService } from '../../services/authetication/auth.service';

@Component({
  selector: 'app-avatar-menu',
  standalone: true,
  imports: [CommonModule, AvatarComponent],
  templateUrl: './avatar-menu.component.html'
})
export class AvatarMenuComponent {
  showUserMenu = false;

  constructor(
    private appService: AppService,
    private authService: AuthService,
    private router: Router
  ) {}

  get displayName(): string {
    return this.appService.userSessionData().user.username || 'User';
  }

  get email(): string {
    return this.appService.userSessionData().user.email || '';
  }

  get avatar(): string | null {
    return (this.appService.userSessionData() as any)?.user?.image || this.appService.userImageUrl();
  }

  toggleMenu(event: MouseEvent): void {
    event.stopPropagation();
    this.showUserMenu = !this.showUserMenu;
  }

  closeMenu(): void {
    this.showUserMenu = false;
  }

  @HostListener('document:mousedown', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu-container')) {
      this.closeMenu();
    }
  }

  async goProfile(): Promise<void> {
    await this.router.navigate(['/dashboard/profile']);
    this.closeMenu();
  }

  async goSettings(): Promise<void> {
    await this.router.navigate(['/dashboard/settings']);
    this.closeMenu();
  }

  async goDashboard(): Promise<void> {
    await this.router.navigate(['/dashboard/overview']);
    this.closeMenu();
  }

  logout(): void {
    this.closeMenu();
    this.authService.logout();
  }
}
