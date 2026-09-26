import { Component, Input, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TimeSeriesDataPoint } from '../../../core/models/analytics.models';

@Component({
  selector: 'app-trend-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './trend-chart.component.html',
  styleUrl: './trend-chart.component.css',
})
export class TrendChartComponent {
  @Input() title = 'Usage Over Time';
  @Input() subtitle = 'Activity & Search volume over the past 7 days';

  private _rawPoints = signal<TimeSeriesDataPoint[]>([]);

  @Input()
  set data(points: TimeSeriesDataPoint[] | undefined | null) {
    this._rawPoints.set(points || []);
  }

  readonly points = computed(() => this._rawPoints());
  readonly hoveredIndex = signal<number | null>(null);

  readonly maxSearchCount = computed(() => {
    const vals = this._rawPoints().map((p) => p.searches);
    return vals.length > 0 ? Math.max(...vals, 5) : 5;
  });

  readonly totalSearches = computed(() => {
    return this._rawPoints().reduce((sum, p) => sum + (p.searches || 0), 0);
  });

  readonly totalCreations = computed(() => {
    return this._rawPoints().reduce(
      (sum, p) => sum + (p.policies_created || 0) + (p.schemes_created || 0),
      0
    );
  });

  getBarHeightPct(val: number): number {
    return Math.max(8, Math.round((val / this.maxSearchCount()) * 100));
  }

  onHover(idx: number | null): void {
    this.hoveredIndex.set(idx);
  }
}
