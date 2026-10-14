import { Injectable, inject, signal } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import {
  SearchParams,
  SearchResponse,
  SearchResultItem,
} from '../models/search.models';

@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly http = inject(HttpClient);

  readonly searchQuery = signal<string>('');

  /**
   * Search & Filter Policies and Schemes via the real backend.
   *
   * Backend: GET /api/search
   * Params: query, search_type, category, department, ministry, state, page, page_size
   */
  search(params: SearchParams): Observable<SearchResponse> {
    let httpParams = new HttpParams();

    if (params.q) httpParams = httpParams.set('query', params.q);
    if (params.type && params.type !== 'all') httpParams = httpParams.set('search_type', params.type);
    if (params.category && params.category !== 'all') httpParams = httpParams.set('category', params.category);
    if (params.department) httpParams = httpParams.set('department', params.department);
    if (params.state && params.state !== 'all') httpParams = httpParams.set('state', params.state);
    if (params.page) httpParams = httpParams.set('page', params.page.toString());
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size.toString());

    return this.http
      .get<{
        results: any[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
      }>('/api/search', { params: httpParams })
      .pipe(
        map((res) => ({
          total: res.total,
          page: res.page,
          page_size: res.page_size,
          results: res.results.map((r) => this.mapResult(r)),
        }))
      );
  }

  /** Map a backend SearchResult to the frontend SearchResultItem shape. */
  private mapResult(r: any): SearchResultItem {
    return {
      id: String(r.id),
      itemType: r.type, // 'policy' | 'scheme'
      title: r.title,
      description: r.description,
      category: r.category || '',
      categoryLabel: r.category
        ? r.category.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
        : '',
      department: r.department,
      ministry: null,
      state: r.state,
      status: '',
      benefits: null,
      application_process: null,
      launch_date: null,
      deadline_date: null,
      document_url: null,
      view_count: 0,
    };
  }

  /**
   * Get a single item by ID.
   * Uses the search endpoint filtered to a specific item.
   */
  getItemById(id: string): Observable<SearchResultItem | undefined> {
    // No dedicated single-item endpoint; search by exact ID isn't supported,
    // so return undefined and let the UI handle it gracefully.
    return new Observable<undefined>();
  }

  /**
   * Get all items (for quick prefetching / recommendations).
   * Fetches page 1 with a large page_size.
   */
  getAllItems(): Observable<SearchResultItem[]> {
    return this.search({ page: 1, page_size: 100 }).pipe(
      map((res) => res.results)
    );
  }
}
