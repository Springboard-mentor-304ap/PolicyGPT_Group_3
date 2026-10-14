import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { PolicyService } from '../../../core/services/policy.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  PolicyCategory,
  PolicyStatus,
  POLICY_CATEGORY_LABELS,
} from '../../../core/models/policy.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { DepartmentSelectComponent } from '../../../shared/components/department-select/department-select.component';
import { StateSelectComponent } from '../../../shared/components/state-select/state-select.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-policy-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    ButtonComponent,
    DepartmentSelectComponent,
    StateSelectComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './policy-form.component.html',
  styleUrl: './policy-form.component.css',
})
export class PolicyFormComponent implements OnInit {
  private readonly policyService = inject(PolicyService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  readonly isEditMode = signal(false);
  readonly loading = signal(false);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);
  readonly successMessage = signal<string | null>(null);
  readonly policyId = signal<string>('');

  /**
   * Ministry/department a government official is limited to. The API rejects
   * a policy outside this scope, so the form pre-fills and locks both fields
   * instead of letting the user fill in something that cannot be saved.
   */
  readonly officialScope = signal<string | null>(null);
  readonly isGovernmentOfficial = computed(
    () => this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL
  );
  /** The scope only locks the form once it is known (or when none exists). */
  readonly scopeResolved = signal(false);

  readonly form: FormGroup = this.fb.group({
    title: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(255)]],
    description: ['', [Validators.required, Validators.minLength(1)]],
    category: ['', Validators.required],
    department: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(150)]],
    ministry: ['', Validators.maxLength(150)],
    state: ['', Validators.maxLength(100)],
    document_url: ['', Validators.maxLength(500)],
    published_date: [''],
    required_documents: [''],
  });

  readonly categoryOptions: { value: PolicyCategory; label: string }[] = Object.values(
    PolicyCategory
  ).map((cat) => ({
    value: cat,
    label: POLICY_CATEGORY_LABELS[cat],
  }));

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditMode.set(true);
      this.policyId.set(id);
      this.loadPolicy(id);
    }

    this.loadOfficialScope();
  }

  /**
   * New policies are created inside the official's own ministry, so the form
   * pre-fills the scope. Editing keeps the record's stored values.
   */
  private loadOfficialScope(): void {
    if (!this.isGovernmentOfficial()) {
      this.scopeResolved.set(true);
      return;
    }

    this.authService.getGovernmentOfficialProfile().subscribe({
      next: (profile) => {
        this.officialScope.set(profile.department);
        this.scopeResolved.set(true);

        if (!this.isEditMode()) {
          this.form.patchValue({
            ministry: profile.department,
            department: profile.department,
          });
        }
      },
      error: (error) => {
        this.scopeResolved.set(true);
        this.officialScope.set(null);

        if (!this.isEditMode()) {
          this.error.set(
            error?.error?.detail ||
              'Your ministry could not be loaded, so a policy cannot be created right now.'
          );
        }
      },
    });
  }

  loadPolicy(id: string): void {
    this.loading.set(true);
    this.policyService.getPolicy(id).subscribe({
      next: (policy) => {
        this.form.patchValue({
          title: policy.title,
          description: policy.description,
          category: policy.category,
          department: policy.department,
          ministry: policy.ministry || '',
          state: policy.state || '',
          document_url: policy.document_url || '',
          published_date: policy.published_date || '',
          required_documents: policy.required_documents
            ? policy.required_documents.join(', ')
            : '',
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load policy');
        this.loading.set(false);
      },
    });
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.error.set(null);
    this.successMessage.set(null);

    const formValue = this.form.value;

    // Parse required_documents from comma-separated string
    const requiredDocs = formValue.required_documents
      ? formValue.required_documents
          .split(',')
          .map((d: string) => d.trim())
          .filter((d: string) => d.length > 0)
      : null;

    const payload = {
      title: formValue.title,
      description: formValue.description,
      category: formValue.category,
      department: formValue.department,
      ministry: formValue.ministry || null,
      state: formValue.state || null,
      document_url: formValue.document_url || null,
      published_date: formValue.published_date || null,
      required_documents: requiredDocs,
    };

    if (this.isEditMode()) {
      this.policyService.updatePolicy(this.policyId(), payload).subscribe({
        next: (policy) => {
          this.successMessage.set('Policy updated successfully');
          this.submitting.set(false);
          setTimeout(() => {
            this.router.navigate(['/policies', policy.id]);
          }, 1000);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Failed to update policy');
          this.submitting.set(false);
        },
      });
    } else {
      this.policyService.createPolicy(payload).subscribe({
        next: (policy) => {
          this.successMessage.set('Policy created successfully');
          this.submitting.set(false);
          setTimeout(() => {
            this.router.navigate(['/policies', policy.id]);
          }, 1000);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Failed to create policy');
          this.submitting.set(false);
        },
      });
    }
  }

  goBack(): void {
    if (this.isEditMode()) {
      this.router.navigate(['/policies', this.policyId()]);
    } else {
      this.router.navigate(['/policies']);
    }
  }

  /** Officials always file inside their scope, so both fields are locked. */
  isOfficialScopeLocked(): boolean {
    return this.isGovernmentOfficial() && !!this.officialScope();
  }

  get scopeHint(): string {
    const scope = this.officialScope();

    return scope
      ? `Locked to your ministry/department: ${scope}`
      : '';
  }

  getFieldError(field: string): string | null {
    const control = this.form.get(field);
    if (!control || !control.touched || !control.errors) return null;

    if (control.errors['required']) return `${this.getFieldLabel(field)} is required`;
    if (control.errors['minlength']) {
      const min = control.errors['minlength'].requiredLength;
      return `${this.getFieldLabel(field)} must be at least ${min} characters`;
    }
    if (control.errors['maxlength']) {
      const max = control.errors['maxlength'].requiredLength;
      return `${this.getFieldLabel(field)} must be at most ${max} characters`;
    }
    return null;
  }

  private getFieldLabel(field: string): string {
    const labels: Record<string, string> = {
      title: 'Title',
      description: 'Description',
      category: 'Category',
      department: 'Department',
      ministry: 'Ministry',
      state: 'State',
      document_url: 'Document URL',
      published_date: 'Published Date',
      required_documents: 'Required Documents',
    };
    return labels[field] || field;
  }
}
