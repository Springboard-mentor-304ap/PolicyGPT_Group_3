import { Component, Input, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface BarItem {
  label: string;
  count: number;
  color?: string;
}

@Component({
  selector: 'app-bar-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './bar-chart.component.html',
  styleUrl: './bar-chart.component.css',
})
export class BarChartComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() unitLabel = 'Items';

  private _rawItems = signal<BarItem[]>([]);

  @Input()
  set data(items: { label?: string; department?: string; state?: string; count: number; color?: string }[] | undefined | null) {
    if (!items || items.length === 0) {
      this._rawItems.set([]);
      return;
    }
    const formatted: BarItem[] = items.map((it) => ({
      label: it.label || it.department || it.state || 'General',
      count: it.count || 0,
      color: it.color,
    }));
    this._rawItems.set(formatted);
  }

  readonly hoveredIndex = signal<number | null>(null);

  readonly items = computed(() => this._rawItems());

  readonly totalCount = computed(() => {
    return this._rawItems().reduce((sum, it) => sum + it.count, 0);
  });

  readonly maxCount = computed(() => {
    const counts = this._rawItems().map((it) => it.count);
    return counts.length > 0 ? Math.max(...counts, 1) : 1;
  });

  getBarPercentage(count: number): number {
    return Math.round((count / this.maxCount()) * 100);
  }

  onHover(idx: number | null): void {
    this.hoveredIndex.set(idx);
  }
}
