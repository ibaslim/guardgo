import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';

/**
 * Onboarding Guard
 * 
 * Enforces onboarding flow based on tenant status:
 * - If tenant status is 'onboarding' and user tries to access protected routes -> redirect to /dashboard/onboarding
 * - If tenant status is NOT 'onboarding' and user tries to access /dashboard/onboarding -> redirect to /dashboard
 */
export const onboardingGuard: CanActivateFn = (route, state) => {
    const appService = inject(AppService);
    const router = inject(Router);

    const sessionData = appService.userSessionData();
    const tenantStatus = sessionData?.tenant?.status?.toLowerCase();
    const currentUrl = state.url;

    // Check if current URL is onboarding-related
    const isOnboardingRoute = currentUrl === '/dashboard/onboarding' ||
        currentUrl.startsWith('/dashboard/onboarding');

    // If tenant is in onboarding status
    if (tenantStatus === 'onboarding') {
        // Allow access to onboarding routes only
        if (isOnboardingRoute) {
            return true;
        }
        // Redirect all other routes to dashboard/onboarding
        return router.createUrlTree(['/dashboard/onboarding']);
    }

    // If tenant is NOT in onboarding status (active, disable, etc.)
    if (tenantStatus === 'active' || tenantStatus === 'disable') {
        // Block access to onboarding routes
        if (isOnboardingRoute) {
            return router.createUrlTree(['/dashboard']);
        }
        // Allow access to all other routes
        return true;
    }

    // Default: allow access (for cases where status is undefined/null)
    return true;
};