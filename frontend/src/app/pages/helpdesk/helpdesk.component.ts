import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { HelpdeskSource } from '../../core/models/helpdesk.models';
import { HelpdeskService } from '../../core/services/helpdesk.service';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { parseAnswer } from './answer-format';
import { HelpdeskAnswerTextComponent } from './components/helpdesk-answer-text/helpdesk-answer-text.component';

/** Question length accepted by the backend HelpdeskChatRequest schema. */
const MAX_QUESTION_LENGTH = 2000;

const UNAVAILABLE_MESSAGE =
  "We couldn't get an answer right now. Please try again.";
const SIGNED_OUT_MESSAGE = 'You need to sign in to use the AI Helpdesk.';
const EMPTY_QUESTION_MESSAGE =
  'Enter a question before asking the Helpdesk.';

/**
 * AI Helpdesk page.
 *
 * A single question → answer → sources interaction. The answer and its
 * sources come straight from the backend knowledge base; the page only
 * formats them. The API requires authentication, so the route is guarded and
 * a 401 falls back to the application's normal sign-in flow instead of
 * retrying the request.
 */
@Component({
  selector: 'app-helpdesk',
  standalone: true,
  imports: [
    CommonModule,
    BackToDashboardComponent,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    SkeletonComponent,
    HelpdeskAnswerTextComponent,
  ],
  templateUrl: './helpdesk.component.html',
  styleUrl: './helpdesk.component.css',
})
export class HelpdeskComponent {
  private readonly helpdeskService = inject(HelpdeskService);
  private readonly router = inject(Router);

  readonly maxQuestionLength = MAX_QUESTION_LENGTH;

  /** Subtle starting points. They fill the textarea and never auto-submit. */
  readonly examples = [
    'What health schemes are available?',
    'What are the benefits of Ayushman Bharat?',
    'What documents are required for this scheme?',
    'Tell me about education schemes.',
  ];

  // ── State ────────────────────────────────────────────────────────────────
  readonly question = signal('');
  readonly questionError = signal<string | null>(null);
  readonly asking = signal(false);

  /** The question the currently displayed answer belongs to. */
  readonly askedQuestion = signal('');
  readonly answer = signal('');
  readonly sources = signal<HelpdeskSource[]>([]);
  readonly errorMessage = signal<string | null>(null);
  readonly signedOut = signal(false);

  readonly answerBlocks = computed(() => parseAnswer(this.answer()));
  readonly hasAnswer = computed(() => this.answer().length > 0);
  readonly idle = computed(
    () => !this.asking() && !this.hasAnswer() && this.errorMessage() === null,
  );

  // ── Actions ──────────────────────────────────────────────────────────────
  /** The ask form has no FormGroupDirective, so submit is handled manually. */
  onAskSubmit(event: Event): void {
    event.preventDefault();
    this.ask();
  }

  onQuestionInput(event: Event): void {
    const value = (event.target as HTMLTextAreaElement).value;
    this.question.set(value);
    if (value.trim().length > 0) {
      this.questionError.set(null);
    }
  }

  ask(): void {
    if (this.asking()) {
      return;
    }

    const question = this.question().trim();
    if (question.length === 0) {
      this.questionError.set(EMPTY_QUESTION_MESSAGE);
      return;
    }
    if (question.length > MAX_QUESTION_LENGTH) {
      this.questionError.set(
        `Questions can be at most ${MAX_QUESTION_LENGTH} characters long.`,
      );
      return;
    }

    this.submit(question);
  }

  /** Re-send the question that produced the current error. */
  retry(): void {
    const question = this.askedQuestion().trim() || this.question().trim();
    if (question.length === 0) {
      this.signedOut.set(false);
      this.errorMessage.set(null);
      return;
    }
    this.submit(question);
  }

  signIn(): void {
    this.router.navigate(['/login'], {
      queryParams: { returnUrl: '/helpdesk' },
    });
  }

  /** Fill the textarea from a suggestion and put the caret there. */
  useExample(example: string): void {
    this.question.set(example);
    this.questionError.set(null);
    setTimeout(() => document.getElementById('helpdesk-question')?.focus());
  }

