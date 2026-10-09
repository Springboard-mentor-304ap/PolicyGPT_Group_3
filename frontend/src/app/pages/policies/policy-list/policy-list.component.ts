import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PolicyService } from '../../../core/services/policy.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  Policy,
  PolicyStatus,
  PolicyCategory,
  POLICY_CATEGORY_LABELS,
  POLICY_STATUS_LABELS,
  POLICY_STATUS_BADGE,
  BadgeVariant,
} from '../../../core/models/policy.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BadgeComponent } from '../../../shared/components/badge/badge.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

/** Listing scope offered to government officials. */
export type PolicyOwnerFilter = 'all' | 'mine';

@Component({
  selector: 'app-policy-list',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonComponent,
    BadgeComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './policy-list.component.html',
  styleUrl: './policy-list.component.css',
})
export class PolicyListComponent implements OnInit {
  private readonly policyService = inject(PolicyService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly policies = signal<Policy[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly searchQuery = signal('');
  readonly statusFilter = signal<string>('');
  readonly categoryFilter = signal<string>('');
  readonly includeArchived = signal(false);
  /**
   * "All" shows every policy in the official's ministry/department scope;
   * "By Me" narrows that scope to the records they uploaded themselves. The
   * backend applies both filters, so the signal only drives the request.
   */
  readonly ownerFilter = signal<PolicyOwnerFilter>('all');

  readonly isGovernmentOfficial = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.GOVERNMENT_OFFICIAL;
  });

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly filteredPolicies = computed(() => {
    let result = this.policies();

    const query = this.searchQuery().toLowerCase();
    if (query) {
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(query) ||
          p.department.toLowerCase().includes(query) ||
          p.description.toLowerCase().includes(query)
      );
    }

    const status = this.statusFilter();
    if (status) {
      result = result.filter((p) => p.status === status);
    }

    const category = this.categoryFilter();
    if (category) {
      result = result.filter((p) => p.category === category);
    }

    return result;
  });

  ngOnInit(): void {
    this.loadPolicies();
  }

  loadPolicies(): void {
    this.loading.set(true);
    this.error.set(null);
    this.policyService
      .listPolicies(this.includeArchived(), this.isByMe())
      .subscribe({
        next: (policies) => {
          this.policies.set(policies);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail || 'Failed to load policies');
          this.loading.set(false);
        },
      });
  }

  /** Only an official's listing has a "By Me" scope. */
  readonly isByMe = computed(
    () => this.isGovernmentOfficial() && this.ownerFilter() === 'mine'
  );

  setOwnerFilter(filter: PolicyOwnerFilter): void {
    if (this.ownerFilter() === filter) {
      return;
    }

    this.ownerFilter.set(filter);
    this.loadPolicies();
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  onStatusFilter(event: Event): void {
    this.statusFilter.set((event.target as HTMLSelectElement).value);
  }

  onCategoryFilter(event: Event): void {
    this.categoryFilter.set((event.target as HTMLSelectElement).value);
  }

  toggleArchived(): void {
    this.includeArchived.set(!this.includeArchived());
    this.loadPolicies();
  }

  viewPolicy(policy: Policy): void {
    this.router.navigate(['/policies', policy.id]);
  }

  createPolicy(): void {
    this.router.navigate(['/policies/create']);
  }

  formatCategory(category: PolicyCategory): string {
    return POLICY_CATEGORY_LABELS[category] || category;
  }

  formatStatus(status: PolicyStatus): string {
    return POLICY_STATUS_LABELS[status] || status;
  }

  getStatusBadgeVariant(status: PolicyStatus): BadgeVariant {
    return POLICY_STATUS_BADGE[status] || 'neutral';
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  getStatusOptions(): { value: string; label: string }[] {
    return [
      { value: '', label: 'All Statuses' },
      { value: PolicyStatus.PENDING_APPROVAL, label: 'Pending Approval' },
      { value: PolicyStatus.APPROVED, label: 'Approved' },
      { value: PolicyStatus.REJECTED, label: 'Rejected' },
      { value: PolicyStatus.ARCHIVED, label: 'Archived' },
    ];
  }

  getCategoryOptions(): { value: string; label: string }[] {
    const options = [{ value: '', label: 'All Categories' }];
    Object.values(PolicyCategory).forEach((cat) => {
      options.push({ value: cat, label: POLICY_CATEGORY_LABELS[cat] });
    });
    return options;
  }
}
