import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { EligibilityCheckRequest, EligibilityResult } from '../../core/models/eligibility.models';
import { EligibilityService } from '../../core/services/eligibility.service';
import { AuthService } from '../../core/services/auth.service';
import { InputComponent } from '../../shared/components/input/input.component';
import { SelectComponent, SelectOption } from '../../shared/components/select/select.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EligibilityResultComponent } from './components/eligibility-result/eligibility-result.component';

@Component({
  selector: 'app-eligibility',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    RouterLink,
    InputComponent,
    SelectComponent,
    ButtonComponent,
    EligibilityResultComponent,
  ],
  templateUrl: './eligibility.component.html',
  styleUrl: './eligibility.component.css',
})
export class EligibilityComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly eligibilityService = inject(EligibilityService);
  private readonly authService = inject(AuthService);

  profileForm!: FormGroup;
  evaluating = signal<boolean>(false);
  hasEvaluated = signal<boolean>(false);
  results = signal<EligibilityResult[]>([]);
  activeTab = signal<'eligible' | 'all'>('eligible');

  genderOptions: SelectOption[] = [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' },
  ];

  socialCategoryOptions: SelectOption[] = [
    { value: 'general', label: 'General / Open' },
    { value: 'obc', label: 'OBC (Other Backward Class)' },
    { value: 'sc', label: 'SC (Scheduled Caste)' },
    { value: 'st', label: 'ST (Scheduled Tribe)' },
    { value: 'other', label: 'Other Minorities' },
  ];

  stateOptions: SelectOption[] = [
    { value: 'Maharashtra', label: 'Maharashtra' },
    { value: 'Karnataka', label: 'Karnataka' },
    { value: 'Uttar Pradesh', label: 'Uttar Pradesh' },
    { value: 'Tamil Nadu', label: 'Tamil Nadu' },
    { value: 'Delhi', label: 'Delhi' },
    { value: 'Gujarat', label: 'Gujarat' },
    { value: 'Rajasthan', label: 'Rajasthan' },
  ];

  occupationOptions: SelectOption[] = [
    { value: 'farmer', label: 'Farmer / Agriculturalist' },
    { value: 'student', label: 'Student / Enrolled in Education' },
    { value: 'salaried', label: 'Salaried Private/Govt Employee' },
    { value: 'self_employed', label: 'Self-Employed / MSME Owner' },
    { value: 'unemployed', label: 'Unemployed / Job Seeker' },
    { value: 'senior_citizen', label: 'Retired / Senior Citizen' },
  ];

  educationOptions: SelectOption[] = [
    { value: '10th', label: 'Secondary (10th Pass)' },
    { value: '12th', label: 'Higher Secondary (12th Pass)' },
    { value: 'Diploma', label: 'Diploma / Vocational' },
    { value: 'Graduate', label: 'Bachelor’s Degree (Graduate)' },
    { value: 'Post-Graduate', label: 'Master’s Degree / Doctorate' },
  ];

  ngOnInit(): void {
    this.profileForm = this.fb.group({
      age: [25, [Validators.required, Validators.min(0), Validators.max(120)]],
      gender: ['male', [Validators.required]],
      annual_income: [180000, [Validators.required, Validators.min(0)]],
      occupation: ['farmer', [Validators.required]],
      education: ['Graduate', [Validators.required]],
      social_category: ['general', [Validators.required]],
      state: ['Maharashtra', [Validators.required]],
      district: ['Pune'],
      disability_status: [false],
    });
  }

  onEvaluate(): void {
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      return;
    }

    this.evaluating.set(true);

    const val = this.profileForm.value;
    const req: EligibilityCheckRequest = {
      age: Number(val.age),
      gender: val.gender,
      annual_income: Number(val.annual_income),
      occupation: val.occupation,
      education: val.education,
      social_category: val.social_category,
      state: val.state,
      district: val.district,
      disability_status: Boolean(val.disability_status),
    };

    this.eligibilityService.evaluateAllSchemes(req).subscribe({
      next: (resList: EligibilityResult[]) => {
        // Sort: eligible first, then higher match score
        const sorted = [...resList].sort((a, b) => b.match_percentage - a.match_percentage);
        this.results.set(sorted);
        this.evaluating.set(false);
        this.hasEvaluated.set(true);
      },
      error: () => {
        this.evaluating.set(false);
      },
    });
  }

  get eligibleSchemes(): EligibilityResult[] {
    return this.results().filter((r) => r.is_eligible);
  }

  get allSchemes(): EligibilityResult[] {
    return this.results();
  }

  resetForm(): void {
    this.hasEvaluated.set(false);
    this.results.set([]);
  }
}
