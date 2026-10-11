/**
 * Natural-Language Scheme Finder models.
 *
 * These mirror the backend Finder API exactly:
 *   POST /api/finder/extract -> FinderProfile
 *   POST /api/finder/match   -> SchemeMatchResponse
 *
 * The backend is the only place eligibility is decided. The frontend sends a
 * profile and renders whatever the API returns — it never compares profile
 * values against rule values itself.
 */

/**
 * The profile fields accepted by both Finder endpoints.
 * `null` means "not provided" and is always preserved as such.
 */
export interface FinderProfile {
  age: number | null;
  gender: string | null;
  annual_income: number | null;
  occupation: string | null;
  education: string | null;
  state: string | null;
  district: string | null;
  social_category: string | null;
  disability_status: boolean | null;
}

/** Body of POST /api/finder/extract. */
export interface ProfileExtractionRequest {
  text: string;
}

/** Body of POST /api/finder/match. */
export interface SchemeMatchRequest {
  profile: FinderProfile;
}

/** One evaluated eligibility rule, returned by the backend rule engine. */
export interface FinderRuleResult {
  parameter: string;
  operator: string;
  required_value: string;
  actual_value: string | null;
  satisfied: boolean;
  message: string;
}

export type FinderMatchStatus =
  | 'eligible'
  | 'more_information_required'
  | 'not_eligible'
  | 'no_criteria_defined';

/** A single scheme in one of the four result groups. */
export interface SchemeMatch {
  scheme_id: string;
  scheme_title: string;
  status: FinderMatchStatus | string;
  summary: string;
  rules: FinderRuleResult[];
  missing_information: string[];
}

/** Response of POST /api/finder/match, grouped by backend verdict. */
export interface SchemeMatchResponse {
  eligible: SchemeMatch[];
  more_information_required: SchemeMatch[];
  not_eligible: SchemeMatch[];
  no_criteria_defined: SchemeMatch[];
}

/** Keys of the four result groups, in the order the page renders them. */
export type FinderResultGroup = keyof SchemeMatchResponse;
