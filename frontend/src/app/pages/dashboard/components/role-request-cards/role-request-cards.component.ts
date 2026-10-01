import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * Citizen "Upgrade Your PolicyGPT Role" cards.
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. Purely presentational —
 * the parent still gates rendering with `isCitizen()`.
 */
@Component({
  selector: 'app-role-request-cards',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './role-request-cards.component.html',
  styleUrl: './role-request-cards.component.css',
})
export class RoleRequestCardsComponent {}
