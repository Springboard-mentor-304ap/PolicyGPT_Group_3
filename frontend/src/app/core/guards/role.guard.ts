import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { UserRole } from '../models/auth.models';
import { AuthService } from '../services/auth.service';

/**
 * Functional Role Guard
 * Enforces role-based access control based strictly on backend UserRole values from GET /auth/me.
 * Valid roles: 'admin', 'government_official', 'citizen', 'researcher', 'organization'
 */
export const roleGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  const allowedRoles = (route.data?.['roles'] as (UserRole | string)[]) || [];

  const checkRole = (role: string | null): boolean => {
    if (!role || !allowedRoles.includes(role)) {
      // Redirect to appropriate area based on user's actual role
      if (role === UserRole.ADMIN || role === UserRole.GOVERNMENT_OFFICIAL) {
        router.navigate(['/admin']);
      } else {
        router.navigate(['/dashboard']);
      }
      return false;
    }
    return true;
  };

  const user = authService.currentUser();

  if (user) {
    return checkRole(user.role);
  }

  // If user profile is not yet hydrated, fetch from backend
  const token = authService.getAccessToken();
  if (!token) {
    router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
    return false;
  }

  return authService.getMe().pipe(
    map((fetchedUser) => checkRole(fetchedUser.role)),
    catchError(() => {
      authService.clearTokens();
      router.navigate(['/login'], { queryParams: { returnUrl: state.url } });
      return of(false);
    })
  );
};
