import { Component, effect, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { DepartmentService } from '../../core/services/department.service';
import { ReportService } from '../../core/services/report.service';
import { UserRole } from '../../core/models/auth.models';
import {
  Report,
  ReportFormat,
  ReportType,
} from '../../core/models/report.models';
import {
  POLICY_CATEGORY_LABELS,
  POLICY_STATUS_LABELS,
  PolicyCategory,
  PolicyStatus,
} from '../../core/models/policy.models';
import {
  SCHEME_CATEGORY_LABELS,
  SCHEME_STATUS_LABELS,
  SchemeCategory,
  SchemeStatus,
} from '../../core/models/scheme.models';

/** Every report type, in menu order. */
const ALL_REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: 'policy', label: 'Policies' },
  { value: 'scheme', label: 'Schemes' },
  { value: 'user_activity', label: 'User Activity' },
  { value: 'department', label: 'Departments' },
  { value: 'analytics', label: 'Analytics' },
];

/**
 * Report types that cover the whole platform instead of a single department.
 * Only administrators / super admins may generate them — mirrors
 * `_build_user_activity_report` in `backend/app/reports/service.py`, which
 * still rejects a government official even if the UI is bypassed.
 */
const PLATFORM_REPORT_TYPES: ReportType[] = ['user_activity'];

/** Which filters each report type accepts (mirrors FILTERS_BY_REPORT_TYPE). */
const FILTERS_BY_TYPE: Record<ReportType, readonly string[]> = {
  policy: ['category', 'status', 'department', 'date_from', 'date_to'],
  scheme: ['category', 'status', 'department', 'date_from', 'date_to'],
  user_activity: ['role', 'date_from', 'date_to'],
  department: ['department', 'date_from', 'date_to'],
  analytics: [],
};

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
  private readonly departmentService = inject(DepartmentService);

  /** Mirrors `REPORT_ALLOWED_ROLES` on the backend. */
  readonly canAccessReports = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.GOVERNMENT_OFFICIAL ||
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN
    );
  });

  /** Administrators are the only role that may run platform-wide reports. */
  readonly canGeneratePlatformReports = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly isGovernmentOfficial = computed(
    () => this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL
  );

  /** Paid report types this account may pick from. */
  readonly reportTypes = computed(() =>
    ALL_REPORT_TYPES.filter(
      (type) =>
        !PLATFORM_REPORT_TYPES.includes(type.value) ||
        this.canGeneratePlatformReports()
    )
  );

  readonly reports = signal<Report[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  // ── Generate form ───────────────────────────────────────────────────────
  readonly reportType = signal<ReportType>('policy');
  readonly format = signal<ReportFormat>('pdf');
  readonly category = signal('');
  readonly status = signal('');
  readonly department = signal('');
  readonly role = signal('');
  readonly dateFrom = signal('');
  readonly dateTo = signal('');
  readonly generating = signal(false);
  readonly generateError = signal<string | null>(null);
  readonly generateSuccess = signal(false);

  readonly downloadId = signal<string | null>(null);

  /** Department values from the API (officials only ever see their own). */
  readonly departmentOptions = signal<string[]>([]);

  readonly roleOptions = Object.values(UserRole).map((value) => ({
    value,
    label: value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  }));

  constructor() {
    // A role change (or a role that resolves after load) must not leave a
    // report type selected that this account is not allowed to generate.
    effect(() => {
      const allowed = this.reportTypes().map((type) => type.value);
      if (!allowed.includes(this.reportType())) {
        this.reportType.set(allowed[0] ?? 'policy');
      }
    });
  }

  ngOnInit(): void {
    if (!this.canAccessReports()) {
      this.loading.set(false);
      return;
    }
    this.loadReports();
    this.loadDepartments();
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

  /**
   * Officials are locked to their department scope on the server, so they are
   * only offered their own department; administrators pick from the values in
   * use. A 403 for any other department is still enforced by the API.
   */
  private loadDepartments(): void {
    if (this.isGovernmentOfficial()) {
      this.authService.getGovernmentOfficialProfile().subscribe({
        next: (profile) => this.departmentOptions.set([profile.department]),
        error: () => this.departmentOptions.set([]),
      });
      return;
    }

    this.departmentService.listDepartments().subscribe({
      next: (departments) => this.departmentOptions.set(departments),
      error: () => this.departmentOptions.set([]),
    });
  }

  // ── Which filters apply to the selected report type ─────────────────────
  supports(filter: string): boolean {
    return FILTERS_BY_TYPE[this.reportType()].includes(filter);
  }

  /** Category filter values are the existing policy/scheme category enums. */
  get categoryOptions(): { value: string; label: string }[] {
    const type = this.reportType();

    if (type === 'policy') {
      return Object.values(PolicyCategory).map((value) => ({
        value,
        label: POLICY_CATEGORY_LABELS[value],
      }));
    }

    if (type === 'scheme') {
      return Object.values(SchemeCategory).map((value) => ({
        value,
        label: SCHEME_CATEGORY_LABELS[value],
      }));
    }

    return [];
  }

  get statusOptions(): { value: string; label: string }[] {
    const type = this.reportType();

    if (type === 'policy') {
      return Object.values(PolicyStatus).map((value) => ({
        value,
        label: POLICY_STATUS_LABELS[value],
      }));
    }

    if (type === 'scheme') {
      return Object.values(SchemeStatus).map((value) => ({
        value,
        label: SCHEME_STATUS_LABELS[value],
      }));
    }

    return [];
  }

  /** Switching report type clears filters the new type does not support. */
  selectReportType(type: ReportType): void {
    this.reportType.set(type);

    if (!this.supports('category')) this.category.set('');
    if (!this.supports('status')) this.status.set('');
    if (!this.supports('department')) this.department.set('');
    if (!this.supports('role')) this.role.set('');
  }

  generate(): void {
    // An official's department scope and the user-activity restriction are
    // both enforced by the API as well; this only keeps the form honest.
    if (
      PLATFORM_REPORT_TYPES.includes(this.reportType()) &&
      !this.canGeneratePlatformReports()
    ) {
      this.generateError.set(
        'User activity reports require administrator access.'
      );
      return;
    }

    const filters: Record<string, string> = {};
    if (this.supports('category') && this.category()) filters['category'] = this.category();
    if (this.supports('status') && this.status()) filters['status'] = this.status();
    if (this.supports('department') && this.department().trim()) {
      filters['department'] = this.department().trim();
    }
    if (this.supports('role') && this.role()) filters['role'] = this.role();
    if (this.supports('date_from') && this.dateFrom()) filters['date_from'] = this.dateFrom();
    if (this.supports('date_to') && this.dateTo()) filters['date_to'] = this.dateTo();

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
    return (
      ALL_REPORT_TYPES.find((entry) => entry.value === type)?.label ??
      type.replace(/_/g, ' ')
    );
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
      return 'You do not have permission to generate this report.';
    }
    return 'The report could not be generated. Please try again.';
  }
}
