import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';

export const billingConfigurationsGuard: CanActivateFn = (_route, _state) => {
  const appService = inject(AppService);
  const router = inject(Router);

  const role = appService.userSessionData()?.user?.role ?? '';
  if (role === 'super_admin') {
    return true;
  }
  return router.createUrlTree(['/dashboard']);
};
