/**
 * Pure adapters that translate canonical analytics responses into the
 * `{ label, count }` / `{ date, label, count }` shapes consumed by the
 * donut / bar / trend chart components.
 *
 * The backend returns plain `{ key: count }` dictionaries; the charts need
 * arrays, so the transformation lives here instead of changing the API.
 */
import {
  BreakdownItem,
  MetricSlice,
  RawSchemeUsageItem,
  SchemeUsageItem,
  TimeSeriesPoint,
  TrendPoint,
} from '../models/analytics.models';

/** Preferred display order for lifecycle statuses (unknown values sort last). */
const STATUS_ORDER: Record<string, number> = {
  draft: 0,
  pending_approval: 1,
  pending: 1,
  approved: 2,
  active: 2,
  rejected: 3,
  archived: 4,
};

/** `women_child_welfare` -> `Women Child Welfare` */
export function humanize(value: string): string {
  if (!value) return 'Unknown';
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export interface MetricSliceOptions {
  /** Keep lifecycle order (draft -> pending -> approved -> rejected -> archived). */
  sortByStatusOrder?: boolean;
  /** Override the generated label for specific backend keys. */
  labels?: Record<string, string>;
}

/**
 * Convert a `{ key: count }` dictionary into sorted donut slices.
 * Status dictionaries keep their lifecycle order; everything else is sorted
 * by count (descending) so the biggest segment leads.
 */
export function toMetricSlices(
  record: Record<string, number> | null | undefined,
  options: MetricSliceOptions = {}
): MetricSlice[] {
  const entries = Object.entries(record ?? {}).filter(
    ([, count]) => typeof count === 'number'
  );

  const sorted = entries.sort((a, b) => {
    if (options.sortByStatusOrder) {
      const rankA = STATUS_ORDER[a[0]] ?? Number.MAX_SAFE_INTEGER;
      const rankB = STATUS_ORDER[b[0]] ?? Number.MAX_SAFE_INTEGER;
      if (rankA !== rankB) return rankA - rankB;
    }
    if (b[1] !== a[1]) return b[1] - a[1];
    return a[0].localeCompare(b[0]);
  });

  return sorted.map(([key, count]) => ({
    label: options.labels?.[key] ?? humanize(key),
    count,
  }));
}

/** Convert a `{ key: count }` dictionary into sorted bar-chart rows. */
export function toBreakdownItems(
  record: Record<string, number> | null | undefined
): BreakdownItem[] {
  return Object.entries(record ?? {})
    .filter(([, count]) => typeof count === 'number')
    .sort((a, b) => (b[1] !== a[1] ? b[1] - a[1] : a[0].localeCompare(b[0])))
    .map(([key, count]) => ({ label: humanize(key), count }));
}

/** Canonical `{ date, count }` points -> chart points with a short axis label. */
export function toTrendPoints(
  points: TimeSeriesPoint[] | null | undefined
): TrendPoint[] {
  return (points ?? []).map((point) => ({
    date: point.date,
    label: formatShortDate(point.date),
    count: point.count ?? 0,
  }));
}

/** `2026-09-29` -> `Sep 29` (falls back to the raw value). */
export function formatShortDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '');
  if (!match) return value;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3])
  );
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Scheme usage leaderboard. The canonical endpoint only returns
 * `scheme_id`, `title` and `view_count`, so the view model carries exactly
 * those fields (no category / department / status).
 */
export function toSchemeUsage(
  items: RawSchemeUsageItem[] | null | undefined,
  limit = 8
): SchemeUsageItem[] {
  return (items ?? [])
    .map((item) => ({
      id: item.scheme_id,
      title: item.title,
      view_count: item.view_count ?? 0,
    }))
    .sort((a, b) => b.view_count - a.view_count)
    .slice(0, limit);
}
