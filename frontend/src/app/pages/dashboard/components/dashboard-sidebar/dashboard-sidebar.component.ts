import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink } from '@angular/router';

export interface DashboardMenuItem {
  id: string;
  label: string;
  icon: string;
}

/**
 * Dashboard sidebar shell (logo, collapsible nav, footer sign-in/out).
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. All navigation decisions
 * stay in the parent via outputs — no behaviour is duplicated here.
 */
@Component({
  selector: 'app-dashboard-sidebar',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard-sidebar.component.html',
  styleUrl: './dashboard-sidebar.component.css',
})
export class DashboardSidebarComponent {
  @Input({ required: true }) sidebarOpen = true;
  @Input({ required: true }) menuItems: DashboardMenuItem[] = [];
  @Input({ required: true }) activeMenu = '';
  @Input({ required: true }) isGuest = false;

  @Output() sidebarToggle = new EventEmitter<void>();
  @Output() menuSelect = new EventEmitter<string>();
  @Output() signOut = new EventEmitter<void>();
}
