import { HttpInterceptorFn } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * API base-URL interceptor.
 *
 * Services call the backend with root-relative URLs (`/api/...`), which is
 * what the dev server proxies to localhost:8000. A production bundle has no
 * proxy, so this interceptor prefixes the API origin baked in by
 * environment.prod.ts at build time. Running it first means every later
 * interceptor (and every caller) sees the final URL.
 *
 * Absolute URLs and the dev build (empty `apiUrl`) pass through untouched.
 */
export const apiBaseUrlInterceptor: HttpInterceptorFn = (req, next) => {
  const base = environment.apiUrl;

  if (!base || !req.url.startsWith('/')) {
    return next(req);
  }

  const url = `${base.replace(/\/+$/, '')}${req.url}`;

  return next(req.clone({ url }));
};
