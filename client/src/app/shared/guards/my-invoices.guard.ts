import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AppService } from '../../services/core/app/app.service';
import { normalizeRole } from '../helpers/access-control.helper';

export const myInvoicesGuard: CanActivateFn = async () => {
  const appService = inject(AppService);
  const router = inject(Router);

  await appService.loadSession(true);
  const role = normalizeRole(appService.userSessionData()?.user?.role);
  const tenantType = String(appService.userSessionData()?.tenant?.tenant_type || '').trim().toLowerCase();

  if (role === 'guard_admin' && tenantType === 'guard') {
    return true;
  }

  if (role === 'sp_admin' && tenantType === 'service_provider') {
    return true;
  }

  return router.createUrlTree(['/dashboard']);
};
