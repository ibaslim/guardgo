import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AvatarComponent } from '../../components/avatar/avatar.component';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from "../../services/authetication/auth.service";
import { AppService } from "../../services/core/app/app.service";
import { ThemeService } from "../../services/theme/theme.service";

@Component({
  selector: 'app-dashboard-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    AvatarComponent
  ],
  // ...existing code...
  templateUrl: './dashboard-layout.component.html',
})
export class DashboardLayoutComponent implements OnInit {
  showUserMenu = false;
  user = { name: '', avatar: '' };
  sidebarCollapsed = false;

  constructor(
    private authService: AuthService,
    protected appService: AppService,
    private router: Router,
    protected themeService: ThemeService
  ) {
    const session = this.appService.userSessionData();
    this.user.name = session?.user?.username || 'User';
    this.user.avatar = session?.user?.image || '';
  }

  onClickOutside = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu-container')) {
      this.showUserMenu = false;
    }
  };

  ngOnInit() {
    document.addEventListener('mousedown', this.onClickOutside);
  }

  ngOnDestroy() {
    document.removeEventListener('mousedown', this.onClickOutside);
  }

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }

  logout() {
    this.authService.logout();
  }
}
