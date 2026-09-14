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
  // Policy Management Routes
  {
    path: 'policies',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/policies/policy-list/policy-list.component').then(
        (m) => m.PolicyListComponent
      ),
  },
  {
    path: 'policies/create',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/policies/policy-form/policy-form.component').then(
        (m) => m.PolicyFormComponent
      ),
  },
  {
    path: 'policies/:id',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/policies/policy-detail/policy-detail.component').then(
        (m) => m.PolicyDetailComponent
      ),
  },
  {
    path: 'policies/:id/edit',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/policies/policy-form/policy-form.component').then(
        (m) => m.PolicyFormComponent
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
