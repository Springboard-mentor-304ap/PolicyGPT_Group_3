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
        const matching = allItems.filter((i) => ids.includes(i.id));
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
