import { HttpContextToken } from '@angular/common/http';

export type HttpLoadingMode = 'global' | 'silent';

export const HTTP_LOADING_MODE = new HttpContextToken<HttpLoadingMode>(() => 'global');
export const HTTP_LOADING_SCOPE = new HttpContextToken<string>(() => '');
