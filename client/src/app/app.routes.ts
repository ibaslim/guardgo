import { Routes } from '@angular/router';
import { AuthGuard } from './shared/guards/auth-guard.guard';
import { onboardingGuard } from './shared/guards/onboarding.guard';
import { billingConfigurationsGuard } from './shared/guards/billing-configurations.guard';
import { LoginComponent } from './pages/login/login.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DashboardLayoutComponent } from './layouts/dashboard-layout/dashboard-layout.component';
import { SignupComponent } from './pages/signup/signup.component';
import { WelcomeComponent } from './pages/welcome/welcome.component';
import { ResetPasswordComponent } from './shared/partials/forgot-password/reset-password.component';
import { InviteActivationComponent } from './shared/partials/invite-activation/invite-activation.component';
import { NotificationComponent } from './shared/partials/notification/notification.component';
import { ConfigResolver } from './shared/resolvers/config.resolver';
import { UsersComponent } from './pages/users/users.component';
import { AnalyticsComponent } from './pages/analytics/analytics.component';
import { OnboardingComponent } from './pages/onboarding/onboarding.component';
import { TenantSettingsComponent } from './pages/tenant-settings/tenant-settings.component';
import { PendingVerificationComponent } from './pages/pending-verification/pending-verification.component';
import { pendingVerificationGuard } from './shared/guards/pending-verification.guard';
import { clientRequestsGuard } from './shared/guards/client-requests.guard';
import { myInvoicesGuard } from './shared/guards/my-invoices.guard';
import { platformSettingsGuard, platformUserManagementGuard, tenantSettingsGuard } from './shared/guards/settings.guard';

export const routes: Routes = [



  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
    data: { animation: 'RootPage' }
  },
  {
    path: 'signup',
    component: SignupComponent,
    data: { animation: 'SignupPage' }
  },
  {
    path: 'login',
    resolve: { config: ConfigResolver },
    component: LoginComponent,
    data: { animation: 'LoginPage' }
  },
  {
    path: 'welcome',
    component: WelcomeComponent,
    data: { animation: 'WelcomePage' }
  },
  {
    path: 'welcome/:token',
    component: WelcomeComponent,
    data: { animation: 'WelcomePage' }
  },
  {
    path: 'reset',
    component: ResetPasswordComponent,
    data: { animation: 'ForgotPasswordComponent' }
  },
  {
    path: 'notification',
    component: NotificationComponent,
    data: { animation: 'PaymentGatewayComponent' }
  },
  {
    path: 'reset/:token',
    component: ResetPasswordComponent,
    data: { animation: 'ForgotPasswordComponent' }
  },
  {
    path: 'invite/:token',
    component: InviteActivationComponent,
    data: { animation: 'ForgotPasswordComponent' }
  },
  {
    path: 'dashboard',
    component: DashboardLayoutComponent,
    canActivate: [AuthGuard],
    resolve: {
      config: ConfigResolver,
    },
    data: { animation: 'DashboardPage' },
    children: [
      {
        path: '',
        redirectTo: 'overview',
        pathMatch: 'full'
      },
      {
        path: 'overview',
        component: DashboardComponent,
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'users',
        component: UsersComponent,
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'admin-users',
        loadComponent: () => import('./pages/admin-users/admin-users.component').then(m => m.AdminUsersComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard, platformUserManagementGuard]
      },
      {
        path: 'analytics',
        component: AnalyticsComponent,
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'components-demo',
        loadComponent: () => import('./pages/components-demo/components-demo.component').then(m => m.ComponentsDemoComponent),
      },
      {
        path: 'forms',
        loadComponent: () => import('./pages/forms/forms-page.component').then(m => m.FormsPageComponent),
      },
      {
        path: 'settings',
        component: TenantSettingsComponent,
        canActivate: [tenantSettingsGuard]
      },
      {
        path: 'platform-settings',
        loadComponent: () => import('./pages/platform-settings/platform-settings.component').then(m => m.PlatformSettingsComponent),
        canActivate: [platformSettingsGuard]
      },
      {
        path: 'tenants/:id',
        loadComponent: () => import('./pages/tenants').then(m => m.TenantsComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'tenants',
        loadComponent: () => import('./pages/tenants').then(m => m.TenantsComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'billing-configurations',
        loadComponent: () => import('./pages/billing-configurations').then(m => m.BillingConfigurationsComponent),
        canActivate: [billingConfigurationsGuard]
      },
      {
        path: 'requests',
        loadComponent: () => import('./pages/requests/requests.component').then(m => m.RequestsComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard, clientRequestsGuard]
      },
      {
        path: 'my-invoices',
        loadComponent: () => import('./pages/my-invoices/my-invoices.component').then(m => m.MyInvoicesComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard, myInvoicesGuard]
      },
      {
        path: 'payout-invoices',
        loadComponent: () => import('./pages/platform-payout-invoices/platform-payout-invoices.component').then(m => m.PlatformPayoutInvoicesComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard, platformSettingsGuard]
      },
      {
        path: 'notifications',
        loadComponent: () => import('./pages/notifications/notifications.component').then(m => m.NotificationsComponent),
        canActivate: [onboardingGuard, pendingVerificationGuard]
      },
      {
        path: 'onboarding',
        component: OnboardingComponent,
        canActivate: [onboardingGuard]
      },
      {
        path: 'pending-verification',
        component: PendingVerificationComponent,
        canActivate: [pendingVerificationGuard]
      }

    ]
  },
  {
    path: '**',
    loadComponent: () => import('./pages/not-found/not-found.component').then(m => m.NotFoundComponent),
    data: { animation: 'ErrorPage' }
  }
];
