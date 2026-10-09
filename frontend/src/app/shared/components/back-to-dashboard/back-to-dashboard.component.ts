import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

/**
 * Single source of truth for the "back" control at the top of a page.
 *
 * Every page used to render its own arrow (or plain text, or a button calling
 * a router method) with its own spacing and colour. This component keeps the
 * icon, spacing, typography and navigation identical everywhere; pages that
 * return to a listing instead of the dashboard only override the destination
 * and the label.
 */
@Component({
  selector: 'app-back-to-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './back-to-dashboard.component.html',
  styleUrl: './back-to-dashboard.component.css',
})
export class BackToDashboardComponent {
  /** Where the link navigates; defaults to the dashboard. */
  @Input() link: string = '/dashboard';

  /** Label shown next to the arrow. */
  @Input() label: string = 'Back to Dashboard';
}
