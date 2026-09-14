import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of, tap } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Functional Auth Guard
 * Protects authenticated routes by verifying user session and access token.
 *
 * Resilient design:
 * - If tokens exist, grant access immediately (let HTTP 401s handle auth failures)
 * - Only redirect to login when tokens are completely absent
 * - Never aggressively clear tokens on transient failures
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const token = authService.getAccessToken();
  const refreshToken = authService.getRefreshToken();

  // No tokens at all → definitely not authenticated
  if (!token && !refreshToken) {
    router.navigate(['/login'], {
      queryParams: { returnUrl: state.url }
    });
    return false;
  }

  // If user profile is already in memory signal, grant access
  if (authService.currentUser()) {
    return true;
  }

  // Token exists but user signal not yet populated (page refresh scenario)
  // Try to hydrate, but on failure just grant access anyway —
  // the HTTP interceptor will handle 401s properly with token refresh.
  return authService.getMe().pipe(
    map(() => true),
    catchError(() => {
      // Don't clear tokens here — the error interceptor handles refresh.
      // Just let the user through; if the token is truly invalid,
      // the actual API call will trigger the refresh flow.
      return of(true);
    })
  );
};
