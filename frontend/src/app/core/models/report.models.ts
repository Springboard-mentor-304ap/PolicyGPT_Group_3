/**
 * Report models — mapped to `backend/app/reports/schemas.py`.
 *
 *   POST /api/reports/generate        -> Report (201)
 *   GET  /api/reports                 -> Report[]
 *   GET  /api/reports/{id}            -> Report
 *   GET  /api/reports/{id}/download   -> file stream (PDF / Excel)
 *
 * Router access is limited to government officials, administrators and
 * super admins (`REPORT_ALLOWED_ROLES`).
 */

export type ReportType =
  | 'policy'
  | 'scheme'
  | 'user_activity'
  | 'department'
  | 'analytics';

export type ReportFormat = 'pdf' | 'excel';

export interface ReportFilters {
  department?: string | null;
  ministry?: string | null;
  state?: string | null;
  category?: string | null;
  status?: string | null;
  role?: string | null;
  date_from?: string | null;
  date_to?: string | null;
}

export interface ReportGenerateRequest {
  report_type: ReportType;
  format: ReportFormat;
  filters?: ReportFilters | null;
}

export interface Report {
  id: string;
  generated_by: string;
  report_type: ReportType;
  format: ReportFormat;
  filters_used: Record<string, unknown> | null;
  file_url: string;
  generated_at: string;
}
