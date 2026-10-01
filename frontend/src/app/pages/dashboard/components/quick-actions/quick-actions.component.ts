import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * Citizen "Quick Actions" card grid (Search, Eligibility, Compare, Profile).
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. Purely presentational —
 * navigation targets are static router links.
 */
@Component({
  selector: 'app-quick-actions',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './quick-actions.component.html',
  styleUrl: './quick-actions.component.css',
})
export class QuickActionsComponent {}
