import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../core/services/application.service';
import { SchemeService } from '../../core/services/scheme.service';
import {
  Application,
  ApplicationStatus,
} from '../../core/models/application.models';

@Component({
  selector: 'app-my-applications',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './my-applications.component.html',
  styleUrl: './my-applications.component.css',
})
export class MyApplicationsComponent implements OnInit {
  private readonly applicationService = inject(ApplicationService);
  private readonly schemeService = inject(SchemeService);

  readonly applications = signal<Application[]>([]);
  readonly schemeTitles = signal<Record<string, string>>({});
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  ngOnInit(): void {
    this.applicationService.listMyApplications().subscribe({
      next: (items) => {
        this.applications.set(items);
        this.loading.set(false);
        this.resolveSchemeTitles(items);
      },
      error: () => {
        this.loading.set(false);
        this.loadError.set('Could not load your applications. Please try again.');
      },
    });
  }

  /** The API returns only scheme ids; resolve titles for readable cards. */
  private resolveSchemeTitles(items: Application[]): void {
    const seen = new Set<string>();
    for (const item of items) {
      if (seen.has(item.scheme_id)) {
        continue;
      }
      seen.add(item.scheme_id);
      this.schemeService.getScheme(item.scheme_id).subscribe({
        next: (scheme) =>
          this.schemeTitles.update((titles) => ({
            ...titles,
            [item.scheme_id]: scheme.title,
          })),
        error: () => {
          // Keep the short-id fallback when the scheme cannot be fetched.
        },
      });
    }
  }

  schemeTitle(schemeId: string): string {
    return this.schemeTitles()[schemeId] ?? `Scheme ${schemeId.slice(0, 8)}…`;
  }

  statusLabel(status: ApplicationStatus): string {
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  formatDate(value: string): string {
    return new Date(value).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }
}
