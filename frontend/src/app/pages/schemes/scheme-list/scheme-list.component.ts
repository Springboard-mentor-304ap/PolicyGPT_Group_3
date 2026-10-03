import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SchemeService } from '../../../core/services/scheme.service';
import { AuthService } from '../../../core/services/auth.service';
import {
  Scheme,
  SchemeStatus,
  SchemeCategory,
  SCHEME_CATEGORY_LABELS,
  SCHEME_STATUS_LABELS,
  SCHEME_STATUS_BADGE,
  BadgeVariant,
} from '../../../core/models/scheme.models';
import { UserRole } from '../../../core/models/auth.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { BadgeComponent } from '../../../shared/components/badge/badge.component';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

/** Listing scope offered to government officials. */
export type SchemeOwnerFilter = 'all' | 'mine';

@Component({
  selector: 'app-scheme-list',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ButtonComponent,
    BadgeComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './scheme-list.component.html',
  styleUrl: './scheme-list.component.css',
})
export class SchemeListComponent implements OnInit {
  private readonly schemeService = inject(SchemeService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly schemes = signal<Scheme[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly searchQuery = signal('');
  readonly statusFilter = signal('');
  readonly categoryFilter = signal('');
  readonly includeArchived = signal(false);
  /**
   * "All" shows every scheme in the official's department/ministry scope;
   * "By Me" narrows that scope to the records they created themselves. The
   * backend applies both filters, so the signal only drives the request.
   */
  readonly ownerFilter = signal<SchemeOwnerFilter>('all');

  readonly isGovernmentOfficial = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.GOVERNMENT_OFFICIAL;
  });

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  /** Only an official's listing has a "By Me" scope. */
  readonly isByMe = computed(
    () => this.isGovernmentOfficial() && this.ownerFilter() === 'mine'
  );

  /** A record can only be edited/archived by the official who created it. */
  isOwnScheme(scheme: Scheme): boolean {
    return (
      this.isGovernmentOfficial() &&
      scheme.created_by === this.authService.currentUser()?.id
    );
  }

  readonly filteredSchemes = computed(() => {
    let result = this.schemes();

    // Search filter
    const query = this.searchQuery().toLowerCase();
    if (query) {
      result = result.filter(
        (s) =>
          s.title.toLowerCase().includes(query) ||
          s.description.toLowerCase().includes(query) ||
          (s.department || '').toLowerCase().includes(query)
      );
    }

    // Status filter
    const status = this.statusFilter();
    if (status) {
      result = result.filter((s) => s.status === status);
    }

    // Category filter
    const category = this.categoryFilter();
    if (category) {
      result = result.filter((s) => s.category === category);
    }

    return result;
  });

  ngOnInit(): void {
    this.loadSchemes();
  }

  loadSchemes(): void {
    this.loading.set(true);
    this.error.set(null);

    this.schemeService
      .listSchemes(this.includeArchived(), this.isByMe())
      .subscribe({
        next: (schemes) => {
          this.schemes.set(schemes);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to load schemes');
          this.loading.set(false);
        },
      });
  }

  setOwnerFilter(filter: SchemeOwnerFilter): void {
    if (this.ownerFilter() === filter) {
      return;
    }

    this.ownerFilter.set(filter);
    this.loadSchemes();
  }

  createScheme(): void {
    this.router.navigate(['/schemes/create']);
  }

  viewScheme(schemeId: string): void {
    this.router.navigate(['/schemes', schemeId]);
  }

  editScheme(schemeId: string, event: Event): void {
    event.stopPropagation();
    this.router.navigate(['/schemes', schemeId, 'edit']);
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  onStatusFilter(event: Event): void {
    this.statusFilter.set((event.target as HTMLSelectElement).value);
  }

  onCategoryFilter(event: Event): void {
    this.categoryFilter.set((event.target as HTMLSelectElement).value);
  }

  onIncludeArchivedChange(event: Event): void {
    this.includeArchived.set((event.target as HTMLInputElement).checked);
    this.loadSchemes();
  }

  getStatusOptions(): { value: string; label: string }[] {
    return [
      { value: '', label: 'All Statuses' },
      ...Object.values(SchemeStatus).map((s) => ({
        value: s,
        label: SCHEME_STATUS_LABELS[s],
      })),
    ];
  }

  getCategoryOptions(): { value: string; label: string }[] {
    return [
      { value: '', label: 'All Categories' },
      ...Object.values(SchemeCategory).map((c) => ({
        value: c,
        label: SCHEME_CATEGORY_LABELS[c],
      })),
    ];
  }

  getStatusLabel(status: SchemeStatus): string {
    return SCHEME_STATUS_LABELS[status] || status;
  }

  getStatusBadge(status: SchemeStatus): BadgeVariant {
    return SCHEME_STATUS_BADGE[status] || 'neutral';
  }

  getCategoryLabel(category: SchemeCategory): string {
    return SCHEME_CATEGORY_LABELS[category] || category;
  }

  formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
}
