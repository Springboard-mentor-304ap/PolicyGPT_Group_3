import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { CardComponent } from '../../../shared/components/card/card.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    CardComponent,
    InputComponent,
    ButtonComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  loginForm: FormGroup;
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  /** Email to prefill on /verify-email when login is blocked as unverified. */
  verifyEmailLink = signal<string | null>(null);

  constructor() {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
      password: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(128)]],
    });
  }

  onSubmit(): void {
    if (this.loginForm.invalid) {
      this.loginForm.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);
    this.verifyEmailLink.set(null);

    const email = (this.loginForm.value.email as string).trim();
    const password = this.loginForm.value.password as string;

    this.authService.login({ email, password }).subscribe({
      next: () => {
        // After successful login, fetch user profile to get role
        this.authService.getMe().subscribe({
          next: (user) => {
            this.loading.set(false);
            console.log('[LOGIN] Profile loaded:', user.email, user.email_verified, user.role);
            this.routeUserByRole(user.role);
          },
          error: () => {
            // Login succeeded but profile fetch failed — still authenticated
            this.loading.set(false);
            this.routeUserByRole(this.authService.userRole());
          },
        });
      },
      error: (error) => {
        this.loading.set(false);
        this.handleApiError(error);
      },
    });
  }

  private routeUserByRole(role: string | null): void {
    console.log('[LOGIN] Routing user by role:', role);

    const returnUrl = this.route.snapshot.queryParams['returnUrl'];

    if (returnUrl && !returnUrl.startsWith('/verify-email')) {
      this.router.navigateByUrl(returnUrl);
      return;
    }

    switch (role) {
      case 'admin':
      case 'super_admin':
        this.router.navigate(['/admin']);
        break;
      case 'government_official':
      case 'citizen':
      case 'researcher':
      case 'organization':
      default:
        this.router.navigate(['/dashboard']);
        break;
    }
  }

  private handleApiError(error: any): void {
    const status = error?.status;
    const detail = error?.error?.detail;

    // 403 is the backend's way of saying the credentials were right but the
    // account is not usable yet — each case gets its own message.
    if (status === 403 && typeof detail === 'string') {
      if (/not verified/i.test(detail)) {
        this.errorMessage.set(
          'Your email address has not been verified yet. Check your inbox for the 6-digit code, or resend it from the verification page.'
        );
        this.verifyEmailLink.set(
          (this.loginForm.value.email as string | null)?.trim() ?? ''
        );
        return;
      }

      if (/inactive|deactivat/i.test(detail)) {
        this.errorMessage.set(
          'Your account has been deactivated. Contact your administrator to have it reactivated.'
        );
        return;
      }
    }

    if (typeof detail === 'string') {
      this.errorMessage.set(detail);
    } else if (Array.isArray(detail)) {
      this.errorMessage.set(detail.map((d: any) => d.msg).join('. '));
    } else {
      this.errorMessage.set('An unexpected error occurred. Please try again.');
    }
  }

  get email() {
    return this.loginForm.get('email');
  }

  get password() {
    return this.loginForm.get('password');
  }
}
