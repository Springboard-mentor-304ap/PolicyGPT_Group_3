import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SchemeService } from '../../../core/services/scheme.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  Scheme,
  SchemeStatus,
  SCHEME_STATUS_LABELS,
  SCHEME_STATUS_BADGE,
  SCHEME_CATEGORY_LABELS,
  BadgeVariant,
} from '../../../core/models/scheme.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BadgeComponent } from '../../../shared/components/badge/badge.component';

@Component({
  selector: 'app-scheme-details',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonComponent, BadgeComponent],
  templateUrl: './scheme-details.component.html',
  styleUrl: './scheme-details.component.css',
})
export class SchemeDetailsComponent implements OnInit {
  private readonly schemeService = inject(SchemeService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly scheme = signal<Scheme | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionLoading = signal(false);

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

  readonly canEdit = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial()) return false;
    return s.status === SchemeStatus.DRAFT || s.status === SchemeStatus.REJECTED || s.status === SchemeStatus.ARCHIVED;
  });

  readonly canArchive = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial()) return false;
    return s.status === SchemeStatus.ACTIVE;
  });

  readonly canUnarchive = computed(() => {
    const s = this.scheme();
    if (!s || !this.isGovernmentOfficial()) return false;
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
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load scheme');
        this.loading.set(false);
      },
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
