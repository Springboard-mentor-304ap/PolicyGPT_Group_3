import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Application,
  ApplicationStatusUpdate,
} from '../models/application.models';

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
}
