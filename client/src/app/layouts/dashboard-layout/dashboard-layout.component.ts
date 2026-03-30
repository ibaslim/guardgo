import { Component, Host, HostListener, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AvatarMenuComponent } from '../../components/avatar-menu/avatar-menu.component';
import { IconComponent, IconName } from '../../components/icon/icon.component';
import { NotificationBellComponent } from '../../components/notification-bell/notification-bell.component';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from "../../services/authetication/auth.service";
import { AppService } from "../../services/core/app/app.service";
import { ThemeService } from "../../services/theme/theme.service";
import { AccessPolicy, canAccessPolicy } from '../../shared/helpers/access-control.helper';

type DashboardLink = {
  label: string;
  route: string;
  icon: IconName;
  policy?: AccessPolicy;
  hidden?: boolean;
};

@Component({
  selector: 'app-dashboard-layout',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    AvatarMenuComponent,
    NotificationBellComponent,
    IconComponent
  ],
  templateUrl: './dashboard-layout.component.html',
})
export class DashboardLayoutComponent implements OnInit {
  user = { name: '', avatar: '' };
  sidebarCollapsed = false;
  isMobileView = false;
  // Navigation links centralized for easier management and role visibility
  links: DashboardLink[] = [
    {
      label: 'Dashboard',
      route: '/dashboard/overview',
      icon: 'home'
    },
    {
      label: 'Tenants',
      route: '/dashboard/tenants',
      icon: 'users',
      policy: 'tenantManagement'
    },
    {
      label: 'Admin Users',
      route: '/dashboard/admin-users',
      icon: 'users',
      policy: 'platformUserManagement'
    },
    {
      label: 'Billing Configurations',
      route: '/dashboard/billing-configurations',
      icon: 'settings',
      policy: 'billingConfigurations'
    },
    {
      label: 'Requests',
      route: '/dashboard/requests',
      icon: 'file-text',
      policy: 'clientRequests'
    },
    {
      label: 'Notifications',
      route: '/dashboard/notifications',
      icon: 'bell'
    },
    {
      label: 'Settings',
      route: '/dashboard/settings',
      icon: 'settings',
      policy: 'tenantSettings'
    },
    {
      label: 'Settings',
      route: '/dashboard/platform-settings',
      icon: 'settings',
      policy: 'platform'
    }
  ];

  get isAdmin(): boolean {
    return canAccessPolicy(
      'tenantManagement',
      this.appService.userSessionData()?.user?.role,
      this.appService.roleMetadata()
    );
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
    await this.appService.loadRoleMetadata(true);
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

  canShow(link: DashboardLink): boolean {
    if (link.hidden) return false;
    if (!link.policy) return true;
    return canAccessPolicy(link.policy, this.appService.userSessionData()?.user?.role, this.appService.roleMetadata());
  }
}