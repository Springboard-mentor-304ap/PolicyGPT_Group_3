import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

/**
 * Public authentication endpoints that do not require an Authorization header
 */
const PUBLIC_ENDPOINTS = [
  '/auth/login',
  '/auth/register',
  '/auth/forget-password',
  '/auth/reset-password',
  '/auth/refresh'
];

/**
 * JWT Interceptor
 * Injects 'Authorization: Bearer <access_token>' to outgoing HTTP requests when available.
 */
export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);

  // Check if request is directed to a public endpoint
  const isPublic = PUBLIC_ENDPOINTS.some((url) => req.url.includes(url));
  if (isPublic) {
    return next(req);
  }

  const token = authService.getAccessToken();

  // Attach token if present and not already provided
  if (token && !req.headers.has('Authorization')) {
    const clonedReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`
      }
    });
    return next(clonedReq);
  }

  return next(req);
};
