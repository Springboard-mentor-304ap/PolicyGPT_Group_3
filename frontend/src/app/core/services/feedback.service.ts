import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Feedback,
  FeedbackCreate,
  FeedbackStatus,
  FeedbackType,
  FeedbackUpdate,
} from '../models/feedback.models';

@Injectable({ providedIn: 'root' })
export class FeedbackService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** Submit new feedback, an issue report or a query (any signed-in user). */
  createFeedback(data: FeedbackCreate): Observable<Feedback> {
    return this.http.post<Feedback>('/api/feedback', data, {
      headers: this.getAuthHeaders(),
    });
  }

  /** All feedback, optionally filtered by type/status (administrators). */
  listFeedback(options?: {
    type?: FeedbackType;
    status?: FeedbackStatus;
  }): Observable<Feedback[]> {
    let params = new HttpParams();
    if (options?.type) {
      params = params.set('type', options.type);
    }
    if (options?.status) {
      params = params.set('status', options.status);
    }
    return this.http.get<Feedback[]>('/api/feedback', {
      headers: this.getAuthHeaders(),
      params,
    });
  }

  /** Feedback submitted by the current user (newest first). */
  listMyFeedback(): Observable<Feedback[]> {
    return this.http.get<Feedback[]>('/api/feedback/my', {
      headers: this.getAuthHeaders(),
    });
  }

  /** Update status / resolution note (administrators). */
  updateFeedback(id: string, data: FeedbackUpdate): Observable<Feedback> {
    return this.http.patch<Feedback>(`/api/feedback/${id}`, data, {
      headers: this.getAuthHeaders(),
    });
  }
}
