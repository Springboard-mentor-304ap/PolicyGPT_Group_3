import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { CardComponent } from '../../../shared/components/card/card.component';
import { InputComponent } from '../../../shared/components/input/input.component';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { PasswordMeterComponent } from '../../../shared/components/password-meter/password-meter.component';
import { ComplianceAuditComponent } from '../../../shared/components/compliance-audit/compliance-audit.component';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    CardComponent,
    InputComponent,
    ButtonComponent,
    PasswordMeterComponent,
    ComplianceAuditComponent,
  ],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css',
})
export class RegisterComponent {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  registerForm: FormGroup;
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  constructor() {
    this.registerForm = this.fb.group(
      {
        full_name: ['', [Validators.required, Validators.minLength(1)]],
        email: ['', [Validators.required, Validators.email]],
        password: ['', [Validators.required, Validators.minLength(8)]],
        confirmPassword: ['', [Validators.required]],
        agreeTerms: [false, [Validators.requiredTrue]],
      },
      { validators: this.passwordMatchValidator }
    );
  }

  passwordMatchValidator(control: AbstractControl): ValidationErrors | null {
    const password = control.get('password');
    const confirmPassword = control.get('confirmPassword');

    if (password && confirmPassword && password.value !== confirmPassword.value) {
      confirmPassword.setErrors({ passwordMismatch: true });
      return { passwordMismatch: true };
    }

    // Clear the passwordMismatch error when passwords match
    if (confirmPassword?.errors?.['passwordMismatch']) {
      const { passwordMismatch, ...remainingErrors } = confirmPassword.errors;
      confirmPassword.setErrors(Object.keys(remainingErrors).length ? remainingErrors : null);
    }

    return null;
  }

  onSubmit(): void {
    if (this.registerForm.invalid) {
      this.registerForm.markAllAsTouched();
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);

    const { full_name, email, password } = this.registerForm.value;

    this.authService.register({ full_name, email, password }).subscribe({
      next: () => {
        // After successful registration, redirect to role selection
        this.loading.set(false);
        this.router.navigate(['/role-selection']);
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

  get full_name() {
    return this.registerForm.get('full_name');
  }

  get email() {
    return this.registerForm.get('email');
  }

  get password() {
    return this.registerForm.get('password');
  }

  get confirmPassword() {
    return this.registerForm.get('confirmPassword');
  }

  get agreeTerms() {
    return this.registerForm.get('agreeTerms');
  }
}
