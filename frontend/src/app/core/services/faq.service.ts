import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { Faq, FaqCreate, FaqUpdate } from '../models/faq.models';

@Injectable({ providedIn: 'root' })
export class FaqService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /**
   * List FAQs for the signed-in user. Managers may include inactive
   * entries and filter by search / category.
   */
  listFaqs(options?: {
    search?: string;
    category?: string;
    includeInactive?: boolean;
  }): Observable<Faq[]> {
    let params = new HttpParams();
    if (options?.search) {
      params = params.set('search', options.search);
    }
    if (options?.category) {
      params = params.set('category', options.category);
    }
    if (options?.includeInactive) {
      params = params.set('include_inactive', 'true');
    }
    return this.http.get<Faq[]>('/api/faqs', {
      headers: this.getAuthHeaders(),
      params,
    });
  }

  /** Create an FAQ entry (administrators / super admins). */
  createFaq(data: FaqCreate): Observable<Faq> {
    return this.http.post<Faq>('/api/faqs', data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Update an FAQ entry (administrators / super admins). */
  updateFaq(faqId: string, data: FaqUpdate): Observable<Faq> {
    return this.http.patch<Faq>(`/api/faqs/${faqId}`, data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Deactivate an FAQ entry (administrators / super admins). */
  deactivateFaq(faqId: string): Observable<Faq> {
    return this.http.delete<Faq>(`/api/faqs/${faqId}`, {
      headers: this.getAuthHeaders(),
    });
  }
}
