import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { SchemeService } from '../../../core/services/scheme.service';
import {
  SchemeCategory,
  SCHEME_CATEGORY_LABELS,
  SchemeCreateRequest,
  SchemeUpdateRequest,
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
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  readonly isEditMode = signal(false);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly success = signal<string | null>(null);
  private schemeId: string | null = null;

  readonly categories = Object.values(SchemeCategory).map((c) => ({
    value: c,
    label: SCHEME_CATEGORY_LABELS[c],
  }));

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
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.schemeId = id;
      this.isEditMode.set(true);
      this.loadScheme(id);
    }
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
          this.saving.set(false);
          this.success.set('Scheme created successfully');
          setTimeout(() => this.router.navigate(['/schemes', scheme.id]), 1000);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to create scheme');
          this.saving.set(false);
        },
      });
    }
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
