import { HttpErrorResponse, HttpInterceptorFn, HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject, catchError, filter, switchMap, take, throwError } from 'rxjs';

const ACCESS_TOKEN_KEY = 'policygpt_access_token';
const REFRESH_TOKEN_KEY = 'policygpt_refresh_token';

/**
 * Endpoints that should never trigger a token refresh upon receiving a 401
 */
const BYPASS_REFRESH_ENDPOINTS = [
  '/api/auth/login',
  '/api/auth/register',
  '/api/auth/refresh',
  '/api/auth/forget-password',
  '/api/auth/reset-password',
];

let isRefreshing = false;
const refreshTokenSubject = new BehaviorSubject<string | null>(null);

function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Safe Token Refresh & Error Interceptor
 * Intercepts 401 errors, triggers silent token rotation with mutex concurrency safety, and replays failed requests.
 * Uses HttpClient directly for refresh to avoid circular dependency with AuthService.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const http = inject(HttpClient);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      // Check if error is 401 Unauthorized
      if (error.status === 401) {
        const isBypass = BYPASS_REFRESH_ENDPOINTS.some((url) => req.url.includes(url));

        // If it's an auth endpoint, propagate error directly without attempting refresh
        if (isBypass) {
          return throwError(() => error);
        }

        const refreshToken = getRefreshToken();
        if (!refreshToken) {
          clearTokens();
          router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
          return throwError(() => error);
        }

        // Concurrency-safe refresh handling
        if (!isRefreshing) {
          isRefreshing = true;
          refreshTokenSubject.next(null);

          // Call refresh endpoint directly via HttpClient
          return http.post<{ access_token: string; refresh_token: string; token_type: string }>(
            '/api/auth/refresh',
            null,
            { params: { refresh_token: refreshToken } }
          ).pipe(
            switchMap((tokens) => {
              isRefreshing = false;
              refreshTokenSubject.next(tokens.access_token);

              // Save new tokens to localStorage
              if (tokens.access_token) {
                localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
              }
              if (tokens.refresh_token) {
                localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
              }

              // Retry original request with the new access token
              const retryReq = req.clone({
                setHeaders: {
                  Authorization: `Bearer ${tokens.access_token}`
                }
              });
              return next(retryReq);
            }),
            catchError((refreshError) => {
              isRefreshing = false;
              refreshTokenSubject.next(null);
              clearTokens();
              router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
              return throwError(() => refreshError);
            })
          );
        } else {
          // If already refreshing, wait for new token from subject and replay request
          return refreshTokenSubject.pipe(
            filter((token): token is string => token !== null),
            take(1),
            switchMap((newToken) => {
              const retryReq = req.clone({
                setHeaders: {
                  Authorization: `Bearer ${newToken}`
                }
              });
              return next(retryReq);
            })
          );
        }
      }

      return throwError(() => error);
    })
  );
};
