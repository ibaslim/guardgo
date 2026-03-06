import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';
import { canAccessRoute, normalizeRole } from '../helpers/access-control.helper';

export const tenantSettingsGuard: CanActivateFn = async () => {
  const appService = inject(AppService);
  const router = inject(Router);

  await appService.loadRoleMetadata();
  await appService.loadSession(true);
  const role = normalizeRole(appService.userSessionData()?.user?.role);
  const { platformRoles, tenantSettingsRoles } = appService.roleMetadata();

  if (tenantSettingsRoles.includes(role)) return true;
  if (platformRoles.includes(role)) return router.createUrlTree(['/dashboard/platform-settings']);
  return router.createUrlTree(['/dashboard']);
};

export const platformSettingsGuard: CanActivateFn = async () => {
  const appService = inject(AppService);
  const router = inject(Router);

  await appService.loadRoleMetadata();
  await appService.loadSession(true);
  const role = normalizeRole(appService.userSessionData()?.user?.role);
  const { platformRoles, tenantSettingsRoles } = appService.roleMetadata();

  if (platformRoles.includes(role)) return true;
  if (tenantSettingsRoles.includes(role)) return router.createUrlTree(['/dashboard/settings']);
  return router.createUrlTree(['/dashboard']);
};

export const platformUserManagementGuard: CanActivateFn = async () => {
  const appService = inject(AppService);
  const router = inject(Router);

  await appService.loadRoleMetadata(true);
  await appService.loadSession(true);
  const role = normalizeRole(appService.userSessionData()?.user?.role);

  if (canAccessRoute('/dashboard/admin-users', role, appService.roleMetadata())) return true;
  return router.createUrlTree(['/dashboard']);
};
