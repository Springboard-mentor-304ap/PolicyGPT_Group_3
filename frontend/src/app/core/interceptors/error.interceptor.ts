import { HttpErrorResponse, HttpInterceptorFn, HttpClient } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, shareReplay, switchMap, tap, throwError } from 'rxjs';

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

/** Response shape of POST /api/auth/refresh. */
interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * The single refresh request currently in flight.
 *
 * POST /api/auth/refresh rotates the token: the refresh token that was sent
 * is revoked the moment it is used. When several requests 401 at the same
 * time (typical on page load), only the first one may call the endpoint —
 * the rest subscribe to this shared observable and replay their request with
 * the access token it produced. A second, parallel call would present an
 * already-rotated token, which the backend treats as a replay and answers
 * with a 401 that kills the whole session chain.
 */
let inFlightRefresh$: Observable<string> | null = null;

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/** One refresh call, shared by every caller queued behind it. */
function refreshAccessToken(http: HttpClient): Observable<string> {
  if (inFlightRefresh$) {
    return inFlightRefresh$;
  }

  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    // Nothing left to renew — handled by the caller's catchError below.
    return throwError(() => new Error('No refresh token available'));
  }

  inFlightRefresh$ = http
    .post<TokenPair>('/api/auth/refresh', { refresh_token: refreshToken })
    .pipe(
      tap((tokens) => {
        // Store the rotated pair: the token we just sent is dead now, so the
        // next refresh must use the one that came back.
        if (tokens.access_token) {
          localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
        }
        if (tokens.refresh_token) {
          localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
        }
      }),
      map((tokens) => tokens.access_token),
      // Fires on completion and on error, so the next 401 starts a fresh
      // attempt instead of reusing a finished observable.
      finalize(() => {
        inFlightRefresh$ = null;
      }),
      // One HTTP execution, replayed to every subscriber queued behind it —
      // including the error, so no caller is left hanging.
      shareReplay({ bufferSize: 1, refCount: false })
    );

  return inFlightRefresh$;
}

/**
 * Safe Token Refresh & Error Interceptor
 * Intercepts 401 errors, triggers a single shared token rotation (queued
 * behind the one in flight), and replays failed requests with the new token.
 * Uses HttpClient directly for refresh to avoid circular dependency with AuthService.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const http = inject(HttpClient);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      // Check if error is 401 Unauthorized
      if (error.status !== 401) {
        return throwError(() => error);
      }

      const isBypass = BYPASS_REFRESH_ENDPOINTS.some((url) => req.url.includes(url));

      // If it's an auth endpoint, propagate error directly without attempting refresh
      if (isBypass) {
        return throwError(() => error);
      }

      // The refresh call itself (and only it) decides whether the session
      // survives: a failure clears the tokens and sends the user to login.
      return refreshAccessToken(http).pipe(
        catchError((refreshError) => {
          clearTokens();
          router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
          return throwError(() => refreshError);
        }),
        switchMap((accessToken) => {
          // Retry the original request with the new access token. Errors from
          // the retry belong to the caller and do not clear the session.
          const retryReq = req.clone({
            setHeaders: {
              Authorization: `Bearer ${accessToken}`,
            },
          });
          return next(retryReq);
        })
      );
    })
  );
};
