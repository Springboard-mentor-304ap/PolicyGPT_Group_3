import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  FinderProfile,
  ProfileExtractionRequest,
  SchemeMatchRequest,
  SchemeMatchResponse,
} from '../models/finder.models';

/**
 * Thin client for the Natural-Language Scheme Finder API.
 *
 * Relative URLs are used on purpose: the dev server proxies `/api` to the
 * backend (see proxy.conf.json) and the JWT interceptor attaches the access
 * token when the visitor is signed in. Both Finder endpoints are public, so
 * guests can use the page without an account.
 */
@Injectable({ providedIn: 'root' })
export class FinderService {
  private readonly http = inject(HttpClient);

  /** POST /api/finder/extract — free-text description -> extracted profile. */
  extractProfile(text: string): Observable<FinderProfile> {
    const body: ProfileExtractionRequest = { text };
    return this.http.post<FinderProfile>('/api/finder/extract', body);
  }

  /** POST /api/finder/match — deterministic scheme matching for a profile. */
  matchProfile(profile: FinderProfile): Observable<SchemeMatchResponse> {
    const body: SchemeMatchRequest = { profile };
    return this.http.post<SchemeMatchResponse>('/api/finder/match', body);
  }
}
