import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AppService } from '../../services/core/app/app.service';

const normalizeRole = (role: string | undefined | null): string => {
  const raw = String(role || '').trim().toLowerCase();
  if (!raw) return '';
  return raw.includes('.') ? raw.split('.').pop() || '' : raw;
};

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
