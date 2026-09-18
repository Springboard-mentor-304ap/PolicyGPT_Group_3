import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Scheme,
  SchemeCreateRequest,
  SchemeUpdateRequest,
  SchemeRejectRequest,
  EligibilityRule,
  EligibilityRuleCreateRequest,
} from '../models/scheme.models';

@Injectable({ providedIn: 'root' })
export class SchemeService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** List all schemes (optionally include archived) */
  listSchemes(includeArchived = false): Observable<Scheme[]> {
    let params = new HttpParams();
    if (includeArchived) {
      params = params.set('include_archived', 'true');
    }
    return this.http.get<Scheme[]>('/api/schemes', {
      headers: this.getAuthHeaders(),
      params,
    });
  }

  /** Get a single scheme by ID */
  getScheme(schemeId: string): Observable<Scheme> {
    return this.http.get<Scheme>(`/api/schemes/${schemeId}`, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Create a new scheme (Government Official only) */
  createScheme(data: SchemeCreateRequest): Observable<Scheme> {
    return this.http.post<Scheme>('/api/schemes', data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Update an existing scheme (owner Government Official, status-dependent) */
  updateScheme(schemeId: string, data: SchemeUpdateRequest): Observable<Scheme> {
    return this.http.put<Scheme>(`/api/schemes/${schemeId}`, data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Archive an active scheme (owner Government Official) */
  archiveScheme(schemeId: string): Observable<Scheme> {
    return this.http.post<Scheme>(
      `/api/schemes/${schemeId}/archive`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Unarchive a scheme (owner Government Official) */
  unarchiveScheme(schemeId: string): Observable<Scheme> {
    return this.http.post<Scheme>(
      `/api/schemes/${schemeId}/unarchive`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Approve a pending scheme (Administrator only) */
  approveScheme(schemeId: string): Observable<Scheme> {
    return this.http.post<Scheme>(
      `/api/schemes/${schemeId}/approve`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Reject a pending scheme (Administrator only) */
  rejectScheme(schemeId: string, data: SchemeRejectRequest): Observable<Scheme> {
    return this.http.post<Scheme>(
      `/api/schemes/${schemeId}/reject`,
      data,
      { headers: this.getAuthHeaders() }
    );
  }

  listEligibilityRules(schemeId: string): Observable<EligibilityRule[]> {
    return this.http.get<EligibilityRule[]>(`/api/schemes/${schemeId}/eligibility-rules`, {
      headers: this.getAuthHeaders(),
    });
  }

  createEligibilityRule(
    schemeId: string,
    data: EligibilityRuleCreateRequest,
  ): Observable<EligibilityRule> {
    return this.http.post<EligibilityRule>(`/api/schemes/${schemeId}/eligibility-rules`, data, {
      headers: this.getAuthHeaders(),
    });
  }

  deleteEligibilityRule(ruleId: string): Observable<void> {
    return this.http.delete<void>(`/api/schemes/eligibility-rules/${ruleId}`, {
      headers: this.getAuthHeaders(),
    });
  }
}
