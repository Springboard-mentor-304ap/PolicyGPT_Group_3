import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { CardComponent } from '../../../shared/components/card/card.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    CardComponent,
    InputComponent,
    ButtonComponent,
  ],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.css',
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);

  forgotForm: FormGroup;
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  constructor() {
    this.forgotForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
    });
  }

  onSubmit(): void {
    if (this.forgotForm.invalid) {
      this.forgotForm.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const { email } = this.forgotForm.value;

    this.authService.forgotPassword({ email }).subscribe({
      next: (response) => {
        this.loading.set(false);
        // The response is intentionally generic: the reset link is emailed,
        // so there is no token for the client to carry to the next step.
        this.successMessage.set(response.message);
      },
      error: (error) => {
        this.loading.set(false);
        this.handleApiError(error);
      },
    });
  }

  private handleApiError(error: any): void {
    const detail = error?.error?.detail;

    if (typeof detail === 'string') {
      this.errorMessage.set(detail);
    } else if (Array.isArray(detail)) {
      this.errorMessage.set(detail.map((d: any) => d.msg).join('. '));
    } else {
      this.errorMessage.set('An unexpected error occurred. Please try again.');
    }
  }

  get email() {
    return this.forgotForm.get('email');
  }
}
