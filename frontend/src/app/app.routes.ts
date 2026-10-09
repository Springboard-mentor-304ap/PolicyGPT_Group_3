import { Routes } from '@angular/router';
import { AuthLayoutComponent } from './layouts/auth-layout/auth-layout.component';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';
import { UserRole } from './core/models/auth.models';

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
  // Search, Eligibility, Comparison
  {
    path: 'search',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/search/search.component').then((m) => m.SearchComponent),
  },
  {
    path: 'eligibility',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/eligibility/eligibility.component').then((m) => m.EligibilityComponent),
  },
  {
    path: 'compare',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/comparison/comparison.component').then((m) => m.ComparisonComponent),
  },
  // Backend integration routes — applications, feedback, FAQ, reports
  {
    path: 'applications',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/applications/my-applications.component').then(
        (m) => m.MyApplicationsComponent
      ),
  },
  // Government-official application status review (staff roles only)
  {
    path: 'applications/review',
    canActivate: [authGuard, roleGuard],
    data: {
      roles: [
        UserRole.GOVERNMENT_OFFICIAL,
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
      ],
    },
    loadComponent: () =>
      import(
        './pages/applications/application-review/application-review.component'
      ).then((m) => m.ApplicationReviewComponent),
  },
  // Legacy manual-ID lookup page → replaced by the review page
  {
    path: 'applications/status',
    redirectTo: 'applications/review',
    pathMatch: 'full',
  },
  {
    path: 'feedback',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/feedback/feedback.component').then(
        (m) => m.FeedbackComponent
      ),
  },
  {
    path: 'faq',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./pages/faq/faq.component').then((m) => m.FaqComponent),
  },
  // Reports are limited to staff roles and researchers (mirrors
  // REPORT_ALLOWED_ROLES); the API rejects other roles as well, so this only
  // avoids a dead-end page. User activity reports stay administrator-only.
  {
    path: 'reports',
    canActivate: [authGuard, roleGuard],
    data: {
      roles: [
        UserRole.GOVERNMENT_OFFICIAL,
        UserRole.RESEARCHER,
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
      ],
    },
    loadComponent: () =>
      import('./pages/reports/reports.component').then(
        (m) => m.ReportsComponent
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
