import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { SearchResultItem } from '../../../../core/models/search.models';
import { EligibilityCheckRequest, EligibilityResult } from '../../../../core/models/eligibility.models';
import { EligibilityService } from '../../../../core/services/eligibility.service';
import { AuthService } from '../../../../core/services/auth.service';
import { ModalComponent } from '../../../../shared/components/modal/modal.component';
import { InputComponent } from '../../../../shared/components/input/input.component';
import { SelectComponent, SelectOption } from '../../../../shared/components/select/select.component';
import { ButtonComponent } from '../../../../shared/components/button/button.component';
import { EligibilityResultComponent } from '../eligibility-result/eligibility-result.component';

@Component({
  selector: 'app-eligibility-modal',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    ModalComponent,
    InputComponent,
    SelectComponent,
    ButtonComponent,
    EligibilityResultComponent,
  ],
  templateUrl: './eligibility-modal.component.html',
  styleUrl: './eligibility-modal.component.css',
})
export class EligibilityModalComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly eligibilityService = inject(EligibilityService);
  private readonly authService = inject(AuthService);

  @Input({ required: true }) scheme!: SearchResultItem;
  @Output() close = new EventEmitter<void>();

  checkForm!: FormGroup;
  evaluating = signal<boolean>(false);
  result = signal<EligibilityResult | null>(null);

  genderOptions: SelectOption[] = [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' },
  ];

  socialCategoryOptions: SelectOption[] = [
    { value: 'general', label: 'General' },
    { value: 'obc', label: 'OBC (Other Backward Class)' },
    { value: 'sc', label: 'SC (Scheduled Caste)' },
    { value: 'st', label: 'ST (Scheduled Tribe)' },
  ];

  stateOptions: SelectOption[] = [
    { value: 'Central', label: 'All India / Central' },
    { value: 'Maharashtra', label: 'Maharashtra' },
    { value: 'Karnataka', label: 'Karnataka' },
    { value: 'Uttar Pradesh', label: 'Uttar Pradesh' },
    { value: 'Tamil Nadu', label: 'Tamil Nadu' },
    { value: 'Delhi', label: 'Delhi' },
  ];

  occupationOptions: SelectOption[] = [
    { value: 'farmer', label: 'Farmer / Agriculture' },
    { value: 'student', label: 'Student / Scholar' },
    { value: 'salaried', label: 'Salaried Employee' },
    { value: 'self_employed', label: 'Self Employed / Business' },
    { value: 'unemployed', label: 'Unemployed / Job Seeker' },
    { value: 'senior_citizen', label: 'Retired / Senior Citizen' },
  ];

  ngOnInit(): void {
    this.checkForm = this.fb.group({
      age: [26, [Validators.required, Validators.min(0), Validators.max(120)]],
      gender: ['male', [Validators.required]],
      annual_income: [200000, [Validators.required, Validators.min(0)]],
      occupation: ['farmer', [Validators.required]],
      education: ['Graduate'],
      social_category: ['general', [Validators.required]],
      state: ['Maharashtra', [Validators.required]],
      disability_status: [false],
    });
  }

  onEvaluate(): void {
    if (this.checkForm.invalid) {
      this.checkForm.markAllAsTouched();
      return;
    }

    this.evaluating.set(true);

    const val = this.checkForm.value;
    const req: EligibilityCheckRequest = {
      scheme_id: this.scheme.id,
      age: Number(val.age),
      gender: val.gender,
      annual_income: Number(val.annual_income),
      occupation: val.occupation,
      education: val.education,
      social_category: val.social_category,
      state: val.state,
      disability_status: Boolean(val.disability_status),
    };

    this.eligibilityService.checkSchemeEligibility(this.scheme.id).subscribe({
      next: (res) => {
        this.result.set(res);
        this.evaluating.set(false);
      },
      error: () => {
        this.evaluating.set(false);
      },
    });
  }

  onReset(): void {
    this.result.set(null);
  }

  onClose(): void {
    this.close.emit();
  }
}
