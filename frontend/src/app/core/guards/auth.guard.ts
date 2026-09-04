import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Functional Auth Guard
 * Protects authenticated routes by verifying user session and access token.
 */
export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const token = authService.getAccessToken();

  if (!token) {
    router.navigate(['/login'], {
      queryParams: { returnUrl: state.url }
    });
    return false;
  }

  // If user profile is already in memory signal, grant access
  if (authService.currentUser()) {
    return true;
  }

  // Hydrate user profile if token exists but signal is empty
  return authService.getMe().pipe(
    map(() => true),
    catchError(() => {
      authService.clearTokens();
      router.navigate(['/login'], {
        queryParams: { returnUrl: state.url }
      });
      return of(false);
    })
  );
};
