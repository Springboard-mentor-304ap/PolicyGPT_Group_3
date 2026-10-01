import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SchemeUsageItem } from '../../../../core/models/analytics.models';

/**
 * "Scheme Usage (Top Viewed)" leaderboard table.
 *
 * Extracted from DashboardComponent so each component stays within
 * Angular's per-component CSS style budget. It is purely presentational:
 * the parent still fetches the analytics payload and passes rows in.
 */
@Component({
  selector: 'app-usage-leaderboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './usage-leaderboard.component.html',
  styleUrl: './usage-leaderboard.component.css',
})
export class UsageLeaderboardComponent {
  @Input({ required: true }) rows: SchemeUsageItem[] = [];
}
