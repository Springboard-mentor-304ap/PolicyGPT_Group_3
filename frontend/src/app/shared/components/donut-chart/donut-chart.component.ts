import { Component, Input, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface DonutSlice {
  label: string;
  count: number;
  percentage: number;
  color?: string;
  category?: string;
}

@Component({
  selector: 'app-donut-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './donut-chart.component.html',
  styleUrl: './donut-chart.component.css',
})
export class DonutChartComponent {
  private readonly defaultColors = [
    '#0062d2', // Primary Blue
    '#10b981', // Emerald Green
    '#f59e0b', // Amber
    '#8b5cf6', // Violet
    '#06b6d4', // Cyan
    '#ec4899', // Pink
    '#6366f1', // Indigo
    '#14b8a6', // Teal
    '#f97316', // Orange
    '#64748b', // Slate
  ];

  @Input() title = '';
  @Input() subtitle = '';
  @Input() totalLabel = 'Total';

  private _rawItems = signal<DonutSlice[]>([]);

  @Input()
  set data(items: { label: string; count: number; percentage?: number; color?: string }[] | undefined | null) {
    if (!items || items.length === 0) {
      this._rawItems.set([]);
      return;
    }
    const total = items.reduce((sum, item) => sum + (item.count || 0), 0);
    const formatted = items.map((item, idx) => ({
      label: item.label,
      count: item.count,
      percentage: total > 0 ? (item.percentage ?? Math.round((item.count / total) * 1000) / 10) : 0,
      color: item.color || this.defaultColors[idx % this.defaultColors.length],
    }));
    this._rawItems.set(formatted);
  }

  readonly hoveredIndex = signal<number | null>(null);

  readonly totalCount = computed(() => {
    return this._rawItems().reduce((sum, item) => sum + item.count, 0);
  });

  readonly slices = computed(() => {
    const items = this._rawItems();
    let accumulatedPct = 0;

    return items.map((item, idx) => {
      const offset = 100 - accumulatedPct + 25; // start at top (12 o'clock)
      accumulatedPct += item.percentage;
      return {
        ...item,
        dashArray: `${item.percentage} ${Math.max(0, 100 - item.percentage)}`,
        dashOffset: offset,
        color: item.color || this.defaultColors[idx % this.defaultColors.length],
      };
    });
  });

  readonly activeSlice = computed(() => {
    const idx = this.hoveredIndex();
    if (idx !== null && idx >= 0 && idx < this._rawItems().length) {
      return this._rawItems()[idx];
    }
    return null;
  });

  onSliceHover(idx: number | null): void {
    this.hoveredIndex.set(idx);
  }
}
