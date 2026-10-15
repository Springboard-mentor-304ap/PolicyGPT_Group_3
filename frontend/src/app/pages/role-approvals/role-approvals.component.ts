import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

import { AuthService } from '../../core/services/auth.service';
import { RoleRequestResponse } from '../../core/models/auth.models';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';
import { PendingApprovalsComponent } from '../dashboard/components/pending-approvals/pending-approvals.component';

/**
 * Administrator "Role Approvals" page.
 *
 * Hosts the exact same PendingApprovalsComponent the dashboard renders and
 * drives it with the same AuthService calls (GET /api/role-requests/pending,
 * PUT …/approve, PUT …/reject), so no approval logic or styling is
 * duplicated. The route is guarded by roleGuard for administrators and
 * super admins, and the API enforces the same rule server-side.
 */
@Component({
  selector: 'app-role-approvals',
  standalone: true,
  imports: [CommonModule, BackToDashboardComponent, PendingApprovalsComponent],
  templateUrl: './role-approvals.component.html',
  styleUrl: './role-approvals.component.css',
})
export class RoleApprovalsComponent implements OnInit {
  private readonly authService = inject(AuthService);

  readonly requests = signal<RoleRequestResponse[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);

    this.authService.getPendingRoleRequests().subscribe({
      next: (requests) => {
        this.requests.set(requests);
        this.loading.set(false);
      },
      error: (err) => {
        this.loadError.set(
          err?.error?.detail || 'Could not load pending role requests.'
        );
        this.requests.set([]);
        this.loading.set(false);
      },
    });
  }

  approveRequest(requestId: string): void {
    this.authService.approveRoleRequest(requestId).subscribe({
      next: () => this.load(),
      error: () => {},
    });
  }

  rejectRequest(requestId: string): void {
    this.authService.rejectRoleRequest(requestId).subscribe({
      next: () => this.load(),
      error: () => {},
    });
  }
}
