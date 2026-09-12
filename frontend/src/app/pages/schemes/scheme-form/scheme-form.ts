import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  FormBuilder,
  FormGroup,
  ReactiveFormsModule,
  Validators
} from '@angular/forms';

@Component({
  selector: 'app-scheme-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './scheme-form.html',
  styleUrl: './scheme-form.css'
})
export class SchemeForm {
  schemeForm: FormGroup;

  categories = [
    'scholarships',
    'farmer-welfare',
    'healthcare',
    'housing',
    'business_support',
    'women_empowerment',
    'senior-citizen-welfare',
    'student-schemes',
    'employment-program',
    'social-security'
  ];

  statuses = [
    'draft',
    'active',
    'archived'
  ];

  constructor(private fb: FormBuilder) {
    this.schemeForm = this.fb.group({
      policy_id: [''],
      title: ['', Validators.required],
      description: ['', Validators.required],
      category: ['', Validators.required],
      benefits: ['', Validators.required],
      application_process: ['', Validators.required],
      department: ['', Validators.required],
      state: ['', Validators.required],
      status: ['draft', Validators.required],
      launch_date: [''],
      deadline_date: [''],
      document_url: ['']
    });
  }

  onSubmit(): void {
    if (this.schemeForm.valid) {
      console.log('Scheme Data:', this.schemeForm.value);
      alert('Scheme submitted successfully!');
    } else {
      this.schemeForm.markAllAsTouched();
    }
  }
}