import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  HelpdeskChatRequest,
  HelpdeskChatResponse,
} from '../models/helpdesk.models';

/**
 * Thin client for the AI Helpdesk API.
 *
 * The URL is relative on purpose: the dev server proxies `/api` to the backend
 * (see proxy.conf.json) and the JWT interceptor attaches the access token, so
 * the request is authenticated through the existing mechanism. The endpoint is
 * protected by `get_current_user` on the backend and the answer always comes
 * from the PolicyGPT knowledge base, so no policy content is composed here.
 */
@Injectable({ providedIn: 'root' })
export class HelpdeskService {
  private readonly http = inject(HttpClient);

  /** POST /api/helpdesk/chat — question -> generated answer + sources. */
  askHelpdesk(question: string): Observable<HelpdeskChatResponse> {
    const body: HelpdeskChatRequest = { question };
    return this.http.post<HelpdeskChatResponse>('/api/helpdesk/chat', body);
  }
}
