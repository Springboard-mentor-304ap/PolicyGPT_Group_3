import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ComparisonService } from '../../core/services/comparison.service';
import { SearchService } from '../../core/services/search.service';
import { ComparisonMatrix } from '../../core/models/comparison.models';
import { SearchResultItem } from '../../core/models/search.models';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EligibilityModalComponent } from '../eligibility/components/eligibility-modal/eligibility-modal.component';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-comparison',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    ButtonComponent,
    BadgeComponent,
    SkeletonComponent,
    EligibilityModalComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './comparison.component.html',
  styleUrl: './comparison.component.css',
})
export class ComparisonComponent implements OnInit {
  readonly comparisonService = inject(ComparisonService);
  private readonly searchService = inject(SearchService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  matrix = signal<ComparisonMatrix | null>(null);
  loading = signal<boolean>(false);
  selectedSchemeForEligibility = signal<SearchResultItem | null>(null);

  ngOnInit(): void {
    this.route.queryParams.subscribe((params) => {
      const idsParam = params['ids'];
      if (idsParam) {
        const idList = idsParam.split(',');
        this.loadByIds(idList);
      } else {
        this.loadCurrentMatrix();
      }
    });
  }

  loadCurrentMatrix(): void {
    this.loading.set(true);
    this.comparisonService.getComparisonMatrix().subscribe({
      next: (m: ComparisonMatrix) => {
        this.matrix.set(m);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  private loadByIds(ids: string[]): void {
    this.loading.set(true);
    this.searchService.getAllItems().subscribe({
      next: (allItems: SearchResultItem[]) => {
        // The shared service caps selections at MAX_ITEMS and one resource
        // type per comparison (the backend compares policies or schemes,
        // never a mix) — the matrix must honour both so a hand-edited
        // ?ids= URL can't show more, or mix types. Group by type and keep
        // the group that covers more of the requested ids.
        const byType = {
          policy: allItems.filter((i) => ids.includes(i.id) && i.itemType === 'policy'),
          scheme: allItems.filter((i) => ids.includes(i.id) && i.itemType === 'scheme'),
        };
        const matching = (byType.policy.length >= byType.scheme.length ? byType.policy : byType.scheme).slice(
          0,
          this.comparisonService.MAX_ITEMS
        );
        matching.forEach((item) => this.comparisonService.addItem(item));
        this.comparisonService.getComparisonMatrix(matching).subscribe((m: ComparisonMatrix) => {
          this.matrix.set(m);
          this.loading.set(false);
        });
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  onRemoveItem(id: string): void {
    this.comparisonService.removeItem(id);
    this.loadCurrentMatrix();
  }

  onClearAll(): void {
    this.comparisonService.clearAll();
    this.matrix.set({ items: [], rows: [] });
  }

  openEligibilityModal(item: SearchResultItem): void {
    this.selectedSchemeForEligibility.set(item);
  }

  closeEligibilityModal(): void {
    this.selectedSchemeForEligibility.set(null);
  }
}
