import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { FeedbackService } from '../../core/services/feedback.service';
import { UserRole } from '../../core/models/auth.models';
import {
  Feedback,
  FeedbackStatus,
  FeedbackType,
} from '../../core/models/feedback.models';

type FeedbackTab = 'submit' | 'mine' | 'all';

@Component({
  selector: 'app-feedback',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './feedback.component.html',
  styleUrl: './feedback.component.css',
})
export class FeedbackComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly feedbackService = inject(FeedbackService);

  readonly isFeedbackAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly tabs: { id: FeedbackTab; label: string }[] = [
    { id: 'submit', label: 'Submit' },
    { id: 'mine', label: 'My Feedback' },
    { id: 'all', label: 'All Feedback' },
  ];

  readonly activeTab = signal<FeedbackTab>('submit');

  // ── Submit form ─────────────────────────────────────────────────────────
  readonly type = signal<FeedbackType>('feedback');
  readonly subject = signal('');
  readonly message = signal('');
  readonly submitting = signal(false);
  readonly submitSuccess = signal(false);
  readonly submitError = signal<string | null>(null);

  // ── Lists ───────────────────────────────────────────────────────────────
  readonly myFeedback = signal<Feedback[]>([]);
  readonly allFeedback = signal<Feedback[]>([]);
  readonly loadingMine = signal(false);
  readonly loadingAll = signal(false);

  // ── Admin resolution editor ─────────────────────────────────────────────
  readonly editingId = signal<string | null>(null);
  readonly editStatus = signal<FeedbackStatus>('resolved');
  readonly editNote = signal('');
  readonly savingId = signal<string | null>(null);

  ngOnInit(): void {
    this.loadMyFeedback();
    if (this.isFeedbackAdmin()) {
      this.loadAllFeedback();
    }
  }

  selectTab(tab: FeedbackTab): void {
    if (tab === 'all' && !this.isFeedbackAdmin()) {
      return;
    }
    this.activeTab.set(tab);
    if (tab === 'mine' && this.myFeedback().length === 0) {
      this.loadMyFeedback();
    }
    if (tab === 'all' && this.allFeedback().length === 0) {
      this.loadAllFeedback();
    }
  }

  submit(): void {
    const subject = this.subject().trim();
    const message = this.message().trim();
    if (!subject || !message) {
      this.submitError.set('Please provide both a subject and a message.');
      return;
    }

    this.submitting.set(true);
    this.submitError.set(null);
    this.submitSuccess.set(false);

    this.feedbackService
      .createFeedback({ type: this.type(), subject, message })
      .subscribe({
        next: (created) => {
          this.submitting.set(false);
          this.submitSuccess.set(true);
          this.subject.set('');
          this.message.set('');
          this.myFeedback.update((items) => [created, ...items]);
        },
        error: (error: unknown) => {
          this.submitting.set(false);
          this.submitError.set(this.describeError(error));
        },
      });
  }

  loadMyFeedback(): void {
    this.loadingMine.set(true);
    this.feedbackService.listMyFeedback().subscribe({
      next: (items) => {
        this.myFeedback.set(items);
        this.loadingMine.set(false);
      },
      error: () => {
        this.myFeedback.set([]);
        this.loadingMine.set(false);
      },
    });
  }

  loadAllFeedback(): void {
    this.loadingAll.set(true);
    this.feedbackService.listFeedback().subscribe({
      next: (items) => {
        this.allFeedback.set(items);
        this.loadingAll.set(false);
      },
      error: () => {
        this.allFeedback.set([]);
        this.loadingAll.set(false);
      },
    });
  }

  startResolve(item: Feedback): void {
    this.editingId.set(item.id);
    this.editStatus.set('resolved');
    this.editNote.set(item.resolution_note ?? '');
  }

  cancelResolve(): void {
    this.editingId.set(null);
    this.editNote.set('');
  }

  saveResolve(item: Feedback): void {
    const note = this.editNote().trim();
    this.savingId.set(item.id);
    this.feedbackService
      .updateFeedback(item.id, {
        status: this.editStatus(),
        resolution_note: note || null,
      })
      .subscribe({
        next: (updated) => {
          this.allFeedback.update((items) =>
            items.map((entry) => (entry.id === updated.id ? updated : entry))
          );
          this.savingId.set(null);
          this.editingId.set(null);
        },
        error: () => {
          this.savingId.set(null);
        },
      });
  }

  statusLabel(status: FeedbackStatus): string {
    return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  typeLabel(type: FeedbackType): string {
    return type.charAt(0).toUpperCase() + type.slice(1);
  }

  formatDate(value: string): string {
    return new Date(value).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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
    if (httpError?.status === 401) {
      return 'Your session has expired. Please sign in again.';
    }
    return 'Your feedback could not be submitted. Please try again.';
  }
}
