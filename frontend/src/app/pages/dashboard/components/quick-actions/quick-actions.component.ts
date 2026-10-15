import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * One shortcut row on the dashboard's "Access Government Services" card.
 * Every entry points at a route that already exists in app.routes.ts.
 */
export interface QuickActionItem {
  /** Icon key rendered by this component's template switch. */
  icon: string;
  /** Pastel tone of the icon tile: blue | green | saffron | navy. */
  tone: string;
  label: string;
  /** One-line description of what the destination offers. */
  hint: string;
  /** Existing route this row navigates to. */
  link: string;
}

/**
 * Dashboard services card (reference-style list of rows with icon tiles,
 * label, hint and a chevron).
 *
 * Presentational only — DashboardComponent decides which real destinations
 * each role sees. Extracted from DashboardComponent so each component stays
 * within Angular's per-component CSS style budget.
 */
@Component({
  selector: 'app-quick-actions',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './quick-actions.component.html',
  styleUrl: './quick-actions.component.css',
})
export class QuickActionsComponent {
  @Input() heading = 'Access Government Services';
  @Input() subtitle = '';
  @Input() items: QuickActionItem[] = [];
}
