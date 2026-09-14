import { Injectable, computed, signal } from '@angular/core';
import { Observable, of, delay } from 'rxjs';
import { ComparisonMatrix, ComparisonMatrixRow } from '../models/comparison.models';
import { SearchResultItem } from '../models/search.models';

// ╔══════════════════════════════════════════════════════════════════════════════╗
// ║  HOW TO RECONNECT TO THE REAL BACKEND COMPARISON API                         ║
// ║                                                                            ║
// ║  1. In frontend/src/app/app.config.ts, ensure provideHttpClient() is active ║
// ║  2. Inject HttpClient: private readonly http = inject(HttpClient);          ║
// ║  3. Replace getComparisonMatrix() with:                                    ║
// ║       return this.http.post<ComparisonMatrix>('/api/comparison', { ids })   ║
// ╚══════════════════════════════════════════════════════════════════════════════╝

@Injectable({ providedIn: 'root' })
export class ComparisonService {
  readonly MAX_ITEMS = 4;

  // Global reactive state for selected comparison items
  readonly selectedItems = signal<SearchResultItem[]>([]);
  readonly selectedCount = computed(() => this.selectedItems().length);
  readonly isFull = computed(() => this.selectedCount() >= this.MAX_ITEMS);
  readonly hasItems = computed(() => this.selectedCount() > 0);

  /**
   * Toggles item in comparison list.
   * Returns true if added, false if removed or reached limit.
   */
  toggleItem(item: SearchResultItem): boolean {
    const current = this.selectedItems();
    const exists = current.some((i) => i.id === item.id);

    if (exists) {
      this.removeItem(item.id);
      return false;
    } else {
      if (current.length >= this.MAX_ITEMS) {
        return false;
      }
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
   * Assembles a comparison matrix for the given or currently selected items.
   *
   * Backend Endpoint: POST /api/comparison
   */
  getComparisonMatrix(itemsToCompare?: SearchResultItem[]): Observable<ComparisonMatrix> {
    const items = itemsToCompare || this.selectedItems();

    if (items.length === 0) {
      return of({ items: [], rows: [] });
    }

    const rows: ComparisonMatrixRow[] = [
      {
        attribute: { key: 'type', label: 'Item Type', category: 'overview' },
        values: this.mapAttributeValues(items, (i) =>
          i.itemType === 'policy' ? 'National Policy' : 'Welfare Scheme'
        ),
      },
      {
        attribute: { key: 'category', label: 'Domain Category', category: 'overview' },
        values: this.mapAttributeValues(items, (i) => i.categoryLabel),
      },
      {
        attribute: { key: 'department', label: 'Department / Ministry', category: 'overview' },
        values: this.mapAttributeValues(items, (i) => i.department || i.ministry || 'Central Government'),
      },
      {
        attribute: { key: 'status', label: 'Current Status', category: 'overview' },
        values: this.mapAttributeValues(items, (i) => i.status),
      },
      {
        attribute: { key: 'benefits', label: 'Financial & Core Benefits', category: 'benefits' },
        values: this.mapAttributeValues(
          items,
          (i) => i.benefits || 'Broad policy framework and public initiative.'
        ),
      },
      {
        attribute: { key: 'application_process', label: 'Application & Access Mode', category: 'application' },
        values: this.mapAttributeValues(
          items,
          (i) => i.application_process || 'Direct portal submission / designated nodal centers.'
        ),
      },
      {
        attribute: { key: 'launch_date', label: 'Launch Date', category: 'overview' },
        values: this.mapAttributeValues(items, (i) => i.launch_date || 'N/A'),
      },
      {
        attribute: { key: 'deadline_date', label: 'Application Deadline', category: 'application' },
        values: this.mapAttributeValues(items, (i) => i.deadline_date || 'Ongoing / No fixed deadline'),
      },
      {
        attribute: { key: 'document_url', label: 'Official Portal / Guidelines', category: 'application' },
        values: this.mapAttributeValues(items, (i) => i.document_url || 'https://india.gov.in'),
      },
    ];

    return of({ items, rows }).pipe(delay(250));
  }

  private mapAttributeValues(
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
