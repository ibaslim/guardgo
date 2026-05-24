import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AppService } from '../../services/core/app/app.service';
import { normalizeRole } from '../helpers/access-control.helper';

export const clientRequestsGuard: CanActivateFn = async () => {
  const appService = inject(AppService);
  const router = inject(Router);

  await appService.loadSession(true);
  const role = normalizeRole(appService.userSessionData()?.user?.role);
  const tenantType = String(appService.userSessionData()?.tenant?.tenant_type || '').trim().toLowerCase();

  const platformRoles = new Set(['admin', 'ops_admin', 'support_admin', 'compliance_admin', 'read_only_admin']);
  if (platformRoles.has(role)) {
    return true;
  }

  if (role === 'client_admin' && tenantType === 'client') {
    const billingMethod = appService.userSessionData()?.tenant?.profile?.['billing_method'];
    const hasBillingMethod = Boolean(
      billingMethod
      && typeof billingMethod === 'object'
      && String(billingMethod.method || billingMethod.type || '').trim()
      && String(billingMethod.cardholder_name || billingMethod.cardholderName || '').trim()
      && String(billingMethod.last4 || billingMethod.card_last4 || '').trim()
    );

    if (!hasBillingMethod) {
      return router.createUrlTree(['/dashboard/settings']);
    }

    return true;
  }

  if (role === 'guard_admin' && tenantType === 'guard') {
    return true;
  }

  if (role === 'sp_admin' && tenantType === 'service_provider') {
    return true;
  }

  return router.createUrlTree(['/dashboard']);
};
