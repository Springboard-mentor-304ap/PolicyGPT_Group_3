import { HttpInterceptorFn } from '@angular/common/http';

const ACCESS_TOKEN_KEY = 'policygpt_access_token';

/**
 * Public authentication endpoints that do not require an Authorization header
 */
const PUBLIC_ENDPOINTS = [
  '/auth/login',
  '/auth/register',
  '/auth/forget-password',
  '/auth/reset-password',
  '/auth/refresh',
  '/auth/verify-email',
  '/auth/resend-verification',
];

/**
 * JWT Interceptor
 * Injects 'Authorization: Bearer <access_token>' to outgoing HTTP requests.
 * Reads the token directly from localStorage to avoid circular dependency with AuthService.
 */
export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  // Skip token injection for public endpoints
  const isPublic = PUBLIC_ENDPOINTS.some((url) => req.url.includes(url));
  if (isPublic) {
    return next(req);
  }

  const token = localStorage.getItem(ACCESS_TOKEN_KEY);

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
