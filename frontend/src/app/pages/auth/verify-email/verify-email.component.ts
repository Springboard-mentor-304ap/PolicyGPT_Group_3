import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { CardComponent } from '../../../shared/components/card/card.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    CardComponent,
    InputComponent,
    ButtonComponent,
  ],
  template: `
    <div class="auth-page">
      <app-card variant="auth" [padding]="'lg'">
        <div class="auth-header">
          <h1 class="auth-title">Verify Your Email</h1>
          <p class="auth-subtitle">Enter the verification code sent to your email</p>
        </div>

        @if (successMessage()) {
          <div class="alert alert-success" role="alert">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <span>{{ successMessage() }}</span>
          </div>
        }

        @if (errorMessage()) {
          <div class="alert alert-error" role="alert">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <span>{{ errorMessage() }}</span>
          </div>
        }

        @if (!verified()) {
          <form [formGroup]="verifyForm" (ngSubmit)="onSubmit()" class="auth-form" novalidate>
            <app-input
              formControlName="token"
              type="text"
              label="Verification Code"
              placeholder="Enter your verification code"
              id="verify-token"
              name="token"
              [required]="true"
              [error]="token?.invalid && token?.touched ? 'Verification code is required' : null"
            />

            <app-button
              type="submit"
              variant="primary"
              [fullWidth]="true"
              [loading]="loading()"
              [disabled]="loading()"
            >
              Verify Email
            </app-button>
          </form>

          <div class="auth-footer">
            <p class="text-sm text-muted">
              Didn't receive the code?
              <button class="text-link" (click)="resendVerification()" [disabled]="resending()">
                {{ resending() ? 'Sending...' : 'Resend Code' }}
              </button>
            </p>
          </div>
        } @else {
          <div class="verified-state">
            <p>Your email has been verified successfully!</p>
            <app-button
              variant="primary"
              [fullWidth]="true"
              (btnClick)="goToDashboard()"
            >
              Go to Dashboard
            </app-button>
          </div>
        }
      </app-card>
    </div>
  `,
  styles: [`
    .auth-page {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 1rem;
    }

    .auth-header {
      text-align: center;
      margin-bottom: 1.5rem;
    }

    .auth-title {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 0.5rem;
    }

    .auth-subtitle {
      color: var(--text-secondary, #64748b);
      font-size: 0.875rem;
      margin: 0;
    }

    .auth-form {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .auth-footer {
      margin-top: 1.5rem;
      text-align: center;
    }

    .alert {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
      margin-bottom: 1rem;
      font-size: 0.875rem;
    }

    .alert svg {
      width: 1.25rem;
      height: 1.25rem;
      flex-shrink: 0;
    }

    .alert-error {
      background: #fef2f2;
      color: #dc2626;
      border: 1px solid #fecaca;
    }

    .alert-success {
      background: #f0fdf4;
      color: #16a34a;
      border: 1px solid #bbf7d0;
    }

    .verified-state {
      text-align: center;
      padding: 2rem 0;
    }

    .verified-state p {
      margin-bottom: 1.5rem;
      color: var(--text-primary, #1a1a2e);
    }

    .text-link {
      background: none;
      border: none;
      color: var(--primary-color, #3b82f6);
      cursor: pointer;
      font-size: inherit;
      padding: 0;
    }

    .text-link:hover {
      text-decoration: underline;
    }

    .text-link:disabled {
      color: var(--text-secondary, #64748b);
      cursor: not-allowed;
    }
  `]
})
export class VerifyEmailComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  verifyForm: FormGroup;
  loading = signal(false);
  resending = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  verified = signal(false);
  userEmail = signal<string>('');

  constructor() {
    this.verifyForm = this.fb.group({
      token: ['', [Validators.required]],
    });
  }

  ngOnInit(): void {
    // Get email from query params
    this.route.queryParams.subscribe(params => {
      if (params['email']) {
        this.userEmail.set(params['email']);
      }
    });

    // Check if there's a token in query params (for direct link verification)
    this.route.queryParams.subscribe(params => {
      if (params['token']) {
        this.verifyWithToken(params['token']);
      }
    });
  }

  private verifyWithToken(token: string): void {
    this.loading.set(true);
    this.authService.verifyEmail({ token }).subscribe({
      next: () => {
        this.loading.set(false);
        this.verified.set(true);
        this.successMessage.set('Email verified successfully!');
        // Refresh user data
        this.authService.getMe().subscribe();
      },
      error: (error) => {
        this.loading.set(false);
        const detail = error?.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Invalid or expired verification code');
      },
    });
  }

  onSubmit(): void {
    if (this.verifyForm.invalid) {
      this.verifyForm.markAllAsTouched();
      return;
    }

    const token = this.verifyForm.value.token as string;
    this.verifyWithToken(token);
  }

  resendVerification(): void {
    if (!this.userEmail()) {
      this.errorMessage.set('No email address found. Please register again.');
      return;
    }

    this.resending.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    this.authService.resendVerification({ email: this.userEmail() }).subscribe({
      next: (response) => {
        this.resending.set(false);
        this.successMessage.set('Verification code resent! Check your email.');
        // If the response contains the token (dev mode), show it
        if (response.verification_token) {
          this.successMessage.set(`Verification code: ${response.verification_token}`);
        }
      },
      error: (error) => {
        this.resending.set(false);
        this.errorMessage.set('Failed to resend verification code. Please try again.');
      },
    });
  }

  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }

  get token() {
    return this.verifyForm.get('token');
  }
}
