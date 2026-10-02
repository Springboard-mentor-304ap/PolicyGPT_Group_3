import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, map, shareReplay, throwError } from 'rxjs';

import { DepartmentOptionsResponse } from '../models/department.models';

@Injectable({
  providedIn: 'root',
})
export class DepartmentService {
  private readonly http = inject(HttpClient);

  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';
  private readonly baseUrl = '/api/departments';

  /** Shared in-flight/complete request so each form does not refetch. */
  private departments$: Observable<string[]> | null = null;

  private getAuthHeaders(): HttpHeaders {
    const token = localStorage.getItem(this.ACCESS_TOKEN_KEY);
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }

  /** Department values already used by existing policies and schemes. */
  listDepartments(): Observable<string[]> {
    if (!this.departments$) {
      this.departments$ = this.http
        .get<DepartmentOptionsResponse>(this.baseUrl, {
          headers: this.getAuthHeaders(),
        })
        .pipe(
          map((response) => response.departments ?? []),
          shareReplay({ bufferSize: 1, refCount: false }),
          catchError((error) => {
            // A failed lookup is not cached, so the next form can retry.
            this.departments$ = null;
            return throwError(() => error);
          })
        );
    }

    return this.departments$;
  }
}
