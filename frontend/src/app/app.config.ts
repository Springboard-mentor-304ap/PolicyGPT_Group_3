import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

// ╔══════════════════════════════════════════════════════════════════════════════╗
// ║  HOW TO RECONNECT TO THE BACKEND                                           ║
// ║                                                                            ║
// ║  1. Uncomment the provideHttpClient import below                           ║
// ║  2. Uncomment provideHttpClient(withInterceptors([...])) in providers      ║
// ║  3. Restore the AuthService HTTP calls (see auth.service.ts comments)     ║
// ║  4. Ensure backend is running and proxy.conf.json routes to it             ║
// ╚══════════════════════════════════════════════════════════════════════════════╝

// import { provideHttpClient, withInterceptors } from '@angular/common/http';
// import { jwtInterceptor } from './core/interceptors/jwt.interceptor';
// import { errorInterceptor } from './core/interceptors/error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // provideHttpClient(withInterceptors([jwtInterceptor, errorInterceptor])),
  ]
};
