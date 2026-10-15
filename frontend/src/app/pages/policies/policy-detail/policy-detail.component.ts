import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PolicyService } from '../../../core/services/policy.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  Policy,
  PolicyStatus,
  POLICY_CATEGORY_LABELS,
  POLICY_STATUS_LABELS,
  POLICY_STATUS_BADGE,
  BadgeVariant,
} from '../../../core/models/policy.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BadgeComponent } from '../../../shared/components/badge/badge.component';
import { CardComponent } from '../../../shared/components/card/card.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-policy-detail',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonComponent,
    BadgeComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './policy-detail.component.html',
  styleUrl: './policy-detail.component.css',
})
export class PolicyDetailComponent implements OnInit {
  private readonly policyService = inject(PolicyService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly policy = signal<Policy | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionLoading = signal(false);
  readonly showRejectDialog = signal(false);
  readonly rejectReason = signal('');

  readonly policyId = signal<string>('');

  readonly isGovernmentOfficial = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.GOVERNMENT_OFFICIAL;
  });

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly isOwner = computed(() => {
    const p = this.policy();
    const user = this.authService.currentUser();
    return p && user && p.uploaded_by === user.id;
  });

  readonly canEdit = computed(() => {
    const p = this.policy();
    return (
      p &&
      this.isOwner() &&
      (p.status === PolicyStatus.DRAFT ||
        p.status === PolicyStatus.REJECTED ||
        p.status === PolicyStatus.ARCHIVED)
    );
  });

  readonly canArchive = computed(() => {
    const p = this.policy();
    return (
      p &&
      this.isOwner() &&
      p.status !== PolicyStatus.ARCHIVED &&
      p.status !== PolicyStatus.PENDING_APPROVAL
    );
  });

  readonly canUnarchive = computed(() => {
    const p = this.policy();
    return p && this.isOwner() && p.status === PolicyStatus.ARCHIVED;
  });

  readonly canApprove = computed(() => {
    const p = this.policy();
    return this.isAdmin() && p && p.status === PolicyStatus.PENDING_APPROVAL;
  });

  readonly canReject = computed(() => {
    const p = this.policy();
    return this.isAdmin() && p && p.status === PolicyStatus.PENDING_APPROVAL;
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.policyId.set(id);
      this.loadPolicy(id);
    }
  }

  loadPolicy(id: string): void {
    this.loading.set(true);
    this.error.set(null);
    this.policyService.getPolicy(id).subscribe({
      next: (policy) => {
        this.updatePolicyDetails(policy);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to load policy');
        this.loading.set(false);
      },
    });
  }

  editPolicy(): void {
    const id = this.policyId();
    if (id) {
      this.router.navigate(['/policies', id, 'edit']);
    }
  }

  archivePolicy(): void {
    if (!confirm('Are you sure you want to archive this policy?')) return;
    this.actionLoading.set(true);
    this.policyService.archivePolicy(this.policyId()).subscribe({
      next: (policy) => {
        this.updatePolicyDetails(policy);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to archive policy');
        this.actionLoading.set(false);
      },
    });
  }

  unarchivePolicy(): void {
    this.actionLoading.set(true);
    this.policyService.unarchivePolicy(this.policyId()).subscribe({
      next: (policy) => {
        this.updatePolicyDetails(policy);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to unarchive policy');
        this.actionLoading.set(false);
      },
    });
  }

  approvePolicy(): void {
    if (!confirm('Approve this policy?')) return;
    this.actionLoading.set(true);
    this.policyService.approvePolicy(this.policyId()).subscribe({
      next: (policy) => {
        this.updatePolicyDetails(policy);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to approve policy');
        this.actionLoading.set(false);
      },
    });
  }

  openRejectDialog(): void {
    this.rejectReason.set('');
    this.showRejectDialog.set(true);
  }

  closeRejectDialog(): void {
    this.showRejectDialog.set(false);
    this.rejectReason.set('');
  }

  submitRejection(): void {
    const reason = this.rejectReason().trim();
    if (!reason) return;

    this.actionLoading.set(true);
    this.policyService.rejectPolicy(this.policyId(), { rejection_reason: reason }).subscribe({
      next: (policy) => {
        this.policy.set(policy);
        this.showRejectDialog.set(false);
        this.rejectReason.set('');
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || 'Failed to reject policy');
        this.actionLoading.set(false);
      },
    });
  }

  goBack(): void {
    this.router.navigate(['/policies']);
  }

  private updatePolicyDetails(policy: Policy): void {
    // The detail endpoint returns the policy WITH its schemes, but the action
    // endpoints (archive/approve/reject/update) return the scheme-less
    // summary. Keep the already-loaded list in that case — and never drop
    // the one the detail response provides, which used to zero the
    // "Available Schemes" count on first load.
    const schemes = policy.schemes ?? this.policy()?.schemes;
    this.policy.set({ ...policy, schemes });
  }

  formatCategory(category: string): string {
    return POLICY_CATEGORY_LABELS[category as keyof typeof POLICY_CATEGORY_LABELS] || category;
  }

  formatStatus(status: PolicyStatus): string {
    return POLICY_STATUS_LABELS[status] || status;
  }

  getStatusBadgeVariant(status: PolicyStatus): BadgeVariant {
    return POLICY_STATUS_BADGE[status] || 'neutral';
  }

  viewScheme(schemeId: string): void {
    this.router.navigate(['/schemes', schemeId]);
  }

  formatSchemeCategory(category: string): string {
    return category.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  }

  formatDateTime(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
