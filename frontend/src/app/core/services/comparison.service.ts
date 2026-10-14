import { Injectable, inject, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ComparisonMatrix, ComparisonMatrixRow } from '../models/comparison.models';
import { SearchResultItem } from '../models/search.models';

@Injectable({ providedIn: 'root' })
export class ComparisonService {
  private readonly http = inject(HttpClient);

  readonly MAX_ITEMS = 4;

  // Global reactive state for selected comparison items
  readonly selectedItems = signal<SearchResultItem[]>([]);
  readonly selectedCount = computed(() => this.selectedItems().length);
  readonly isFull = computed(() => this.selectedCount() >= this.MAX_ITEMS);
  readonly hasItems = computed(() => this.selectedCount() > 0);

  toggleItem(item: SearchResultItem): boolean {
    const current = this.selectedItems();
    const exists = current.some((i) => i.id === item.id);

    if (exists) {
      this.removeItem(item.id);
      return false;
    } else {
      if (current.length >= this.MAX_ITEMS) return false;
      this.selectedItems.set([...current, item]);
      return true;
    }
  }

  addItem(item: SearchResultItem): boolean {
    const current = this.selectedItems();
    if (current.length >= this.MAX_ITEMS || current.some((i) => i.id === item.id)) {
      return false;
    }
    this.selectedItems.set([...current, item]);
    return true;
  }

  removeItem(id: string): void {
    this.selectedItems.set(this.selectedItems().filter((i) => i.id !== id));
  }

  clearAll(): void {
    this.selectedItems.set([]);
  }

  isSelected(id: string): boolean {
    return this.selectedItems().some((i) => i.id === id);
  }

  /**
   * Fetch comparison data from the backend and assemble a matrix.
   *
   * Backend: POST /api/comparison  { ids: UUID[], type: "policy" | "scheme" }
   * Response: { items: ComparisonItem[] }
   */
  getComparisonMatrix(itemsToCompare?: SearchResultItem[]): Observable<ComparisonMatrix> {
    const items = itemsToCompare || this.selectedItems();

    if (items.length === 0) {
      return new Observable((obs) => {
        obs.next({ items: [], rows: [] });
        obs.complete();
      });
    }

    // Determine type from first item (mixed comparison not supported by backend)
    const type = items[0].itemType === 'policy' ? 'policy' : 'scheme';

    const body = {
      ids: items.map((i) => i.id),
      type,
    };

    return this.http
      .post<{ items: any[] }>('/api/comparison', body)
      .pipe(
        map((res) => {
          // Map backend ComparisonItem to SearchResultItem for matrix building
          const mappedItems: SearchResultItem[] = res.items.map((item) => ({
            id: String(item.id),
            itemType: item.type as 'policy' | 'scheme',
            title: item.title,
            description: item.description,
            category: item.category || '',
            categoryLabel: item.category
              ? item.category.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
              : '',
            department: item.department,
            ministry: item.ministry,
            state: item.state,
            status: item.status || '',
            benefits: Array.isArray(item.benefits)
              ? item.benefits.join(', ')
              : item.benefits || null,
            application_process: item.application_process,
            launch_date: item.launch_date,
            deadline_date: item.deadline_date,
            document_url: item.document_url,
            view_count: 0,
          }));

          const rows = this.buildRows(mappedItems);
          return { items: mappedItems, rows };
        })
      );
  }

  /** Build comparison matrix rows from items. */
  private buildRows(items: SearchResultItem[]): ComparisonMatrixRow[] {
    return [
      {
        attribute: { key: 'type', label: 'Item Type', category: 'overview' },
        values: this.mapVals(items, (i) =>
          i.itemType === 'policy' ? 'National Policy' : 'Welfare Scheme'
        ),
      },
      {
        attribute: { key: 'category', label: 'Domain Category', category: 'overview' },
        values: this.mapVals(items, (i) => i.categoryLabel),
      },
      {
        attribute: { key: 'department', label: 'Department / Ministry', category: 'overview' },
        values: this.mapVals(items, (i) => i.department || i.ministry || 'Central Government'),
      },
      {
        attribute: { key: 'status', label: 'Current Status', category: 'overview' },
        values: this.mapVals(items, (i) => i.status),
      },
      {
        attribute: { key: 'benefits', label: 'Financial & Core Benefits', category: 'benefits' },
        values: this.mapVals(items, (i) => i.benefits || 'Broad policy framework and public initiative.'),
      },
      {
        attribute: { key: 'application_process', label: 'Application & Access Mode', category: 'application' },
        values: this.mapVals(items, (i) => i.application_process || 'Direct portal submission.'),
      },
      {
        attribute: { key: 'launch_date', label: 'Launch Date', category: 'overview' },
        values: this.mapVals(items, (i) => i.launch_date || 'N/A'),
      },
      {
        attribute: { key: 'deadline_date', label: 'Application Deadline', category: 'application' },
        values: this.mapVals(items, (i) => i.deadline_date || 'Ongoing / No fixed deadline'),
      },
      {
        attribute: { key: 'document_url', label: 'Official Portal / Guidelines', category: 'application' },
        values: this.mapVals(items, (i) => i.document_url || 'https://india.gov.in'),
      },
    ];
  }

  private mapVals(
    items: SearchResultItem[],
    extractor: (i: SearchResultItem) => string | null | undefined
  ): Record<string, string | null | undefined> {
    const valMap: Record<string, string | null | undefined> = {};
    items.forEach((item) => {
      valMap[item.id] = extractor(item);
    });
    return valMap;
  }
}
