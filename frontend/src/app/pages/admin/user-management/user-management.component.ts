import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, debounceTime } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { AdminService } from '../../../core/services/admin.service';
import { AdminUser } from '../../../core/models/admin.models';
import { UserRole } from '../../../core/models/auth.models';
import { humanize } from '../../../core/services/analytics.mappers';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

/**
 * Administrator "User Management" page.
 *
 * Backed entirely by the existing /api/admin/users API (list, deactivate,
 * reactivate, revoke-role). The available actions mirror the backend
 * permission matrix: nobody acts on their own account or on a super admin,
 * and an administrator only manages citizen / researcher / organization /
 * government-official accounts — the server enforces the same rules, this
 * page simply never offers an action the API would refuse.
 */
@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [CommonModule, FormsModule, BackToDashboardComponent],
  templateUrl: './user-management.component.html',
  styleUrl: './user-management.component.css',
})
export class UserManagementComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly authService = inject(AuthService);

  readonly users = signal<AdminUser[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly unauthorized = signal(false);
  readonly total = signal(0);
  readonly actionBusyId = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);

  readonly pageSize = 25;
  page = 0;

  searchTerm = '';
  roleFilter = '';
  statusFilter = '';

  /** Row whose destructive action is awaiting inline confirmation. */
  confirmingId = signal<string | null>(null);

  private readonly searchInput$ = new Subject<string>();

  readonly roleOptions = [
    { value: '', label: 'All roles' },
    { value: UserRole.CITIZEN, label: 'Citizens' },
    { value: UserRole.RESEARCHER, label: 'Researchers' },
    { value: UserRole.ORGANIZATION, label: 'Organizations' },
    { value: UserRole.GOVERNMENT_OFFICIAL, label: 'Government Officials' },
    { value: UserRole.ADMINISTRATOR, label: 'Administrators' },
    { value: UserRole.SUPER_ADMIN, label: 'Super Admins' },
  ];

  readonly statusOptions = [
    { value: '', label: 'All statuses' },
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Deactivated' },
  ];

  ngOnInit(): void {
    this.load();

    this.searchInput$
      .pipe(debounceTime(300))
      .subscribe((value) => this.applySearch(value));
  }

  get actorId(): string | null {
    return this.authService.currentUser()?.id ?? null;
  }

  get actorRole(): UserRole | string | null {
    return this.authService.userRole();
  }

  load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.unauthorized.set(false);

    const is_active =
      this.statusFilter === '' ? undefined : this.statusFilter === 'active';

    this.adminService
      .listUsers({
        role: this.roleFilter || undefined,
        is_active,
        search: this.searchTerm,
        limit: this.pageSize,
        offset: this.page * this.pageSize,
      })
      .subscribe({
        next: ({ items, total }) => {
          this.users.set(items);
          this.total.set(total);
          this.loading.set(false);
        },
        error: (err) => this.handleLoadError(err),
      });
  }

  onSearchInput(value: string): void {
    this.searchInput$.next(value);
  }

  applySearch(value: string): void {
    this.searchTerm = value;
    this.page = 0;
    this.load();
  }

  onRoleFilterChange(value: string): void {
    this.roleFilter = value;
    this.page = 0;
    this.load();
  }

  onStatusFilterChange(value: string): void {
    this.statusFilter = value;
    this.page = 0;
    this.load();
  }

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.total() / this.pageSize));
  }

  get pageStart(): number {
    return this.total() === 0 ? 0 : this.page * this.pageSize + 1;
  }

  get pageEnd(): number {
    return Math.min(this.total(), (this.page + 1) * this.pageSize);
  }

  prevPage(): void {
    if (this.page > 0) {
      this.page -= 1;
      this.load();
    }
  }

  nextPage(): void {
    if (this.page + 1 < this.totalPages) {
      this.page += 1;
      this.load();
    }
  }

  canManage(user: AdminUser): boolean {
    return AdminService.canManageUser(this.actorRole, this.actorId, user);
  }

  /** The only action offered for a currently-active account. */
  isDeactivateAction(user: AdminUser): boolean {
    return this.confirmingId() === user.id && user.is_active;
  }

  /** The only action offered for a currently-deactivated account. */
  isReactivateAction(user: AdminUser): boolean {
    return this.confirmingId() === user.id && !user.is_active;
  }

  requestConfirm(user: AdminUser): void {
    this.actionError.set(null);
    this.confirmingId.set(user.id);
  }

  cancelConfirm(): void {
    this.confirmingId.set(null);
  }

  confirmDeactivate(user: AdminUser): void {
    this.runAction(user, 'deactivate');
  }

  confirmReactivate(user: AdminUser): void {
    this.runAction(user, 'reactivate');
  }

  confirmRevokeRole(user: AdminUser): void {
    this.runAction(user, 'revoke-role');
  }

  private runAction(
    user: AdminUser,
    action: 'deactivate' | 'reactivate' | 'revoke-role'
  ): void {
    this.actionBusyId.set(user.id);
    this.actionError.set(null);

    const request$ =
      action === 'deactivate'
        ? this.adminService.deactivateUser(user.id)
        : action === 'reactivate'
          ? this.adminService.reactivateUser(user.id)
          : this.adminService.revokeUserRole(user.id);

    request$.subscribe({
      next: (updated) => {
        // Row count is unchanged: only the row's state flips.
        this.users.set(
          this.users().map((row) => (row.id === updated.id ? updated : row))
        );
        this.actionBusyId.set(null);
        this.confirmingId.set(null);
      },
      error: (err) => {
        const detail = err?.error?.detail;
        this.actionError.set(
          typeof detail === 'string' && detail
            ? detail
            : 'The action could not be completed.'
        );
        this.actionBusyId.set(null);
        this.confirmingId.set(null);
      },
    });
  }

  private handleLoadError(err: unknown): void {
    const httpError = err as { status?: number; error?: { detail?: unknown } };
    this.loading.set(false);

    if (httpError?.status === 403) {
      // The API refuses non-administrators; the route guard should already
      // prevent this, but the page degrades honestly if it ever happens.
      this.unauthorized.set(true);
      this.users.set([]);
      this.total.set(0);
      return;
    }

    const detail = httpError?.error?.detail;
    this.loadError.set(
      typeof detail === 'string' && detail
        ? detail
        : 'Could not load users. Please try again.'
    );
  }

  formatRole(value: string): string {
    return humanize(value);
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  trackById(_index: number, user: AdminUser): string {
    return user.id;
  }
}
