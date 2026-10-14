import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, of, switchMap, map, catchError } from 'rxjs';
import {
  EligibilityCheckRequest,
  EligibilityResult,
  EligibilityStatus,
  CriterionResult,
} from '../models/eligibility.models';

/**
 * Maps a backend rule result to the frontend CriterionResult shape.
 */
function mapRule(r: any): CriterionResult {
  const paramLabel = (r.parameter || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c: string) => c.toUpperCase());

  return {
    parameter: r.parameter,
    label: `${paramLabel} Check`,
    passed: r.satisfied,
    ruleDescription: r.message || '',
    userValue: r.actual_value ?? 'N/A',
    failureReason: r.satisfied ? undefined : r.message,
  };
}

@Injectable({ providedIn: 'root' })
export class EligibilityService {
  private readonly http = inject(HttpClient);

  /**
   * Check eligibility for a single scheme.
   *
   * Backend: GET /api/eligibility/schemes/{scheme_id}
   * Uses the authenticated user's citizen profile from the database.
   */
  checkSchemeEligibility(schemeId: string): Observable<EligibilityResult> {
    return this.http
      .get<any>(`/api/eligibility/schemes/${schemeId}`)
      .pipe(map((res) => this.mapResponse(res)));
  }

  /**
   * Evaluate all schemes the user has eligibility rules against.
   *
   * No batch backend endpoint — fetches all scheme IDs via the search API,
   * then calls the single-scheme eligibility endpoint for each.
   */
  evaluateAllSchemes(): Observable<EligibilityResult[]> {
    return this.http
      .get<{ results: any[]; total: number }>('/api/search', {
        params: { search_type: 'scheme', page_size: '100' },
      })
      .pipe(
        map((res) => res.results.map((r: any) => String(r.id))),
        switchMap((ids: string[]) => {
          if (ids.length === 0) return of([]);
          const calls = ids.map((id) =>
            this.http
              .get<any>(`/api/eligibility/schemes/${id}`)
              .pipe(
                map((res) => this.mapResponse(res)),
                catchError(() => of(null))
              )
          );
          return forkJoin(calls).pipe(
            map((results) => results.filter(Boolean) as EligibilityResult[])
          );
        })
      );
  }

  /**
   * Map the backend EligibilityCheckResponse to the frontend EligibilityResult.
   *
   * Backend: { scheme_id, scheme_title, status, summary, rules, missing_information }
   * Frontend: { scheme_id, scheme_title, category, is_eligible, match_percentage, criteria_results, ... }
   */
  private mapResponse(res: any): EligibilityResult {
    const rules: any[] = res.rules || [];
    const totalRules = rules.length;
    const satisfiedRules = rules.filter((r: any) => r.satisfied).length;

    const status: EligibilityStatus =
      res.status ??
      (res.missing_information?.length
        ? 'more_information_required'
        : 'not_eligible');
    const isEligible = status === 'eligible';

    // A percentage is only meaningful when rules were actually evaluated.
    // The backend returns no rules when the profile is missing, and a
    // "not eligible / more info required" verdict with zero evaluated rules
    // must never be reported as a perfect 100% match.
    const matchPct =
      totalRules > 0
        ? Math.round((satisfiedRules / totalRules) * 100)
        : isEligible
          ? 100
          : 0;

    return {
      scheme_id: String(res.scheme_id),
      scheme_title: res.scheme_title || '',
      category: '',
      is_eligible: isEligible,
      status,
      match_percentage: matchPct,
      criteria_results: rules.map(mapRule),
      missing_information: res.missing_information || [],
      benefits_summary: res.summary || null,
      application_process: null,
      document_url: null,
    };
  }
}
