import { Component, Input, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendPoint } from '../../../core/models/analytics.models';

/**
 * Generic bar-style time series chart.
 *
 * Every canonical analytics time series (`searches_over_time`,
 * `user_registrations_over_time`, `notifications_over_time`) has the shape
 * `{ date, count }`, so this component renders a single labelled series.
 */
@Component({
  selector: 'app-trend-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './trend-chart.component.html',
  styleUrl: './trend-chart.component.css',
})
export class TrendChartComponent {
  @Input() title = 'Activity Over Time';
  @Input() subtitle = '';
  @Input() seriesLabel = 'Events';

  private _rawPoints = signal<TrendPoint[]>([]);

  @Input()
  set data(points: TrendPoint[] | undefined | null) {
    this._rawPoints.set(points || []);
  }

  readonly points = computed(() => this._rawPoints());
  readonly hoveredIndex = signal<number | null>(null);

  readonly maxCount = computed(() => {
    const values = this._rawPoints().map((point) => point.count);
    return values.length > 0 ? Math.max(...values, 5) : 5;
  });

  readonly totalCount = computed(() =>
    this._rawPoints().reduce((sum, point) => sum + (point.count || 0), 0)
  );

  getBarHeightPct(value: number): number {
    return Math.max(8, Math.round((value / this.maxCount()) * 100));
  }

  onHover(idx: number | null): void {
    this.hoveredIndex.set(idx);
  }
}
