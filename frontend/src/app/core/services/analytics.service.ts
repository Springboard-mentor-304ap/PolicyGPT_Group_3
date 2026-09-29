import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, forkJoin, map, of } from 'rxjs';

import { UserRole } from '../models/auth.models';
import {
  AnalyticsOverviewResponse,
  DashboardAnalytics,
  DepartmentStatisticsResponse,
  NotificationStatisticsResponse,
  PolicyStatisticsResponse,
  SchemeStatisticsResponse,
  UserUsageStatisticsResponse,
} from '../models/analytics.models';

/**
 * Roles allowed to reach any `/api/analytics/*` endpoint.
 * Mirrors `ANALYTICS_ALLOWED_ROLES` in `backend/app/analytics/router.py`.
 */
const ANALYTICS_ALLOWED_ROLES: string[] = [
  UserRole.GOVERNMENT_OFFICIAL,
  UserRole.RESEARCHER,
  UserRole.ADMINISTRATOR,
  UserRole.SUPER_ADMIN,
];

/**
 * Roles allowed to reach `/api/analytics/users`.
 * Mirrors `require_user_analytics_access` in `backend/app/analytics/router.py`.
 */
const USER_ANALYTICS_ALLOWED_ROLES: string[] = [
  UserRole.ADMINISTRATOR,
  UserRole.SUPER_ADMIN,
];

@Injectable({
  providedIn: 'root',
})
export class AnalyticsService {
  private readonly http = inject(HttpClient);
  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';
  private readonly baseUrl = '/api/analytics';

  /** Frontend mirror of the backend's analytics RBAC. */
  static isAnalyticsRole(role: UserRole | string | null | undefined): boolean {
    return !!role && ANALYTICS_ALLOWED_ROLES.includes(role);
  }

  /** Frontend mirror of the backend's user-analytics RBAC. */
  static isUserAnalyticsRole(role: UserRole | string | null | undefined): boolean {
    return !!role && USER_ANALYTICS_ALLOWED_ROLES.includes(role);
  }

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  private get<T>(path: string): Observable<T> {
    return this.http.get<T>(`${this.baseUrl}${path}`, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Platform totals, scoped to the official's ministry where applicable. */
  getOverview(): Observable<AnalyticsOverviewResponse> {
    return this.get<AnalyticsOverviewResponse>('/overview');
  }

  /** Policy counts by category / status / department. */
  getPolicyStatistics(): Observable<PolicyStatisticsResponse> {
    return this.get<PolicyStatisticsResponse>('/policies');
  }

  /** Scheme counts by category / status plus the usage leaderboard. */
  getSchemeStatistics(): Observable<SchemeStatisticsResponse> {
    return this.get<SchemeStatisticsResponse>('/schemes');
  }

  /** User + search-usage statistics (administrators / super admins only). */
  getUserUsageStatistics(): Observable<UserUsageStatisticsResponse> {
    return this.get<UserUsageStatisticsResponse>('/users');
  }

  /** Policy and scheme counts by department. */
  getDepartmentStatistics(): Observable<DepartmentStatisticsResponse> {
    return this.get<DepartmentStatisticsResponse>('/departments');
  }

  /** Notification analytics across type / channel / read status / time. */
  getNotificationStatistics(): Observable<NotificationStatisticsResponse> {
    return this.get<NotificationStatisticsResponse>('/notifications');
  }

  /**
   * Compose the dashboard from the canonical endpoints.
   *
   * Only endpoints the caller's role can actually reach are requested:
   * `/users` is admin-only, and non-analytics roles never trigger a request
   * at all (see `DashboardComponent`). Secondary panels degrade to `null`
   * instead of blanking the whole dashboard, and are reported in
   * `failedPanels` so the UI can surface a partial-load notice.
   */
  getDashboardAnalytics(
    role: UserRole | string | null | undefined
  ): Observable<DashboardAnalytics> {
    const failedPanels: string[] = [];

    const optional = <T>(
      panel: string,
      request$: Observable<T>
    ): Observable<T | null> =>
      request$.pipe(
        catchError(() => {
          failedPanels.push(panel);
          return of(null);
        })
      );

    return forkJoin({
      overview: this.getOverview(),
      policies: optional('Policies', this.getPolicyStatistics()),
      schemes: optional('Schemes', this.getSchemeStatistics()),
      users: AnalyticsService.isUserAnalyticsRole(role)
        ? optional('Users', this.getUserUsageStatistics())
        : of(null),
      departments: optional('Departments', this.getDepartmentStatistics()),
      notifications: optional('Notifications', this.getNotificationStatistics()),
    }).pipe(
      map((result) => ({ ...result, failedPanels } as DashboardAnalytics))
    );
  }
}
