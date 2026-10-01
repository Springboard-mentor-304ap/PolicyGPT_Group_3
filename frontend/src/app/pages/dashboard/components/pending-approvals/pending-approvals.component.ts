import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RoleRequestResponse } from '../../../../core/models/auth.models';
import { humanize } from '../../../../core/services/analytics.mappers';

/**
 * Administrator-only "Pending Role Approvals" section.
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. Approval/rejection stays
 * in the parent (same API calls) and is triggered through outputs.
 */
@Component({
  selector: 'app-pending-approvals',
  standalone: true,
  imports: [],
  templateUrl: './pending-approvals.component.html',
  styleUrl: './pending-approvals.component.css',
})
export class PendingApprovalsComponent {
  @Input({ required: true }) requests: RoleRequestResponse[] = [];

  @Output() approve = new EventEmitter<string>();
  @Output() reject = new EventEmitter<string>();

  formatRole(value: string): string {
    return humanize(value);
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  getDetailEntries(details: Record<string, any>): [string, any][] {
    return Object.entries(details).slice(0, 4);
  }
}
