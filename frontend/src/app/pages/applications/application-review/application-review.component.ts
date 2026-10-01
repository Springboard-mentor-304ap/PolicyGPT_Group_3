import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../../core/services/application.service';
import {
  ApplicationReviewItem,
  ApplicationStatus,
} from '../../../core/models/application.models';

/**
 * Government Official "Application Approvals" review page.
 *
 * Replaces the earlier manual-ID lookup: applications are listed from
 * GET /api/applications/review (server-side department-scoped) and the
 * status change reuses PATCH /api/applications/{id}/status.
 */

/** Mirrors ALLOWED_STATUS_TRANSITIONS in backend/app/applications/service.py. */
const ALLOWED_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  submitted: ['under_review'],
  under_review: ['additional_information_required', 'approved', 'rejected'],
  additional_information_required: ['under_review'],
  approved: [],
  rejected: [],
};

/** Statuses counted as "Pending Review" (everything not terminal). */
const PENDING_STATUSES: ApplicationStatus[] = [
  'submitted',
  'under_review',
  'additional_information_required',
];

type StatusFilter = 'all' | 'pending' | ApplicationStatus;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

@Component({
  selector: 'app-application-review',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './application-review.component.html',
  styleUrl: './application-review.component.css',
})
export class ApplicationReviewComponent implements OnInit {
  private readonly applicationService = inject(ApplicationService);

  // ── List state ───────────────────────────────────────────────────────────
  readonly items = signal<ApplicationReviewItem[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  // ── Filters ──────────────────────────────────────────────────────────────
  readonly statusFilter = signal<StatusFilter>('all');
  readonly schemeFilter = signal<string>('all');
  readonly search = signal('');

  // ── Detail / update form ─────────────────────────────────────────────────
  readonly selectedId = signal<string | null>(null);
  readonly selectedStatus = signal<ApplicationStatus | ''>('');
  readonly remarks = signal('');
  readonly updating = signal(false);
  readonly successMessage = signal<string | null>(null);
  readonly updateError = signal<string | null>(null);

  // ── Summary counts (always over the full scoped list) ────────────────────
  readonly pendingCount = computed(
    () =>
      this.items().filter((item) =>
        PENDING_STATUSES.includes(item.status)
      ).length
  );
  readonly approvedCount = computed(
    () => this.items().filter((item) => item.status === 'approved').length
  );
  readonly rejectedCount = computed(
    () => this.items().filter((item) => item.status === 'rejected').length
  );

  readonly schemeOptions = computed<string[]>(() => {
    const titles = new Set<string>();
    for (const item of this.items()) {
      titles.add(item.scheme_title);
    }
    return [...titles].sort((a, b) => a.localeCompare(b));
  });

  readonly filteredItems = computed<ApplicationReviewItem[]>(() => {
    const status = this.statusFilter();
    const scheme = this.schemeFilter();
    const search = this.search().trim().toLowerCase();

    return this.items().filter((item) => {
      if (status === 'pending' && !PENDING_STATUSES.includes(item.status)) {
        return false;
      }
      if (status !== 'all' && status !== 'pending' && item.status !== status) {
        return false;
      }
      if (scheme !== 'all' && item.scheme_title !== scheme) {
        return false;
      }
      if (search) {
        const haystack = [
          item.applicant_name ?? '',
          item.scheme_title,
          item.id,
          item.user_id,
        ]
          .join(' ')
          .toLowerCase();
        if (!haystack.includes(search)) {
          return false;
        }
      }
      return true;
    });
  });

  readonly selected = computed<ApplicationReviewItem | null>(() => {
    const id = this.selectedId();
    if (!id || !UUID_PATTERN.test(id)) {
      return null;
    }
    return this.items().find((item) => item.id === id) ?? null;
  });

  /** Legal next statuses for the selected application (backend rules). */
  readonly allowedNextStatuses = computed<ApplicationStatus[]>(() => {
    const app = this.selected();
    if (!app) {
      return [];
    }
    return ALLOWED_TRANSITIONS[app.status] ?? [];
  });

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.applicationService.reviewApplications().subscribe({
      next: (items) => {
        this.items.set(items);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.items.set([]);
        this.loading.set(false);
        this.loadError.set(
          this.describeError(error, 'Unable to load applications. Please try again.')
        );
      },
    });
  }

  setStatusFilter(value: string): void {
    this.statusFilter.set(value as StatusFilter);
  }

  setSchemeFilter(value: string): void {
    this.schemeFilter.set(value);
  }

  select(item: ApplicationReviewItem): void {
    this.selectedId.set(item.id);
    this.selectedStatus.set('');
    this.remarks.set('');
    this.successMessage.set(null);
    this.updateError.set(null);
  }

  cancelSelection(): void {
    this.selectedId.set(null);
    this.selectedStatus.set('');
    this.remarks.set('');
    this.successMessage.set(null);
    this.updateError.set(null);
  }

  selectStatus(value: string): void {
    this.selectedStatus.set((value || '') as ApplicationStatus | '');
  }

  updateStatus(): void {
    const app = this.selected();
    const status = this.selectedStatus();
    if (!app || !status) {
      return;
    }

    this.updating.set(true);
    this.successMessage.set(null);
    this.updateError.set(null);

    const remarks = this.remarks().trim();

    this.applicationService
      .updateApplicationStatus(app.id, { status, remarks: remarks || null })
      .subscribe({
        next: (updated) => {
          this.updating.set(false);
          this.successMessage.set(
            `Application status updated to “${this.statusLabel(updated.status)}”.`
          );
          // Reflect the change in the list immediately (counts recompute).
          this.items.update((list) =>
            list.map((item) =>
              item.id === updated.id ? { ...item, ...updated } : item
            )
          );
          this.selectedStatus.set('');
          this.remarks.set('');
        },
        error: (error: unknown) => {
          this.updating.set(false);
          this.updateError.set(
            this.describeError(
              error,
              'Unable to update application status.'
            )
          );
        },
      });
  }

  isPending(item: ApplicationReviewItem): boolean {
    return PENDING_STATUSES.includes(item.status);
  }

  statusLabel(status: ApplicationStatus): string {
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  shortId(id: string): string {
    return UUID_PATTERN.test(id) ? `APP-${id.slice(0, 8).toUpperCase()}` : id;
  }

  applicantLabel(item: ApplicationReviewItem): string {
    return item.applicant_name?.trim() || 'Applicant';
  }

  departmentLabel(item: ApplicationReviewItem): string {
    return item.scheme_department ?? item.policy_ministry ?? '—';
  }

  formatDate(value: string): string {
    return new Date(value).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  private describeError(error: unknown, fallback: string): string {
    const httpError = error as {
      status?: number;
      error?: { detail?: unknown };
    };
    const detail = httpError?.error?.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail;
    }
    if (httpError?.status === 401) {
      return 'Your session has expired. Please sign in again.';
    }
    if (httpError?.status === 403) {
      return 'You do not have permission to perform this action.';
    }
    return fallback;
  }
}
