import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';

import { AuthService } from '../../core/services/auth.service';
import { FaqService } from '../../core/services/faq.service';
import { UserRole } from '../../core/models/auth.models';
import { Faq } from '../../core/models/faq.models';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [CommonModule, BackToDashboardComponent],
  templateUrl: './faq.component.html',
  styleUrl: './faq.component.css',
})
export class FaqComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly faqService = inject(FaqService);

  /** FAQ management (create / edit / deactivate) is admin-only on the API. */
  readonly isManager = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly faqs = signal<Faq[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly expandedId = signal<string | null>(null);

  // ── Filters ─────────────────────────────────────────────────────────────
  readonly search = signal('');
  readonly category = signal('');

  // ── Manager form ────────────────────────────────────────────────────────
  readonly showForm = signal(false);
  readonly editingId = signal<string | null>(null);
  readonly question = signal('');
  readonly answer = signal('');
  readonly formCategory = signal('');
  readonly saving = signal(false);
  readonly formError = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.faqService
      .listFaqs({
        search: this.search().trim() || undefined,
        category: this.category().trim() || undefined,
        includeInactive: this.isManager(),
      })
      .subscribe({
        next: (items) => {
          this.faqs.set(items);
          this.loading.set(false);
        },
        error: () => {
          this.faqs.set([]);
          this.loading.set(false);
          this.loadError.set('Could not load FAQs. Please try again.');
        },
      });
  }

  applyFilters(): void {
    this.expandedId.set(null);
    this.load();
  }

  clearFilters(): void {
    this.search.set('');
    this.category.set('');
    this.load();
  }

  toggle(faq: Faq): void {
    this.expandedId.update((current) => (current === faq.id ? null : faq.id));
  }

  // ── Manager actions ─────────────────────────────────────────────────────
  openCreateForm(): void {
    this.editingId.set(null);
    this.question.set('');
    this.answer.set('');
    this.formCategory.set('');
    this.formError.set(null);
    this.showForm.set(true);
  }

  openEditForm(faq: Faq): void {
    this.editingId.set(faq.id);
    this.question.set(faq.question);
    this.answer.set(faq.answer);
    this.formCategory.set(faq.category ?? '');
    this.formError.set(null);
    this.showForm.set(true);
    this.expandedId.set(faq.id);
  }

  closeForm(): void {
    this.showForm.set(false);
    this.editingId.set(null);
    this.formError.set(null);
  }

  saveForm(): void {
    const question = this.question().trim();
    const answer = this.answer().trim();
    const category = this.formCategory().trim() || null;

    if (!question || !answer) {
      this.formError.set('Both a question and an answer are required.');
      return;
    }

    this.saving.set(true);
    this.formError.set(null);

    const request =
      this.editingId() === null
        ? this.faqService.createFaq({ question, answer, category })
        : this.faqService.updateFaq(this.editingId()!, {
            question,
            answer,
            category,
          });

    request.subscribe({
      next: (saved) => {
        this.saving.set(false);
        this.faqs.update((items) => {
          const exists = items.some((entry) => entry.id === saved.id);
          return exists
            ? items.map((entry) => (entry.id === saved.id ? saved : entry))
            : [saved, ...items];
        });
        this.closeForm();
      },
      error: (error: unknown) => {
        this.saving.set(false);
        this.formError.set(this.describeError(error));
      },
    });
  }

  toggleActive(faq: Faq): void {
    const request = faq.is_active
      ? this.faqService.deactivateFaq(faq.id)
      : this.faqService.updateFaq(faq.id, { is_active: true });

    request.subscribe({
      next: (updated) => {
        this.faqs.update((items) =>
          items.map((entry) => (entry.id === updated.id ? updated : entry))
        );
      },
      error: () => {
        // Keep the list unchanged if the API call fails.
      },
    });
  }

  private describeError(error: unknown): string {
    const httpError = error as {
      status?: number;
      error?: { detail?: unknown };
    };
    const detail = httpError?.error?.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail;
    }
    if (httpError?.status === 403) {
      return 'Only administrators can manage FAQs.';
    }
    return 'The FAQ could not be saved. Please try again.';
  }
}
