import { Routes } from '@angular/router';
import { AuthGuard } from './shared/guards/auth-guard.guard';
import { LoginComponent } from './pages/login/login.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DashboardLayoutComponent } from './layouts/dashboard-layout/dashboard-layout.component';
import { ErrorHandlerComponent } from './shared/partials/error-handler/error-handler.component';
import { SignupComponent } from './pages/signup/signup.component';
import { TenantComponent } from './pages/tenant/tenant.component';
import { WelcomeComponent } from './pages/welcome/welcome.component';
import { ResetPasswordComponent } from './shared/partials/forgot-password/reset-password.component';
import { TenantGuard } from './shared/guards/tenant-guard.guard';
import { NotificationComponent } from './shared/partials/notification/notification.component';
import { ConfigResolver } from './shared/resolvers/config.resolver';
import { UsersComponent } from './pages/users/users.component';
import { AnalyticsComponent } from './pages/analytics/analytics.component';
import { ComponentsDemoComponent } from './pages/components-demo/components-demo.component';

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
    path: 'onboarding',
    resolve: { config: ConfigResolver },
    component: TenantComponent,
    canActivate: [TenantGuard],
    data: { animation: 'TenantPage' }
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
        component: DashboardComponent
      },
      {
        path: 'users',
        component: UsersComponent
      },
      {
        path: 'analytics',
        component: AnalyticsComponent
      },
      {
        path: 'components-demo',
        loadComponent: () => import('./pages/components-demo/components-demo.component').then(m => m.ComponentsDemoComponent)
      },
      {
        path: 'forms',
        loadComponent: () => import('./pages/forms/forms-page.component').then(m => m.FormsPageComponent)
      }
    ]
  },
  {
    path: '**',
    loadComponent: () => import('./pages/not-found/not-found.component').then(m => m.NotFoundComponent),
    data: { animation: 'ErrorPage' }
  }
];
