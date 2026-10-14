import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  Policy,
  PolicyCreateRequest,
  PolicyUpdateRequest,
  PolicyRejectRequest,
} from '../models/policy.models';

@Injectable({ providedIn: 'root' })
export class PolicyService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** List all policies (optionally include archived) */
  listPolicies(includeArchived = false): Observable<Policy[]> {
    let params = new HttpParams();
    if (includeArchived) {
      params = params.set('include_archived', 'true');
    }
    return this.http.get<Policy[]>('/api/policies', {
      headers: this.getAuthHeaders(),
      params,
    });
  }

  /** Get a single policy by ID */
  getPolicy(policyId: string): Observable<Policy> {
    return this.http.get<Policy>(`/api/policies/${policyId}`, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Create a new policy (Government Official only) */
  createPolicy(data: PolicyCreateRequest): Observable<Policy> {
    return this.http.post<Policy>('/api/policies', data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Update an existing policy (owner Government Official, status-dependent) */
  updatePolicy(policyId: string, data: PolicyUpdateRequest): Observable<Policy> {
    return this.http.put<Policy>(`/api/policies/${policyId}`, data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Archive an approved policy (owner Government Official) */
  archivePolicy(policyId: string): Observable<Policy> {
    return this.http.post<Policy>(
      `/api/policies/${policyId}/archive`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Unarchive a policy (owner Government Official) */
  unarchivePolicy(policyId: string): Observable<Policy> {
    return this.http.post<Policy>(
      `/api/policies/${policyId}/unarchive`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Approve a pending policy (Administrator only) */
  approvePolicy(policyId: string): Observable<Policy> {
    return this.http.post<Policy>(
      `/api/policies/${policyId}/approve`,
      {},
      { headers: this.getAuthHeaders() }
    );
  }

  /** Reject a pending policy (Administrator only) */
  rejectPolicy(policyId: string, data: PolicyRejectRequest): Observable<Policy> {
    return this.http.post<Policy>(
      `/api/policies/${policyId}/reject`,
      data,
      { headers: this.getAuthHeaders() }
    );
  }
}
