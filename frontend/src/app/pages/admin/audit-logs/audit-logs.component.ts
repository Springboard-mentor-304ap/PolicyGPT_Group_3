import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { AdminService } from '../../../core/services/admin.service';
import { AuditLogEntry } from '../../../core/models/admin.models';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

/**
 * Administrator "Audit Logs" page.
 *
 * Reads the existing GET /api/audit-logs endpoint (administrator and super
 * admin only, enforced by the server and mirrored by the route guard).
 * Filters, paging and limits match what the API actually supports; the API
 * returns actor/target IDs only, so rows are identified by short IDs rather
 * than display names.
 */
@Component({
  selector: 'app-audit-logs',
  standalone: true,
  imports: [CommonModule, FormsModule, BackToDashboardComponent],
  templateUrl: './audit-logs.component.html',
  styleUrl: './audit-logs.component.css',
})
export class AuditLogsComponent implements OnInit {
  private readonly adminService = inject(AdminService);

  readonly logs = signal<AuditLogEntry[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly unauthorized = signal(false);
  readonly total = signal(0);

  readonly pageSize = 25;
  page = 0;

  actionFilter = '';
  targetTableFilter = '';
  dateFromFilter = '';
  dateToFilter = '';

  /** Entry whose `changes` payload is expanded inline. */
  expandedId = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.unauthorized.set(false);

    this.adminService
      .listAuditLogs({
        action: this.actionFilter,
        target_table: this.targetTableFilter,
        date_from: this.dateFromFilter || undefined,
        date_to: this.dateToFilter || undefined,
        limit: this.pageSize,
        offset: this.page * this.pageSize,
      })
      .subscribe({
        next: ({ items, total }) => {
          this.logs.set(items);
          this.total.set(total);
          this.loading.set(false);
        },
        error: (err) => this.handleLoadError(err),
      });
  }

  applyFilters(): void {
    this.page = 0;
    this.load();
  }

  clearFilters(): void {
    this.actionFilter = '';
    this.targetTableFilter = '';
    this.dateFromFilter = '';
    this.dateToFilter = '';
    this.page = 0;
    this.load();
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.total() / this.pageSize));
  }

  get pageStart(): number {
    return this.total() === 0 ? 0 : this.page * this.pageSize + 1;
  }

  get pageEnd(): number {
    return Math.min(this.total(), (this.page + 1) * this.pageSize);
  }

  prevPage(): void {
    if (this.page > 0) {
      this.page -= 1;
      this.load();
    }
  }

  nextPage(): void {
    if (this.page + 1 < this.totalPages) {
      this.page += 1;
      this.load();
    }
  }

  toggleChanges(entry: AuditLogEntry): void {
    this.expandedId.set(this.expandedId() === entry.id ? null : entry.id);
  }

  /** Whether the row has a non-empty changes payload to expand. */
  hasChanges(entry: AuditLogEntry): boolean {
    return !!entry.changes && Object.keys(entry.changes).length > 0;
  }

  formatChanges(changes: Record<string, unknown> | null | undefined): string {
    if (!changes || Object.keys(changes).length === 0) {
      return 'No field changes recorded.';
    }
    try {
      return JSON.stringify(changes, null, 2);
    } catch {
      return 'Changes could not be displayed.';
    }
  }

  /** First 8 characters is enough to correlate rows without the noise. */
  shortId(id: string): string {
    return id ? id.slice(0, 8) : '—';
  }

  formatTimestamp(dateStr: string): string {
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  private handleLoadError(err: unknown): void {
    const httpError = err as { status?: number; error?: { detail?: unknown } };
    this.loading.set(false);

    if (httpError?.status === 403) {
      this.unauthorized.set(true);
      this.logs.set([]);
      this.total.set(0);
      return;
    }

    const detail = httpError?.error?.detail;
    this.loadError.set(
      typeof detail === 'string' && detail
        ? detail
        : 'Could not load audit logs. Please try again.'
    );
  }

  trackById(_index: number, entry: AuditLogEntry): string {
    return entry.id;
  }
}
