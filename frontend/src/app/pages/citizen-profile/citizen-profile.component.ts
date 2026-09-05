import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { CardComponent } from '../../shared/components/card/card.component';
import { InputComponent } from '../../shared/components/input/input.component';
import { ButtonComponent } from '../../shared/components/button/button.component';

@Component({
  selector: 'app-citizen-profile',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    InputComponent,
    ButtonComponent,
  ],
  template: `
    <div class="profile-page">
      <div class="profile-container">
        <div class="profile-header">
          <h1>Citizen Profile</h1>
          <p>Complete your profile for eligibility checking</p>
        </div>

        @if (errorMessage()) {
          <div class="alert alert-error" role="alert">
            <span>{{ errorMessage() }}</span>
          </div>
        }

        @if (successMessage()) {
          <div class="alert alert-success" role="alert">
            <span>{{ successMessage() }}</span>
          </div>
        }

        <form [formGroup]="profileForm" (ngSubmit)="onSubmit()" class="profile-form">
          <div class="form-section">
            <h2>Contact Information</h2>
            <div class="form-row">
              <app-input
                formControlName="phone"
                type="tel"
                label="Phone Number"
                placeholder="+91 98765 43210"
                id="phone"
                name="phone"
              />
            </div>
          </div>

          <div class="form-section">
            <h2>Personal Information</h2>
            <div class="form-row">
              <app-input
                formControlName="date_of_birth"
                type="date"
                label="Date of Birth"
                id="dob"
                name="date_of_birth"
              />

              <div class="form-field">
                <label for="gender">Gender</label>
                <select id="gender" formControlName="gender" class="form-select">
                  <option value="">Select Gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h2>Socioeconomic Information</h2>
            <div class="form-row">
              <app-input
                formControlName="occupation"
                type="text"
                label="Occupation"
                placeholder="e.g., Engineer, Teacher, Farmer"
                id="occupation"
                name="occupation"
              />

              <app-input
                formControlName="annual_income"
                type="number"
                label="Annual Income (INR)"
                placeholder="e.g., 500000"
                id="income"
                name="annual_income"
              />
            </div>

            <div class="form-row">
              <div class="form-field">
                <label for="education">Education</label>
                <select id="education" formControlName="education" class="form-select">
                  <option value="">Select Education Level</option>
                  <option value="below_primary">Below Primary</option>
                  <option value="primary">Primary</option>
                  <option value="secondary">Secondary</option>
                  <option value="higher_secondary">Higher Secondary</option>
                  <option value="graduate">Graduate</option>
                  <option value="post_graduate">Post Graduate</option>
                  <option value="doctorate">Doctorate</option>
                  <option value="diploma">Diploma</option>
                  <option value="professional">Professional Degree</option>
                </select>
              </div>

              <div class="form-field">
                <label for="social_category">Social Category</label>
                <select id="social_category" formControlName="social_category" class="form-select">
                  <option value="">Select Category</option>
                  <option value="general">General</option>
                  <option value="obc">OBC</option>
                  <option value="sc">SC</option>
                  <option value="st">ST</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <label class="checkbox-label">
                <input type="checkbox" formControlName="disability_status" class="checkbox-input" />
                <span class="checkbox-text">Person with Disability (PwD)</span>
              </label>
            </div>
          </div>

          <div class="form-section">
            <h2>Location</h2>
            <div class="form-row">
              <app-input
                formControlName="state"
                type="text"
                label="State"
                placeholder="e.g., Maharashtra"
                id="state"
                name="state"
              />

              <app-input
                formControlName="district"
                type="text"
                label="District"
                placeholder="e.g., Mumbai"
                id="district"
                name="district"
              />
            </div>
          </div>

          <div class="form-actions">
            <app-button
              type="button"
              variant="secondary"
              (btnClick)="goBack()"
            >
              Cancel
            </app-button>
            <app-button
              type="submit"
              variant="primary"
              [loading]="loading()"
              [disabled]="loading()"
            >
              Save Profile
            </app-button>
          </div>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .profile-page {
      min-height: 100vh;
      background: var(--bg-secondary, #f8fafc);
      padding: 2rem;
    }

    .profile-container {
      max-width: 800px;
      margin: 0 auto;
    }

    .profile-header {
      margin-bottom: 2rem;
    }

    .profile-header h1 {
      font-size: 1.75rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 0.5rem;
    }

    .profile-header p {
      color: var(--text-secondary, #64748b);
      margin: 0;
    }

    .profile-form {
      background: white;
      border-radius: 0.75rem;
      padding: 2rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .form-section {
      margin-bottom: 2rem;
      padding-bottom: 2rem;
      border-bottom: 1px solid var(--border-color, #e2e8f0);
    }

    .form-section:last-of-type {
      border-bottom: none;
      margin-bottom: 0;
      padding-bottom: 0;
    }

    .form-section h2 {
      font-size: 1.125rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 1rem;
    }

    .form-row {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1rem;
      margin-bottom: 1rem;
    }

    @media (max-width: 640px) {
      .form-row {
        grid-template-columns: 1fr;
      }
    }

    .form-field {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .form-field label {
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--text-primary, #1a1a2e);
    }

    .form-select {
      padding: 0.75rem 1rem;
      border: 1px solid var(--border-color, #e2e8f0);
      border-radius: 0.5rem;
      font-size: 0.875rem;
      background: white;
      color: var(--text-primary, #1a1a2e);
      cursor: pointer;
    }

    .form-select:focus {
      outline: none;
      border-color: var(--primary-color, #3b82f6);
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }

    .checkbox-label {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      cursor: pointer;
    }

    .checkbox-input {
      width: 1.25rem;
      height: 1.25rem;
      cursor: pointer;
    }

    .checkbox-text {
      font-size: 0.875rem;
      color: var(--text-primary, #1a1a2e);
    }

    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 2rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border-color, #e2e8f0);
    }

    .alert {
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
      margin-bottom: 1rem;
      font-size: 0.875rem;
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
  `]
})
export class CitizenProfileComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  profileForm: FormGroup;
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);

  constructor() {
    this.profileForm = this.fb.group({
      phone: [''],
      date_of_birth: [''],
      gender: [''],
      occupation: [''],
      annual_income: [null],
      social_category: [''],
      disability_status: [false],
      education: [''],
      state: [''],
      district: [''],
    });
  }

  ngOnInit(): void {
    this.loadProfile();
  }

  private loadProfile(): void {
    this.authService.getCitizenProfile().subscribe({
      next: (profile) => {
        this.profileForm.patchValue({
          phone: profile.phone || '',
          date_of_birth: profile.date_of_birth || '',
          gender: profile.gender || '',
          occupation: profile.occupation || '',
          annual_income: profile.annual_income || null,
          social_category: profile.social_category || '',
          disability_status: profile.disability_status || false,
          education: profile.education || '',
          state: profile.state || '',
          district: profile.district || '',
        });
      },
      error: (error) => {
        console.error('Failed to load profile:', error);
      },
    });
  }

  onSubmit(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    const formValue = this.profileForm.value;

    // Clean up empty strings to null
    const payload = {
      phone: formValue.phone || null,
      date_of_birth: formValue.date_of_birth || null,
      gender: formValue.gender || null,
      occupation: formValue.occupation || null,
      annual_income: formValue.annual_income || null,
      social_category: formValue.social_category || null,
      disability_status: formValue.disability_status || false,
      education: formValue.education || null,
      state: formValue.state || null,
      district: formValue.district || null,
    };

    this.authService.updateCitizenProfile(payload).subscribe({
      next: () => {
        this.loading.set(false);
        this.successMessage.set('Profile saved successfully!');
      },
      error: (error) => {
        this.loading.set(false);
        const detail = error?.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Failed to save profile. Please try again.');
      },
    });
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
