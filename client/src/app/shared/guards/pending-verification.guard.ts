import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';

export const pendingVerificationGuard: CanActivateFn = (route, state) => {
  const appService = inject(AppService);
  const router = inject(Router);

  const sessionData = appService.userSessionData();
  const tenantStatus = sessionData?.tenant?.status?.toLowerCase();
  const currentUrl = state.url;

  const isPendingRoute = currentUrl === '/dashboard/pending-verification' ||
    currentUrl.startsWith('/dashboard/pending-verification');

  // Only 'active' tenants can access pending-verification
  if (tenantStatus === 'active') {
    if (isPendingRoute) return true;
    return router.createUrlTree(['/dashboard/pending-verification']);
  }

  // Block pending-verification for non-active tenants
  if (isPendingRoute) {
    if (tenantStatus === 'onboarding') {
      return router.createUrlTree(['/dashboard/onboarding']);
    }
    return router.createUrlTree(['/dashboard']);
  }

  // Allow other routes
  return true;
};
