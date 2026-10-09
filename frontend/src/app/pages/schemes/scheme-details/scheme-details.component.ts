import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SchemeService } from '../../../core/services/scheme.service';
import { ApplicationService } from '../../../core/services/application.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  Scheme,
  SchemeStatus,
  SCHEME_STATUS_LABELS,
  SCHEME_STATUS_BADGE,
  SCHEME_CATEGORY_LABELS,
  BadgeVariant,
  EligibilityRule,
  EligibilityParameter,
  EligibilityOperator,
  ELIGIBILITY_PARAMETER_LABELS,
  ELIGIBILITY_OPERATOR_LABELS,
} from '../../../core/models/scheme.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BadgeComponent } from '../../../shared/components/badge/badge.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-scheme-details',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    ButtonComponent,
    BadgeComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './scheme-details.component.html',
  styleUrl: './scheme-details.component.css',
})
export class SchemeDetailsComponent implements OnInit {
  private readonly schemeService = inject(SchemeService);
  private readonly applicationService = inject(ApplicationService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly scheme = signal<Scheme | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionLoading = signal(false);
  readonly eligibilityRules = signal<EligibilityRule[]>([]);
  readonly rulesLoading = signal(false);
  readonly ruleSaving = signal(false);
  readonly ruleError = signal<string | null>(null);
  readonly newRuleParameter = signal<EligibilityParameter>(EligibilityParameter.AGE);
  readonly newRuleOperator = signal<EligibilityOperator>(EligibilityOperator.GTE);
  readonly newRuleValue = signal('');
  readonly eligibilityParameters = Object.values(EligibilityParameter).map((value) => ({ value, label: ELIGIBILITY_PARAMETER_LABELS[value] }));
  readonly eligibilityOperators = Object.values(EligibilityOperator).map((value) => ({ value, label: ELIGIBILITY_OPERATOR_LABELS[value] }));

  // Reject dialog state
  readonly showRejectDialog = signal(false);
  readonly rejectionReason = signal('');

  readonly isGovernmentOfficial = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.GOVERNMENT_OFFICIAL;
  });

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  /**
   * The API only lets the official who created a scheme update or archive it,
   * so the lifecycle actions stay hidden on records created by someone else.
   */
  readonly isOwner = computed(() => {
    const s = this.scheme();
    return !!s && this.authService.currentUser()?.id === s.created_by;
  });

  readonly canEdit = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial() || !this.isOwner()) return false;
    return s.status === SchemeStatus.DRAFT || s.status === SchemeStatus.REJECTED || s.status === SchemeStatus.ARCHIVED;
  });

  readonly canArchive = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial() || !this.isOwner()) return false;
    return s.status === SchemeStatus.ACTIVE;
  });

  readonly canUnarchive = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial() || !this.isOwner()) return false;
    return s.status === SchemeStatus.ARCHIVED;
  });

  readonly canApprove = computed(() => {
    const s = this.scheme();
    if (!s || !this.isAdmin()) return false;
    return s.status === SchemeStatus.PENDING_APPROVAL;
  });

  readonly canReject = computed(() => {
    const s = this.scheme();
    if (!s || !this.isAdmin()) return false;
    return s.status === SchemeStatus.PENDING_APPROVAL;
  });

  readonly canManageEligibility = computed(() => {
    const s = this.scheme();
    return !!s
      && this.isGovernmentOfficial()
      && this.isOwner()
      && s.status !== SchemeStatus.ARCHIVED;
  });

  // ── Apply for the scheme (citizens / organizations) ─────────────────────
  readonly applying = signal(false);
  readonly applySuccess = signal(false);
  readonly applyError = signal<string | null>(null);

  readonly canApply = computed(() => {
    const s = this.scheme();
    if (!s || s.status !== SchemeStatus.ACTIVE) return false;
    const role = this.authService.userRole();
    return role === UserRole.CITIZEN || role === UserRole.ORGANIZATION;
  });

  applyToScheme(): void {
    const s = this.scheme();
    if (!s || this.applying()) return;

    this.applying.set(true);
    this.applyError.set(null);
    this.applySuccess.set(false);

    this.applicationService.submitApplication(s.id).subscribe({
      next: () => {
        this.applying.set(false);
        this.applySuccess.set(true);
      },
      error: (error: unknown) => {
        this.applying.set(false);
        const httpError = error as {
          status?: number;
          error?: { detail?: unknown };
        };
        const detail = httpError?.error?.detail;
        if (typeof detail === 'string' && detail.trim().length > 0) {
          this.applyError.set(detail);
        } else if (httpError?.status === 401) {
          this.applyError.set('Your session has expired. Please sign in again.');
        } else {
          this.applyError.set('Your application could not be submitted. Please try again.');
        }
      },
    });
  }

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadScheme(id);
    } else {
      this.error.set('No scheme ID provided');
      this.loading.set(false);
    }
  }

  loadScheme(id: string): void {
    this.loading.set(true);
    this.error.set(null);

    this.schemeService.getScheme(id).subscribe({
      next: (scheme) => {
        this.scheme.set(scheme);
        this.loadEligibilityRules(scheme.id);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load scheme');
        this.loading.set(false);
      },
    });
  }

  loadEligibilityRules(schemeId: string): void {
    this.rulesLoading.set(true);
    this.schemeService.listEligibilityRules(schemeId).subscribe({
      next: (rules) => { this.eligibilityRules.set(rules); this.rulesLoading.set(false); },
      error: () => { this.ruleError.set('Could not load eligibility rules.'); this.rulesLoading.set(false); },
    });
  }

  addEligibilityRule(): void {
    const scheme = this.scheme();
    const value = this.newRuleValue().trim();
    if (!scheme || !value) return;
    this.ruleSaving.set(true);
    this.ruleError.set(null);
    this.schemeService.createEligibilityRule(scheme.id, { parameter: this.newRuleParameter(), operator: this.newRuleOperator(), value }).subscribe({
      next: (rule) => { this.eligibilityRules.update((rules) => [...rules, rule]); this.newRuleValue.set(''); this.ruleSaving.set(false); },
      error: (err) => { this.ruleError.set(err.error?.detail || 'Could not add eligibility rule.'); this.ruleSaving.set(false); },
    });
  }

  deleteEligibilityRule(rule: EligibilityRule): void {
    this.ruleSaving.set(true);
    this.ruleError.set(null);
    this.schemeService.deleteEligibilityRule(rule.id).subscribe({
      next: () => { this.eligibilityRules.update((rules) => rules.filter((item) => item.id !== rule.id)); this.ruleSaving.set(false); },
      error: (err) => { this.ruleError.set(err.error?.detail || 'Could not remove eligibility rule.'); this.ruleSaving.set(false); },
    });
  }

  goBack(): void {
    this.router.navigate(['/schemes']);
  }

  editScheme(): void {
    const s = this.scheme();
    if (s) {
      this.router.navigate(['/schemes', s.id, 'edit']);
    }
  }

  archiveScheme(): void {
    const s = this.scheme();
    if (!s) return;

    this.actionLoading.set(true);
    this.schemeService.archiveScheme(s.id).subscribe({
      next: (updated) => {
        this.scheme.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to archive scheme');
        this.actionLoading.set(false);
      },
    });
  }

  unarchiveScheme(): void {
    const s = this.scheme();
    if (!s) return;

    this.actionLoading.set(true);
    this.schemeService.unarchiveScheme(s.id).subscribe({
      next: (updated) => {
        this.scheme.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to unarchive scheme');
        this.actionLoading.set(false);
      },
    });
  }

  approveScheme(): void {
    const s = this.scheme();
    if (!s) return;

    this.actionLoading.set(true);
    this.schemeService.approveScheme(s.id).subscribe({
      next: (updated) => {
        this.scheme.set(updated);
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to approve scheme');
        this.actionLoading.set(false);
      },
    });
  }

  openRejectDialog(): void {
    this.rejectionReason.set('');
    this.showRejectDialog.set(true);
  }

  closeRejectDialog(): void {
    this.showRejectDialog.set(false);
    this.rejectionReason.set('');
  }

  rejectScheme(): void {
    const s = this.scheme();
    const reason = this.rejectionReason().trim();
    if (!s || !reason) return;

    this.actionLoading.set(true);
    this.schemeService.rejectScheme(s.id, { rejection_reason: reason }).subscribe({
      next: (updated) => {
        this.scheme.set(updated);
        this.showRejectDialog.set(false);
        this.rejectionReason.set('');
        this.actionLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to reject scheme');
        this.actionLoading.set(false);
      },
    });
  }

  getStatusLabel(status: SchemeStatus): string {
    return SCHEME_STATUS_LABELS[status] || status;
  }

  getStatusBadge(status: SchemeStatus): BadgeVariant {
    return SCHEME_STATUS_BADGE[status] || 'neutral';
  }

  getCategoryLabel(category: string): string {
    return (SCHEME_CATEGORY_LABELS as Record<string, string>)[category] || category;
  }

  getEligibilityParameterLabel(parameter: EligibilityParameter): string {
    return ELIGIBILITY_PARAMETER_LABELS[parameter] || parameter;
  }

  getEligibilityOperatorLabel(operator: EligibilityOperator): string {
    return ELIGIBILITY_OPERATOR_LABELS[operator] || operator;
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  formatDateTime(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
