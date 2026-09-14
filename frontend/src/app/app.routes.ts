import { Routes } from '@angular/router';
import { AuthLayoutComponent } from './layouts/auth-layout/auth-layout.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'dashboard',
    component: DashboardComponent,
  },
  {
    path: 'admin',
    component: DashboardComponent,
  },
  {
    path: 'verify-email',
    loadComponent: () =>
      import('./pages/auth/verify-email/verify-email.component').then(
        (m) => m.VerifyEmailComponent
      ),
  },
  {
    path: 'citizen-profile',
    loadComponent: () =>
      import('./pages/citizen-profile/citizen-profile.component').then(
        (m) => m.CitizenProfileComponent
      ),
  },
  {
    path: 'role-request',
    loadComponent: () =>
      import('./pages/role-request/role-request.component').then(
        (m) => m.RoleRequestComponent
      ),
  },
  // Scheme Management Routes
  {
    path: 'schemes',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/schemes/scheme-list/scheme-list.component').then(
        (m) => m.SchemeListComponent
      ),
  },
  {
    path: 'schemes/create',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/schemes/scheme-form/scheme-form.component').then(
        (m) => m.SchemeFormComponent
      ),
  },
  {
    path: 'schemes/:id',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/schemes/scheme-details/scheme-details.component').then(
        (m) => m.SchemeDetailsComponent
      ),
  },
  {
    path: 'schemes/:id/edit',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/schemes/scheme-form/scheme-form.component').then(
        (m) => m.SchemeFormComponent
      ),
  },
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
  {
    path: '',
    component: AuthLayoutComponent,
    children: [
      {
        path: 'login',
        loadComponent: () =>
          import('./pages/auth/login/login.component').then(
            (m) => m.LoginComponent
          ),
      },
      {
        path: 'register',
        loadComponent: () =>
          import('./pages/auth/register/register.component').then(
            (m) => m.RegisterComponent
          ),
      },
      {
        path: 'forgot-password',
        loadComponent: () =>
          import('./pages/auth/forgot-password/forgot-password.component').then(
            (m) => m.ForgotPasswordComponent
          ),
      },
      {
        path: 'reset-password',
        loadComponent: () =>
          import('./pages/auth/reset-password/reset-password.component').then(
            (m) => m.ResetPasswordComponent
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
