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
  private platformRoles: string[] = [];
  private tenantSettingsRoles: string[] = [];
  private tenantManagementRoles: string[] = [];
  private platformUserManagementRoles: string[] = [];
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
      roles: this.tenantManagementRoles
    },
    {
      label: 'Admin Users',
      route: '/dashboard/admin-users',
      icon: 'users',
      roles: this.platformUserManagementRoles
    },
    {
      label: 'Settings',
      route: '/dashboard/settings',
      icon: 'settings',
      roles: this.tenantSettingsRoles
    },
    {
      label: 'Settings',
      route: '/dashboard/platform-settings',
      icon: 'settings',
      roles: this.platformRoles
    }
  ];

  get isAdmin(): boolean {
    const rawRole = String(this.appService.userSessionData()?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    return !!role && this.tenantManagementRoles.includes(role);
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
    this.initializeRoleMetadata();
    this.checkScreenWidth();
  }

  private async initializeRoleMetadata(): Promise<void> {
    await this.appService.loadRoleMetadata();
    const metadata = this.appService.roleMetadata();
    this.platformRoles = metadata.platformRoles || [];
    this.tenantSettingsRoles = metadata.tenantSettingsRoles || [];
    this.tenantManagementRoles = metadata.tenantManagementRoles || [];
    this.platformUserManagementRoles = metadata.platformUserManagementRoles || [];

    this.links = [
      {
        label: 'Dashboard',
        route: '/dashboard/overview',
        icon: 'home'
      },
      {
        label: 'Tenants',
        route: '/dashboard/tenants',
        icon: 'users',
        roles: this.tenantManagementRoles
      },
      {
        label: 'Admin Users',
        route: '/dashboard/admin-users',
        icon: 'users',
        roles: this.platformUserManagementRoles
      },
      {
        label: 'Settings',
        route: '/dashboard/settings',
        icon: 'settings',
        roles: this.tenantSettingsRoles
      },
      {
        label: 'Settings',
        route: '/dashboard/platform-settings',
        icon: 'settings',
        roles: this.platformRoles
      }
    ];
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
    const rawRole = String(session?.user?.role || '').trim().toLowerCase();
    const role = rawRole.includes('.') ? (rawRole.split('.').pop() || '') : rawRole;
    return !!role && link.roles.includes(role);
  }
}