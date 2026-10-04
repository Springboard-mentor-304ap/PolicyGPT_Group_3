/**
 * Analytics models — strictly mapped to the canonical backend module
 * `backend/app/analytics/` (router.py + service.py):
 *
 *   GET /api/analytics/overview      -> AnalyticsOverviewResponse
 *   GET /api/analytics/policies      -> PolicyStatisticsResponse
 *   GET /api/analytics/schemes       -> SchemeStatisticsResponse
 *   GET /api/analytics/users         -> UserUsageStatisticsResponse (admin only)
 *   GET /api/analytics/departments   -> DepartmentStatisticsResponse
 *   GET /api/analytics/notifications -> NotificationStatisticsResponse
 *
 * Access rules mirror `ANALYTICS_ALLOWED_ROLES` (government officials,
 * researchers, administrators, super admins) and `require_user_analytics_access`
 * (administrators, super admins only, also used for `/notifications`).
 * The platform-wide totals in the overview are null for every role except
 * administrators.
 */

// ─── Raw response shapes (exactly what the backend returns) ─────────────────

export interface AnalyticsOverviewResponse {
  /** Platform-wide; null unless the caller is an administrator. */
  total_users: number | null;
  total_policies: number;
  total_schemes: number;
  /** Platform-wide; null unless the caller is an administrator. */
  total_searches: number | null;
}

export interface PolicyStatisticsResponse {
  policies_by_category: Record<string, number>;
  policies_by_status: Record<string, number>;
  policies_by_department: Record<string, number>;
}

export interface RawSchemeUsageItem {
  scheme_id: string;
  title: string;
  view_count: number | null;
}

export interface SchemeStatisticsResponse {
  schemes_by_category: Record<string, number>;
  schemes_by_status: Record<string, number>;
  scheme_usage: RawSchemeUsageItem[];
}

/** All time series returned by the backend share the `{ date, count }` shape. */
export interface TimeSeriesPoint {
  date: string;
  count: number;
}

export interface UserUsageStatisticsResponse {
  users_by_role: Record<string, number>;
  active_users: number;
  inactive_users: number;
  user_registrations_over_time: TimeSeriesPoint[];
  total_searches: number;
  searches_over_time: TimeSeriesPoint[];
}

export interface DepartmentStatisticsResponse {
  policies_by_department: Record<string, number>;
  schemes_by_department: Record<string, number>;
}

export interface NotificationStatisticsResponse {
  notifications_by_type: Record<string, number>;
  notifications_by_channel: Record<string, number>;
  notifications_by_read_status: Record<string, number>;
  notifications_over_time: TimeSeriesPoint[];
}

// ─── Composed dashboard payload (one endpoint per panel) ────────────────────

export interface DashboardAnalytics {
  overview: AnalyticsOverviewResponse;
  policies: PolicyStatisticsResponse | null;
  schemes: SchemeStatisticsResponse | null;
  users: UserUsageStatisticsResponse | null;
  departments: DepartmentStatisticsResponse | null;
  notifications: NotificationStatisticsResponse | null;
  /** Panels whose request failed independently of the rest. */
  failedPanels: string[];
}

// ─── View models consumed by the chart components ───────────────────────────

/** Donut chart input: `app-donut-chart` computes the percentages itself. */
export interface MetricSlice {
  label: string;
  count: number;
  percentage?: number;
}

/** Bar chart input: `app-bar-chart` renders one row per entry. */
export interface BreakdownItem {
  label: string;
  count: number;
}

export interface SchemeUsageItem {
  id: string;
  title: string;
  view_count: number;
}

/** Trend chart input: canonical points plus a display label for the axis. */
export interface TrendPoint {
  date: string;
  label: string;
  count: number;
}
