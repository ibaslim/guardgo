import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';

export const onboardingGuard: CanActivateFn = (route, state) => {
    const appService = inject(AppService);
    const router = inject(Router);

    const sessionData = appService.userSessionData();
    const tenantStatus = sessionData?.tenant?.status?.toLowerCase();
    const currentUrl = state.url;

    const isOnboardingRoute = currentUrl === '/dashboard/onboarding' || currentUrl.startsWith('/dashboard/onboarding');
    const isPendingRoute = currentUrl === '/dashboard/pending-verification' || currentUrl.startsWith('/dashboard/pending-verification');

    // Tenant is completing onboarding
    if (tenantStatus === 'onboarding') {
        if (isOnboardingRoute) return true; // allow form
        return router.createUrlTree(['/dashboard/onboarding']); // redirect others
    }

    // Tenant has submitted form, pending verification
    if (tenantStatus === 'active') {
        if (isPendingRoute) return true; // allow pending-verification page
        return router.createUrlTree(['/dashboard/pending-verification']); // redirect all others
    }

    // Default allow
    return true;
};
