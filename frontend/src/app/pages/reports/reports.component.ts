import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { ReportService } from '../../core/services/report.service';
import { UserRole } from '../../core/models/auth.models';
import {
  Report,
  ReportFormat,
  ReportType,
} from '../../core/models/report.models';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './reports.component.html',
  styleUrl: './reports.component.css',
})
export class ReportsComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly reportService = inject(ReportService);

  /** Mirrors `REPORT_ALLOWED_ROLES` on the backend. */
  readonly canAccessReports = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.GOVERNMENT_OFFICIAL ||
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN
    );
  });

  readonly reports = signal<Report[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  // ── Generate form ───────────────────────────────────────────────────────
  readonly reportType = signal<ReportType>('policy');
  readonly format = signal<ReportFormat>('pdf');
  readonly category = signal('');
  readonly status = signal('');
  readonly department = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly generating = signal(false);
  readonly generateError = signal<string | null>(null);
  readonly generateSuccess = signal(false);

  readonly downloadId = signal<string | null>(null);

  ngOnInit(): void {
    if (!this.canAccessReports()) {
      this.loading.set(false);
      return;
    }
    this.loadReports();
  }

  loadReports(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.reportService.listReports().subscribe({
      next: (items) => {
        this.reports.set(items);
        this.loading.set(false);
      },
      error: () => {
        this.reports.set([]);
        this.loading.set(false);
        this.loadError.set('Could not load your reports. Please try again.');
      },
    });
  }

  generate(): void {
    const filters: Record<string, string> = {};
    if (this.category().trim()) filters['category'] = this.category().trim();
    if (this.status().trim()) filters['status'] = this.status().trim();
    if (this.department().trim()) filters['department'] = this.department().trim();
    if (this.dateFrom()) filters['date_from'] = this.dateFrom();
    if (this.dateTo()) filters['date_to'] = this.dateTo();

    this.generating.set(true);
    this.generateError.set(null);
    this.generateSuccess.set(false);

    this.reportService
      .generateReport({
        report_type: this.reportType(),
        format: this.format(),
        filters: Object.keys(filters).length > 0 ? filters : null,
      })
      .subscribe({
        next: (report) => {
          this.generating.set(false);
          this.generateSuccess.set(true);
          this.reports.update((items) => [report, ...items]);
        },
        error: (error: unknown) => {
          this.generating.set(false);
          this.generateError.set(this.describeError(error));
        },
      });
  }

  download(report: Report): void {
    this.downloadId.set(report.id);
    this.reportService.downloadReport(report.id).subscribe({
      next: (blob) => {
        this.downloadId.set(null);
        const extension = report.format === 'pdf' ? 'pdf' : 'xlsx';
        const stamp = new Date()
          .toISOString()
          .slice(0, 19)
          .replace(/[:T]/g, '-');
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${report.report_type}-report-${stamp}.${extension}`;
        anchor.click();
        URL.revokeObjectURL(url);
      },
      error: () => {
        this.downloadId.set(null);
      },
    });
  }

  typeLabel(type: ReportType): string {
    return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  formatLabel(format: ReportFormat): string {
    return format === 'pdf' ? 'PDF' : 'Excel';
  }

  filterSummary(report: Report): string {
    const used = report.filters_used;
    if (!used) {
      return 'No filters';
    }
    const parts = Object.entries(used)
      .filter(([, value]) => value !== null && value !== undefined && value !== '')
      .map(([key, value]) => `${key}: ${value}`);
    return parts.length > 0 ? parts.join(' · ') : 'No filters';
  }

  formatDate(value: string): string {
    return new Date(value).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  private describeError(error: unknown): string {
    const httpError = error as {
      status?: number;
      error?: { detail?: unknown };
    };
    const detail = httpError?.error?.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail;
    }
    if (httpError?.status === 403) {
      return 'You do not have permission to access reports.';
    }
    return 'The report could not be generated. Please try again.';
  }
}
