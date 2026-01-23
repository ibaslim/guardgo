import { Routes } from '@angular/router';
import { AuthGuard } from './shared/guards/auth-guard.guard';
import { LoginComponent } from './pages/login/login.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { DashboardLayoutComponent } from './layouts/dashboard-layout/dashboard-layout.component';
import { SignupComponent } from './pages/signup/signup.component';
import { WelcomeComponent } from './pages/welcome/welcome.component';
import { ResetPasswordComponent } from './shared/partials/forgot-password/reset-password.component';
import { NotificationComponent } from './shared/partials/notification/notification.component';
import { ConfigResolver } from './shared/resolvers/config.resolver';
import { UsersComponent } from './pages/users/users.component';
import { AnalyticsComponent } from './pages/analytics/analytics.component';
import { OnboardingComponent } from './pages/onboarding/onboarding.component';
import { ClientSettingComponent } from './pages/client-setting/client-setting.component';
import { GuardSettingComponent } from './pages/guard-setting/guard-setting.component';

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
    component: OnboardingComponent,
    data: { animation: 'OnboardingPage' }
  },
  {
    path: 'guard-setting',
    resolve: { config: ConfigResolver },
    component: GuardSettingComponent,
    data: { animation: 'GuardSettingPage' }
  },
  {
    path: 'clients-setting',
    resolve: { config: ConfigResolver },
    component: ClientSettingComponent,
    data: { animation: 'ClientSettingPage' }
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
      },
      {
        path: 'onboarding',
        component: OnboardingComponent,
      },
      {
        path: 'guard-setting',
        component: GuardSettingComponent,
      },
      {
        path: 'clients-setting',
        component: ClientSettingComponent,
      }
    ]
  },
  {
    path: '**',
    loadComponent: () => import('./pages/not-found/not-found.component').then(m => m.NotFoundComponent),
    data: { animation: 'ErrorPage' }
  }
];
