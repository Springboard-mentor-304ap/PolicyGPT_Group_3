import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  SearchFilters,
  SearchParams,
  SearchResultItem,
} from '../../core/models/search.models';
import { SearchService } from '../../core/services/search.service';
import { ComparisonService } from '../../core/services/comparison.service';
import { SearchBarComponent } from './components/search-bar/search-bar.component';
import { FilterSidebarComponent } from './components/filter-sidebar/filter-sidebar.component';
import { PolicyCardComponent } from './components/policy-card/policy-card.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { FloatingCompareDockComponent } from '../comparison/components/floating-compare-dock/floating-compare-dock.component';
import { EligibilityModalComponent } from '../eligibility/components/eligibility-modal/eligibility-modal.component';

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    SearchBarComponent,
    FilterSidebarComponent,
    PolicyCardComponent,
    SkeletonComponent,
    ButtonComponent,
    FloatingCompareDockComponent,
    EligibilityModalComponent,
  ],
  templateUrl: './search.component.html',
  styleUrl: './search.component.css',
})
export class SearchComponent implements OnInit {
  private readonly searchService = inject(SearchService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly comparisonService = inject(ComparisonService);

  // Reactive State Signals
  query = signal<string>('');
  filters = signal<SearchFilters>({
    type: 'all',
    category: 'all',
    state: 'all',
    department: '',
  });
  results = signal<SearchResultItem[]>([]);
  totalCount = signal<number>(0);
  isLoading = signal<boolean>(false);
  errorMessage = signal<string | null>(null);

  // Mobile Filter Drawer Toggle
  mobileFiltersOpen = signal<boolean>(false);

  // Quick Eligibility Modal Target
  selectedSchemeForEligibility = signal<SearchResultItem | null>(null);

  ngOnInit(): void {
    // Read initial search query and filters from URL parameters
    this.route.queryParams.subscribe((params) => {
      const q = params['q'] || '';
      const type = params['type'] || 'all';
      const category = params['category'] || 'all';
      const state = params['state'] || 'all';

      this.query.set(q);
      this.filters.set({
        type,
        category,
        state,
        department: params['department'] || '',
      });

      this.executeSearch();
    });
  }

  executeSearch(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    const f = this.filters();
    const searchParams: SearchParams = {
      q: this.query(),
      type: f.type,
      category: f.category,
      state: f.state,
      department: f.department,
      page: 1,
      page_size: 20,
    };

    this.searchService.search(searchParams).subscribe({
      next: (res) => {
        this.results.set(res.results);
        this.totalCount.set(res.total);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.errorMessage.set('Failed to fetch search results. Please try again.');
        this.isLoading.set(false);
      },
    });
  }

  onSearchChange(newQuery: string): void {
    this.query.set(newQuery);
    this.syncUrlParams();
  }

  onFiltersChange(newFilters: SearchFilters): void {
    this.filters.set(newFilters);
    this.syncUrlParams();
  }

  onResetAll(): void {
    this.query.set('');
    this.filters.set({
      type: 'all',
      category: 'all',
      state: 'all',
      department: '',
    });
    this.syncUrlParams();
  }

  toggleMobileFilters(): void {
    this.mobileFiltersOpen.set(!this.mobileFiltersOpen());
  }

  viewItem(item: SearchResultItem): void {
    if (item.itemType === 'policy') {
      this.router.navigate(['/policies', item.id]);
    } else {
      this.router.navigate(['/schemes', item.id]);
    }
  }

  openEligibilityModal(item: SearchResultItem): void {
    this.selectedSchemeForEligibility.set(item);
  }

  closeEligibilityModal(): void {
    this.selectedSchemeForEligibility.set(null);
  }

  private syncUrlParams(): void {
    const f = this.filters();
    const qParams: Record<string, string | null> = {};

    if (this.query()) qParams['q'] = this.query();
    if (f.type !== 'all') qParams['type'] = f.type;
    if (f.category !== 'all') qParams['category'] = f.category;
    if (f.state !== 'all') qParams['state'] = f.state;

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: qParams,
    });
  }
}
