import {
  HttpContextToken,
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject, Injector } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, throwError, TimeoutError, Subject } from 'rxjs';
import { catchError, finalize, timeout, takeUntil } from 'rxjs/operators';
import { MessageNotificationService } from '../message_notification/message-notification.service';
import { AuthService } from '../authetication/auth.service';
import {
  HTTP_LOADING_MODE,
  HTTP_LOADING_SCOPE,
  HTTP_SUPPRESSED_ERROR_STATUSES,
} from '../../shared/http/http-loading.tokens';
import { LoadingFeedbackService } from '../../shared/services/loading-feedback.service';

const inFlightCancels = new Map<string, Subject<void>>();
const GLOBAL_TIMEOUT = 150000;
const STATUS_MEANINGS: { [key: number]: string } = {
  400: 'Bad Request',
  401: 'Unauthorized',
  402: 'Payment Required',
  403: 'Forbidden',
  404: 'Not Found',
  408: 'Request Timeout',
  409: 'Conflict',
  422: 'Unprocessable Entity',
  429: 'Too Many Requests',
  500: 'Internal Server Error',
  502: 'Bad Gateway',
  503: 'Service Unavailable',
};

export const httpInterceptor: HttpInterceptorFn = (
  req: HttpRequest<any>,
  next: HttpHandlerFn
): Observable<HttpEvent<any>> => {
  const router = inject(Router);
  const msg = inject(MessageNotificationService);
  const injector = inject(Injector);
  const loading = inject(LoadingFeedbackService);

  const token = localStorage.getItem('token');
  const authReq = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` }, withCredentials: true })
    : req.clone({ withCredentials: true });

  const isAssetRequest = authReq.url.includes('/assets/') || authReq.url.startsWith('assets/');
  const loadingMode = isAssetRequest ? 'silent' : authReq.context.get(HTTP_LOADING_MODE);
  const loadingScope = authReq.context.get(HTTP_LOADING_SCOPE);
  const suppressedErrorStatuses = authReq.context.get(HTTP_SUPPRESSED_ERROR_STATUSES);

  const key = authReq.url.startsWith('api/') ? authReq.url : null;
  let cancel$: Subject<void> | null = null;

  if (key) {
    const existing = inFlightCancels.get(key);
    if (existing) {
      existing.next();
      existing.complete();
    }
    cancel$ = new Subject<void>();
    inFlightCancels.set(key, cancel$);
  }

  loading.begin(loadingMode, loadingScope);

  return next(authReq).pipe(
    cancel$ ? takeUntil(cancel$) : (s) => s,
    timeout<HttpEvent<any>>(GLOBAL_TIMEOUT),
    finalize(() => {
      if (key) {
        const current = inFlightCancels.get(key);
        if (current === cancel$) inFlightCancels.delete(key);
      }
      loading.end(loadingMode, loadingScope);
    }),
    catchError((error: unknown) => {
      const authService = injector.get(AuthService, null);

      if (authService?.isAuthenticated()) {
        if (error instanceof HttpErrorResponse && error.status === 0) {
          msg.show('Cannot connect to server');
          return throwError(() => error);
        }

        let message = STATUS_MEANINGS[(error as any).status] || 'Error';
        if (error instanceof HttpErrorResponse && error.error && typeof error.error === 'object') {
          const keys = Object.keys(error.error);
          if (keys.length === 1) {
            message = `${(error.error as any)[keys[0]]}`;
          }
        }

        const silentLogoutMessages = new Set([
          'Token has expired',
          'Logged out due to multiple active sessions',
        ]);
        const isSilentLogout = silentLogoutMessages.has(message);

        if (error instanceof HttpErrorResponse && error.status === 401) {
          localStorage.clear();
          sessionStorage.clear();
          router.navigate(['/login']).then();
        }

        const shouldSuppressMessage = error instanceof HttpErrorResponse
          && suppressedErrorStatuses.includes(error.status);

        if (!isSilentLogout && !shouldSuppressMessage) {
          msg.show(message);
        }
      }

      if (error instanceof TimeoutError) {
        return throwError(
          () =>
            new HttpErrorResponse({
              error: 'Request timed out',
              status: 408,
              statusText: 'Request Timeout',
              url: (error as any).url,
            })
        );
      }

      return throwError(() => error);
    })
  );
};
