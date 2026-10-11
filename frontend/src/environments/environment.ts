/**
 * Development environment.
 *
 * `apiUrl` is empty on purpose: `ng serve` proxies /api to
 * http://localhost:8000 through frontend/proxy.conf.json, so requests stay
 * same-origin. Production builds swap this file for environment.prod.ts
 * (angular.json → configurations.production → fileReplacements), because the
 * dev-server proxy does not exist in a production bundle.
 */
export const environment = {
  production: false,
  /** Backend origin; '' means "same origin as the Angular app". */
  apiUrl: '',
};
