import { CommonModule } from '@angular/common';
import { Component, Input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FinderRuleResult, SchemeMatch } from '../../../../core/models/finder.models';
import { BadgeComponent } from '../../../../shared/components/badge/badge.component';
import { parameterLabel, requiredValueText } from '../../finder-labels';

export type FinderBadgeVariant =
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'neutral'
  | 'primary';

/**
 * One scheme result. The card stays compact: title, backend summary and any
 * missing information are always visible, while the rule-by-rule explanation
 * sits behind a "View eligibility details" disclosure so long result lists
 * stay scannable.
 */
@Component({
  selector: 'app-finder-match-card',
  standalone: true,
  imports: [CommonModule, RouterLink, BadgeComponent],
  templateUrl: './finder-match-card.component.html',
  styleUrl: './finder-match-card.component.css',
})
export class FinderMatchCardComponent {
  @Input({ required: true }) match!: SchemeMatch;
  @Input({ required: true }) badgeVariant: FinderBadgeVariant = 'neutral';
  @Input({ required: true }) statusLabel = '';

  readonly detailsOpen = signal(false);

  toggleDetails(): void {
    this.detailsOpen.update((open) => !open);
  }

  /** Readable label for a backend parameter key (e.g. `annual_income`). */
  label(parameter: string): string {
    return parameterLabel(parameter);
  }

  /** Readable requirement text for a rule (e.g. "At least 18"). */
  requiredText(rule: FinderRuleResult): string {
    return requiredValueText(rule);
  }

  /** Stable id linking the disclosure button to the rule list it controls. */
  rulesElementId(schemeId: string): string {
    return `finder-rules-${schemeId}`;
  }
}
