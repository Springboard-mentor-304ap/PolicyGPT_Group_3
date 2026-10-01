import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../../core/services/application.service';
import {
  ApplicationReviewItem,
  ApplicationStatus,
} from '../../../core/models/application.models';

/** Statuses that still need a decision (mirrors the review page rules). */
const PENDING_STATUSES: ApplicationStatus[] = [
  'submitted',
  'under_review',
  'additional_information_required',
];

/**
 * Dashboard "Application Approvals" card.
 *
 * Loads GET /api/applications/review (server-side department-scoped) and
 * shows the pending count plus the most recent applications, with a link
 * into the full review page.
 */
@Component({
  selector: 'app-application-approvals',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './application-approvals.component.html',
  styleUrl: './application-approvals.component.css',
})
export class ApplicationApprovalsComponent implements OnInit {
  private readonly applicationService = inject(ApplicationService);

  readonly items = signal<ApplicationReviewItem[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  readonly pendingCount = computed(
    () =>
      this.items().filter((item) =>
        PENDING_STATUSES.includes(item.status)
      ).length
  );

  readonly recent = computed<ApplicationReviewItem[]>(() =>
    this.items().slice(0, 3)
  );

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
      error: () => {
        this.items.set([]);
        this.loading.set(false);
        this.loadError.set('Unable to load applications. Please try again.');
      },
    });
  }

  statusLabel(status: ApplicationStatus): string {
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}
