import { Component, Host, HostListener, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AvatarMenuComponent } from '../../components/avatar-menu/avatar-menu.component';
import { IconComponent, IconName } from '../../components/icon/icon.component';
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
    AvatarMenuComponent,
    IconComponent
  ],
  templateUrl: './dashboard-layout.component.html',
})
export class DashboardLayoutComponent implements OnInit {
  user = { name: '', avatar: '' };
  sidebarCollapsed = false;
  isMobileView = false;
  // Navigation links centralized for easier management and role visibility
  links: { label: string; route: string; icon: IconName; roles?: string[]; hidden?: boolean }[] = [
    {
      label: 'Dashboard',
      route: '/dashboard/overview',
      icon: 'home'
    },
    {
      label: 'Tenants',
      route: '/dashboard/tenants',
      icon: 'users',
      roles: ['admin']
    },
    {
      label: 'Settings',
      route: '/dashboard/settings',
      icon: 'settings'
    }
  ];

  get isAdmin(): boolean {
    const session = this.appService.userSessionData();
    return !!(session && session.user && session.user.role === 'admin');
  }

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

  ngOnInit() {
    this.checkScreenWidth();
  }

  @HostListener('window:resize', ['$event'])
  onResize(event: any) {
    this.checkScreenWidth();
  }

  checkScreenWidth() {
    this.isMobileView = window.innerWidth < 1024;
    this.sidebarCollapsed = this.isMobileView;
  }

  ngOnDestroy() {
  }

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }

  logout() {
    this.authService.logout();
  }

  canShow(link: { roles?: string[]; hidden?: boolean }): boolean {
    if (link.hidden) return false;
    const session = this.appService.userSessionData();
    if (!link.roles || link.roles.length === 0) return true;
    const role = session?.user?.role || '';
    return !!role && link.roles.includes(role);
  }
}