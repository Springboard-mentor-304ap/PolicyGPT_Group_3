import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { apiBaseUrlInterceptor } from './core/interceptors/api-base-url.interceptor';
import { jwtInterceptor } from './core/interceptors/jwt.interceptor';
import { errorInterceptor } from './core/interceptors/error.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    // apiBaseUrlInterceptor runs first so the token and error interceptors
    // (and the refresh retry) all see the final, absolute URL.
    provideHttpClient(
      withInterceptors([apiBaseUrlInterceptor, jwtInterceptor, errorInterceptor])
    ),
  ]
};
