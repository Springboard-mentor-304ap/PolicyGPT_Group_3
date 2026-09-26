export interface OverviewMetrics {
  total_users?: number | null;
  total_policies: number;
  total_schemes: number;
  total_searches?: number | null;
}

export interface CategoryMetric {
  category: string;
  label: string;
  count: number;
  percentage: number;
}

export interface StatusMetric {
  status: string;
  label: string;
  count: number;
  percentage: number;
}

export interface DepartmentMetric {
  department: string;
  count: number;
}

export interface StateMetric {
  state: string;
  count: number;
}

export interface SchemeUsageItem {
  id: string;
  title: string;
  category: string;
  department?: string | null;
  view_count: number;
  status: string;
}

export interface TopQueryMetric {
  query: string;
  count: number;
}

export interface SearchIntelligence {
  total_searches: number;
  top_queries: TopQueryMetric[];
  recent_searches_count: number;
}

export interface ActivityItem {
  id: string;
  action: string;
  target_table: string;
  actor_name?: string | null;
  actor_role?: string | null;
  created_at: string;
  details?: string | null;
}

export interface TimeSeriesDataPoint {
  date: string;
  searches: number;
  policies_created: number;
  schemes_created: number;
}

export interface DashboardAnalyticsResponse {
  user_role: string;
  user_department?: string | null;
  overview: OverviewMetrics;
  policies_by_category: CategoryMetric[];
  policies_by_status?: StatusMetric[] | null;
  policies_by_department: DepartmentMetric[];
  schemes_by_category: CategoryMetric[];
  schemes_by_status?: StatusMetric[] | null;
  schemes_by_department: DepartmentMetric[];
  schemes_by_state: StateMetric[];
  top_viewed_schemes?: SchemeUsageItem[] | null;
  search_intelligence?: SearchIntelligence | null;
  user_activity?: ActivityItem[] | null;
  usage_over_time?: TimeSeriesDataPoint[] | null;
}
