import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { RoleRequestResponse } from '../../core/models/auth.models';
import { CardComponent } from '../../shared/components/card/card.component';
import { InputComponent } from '../../shared/components/input/input.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';

interface RoleOption {
  id: string;
  title: string;
  description: string;
  icon: string;
}

@Component({
  selector: 'app-role-request',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    InputComponent,
    ButtonComponent,
    BackToDashboardComponent,
  ],
  template: `
    <div class="role-request-page">
      <div class="role-request-container">
        <div class="page-header">
          <app-back-to-dashboard></app-back-to-dashboard>
          <h1>Request Elevated Role</h1>
          <p>Select the role you'd like to apply for</p>
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

        @if (!selectedRole()) {
          <!-- Role Selection -->
          <div class="role-grid">
            @for (role of roles; track role.id) {
              <button
                type="button"
                class="role-card"
                (click)="selectRole(role.id)"
              >
                <div class="role-icon" [attr.data-role]="role.icon">
                  @if (role.icon === 'researcher') {
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="11" cy="11" r="8"></circle>
                      <path d="m21 21-4.35-4.35"></path>
                    </svg>
                  } @else if (role.icon === 'organization') {
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
                      <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                    </svg>
                  } @else if (role.icon === 'government') {
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 21h18"></path>
                      <path d="M5 21V7l7-4 7 4v14"></path>
                      <path d="M9 21v-4h6v4"></path>
                      <path d="M10 9h4"></path>
                      <path d="M10 13h4"></path>
                    </svg>
                  } @else {
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                    </svg>
                  }
                </div>
                <div class="role-content">
                  <h3 class="role-title">{{ role.title }}</h3>
                  <p class="role-description">{{ role.description }}</p>
                </div>
              </button>
            }
          </div>
        } @else {
          <!-- Role-Specific Form -->
          <div class="role-form-container">
            <div class="form-header">
              <button class="back-btn" (click)="clearSelection()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M19 12H5M12 19l-7-7 7-7"></path>
                </svg>
                Back to role selection
              </button>
              <h2>{{ getRoleTitle() }} Application</h2>
            </div>

            <form [formGroup]="roleForm" (ngSubmit)="onSubmit()" class="role-form">
              <!-- Researcher Form -->
              @if (selectedRole() === 'researcher') {
                <div class="form-section">
                  <h3>Research / Professional Information</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="institution_name"
                      type="text"
                      label="Institution / Organization Name"
                      placeholder="e.g., IIT Bombay"
                      id="institution"
                      name="institution_name"
                      [required]="true"
                      [error]="roleForm.get('institution_name')?.invalid && roleForm.get('institution_name')?.touched ? 'Institution name is required' : null"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="department"
                      type="text"
                      label="Department / Faculty"
                      placeholder="e.g., Computer Science"
                      id="department"
                      name="department"

                    />
                    <app-input
                      formControlName="designation"
                      type="text"
                      label="Designation / Role"
                      placeholder="e.g., Assistant Professor"
                      id="designation"
                      name="designation"
                      icon="user"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="research_area"
                      type="text"
                      label="Research Area / Field of Study"
                      placeholder="e.g., Artificial Intelligence"
                      id="research_area"
                      name="research_area"
                    />
                  </div>
                </div>
              }

              <!-- Organization Form -->
              @if (selectedRole() === 'organization') {
                <div class="form-section">
                  <h3>Organization Identity</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="organization_name"
                      type="text"
                      label="Organization Name"
                      placeholder="Enter organization name"
                      id="org_name"
                      name="organization_name"
                      [required]="true"
                      [error]="roleForm.get('organization_name')?.invalid && roleForm.get('organization_name')?.touched ? 'Organization name is required' : null"
                    />
                    <app-input
                      formControlName="organization_type"
                      type="text"
                      label="Organization Type"
                      placeholder="e.g., NGO, Private Ltd"
                      id="org_type"
                      name="organization_type"

                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="registration_id"
                      type="text"
                      label="Registration / Organization ID"
                      placeholder="Enter registration number"
                      id="reg_id"
                      name="registration_id"
                      [required]="true"
                      [error]="roleForm.get('registration_id')?.invalid && roleForm.get('registration_id')?.touched ? 'Registration ID is required' : null"
                    />
                    <app-input
                      formControlName="authorized_representative"
                      type="text"
                      label="Authorized Representative Name"
                      placeholder="Enter representative name"
                      id="rep_name"
                      name="authorized_representative"
                      icon="user"
                      [required]="true"
                      [error]="roleForm.get('authorized_representative')?.invalid && roleForm.get('authorized_representative')?.touched ? 'Representative name is required' : null"
                    />
                  </div>
                </div>

                <div class="form-section">
                  <h3>Contact & Location</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="official_email"
                      type="email"
                      label="Official Email Address"
                      placeholder="official@organization.com"
                      id="org_email"
                      name="official_email"
                      icon="mail"
                      [required]="true"
                      [error]="roleForm.get('official_email')?.invalid && roleForm.get('official_email')?.touched ? 'Official email is required' : null"
                    />
                    <app-input
                      formControlName="phone"
                      type="tel"
                      label="Phone Number"
                      placeholder="+91 98765 43210"
                      id="org_phone"
                      name="phone"

                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="address"
                      type="text"
                      label="Address"
                      placeholder="Enter organization address"
                      id="address"
                      name="address"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="state"
                      type="text"
                      label="State"
                      placeholder="e.g., Maharashtra"
                      id="org_state"
                      name="state"
                    />
                    <app-input
                      formControlName="district"
                      type="text"
                      label="District"
                      placeholder="e.g., Mumbai"
                      id="org_district"
                      name="district"
                    />
                  </div>
                </div>

                <div class="form-section">
                  <h3>Organization Details</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="sector"
                      type="text"
                      label="Sector / Industry"
                      placeholder="e.g., IT, Healthcare"
                      id="sector"
                      name="sector"

                    />
                    <app-input
                      formControlName="organization_size"
                      type="text"
                      label="Organization Size"
                      placeholder="e.g., 50-200"
                      id="org_size"
                      name="organization_size"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="annual_revenue"
                      type="text"
                      label="Annual Revenue / Turnover"
                      placeholder="e.g., 10 Crore"
                      id="revenue"
                      name="annual_revenue"
                    />
                    <app-input
                      formControlName="number_of_employees"
                      type="number"
                      label="Number of Employees"
                      placeholder="e.g., 150"
                      id="employees"
                      name="number_of_employees"
                    />
                  </div>
                </div>
              }

              <!-- Government Official Form -->
              @if (selectedRole() === 'government_official') {
                <div class="form-section">
                  <h3>Official / Employment Information</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="department_ministry"
                      type="text"
                      label="Department / Ministry"
                      placeholder="e.g., Ministry of Education"
                      id="dept"
                      name="department_ministry"
                      [required]="true"
                      [error]="roleForm.get('department_ministry')?.invalid && roleForm.get('department_ministry')?.touched ? 'Department is required' : null"
                    />
                    <app-input
                      formControlName="designation"
                      type="text"
                      label="Designation"
                      placeholder="e.g., Section Officer"
                      id="govt_designation"
                      name="designation"
                      icon="user"
                      [required]="true"
                      [error]="roleForm.get('designation')?.invalid && roleForm.get('designation')?.touched ? 'Designation is required' : null"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="official_id"
                      type="text"
                      label="Employee / Official ID"
                      placeholder="Enter your official ID"
                      id="official_id"
                      name="official_id"
                      [required]="true"
                      [error]="roleForm.get('official_id')?.invalid && roleForm.get('official_id')?.touched ? 'Official ID is required' : null"
                    />
                  </div>
                </div>

                <div class="form-section">
                  <h3>Location</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="state"
                      type="text"
                      label="State"
                      placeholder="e.g., Delhi"
                      id="govt_state"
                      name="state"
                      [required]="true"
                      [error]="roleForm.get('state')?.invalid && roleForm.get('state')?.touched ? 'State is required' : null"
                    />
                    <app-input
                      formControlName="district"
                      type="text"
                      label="District"
                      placeholder="e.g., New Delhi"
                      id="govt_district"
                      name="district"

                    />
                  </div>
                </div>
              }

              <!-- Administrator Form -->
              @if (selectedRole() === 'administrator') {
                <div class="form-section">
                  <h3>Administrator Details</h3>
                  <div class="form-row">
                    <app-input
                      formControlName="official_email"
                      type="email"
                      label="Official / Company Email Address"
                      placeholder="admin@company.com"
                      id="admin_email"
                      name="official_email"
                      icon="mail"
                      [required]="true"
                      [error]="roleForm.get('official_email')?.invalid && roleForm.get('official_email')?.touched ? 'Official email is required' : null"
                    />
                  </div>
                  <div class="form-row">
                    <app-input
                      formControlName="employee_id"
                      type="text"
                      label="Employee ID / Employee Identifier"
                      placeholder="Enter your employee ID"
                      id="employee_id"
                      name="employee_id"
                      [required]="true"
                      [error]="roleForm.get('employee_id')?.invalid && roleForm.get('employee_id')?.touched ? 'Employee ID is required' : null"
                    />
                  </div>
                </div>
              }

              <div class="form-actions">
                <app-button
                  type="button"
                  variant="secondary"
                  (btnClick)="clearSelection()"
                >
                  Cancel
                </app-button>
                <app-button
                  type="submit"
                  variant="primary"
                  [loading]="loading()"
                  [disabled]="loading() || roleForm.invalid"
                >
                  Submit Request
                </app-button>
              </div>
            </form>
          </div>
        }

        <!-- Existing Requests -->
        @if (existingRequests().length > 0) {
          <div class="existing-requests">
            <h2>Your Role Requests</h2>
            <div class="requests-list">
              @for (request of existingRequests(); track request.id) {
                <div class="request-item" [attr.data-status]="request.status">
                  <div class="request-info">
                    <span class="request-role">{{ formatRole(request.requested_role) }}</span>
                    <span class="request-status">{{ request.status }}</span>
                  </div>
                  <div class="request-meta">
                    <span class="request-date">Submitted: {{ formatDate(request.created_at) }}</span>
                    @if (request.reviewed_at) {
                      <span class="review-date">Reviewed: {{ formatDate(request.reviewed_at) }}</span>
                    }
                    @if (request.review_reason) {
                      <span class="review-reason">Reason: {{ request.review_reason }}</span>
                    }
                  </div>
                  @if (request.status === 'pending') {
                    <button class="cancel-btn" (click)="cancelRequest(request.id)">
                      Cancel Request
                    </button>
                  }
                </div>
              }
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .role-request-page {
      min-height: 100vh;
      background: var(--bg-secondary, #f8fafc);
      padding: 2rem;
    }

    .role-request-container {
      max-width: 900px;
      margin: 0 auto;
    }

    .page-header {
      margin-bottom: 2rem;
    }

    .page-header h1 {
      font-size: 1.75rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 0.5rem;
    }

    .page-header p {
      color: var(--text-secondary, #64748b);
      margin: 0;
    }

    .role-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1rem;
    }

    @media (max-width: 640px) {
      .role-grid {
        grid-template-columns: 1fr;
      }
    }

    .role-card {
      display: flex;
      align-items: flex-start;
      gap: 1rem;
      padding: 1.5rem;
      background: white;
      border: 2px solid var(--border-color, #e2e8f0);
      border-radius: 0.75rem;
      cursor: pointer;
      text-align: left;
      transition: all 0.2s;
    }

    .role-card:hover {
      border-color: var(--primary-color, #3b82f6);
      box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
    }

    .role-icon {
      width: 3rem;
      height: 3rem;
      border-radius: 0.75rem;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .role-icon svg {
      width: 1.5rem;
      height: 1.5rem;
    }

    .role-icon[data-role="researcher"] {
      background: #dbeafe;
      color: #2563eb;
    }

    .role-icon[data-role="organization"] {
      background: #dcfce7;
      color: #16a34a;
    }

    .role-icon[data-role="government"] {
      background: #fef3c7;
      color: #d97706;
    }

    .role-icon[data-role="administrator"] {
      background: #f3e8ff;
      color: #9333ea;
    }

    .role-content {
      flex: 1;
    }

    .role-title {
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 0.25rem;
    }

    .role-description {
      font-size: 0.875rem;
      color: var(--text-secondary, #64748b);
      margin: 0;
    }

    .role-form-container {
      background: white;
      border-radius: 0.75rem;
      padding: 2rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }

    .form-header {
      margin-bottom: 2rem;
    }

    .back-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: none;
      border: none;
      color: var(--text-secondary, #64748b);
      cursor: pointer;
      font-size: 0.875rem;
      padding: 0;
      margin-bottom: 1rem;
    }

    .back-btn:hover {
      color: var(--primary-color, #3b82f6);
    }

    .back-btn svg {
      width: 1rem;
      height: 1rem;
    }

    .form-header h2 {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0;
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

    .form-section h3 {
      font-size: 1rem;
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

    .form-row:last-child {
      margin-bottom: 0;
    }

    @media (max-width: 640px) {
      .form-row {
        grid-template-columns: 1fr;
      }
    }

    .form-actions {
      display: flex;
      justify-content: flex-end;
      gap: 1rem;
      margin-top: 2rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border-color, #e2e8f0);
    }

    .existing-requests {
      margin-top: 3rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border-color, #e2e8f0);
    }

    .existing-requests h2 {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
      margin: 0 0 1rem;
    }

    .requests-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    .request-item {
      background: white;
      border: 1px solid var(--border-color, #e2e8f0);
      border-radius: 0.5rem;
      padding: 1rem;
    }

    .request-item[data-status="pending"] {
      border-left: 4px solid #f59e0b;
    }

    .request-item[data-status="approved"] {
      border-left: 4px solid #10b981;
    }

    .request-item[data-status="rejected"] {
      border-left: 4px solid #ef4444;
    }

    .request-item[data-status="cancelled"] {
      border-left: 4px solid #6b7280;
    }

    .request-info {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 0.5rem;
    }

    .request-role {
      font-weight: 600;
      color: var(--text-primary, #1a1a2e);
    }

    .request-status {
      font-size: 0.75rem;
      padding: 0.25rem 0.5rem;
      border-radius: 9999px;
      text-transform: uppercase;
      font-weight: 500;
    }

    .request-status[data-status="pending"],
    [data-status="pending"] .request-status {
      background: #fef3c7;
      color: #92400e;
    }

    .request-status[data-status="approved"],
    [data-status="approved"] .request-status {
      background: #dcfce7;
      color: #166534;
    }

    .request-status[data-status="rejected"],
    [data-status="rejected"] .request-status {
      background: #fef2f2;
      color: #991b1b;
    }

    .request-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      font-size: 0.875rem;
      color: var(--text-secondary, #64748b);
    }

    .review-reason {
      color: #dc2626;
    }

    .cancel-btn {
      margin-top: 0.75rem;
      padding: 0.5rem 1rem;
      background: none;
      border: 1px solid #dc2626;
      color: #dc2626;
      border-radius: 0.375rem;
      font-size: 0.875rem;
      cursor: pointer;
      transition: all 0.2s;
    }

    .cancel-btn:hover {
      background: #fef2f2;
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
export class RoleRequestComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  roleForm!: FormGroup;
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  successMessage = signal<string | null>(null);
  selectedRole = signal<string | null>(null);
  existingRequests = signal<RoleRequestResponse[]>([]);

  roles: RoleOption[] = [
    {
      id: 'researcher',
      title: 'Researcher',
      description: 'Analyze policy data, generate reports, and access research tools',
      icon: 'researcher',
    },
    {
      id: 'organization',
      title: 'Organization',
      description: 'Access bulk services, manage team accounts, and submit proposals',
      icon: 'organization',
    },
    {
      id: 'government_official',
      title: 'Government Official',
      description: 'Manage policies, review applications, and publish announcements',
      icon: 'government',
    },
    {
      id: 'administrator',
      title: 'Administrator',
      description: 'Full system access for managing users and platform settings',
      icon: 'administrator',
    },
  ];

  ngOnInit(): void {
    this.loadExistingRequests();
  }

  private loadExistingRequests(): void {
    this.authService.getMyRoleRequests().subscribe({
      next: (requests) => {
        this.existingRequests.set(requests);
      },
      error: (error) => {
        console.error('Failed to load role requests:', error);
      },
    });
  }

  selectRole(roleId: string): void {
    this.selectedRole.set(roleId);
    this.initForm(roleId);
  }

  clearSelection(): void {
    this.selectedRole.set(null);
    this.roleForm = this.fb.group({});
  }

  private initForm(roleId: string): void {
    switch (roleId) {
      case 'researcher':
        this.roleForm = this.fb.group({
          institution_name: ['', Validators.required],
          department: [''],
          designation: [''],
          research_area: [''],
        });
        break;

      case 'organization':
        this.roleForm = this.fb.group({
          organization_name: ['', Validators.required],
          organization_type: [''],
          registration_id: ['', Validators.required],
          authorized_representative: ['', Validators.required],
          official_email: ['', [Validators.required, Validators.email]],
          phone: [''],
          address: [''],
          state: [''],
          district: [''],
          sector: [''],
          annual_revenue: [''],
          organization_size: [''],
          number_of_employees: [null],
        });
        break;

      case 'government_official':
        this.roleForm = this.fb.group({
          department_ministry: ['', Validators.required],
          designation: ['', Validators.required],
          official_id: ['', Validators.required],
          state: ['', Validators.required],
          district: [''],
        });
        break;

      case 'administrator':
        this.roleForm = this.fb.group({
          official_email: ['', [Validators.required, Validators.email]],
          employee_id: ['', Validators.required],
        });
        break;

      default:
        this.roleForm = this.fb.group({});
    }
  }

  onSubmit(): void {
    if (this.roleForm.invalid) {
      this.roleForm.markAllAsTouched();
      return;
    }

    const roleId = this.selectedRole();
    if (!roleId) return;

    this.loading.set(true);
    this.errorMessage.set(null);
    this.successMessage.set(null);

    // Clean form values - remove empty strings
    const details: Record<string, any> = {};
    Object.keys(this.roleForm.value).forEach(key => {
      const value = this.roleForm.value[key];
      if (value !== null && value !== undefined && value !== '') {
        details[key] = value;
      }
    });

    this.authService.submitRoleRequest({
      requested_role: roleId,
      details,
    }).subscribe({
      next: () => {
        this.loading.set(false);
        this.successMessage.set('Role request submitted successfully!');
        this.clearSelection();
        this.loadExistingRequests();
      },
      error: (error) => {
        this.loading.set(false);
        const detail = error?.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Failed to submit request. Please try again.');
      },
    });
  }

  cancelRequest(requestId: string): void {
    this.authService.cancelRoleRequest(requestId).subscribe({
      next: () => {
        this.successMessage.set('Request cancelled successfully');
        this.loadExistingRequests();
      },
      error: (error) => {
        const detail = error?.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Failed to cancel request');
      },
    });
  }

  getRoleTitle(): string {
    const role = this.roles.find(r => r.id === this.selectedRole());
    return role?.title || '';
  }

  formatRole(role: string): string {
    return role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }
}