  // ── Source presentation ──────────────────────────────────────────────────
  sourceLabel(source: HelpdeskSource): string {
    const type = (source.source_type ?? '').toString().trim().toLowerCase();
    if (type === 'policy') {
      return 'Policy';
    }
    if (type === 'scheme') {
      return 'Scheme';
    }
    return type.length > 0 ? type.charAt(0).toUpperCase() + type.slice(1) : 'Source';
  }

  sourceBadge(source: HelpdeskSource): 'info' | 'primary' | 'neutral' {
    const type = (source.source_type ?? '').toString().trim().toLowerCase();
    if (type === 'policy') {
      return 'info';
    }
    if (type === 'scheme') {
      return 'primary';
    }
    return 'neutral';
  }

  /** Relevance as a whole percentage, or null when the backend omitted it. */
  relevance(source: HelpdeskSource): number | null {
    const similarity = Number(source.similarity);
    if (!Number.isFinite(similarity) || similarity <= 0) {
      return null;
    }
    const clamped = Math.min(Math.max(similarity, 0), 1);
    return Math.round(clamped * 100);
  }

  // ── Internals ────────────────────────────────────────────────────────────
  private submit(question: string): void {
    this.asking.set(true);
    this.questionError.set(null);
    this.errorMessage.set(null);
    this.signedOut.set(false);

    this.helpdeskService.askHelpdesk(question).subscribe({
      next: (response) => {
        this.asking.set(false);
        const answer =
          typeof response?.answer === 'string' ? response.answer.trim() : '';

        if (answer.length === 0) {
          this.clearResult();
          this.errorMessage.set(UNAVAILABLE_MESSAGE);
          return;
        }

        this.answer.set(answer);

        // Nothing renderable came back (for example a bare table shell or a
        // lone separator) — treat it like a missing answer so the user still
        // gets an explanation and a retry instead of an empty card.
        if (this.answerBlocks().length === 0) {
          this.clearResult();
          this.errorMessage.set(UNAVAILABLE_MESSAGE);
          return;
        }

        this.askedQuestion.set(question);
        this.sources.set(this.normalizeSources(response?.sources));
        this.scrollToAnswer();
      },
      error: (error) => {
        this.asking.set(false);
        this.clearResult();
        this.handleError(error);
      },
    });
  }

  private handleError(error: unknown): void {
    const status = (error as { status?: number } | null)?.status;

    if (status === 401) {
      this.signedOut.set(true);
      this.errorMessage.set(SIGNED_OUT_MESSAGE);
      return;
    }
    if (status === 403) {
      this.errorMessage.set(
        'Your account does not have access to the AI Helpdesk.',
      );
      return;
    }
    if (status === 400 || status === 422) {
      this.errorMessage.set(
        'The Helpdesk could not accept that question. Please rephrase it and try again.',
      );
      return;
    }
    if (status === 429) {
      this.errorMessage.set(
        'You have used up your daily AI Helpdesk quota. Please try again tomorrow.',
      );
      return;
    }

    this.errorMessage.set(UNAVAILABLE_MESSAGE);
  }

  /** Keep only usable sources so an odd payload cannot break the list. */
  private normalizeSources(sources: unknown): HelpdeskSource[] {
    if (!Array.isArray(sources)) {
      return [];
    }

    return sources
      .filter(
        (source): source is Partial<HelpdeskSource> =>
          !!source && typeof source === 'object',
      )
      .map((source, index) => {
        const title =
          typeof source.title === 'string' ? source.title.trim() : '';
        return {
          id: source.id ? String(source.id) : `source-${index}`,
          source_type:
            typeof source.source_type === 'string' ? source.source_type : '',
          title,
          similarity: Number(source.similarity),
        };
      })
      .filter((source) => source.title.length > 0)
      .map((source) => ({
        ...source,
        similarity: Number.isFinite(source.similarity) ? source.similarity : 0,
      }));
  }

  private clearResult(): void {
    this.answer.set('');
    this.sources.set([]);
  }

  private scrollToAnswer(): void {
    setTimeout(() =>
      document
        .getElementById('helpdesk-answer')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    );
  }
}
