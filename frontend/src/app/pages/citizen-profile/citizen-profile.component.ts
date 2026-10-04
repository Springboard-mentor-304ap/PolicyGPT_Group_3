import { Component, computed, effect, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { UserRole } from '../../core/models/auth.models';
import { GovernmentOfficialProfileResponse } from '../../core/models/auth.models';
import { isCitizenProfileComplete } from '../../core/services/profile-completion';
import { InputComponent } from '../../shared/components/input/input.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-citizen-profile',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    InputComponent,
    ButtonComponent,
    BackToDashboardComponent,
  ],
  template: `
    <div class="profile-page">
      <div class="profile-container page-container page-container--form">
        <!-- Header with back button -->
        <div class="profile-header">
          <div class="header-nav">
            <app-back-to-dashboard></app-back-to-dashboard>
          </div>
          <h1>{{ isGovernmentOfficial() ? 'Government Profile' : 'Citizen Profile' }}</h1>
          <p>
            {{ isGovernmentOfficial()
              ? 'Your official account details and department scope'
              : 'Complete your profile for eligibility checking' }}
          </p>
        </div>

        <!-- Government officials get the read-only official profile instead
             of the citizen eligibility form. -->
        @if (isGovernmentOfficial()) {
          <div class="official-banner">
            <div class="banner-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 21h18"/>
                <path d="M5 21V7l7-4 7 4v14"/>
                <path d="M9 21v-4h6v4"/>
              </svg>
            </div>
            <div class="banner-content">
              <h3>Government official account</h3>
              <p>
                These details come from your approved role request and are
                read-only. Contact an administrator to change them.
              </p>
            </div>
          </div>

          @if (officialProfileError()) {
            <div class="alert alert-error" role="alert">
              <span>{{ officialProfileError() }}</span>
            </div>
          }

          @if (loadingOfficialProfile()) {
            <div class="official-card">
              <p class="official-state">Loading your government profile…</p>
            </div>
          } @else if (officialProfile(); as profile) {
            <div class="official-card">
              <div class="official-grid">
                <div class="official-field">
                  <span class="official-label">Full name</span>
                  <span class="official-value">{{ profile.full_name }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">Email</span>
                  <span class="official-value">{{ profile.email }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">Phone</span>
                  <span class="official-value">{{ profile.phone || 'Not provided' }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">Department / Ministry</span>
                  <span class="official-value">{{ profile.department }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">Designation</span>
                  <span class="official-value">{{ profile.designation }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">Official ID</span>
                  <span class="official-value">{{ profile.official_id }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">State</span>
                  <span class="official-value">{{ profile.state }}</span>
                </div>
                <div class="official-field">
                  <span class="official-label">District</span>
                  <span class="official-value">{{ profile.district || 'Not provided' }}</span>
                </div>
              </div>
            </div>
          }
        } @else {

        <!-- Profile Incomplete Banner -->
        @if (!profileComplete()) {
          <div class="incomplete-banner">
            <div class="banner-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <div class="banner-content">
              <h3>Profile Not Complete</h3>
              <p>Complete your profile to enable eligibility checking for welfare schemes.</p>
            </div>
          </div>
        }

        <!-- Profile Complete Banner -->
        @if (profileComplete()) {
          <div class="complete-banner">
            <div class="banner-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
              </svg>
            </div>
            <div class="banner-content">
              <h3>Profile Complete</h3>
              <p>Your profile is ready for eligibility checking.</p>
            </div>
          </div>
        }

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
        }
      </div>
    </div>
  `,
  styles: [`
    .profile-page {
      min-height: 100vh;
      background: var(--color-bg-app, #f8fafc);
      padding-block: var(--space-6);
    }

    .profile-header {
      margin-bottom: var(--space-6);
    }

    .header-nav {
      margin-bottom: var(--space-2);
    }

    .profile-header h1 {
      font-size: var(--font-size-2xl);
      font-weight: var(--font-weight-bold);
      color: var(--color-text-primary, #0f172a);
      margin: 0 0 var(--space-1);
    }

    .profile-header p {
      color: var(--color-text-secondary, #64748b);
      margin: 0;
    }

    /* Banners */
    .incomplete-banner,
    .complete-banner {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1rem 1.25rem;
      border-radius: 0.75rem;
      margin-bottom: 1.5rem;
    }

    .incomplete-banner {
      background: #fef3c7;
      border: 1px solid #fcd34d;
    }

    .complete-banner {
      background: #d1fae5;
      border: 1px solid #6ee7b7;
    }

    .banner-icon {
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .incomplete-banner .banner-icon {
      color: #d97706;
    }

    .complete-banner .banner-icon {
      color: #059669;
    }

    .banner-icon svg {
      width: 24px;
      height: 24px;
    }

    .banner-content h3 {
      font-size: 0.9375rem;
      font-weight: 600;
      margin: 0 0 0.25rem;
    }

    .incomplete-banner .banner-content h3 {
      color: #92400e;
    }

    .complete-banner .banner-content h3 {
      color: #065f46;
    }

    .banner-content p {
      font-size: 0.8125rem;
      margin: 0;
    }

    .incomplete-banner .banner-content p {
      color: #a16207;
    }

    .complete-banner .banner-content p {
      color: #047857;
    }

    /* Form */
    .profile-form {
      background: white;
      border-radius: 0.75rem;
      padding: 2rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .form-section {
      margin-bottom: 2rem;
      padding-bottom: 2rem;
      border-bottom: 1px solid var(--color-border-subtle, #e2e8f0);
    }

    .form-section:last-of-type {
      border-bottom: none;
      margin-bottom: 0;
      padding-bottom: 0;
    }

    .form-section h2 {
      font-size: 1.125rem;
      font-weight: 600;
      color: var(--color-text-heading, #1a1a2e);
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
      color: var(--color-text-heading, #1a1a2e);
    }

    .form-select {
      padding: 0.75rem 1rem;
      border: 1px solid var(--color-border-subtle, #e2e8f0);
      border-radius: 0.5rem;
      font-size: 0.875rem;
      background: white;
      color: var(--color-text-heading, #1a1a2e);
      cursor: pointer;
    }

    .form-select:focus {
      outline: none;
      border-color: var(--color-primary-blue, #3b82f6);
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
      color: var(--color-text-heading, #1a1a2e);
    }

    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 2rem;
      padding-top: 2rem;
      border-top: 1px solid var(--color-border-subtle, #e2e8f0);
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

    /* Government official (read-only) profile */
    .official-banner {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1rem 1.25rem;
      border-radius: 0.75rem;
      margin-bottom: 1.5rem;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
    }

    .official-banner .banner-icon {
      color: #2563eb;
    }

    .official-banner .banner-content h3 {
      color: #1e3a8a;
    }

    .official-banner .banner-content p {
      color: #1d4ed8;
    }

    .official-card {
      background: white;
      border-radius: 0.75rem;
      padding: 2rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .official-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.25rem 2rem;
    }

    @media (max-width: 640px) {
      .official-grid {
        grid-template-columns: 1fr;
      }
    }

    .official-field {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--color-border-subtle, #e2e8f0);
    }

    .official-label {
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      text-transform: uppercase;
      color: var(--color-text-muted, #64748b);
    }

    .official-value {
      font-size: 0.9375rem;
      font-weight: 500;
      color: var(--color-text-heading, #1a1a2e);
      word-break: break-word;
    }

    .official-state {
      margin: 0;
      color: var(--color-text-muted, #64748b);
      font-size: 0.875rem;
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
  profileComplete = signal(false);

  // ── Government official profile (read-only) ──────────────────────────────
  readonly officialProfile = signal<GovernmentOfficialProfileResponse | null>(null);
  readonly loadingOfficialProfile = signal(false);
  readonly officialProfileError = signal<string | null>(null);

  readonly isGovernmentOfficial = computed(
    () => this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL
  );

  /** Guards the one-shot official profile fetch (see the effect below). */
  private officialProfileRequested = false;

  constructor() {
    // `/auth/me` may still be resolving when this page loads, so the official
    // profile is fetched as soon as the role is known to be an official's.
    effect(() => {
      if (!this.isGovernmentOfficial() || this.officialProfileRequested) {
        return;
      }
      this.officialProfileRequested = true;
      this.loadOfficialProfile();
    });

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

        // Same completion rule the dashboard card uses.
        this.profileComplete.set(isCitizenProfileComplete(profile));
      },
      error: (error) => {
        console.error('Failed to load profile:', error);
        // If 404, profile doesn't exist yet
        this.profileComplete.set(false);
      },
    });
  }

  private loadOfficialProfile(): void {
    this.loadingOfficialProfile.set(true);
    this.officialProfileError.set(null);

    this.authService.getGovernmentOfficialProfile().subscribe({
      next: (profile) => {
        this.officialProfile.set(profile);
        this.loadingOfficialProfile.set(false);
      },
      error: (error) => {
        this.loadingOfficialProfile.set(false);
        const detail = error?.error?.detail;
        this.officialProfileError.set(
          typeof detail === 'string' && detail.trim().length > 0
            ? detail
            : 'Your government profile could not be loaded. Please try again.'
        );
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
        this.profileComplete.set(true);
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
