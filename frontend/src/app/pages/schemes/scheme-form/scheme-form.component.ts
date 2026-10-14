import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import {
  FormBuilder,
  FormArray,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { forkJoin } from 'rxjs';
import { SchemeService } from '../../../core/services/scheme.service';
import { PolicyService } from '../../../core/services/policy.service';
import { Policy, PolicyStatus } from '../../../core/models/policy.models';
import {
  SchemeCategory,
  SCHEME_CATEGORY_LABELS,
  SchemeCreateRequest,
  SchemeUpdateRequest,
  EligibilityParameter,
  EligibilityOperator,
  ELIGIBILITY_PARAMETER_LABELS,
  ELIGIBILITY_OPERATOR_LABELS,
} from '../../../core/models/scheme.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';

@Component({
  selector: 'app-scheme-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, ButtonComponent],
  templateUrl: './scheme-form.component.html',
  styleUrl: './scheme-form.component.css',
})
export class SchemeFormComponent implements OnInit {
  private readonly schemeService = inject(SchemeService);
  private readonly policyService = inject(PolicyService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  readonly isEditMode = signal(false);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly success = signal<string | null>(null);
  readonly policies = signal<Policy[]>([]);
  readonly policiesLoading = signal(false);
  private schemeId: string | null = null;

  readonly categories = Object.values(SchemeCategory).map((c) => ({
    value: c,
    label: SCHEME_CATEGORY_LABELS[c],
  }));
  readonly eligibilityParameters = Object.values(EligibilityParameter).map((value) => ({ value, label: ELIGIBILITY_PARAMETER_LABELS[value] }));
  readonly eligibilityOperators = Object.values(EligibilityOperator).map((value) => ({ value, label: ELIGIBILITY_OPERATOR_LABELS[value] }));
  readonly states = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa',
    'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala',
    'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
    'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
    'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Andaman and Nicobar Islands',
    'Chandigarh', 'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Jammu and Kashmir',
    'Ladakh', 'Lakshadweep', 'Puducherry',
  ];

  schemeForm: FormGroup = this.fb.group({
    policy_id: ['', Validators.required],
    title: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(255)]],
    description: ['', [Validators.required, Validators.minLength(1)]],
    category: ['', Validators.required],
    benefits: [''],
    application_process: [''],
    department: [''],
    state: [''],
    required_documents: [''],
    launch_date: [''],
    deadline_date: [''],
    document_url: [''],
    eligibilityRules: this.fb.array([]),
  });

  get eligibilityRules(): FormArray {
    return this.schemeForm.get('eligibilityRules') as FormArray;
  }

  addEligibilityRule(): void {
    this.eligibilityRules.push(this.fb.group({
      parameter: [EligibilityParameter.AGE, Validators.required],
      operator: [EligibilityOperator.GTE, Validators.required],
      value: ['', Validators.required],
    }));
  }

  removeEligibilityRule(index: number): void {
    this.eligibilityRules.removeAt(index);
  }

  ngOnInit(): void {
    this.loadApprovedPolicies();
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.schemeId = id;
      this.isEditMode.set(true);
      this.loadScheme(id);
    }
  }

  loadApprovedPolicies(): void {
    this.policiesLoading.set(true);
    this.policyService.listPolicies().subscribe({
      next: (policies) => {
        this.policies.set(policies.filter((policy) => policy.status === PolicyStatus.APPROVED));
        this.policiesLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load approved policies');
        this.policiesLoading.set(false);
      },
    });
  }

  loadScheme(id: string): void {
    this.loading.set(true);
    this.schemeService.getScheme(id).subscribe({
      next: (scheme) => {
        this.schemeForm.patchValue({
          policy_id: scheme.policy_id,
          title: scheme.title,
          description: scheme.description,
          category: scheme.category,
          benefits: Array.isArray(scheme.benefits) ? scheme.benefits.join('\n') : '',
          application_process: scheme.application_process || '',
          department: scheme.department || '',
          state: scheme.state || '',
          required_documents: Array.isArray(scheme.required_documents) ? scheme.required_documents.join('\n') : '',
          launch_date: scheme.launch_date || '',
          deadline_date: scheme.deadline_date || '',
          document_url: scheme.document_url || '',
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load scheme');
        this.loading.set(false);
      },
    });
  }

  onSubmit(): void {
    if (this.schemeForm.invalid) {
      this.schemeForm.markAllAsTouched();
      return;
    }

    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);

    const formValue = this.schemeForm.value;

    // Parse comma/newline separated strings into arrays
    const parseList = (val: string): string[] | null => {
      if (!val || !val.trim()) return null;
      return val.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    };

    if (this.isEditMode() && this.schemeId) {
      const data: SchemeUpdateRequest = {
        title: formValue.title,
        description: formValue.description,
        category: formValue.category,
        benefits: parseList(formValue.benefits),
        application_process: formValue.application_process || null,
        department: formValue.department || null,
        state: formValue.state || null,
        required_documents: parseList(formValue.required_documents),
        launch_date: formValue.launch_date || null,
        deadline_date: formValue.deadline_date || null,
        document_url: formValue.document_url || null,
      };

      this.schemeService.updateScheme(this.schemeId, data).subscribe({
        next: () => {
          this.saving.set(false);
          this.success.set('Scheme updated successfully');
          setTimeout(() => this.router.navigate(['/schemes', this.schemeId]), 1000);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to update scheme');
          this.saving.set(false);
        },
      });
    } else {
      const data: SchemeCreateRequest = {
        policy_id: formValue.policy_id,
        title: formValue.title,
        description: formValue.description,
        category: formValue.category,
        benefits: parseList(formValue.benefits),
        application_process: formValue.application_process || null,
        department: formValue.department || null,
        state: formValue.state || null,
        required_documents: parseList(formValue.required_documents),
        launch_date: formValue.launch_date || null,
        deadline_date: formValue.deadline_date || null,
        document_url: formValue.document_url || null,
      };

      this.schemeService.createScheme(data).subscribe({
        next: (scheme) => {
          const rules = this.eligibilityRules.getRawValue();
          if (!rules.length) {
            this.finishCreation(scheme.id);
            return;
          }
          forkJoin(rules.map((rule) => this.schemeService.createEligibilityRule(scheme.id, rule))).subscribe({
            next: () => this.finishCreation(scheme.id),
            error: (err) => {
              this.error.set(err.error?.detail || 'Scheme was created, but its eligibility rules could not be saved. You can add them from the scheme page.');
              this.saving.set(false);
            },
          });
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to create scheme');
          this.saving.set(false);
        },
      });
    }
  }

  private finishCreation(schemeId: string): void {
    this.saving.set(false);
    this.success.set('Scheme and eligibility rules created successfully');
    setTimeout(() => this.router.navigate(['/schemes', schemeId]), 1000);
  }

  cancel(): void {
    if (this.isEditMode() && this.schemeId) {
      this.router.navigate(['/schemes', this.schemeId]);
    } else {
      this.router.navigate(['/schemes']);
    }
  }

  goBack(): void {
    this.router.navigate(['/schemes']);
  }
}
