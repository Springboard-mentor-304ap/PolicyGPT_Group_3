import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

import { NotificationItem, UnreadCountResponse } from '../models/notification.models';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';
  private readonly baseUrl = '/api/notifications';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** Notifications addressed to the current user (newest first). */
  list(): Observable<NotificationItem[]> {
    return this.http.get<NotificationItem[]>(this.baseUrl, {
      headers: this.getAuthHeaders(),
    });
  }

  /** Number of unread notifications for the current user. */
  unreadCount(): Observable<UnreadCountResponse> {
    return this.http.get<UnreadCountResponse>(`${this.baseUrl}/unread-count`, {
      headers: this.getAuthHeaders(),
    });
  }
}
