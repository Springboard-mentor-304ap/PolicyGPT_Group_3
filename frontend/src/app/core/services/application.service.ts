import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Application,
  ApplicationReviewItem,
  ApplicationStatus,
  ApplicationStatusUpdate,
} from '../models/application.models';
import { UserRole } from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class ApplicationService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** Submit an application for a scheme (citizens and organizations only). */
  submitApplication(schemeId: string): Observable<Application> {
    return this.http.post<Application>(
      '/api/applications',
      { scheme_id: schemeId },
      { headers: this.getAuthHeaders() }
    );
  }

  /** Applications submitted by the current user (newest first). */
  listMyApplications(): Observable<Application[]> {
    return this.http.get<Application[]>('/api/applications', {
      headers: this.getAuthHeaders(),
    });
  }

  /** Details for a single application (owner or staff). */
  getApplication(applicationId: string): Observable<Application> {
    return this.http.get<Application>(`/api/applications/${applicationId}`, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Move an application through the review workflow (staff only). */
  updateApplicationStatus(
    applicationId: string,
    data: ApplicationStatusUpdate
  ): Observable<Application> {
    return this.http.patch<Application>(
      `/api/applications/${applicationId}/status`,
      data,
      { headers: this.getAuthHeaders() }
    );
  }

  /**
   * Staff review list (GET /api/applications/review).
   * Server-side department-scoped: officials only receive applications in
   * their own ministry/department; admins receive all.
   */
  reviewApplications(
    status?: ApplicationStatus
  ): Observable<ApplicationReviewItem[]> {
    let params = new HttpParams();
    if (status) {
      params = params.set('status', status);
    }
    return this.http.get<ApplicationReviewItem[]>('/api/applications/review', {
      headers: this.getAuthHeaders(),
      params,
    });
  }

  /** Mirrors the backend staff-only roles for application review. */
  static canReviewApplications(
    role: UserRole | string | null | undefined
  ): boolean {
    return (
      !!role &&
      [
        UserRole.GOVERNMENT_OFFICIAL,
        UserRole.ADMINISTRATOR,
        UserRole.SUPER_ADMIN,
      ].includes(role as UserRole)
    );
  }
}
