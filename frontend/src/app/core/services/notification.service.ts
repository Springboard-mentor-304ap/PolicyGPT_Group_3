import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  Notification,
  UnreadNotificationCount,
  MarkAllNotificationsReadResponse,
} from '../models/notification.models';

@Injectable({
  providedIn: 'root',
})
export class NotificationService {
  private readonly http = inject(HttpClient);
  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);

    return token
      ? new HttpHeaders({
          Authorization: `Bearer ${token}`,
        })
      : new HttpHeaders();
  }

  getNotifications(): Observable<Notification[]> {
    return this.http.get<Notification[]>('/api/notifications', {
      headers: this.getAuthHeaders(),
    });
  } 

  getUnreadCount(): Observable<UnreadNotificationCount> {
    return this.http.get<UnreadNotificationCount>(
      '/api/notifications/unread-count',
      {
        headers: this.getAuthHeaders(),
      }
    );
  }

  markAsRead(notificationId: string): Observable<Notification> {
    return this.http.patch<Notification>(
      `/api/notifications/${notificationId}/read`,
      {},
      {
        headers: this.getAuthHeaders(),
      }
    );
  }

  markAllAsRead(): Observable<MarkAllNotificationsReadResponse> {
    return this.http.patch<MarkAllNotificationsReadResponse>(
      '/api/notifications/read-all',
      {},
      {
        headers: this.getAuthHeaders(),
      }
    );
  }
}