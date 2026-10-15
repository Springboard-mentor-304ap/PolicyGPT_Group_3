import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams, HttpResponse } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { UserRole } from '../models/auth.models';
import {
  AdminUser,
  AdminUserListParams,
  AuditLogEntry,
  AuditLogListParams,
} from '../models/admin.models';

/** One page of results plus the server-side total (X-Total-Count). */
export interface Paged<T> {
  items: T[];
  total: number;
}

/**
 * Administrative user management and audit-log APIs.
 *
 * Both endpoints are administrator/super-admin only on the server; the
 * backend additionally refuses self-actions, never lets anyone manage a
 * super admin, and lets a super admin also manage administrators. The UI
 * mirrors that matrix via `canManageUser` so impossible actions are never
 * offered, but every action is enforced server-side regardless.
 */
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** GET /api/admin/users — filtered, paginated account list. */
  listUsers(params: AdminUserListParams = {}): Observable<Paged<AdminUser>> {
    let httpParams = new HttpParams();
    if (params.role) {
      httpParams = httpParams.set('role', params.role);
    }
    if (params.is_active !== undefined) {
      httpParams = httpParams.set('is_active', String(params.is_active));
    }
    if (params.search?.trim()) {
      httpParams = httpParams.set('search', params.search.trim());
    }
    httpParams = httpParams
      .set('limit', String(params.limit ?? 25))
      .set('offset', String(params.offset ?? 0));

    return this.http
      .get<AdminUser[]>('/api/admin/users', {
        headers: this.getAuthHeaders(),
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPage<AdminUser>(res)));
  }

  /** POST /api/admin/users/{id}/deactivate — disables + revokes sessions. */
  deactivateUser(userId: string): Observable<AdminUser> {
    return this.http.post<AdminUser>(
      `/api/admin/users/${userId}/deactivate`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** POST /api/admin/users/{id}/reactivate */
  reactivateUser(userId: string): Observable<AdminUser> {
    return this.http.post<AdminUser>(
      `/api/admin/users/${userId}/reactivate`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** POST /api/admin/users/{id}/revoke-role — returns the account to citizen. */
  revokeUserRole(userId: string): Observable<AdminUser> {
    return this.http.post<AdminUser>(
      `/api/admin/users/${userId}/revoke-role`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** GET /api/audit-logs — filtered, paginated audit trail. */
  listAuditLogs(
    params: AuditLogListParams = {}
  ): Observable<Paged<AuditLogEntry>> {
    let httpParams = new HttpParams();
    if (params.actor_id?.trim()) {
      httpParams = httpParams.set('actor_id', params.actor_id.trim());
    }
    if (params.action?.trim()) {
      httpParams = httpParams.set('action', params.action.trim());
    }
    if (params.target_table?.trim()) {
      httpParams = httpParams.set('target_table', params.target_table.trim());
    }
    if (params.date_from) {
      httpParams = httpParams.set('date_from', params.date_from);
    }
    if (params.date_to) {
      httpParams = httpParams.set('date_to', params.date_to);
    }
    httpParams = httpParams
      .set('limit', String(params.limit ?? 25))
      .set('offset', String(params.offset ?? 0));

    return this.http
      .get<AuditLogEntry[]>('/api/audit-logs', {
        headers: this.getAuthHeaders(),
        params: httpParams,
        observe: 'response',
      })
      .pipe(map((res) => this.toPage<AuditLogEntry>(res)));
  }

  private toPage<T>(res: HttpResponse<T[]>): Paged<T> {
    const header = res.headers.get('X-Total-Count');
    const total = Number(header);
    return {
      items: res.body ?? [],
      // Fall back to the page length when the header is absent so the pager
      // still works instead of showing "0 of 0".
      total: Number.isFinite(total) ? total : (res.body?.length ?? 0),
    };
  }

  /**
   * Frontend mirror of the backend permission matrix in admin/users.py:
   * no self-actions, nobody manages a super admin, and an administrator
   * only manages citizen / researcher / organization / government_official
   * while a super admin additionally manages administrators.
   */
  static canManageUser(
    actorRole: UserRole | string | null,
    actorId: string | null,
    target: AdminUser
  ): boolean {
    if (!actorRole || !actorId || target.id === actorId) {
      return false;
    }
    if (target.role === UserRole.SUPER_ADMIN) {
      return false;
    }
    if (actorRole === UserRole.SUPER_ADMIN) {
      return true;
    }
    if (actorRole === UserRole.ADMINISTRATOR) {
      return (
        target.role === UserRole.CITIZEN ||
        target.role === UserRole.RESEARCHER ||
        target.role === UserRole.ORGANIZATION ||
        target.role === UserRole.GOVERNMENT_OFFICIAL
      );
    }
    return false;
  }
}
