export type Gender = 'male' | 'female' | 'other';
export type SocialCategory = 'general' | 'obc' | 'sc' | 'st' | 'other';
export type MaritalStatus = 'single' | 'married' | 'other';

export type EligibilityParameter =
  | 'age'
  | 'gender'
  | 'income'
  | 'occupation'
  | 'education'
  | 'location'
  | 'social_category'
  | 'disability_status';

export type EligibilityOperator =
  | 'eq'
  | 'neq'
  | 'lt'
  | 'lte'
  | 'gt'
  | 'gte'
  | 'in'
  | 'not_in';

export interface EligibilityRuleItem {
  id: string;
  scheme_id: string;
  parameter: EligibilityParameter;
  operator: EligibilityOperator;
  value: string;
}

export interface EligibilityCheckRequest {
  scheme_id?: string; // Optional: if checking against specific scheme
  age: number;
  gender: Gender | string;
  annual_income: number;
  occupation: string;
  education: string;
  social_category: SocialCategory | string;
  state: string;
  district?: string;
  disability_status: boolean;
  marital_status?: MaritalStatus | string;
}

export interface CriterionResult {
  parameter: EligibilityParameter | string;
  label: string;
  passed: boolean;
  ruleDescription: string;
  userValue: string;
  failureReason?: string;
}

/**
 * Backend verdict for a scheme check (`EligibilityCheckResponse.status`).
 * `more_information_required` means eligibility could NOT be established
 * because profile data is missing — it is not a failed match.
 */
export type EligibilityStatus =
  | 'eligible'
  | 'not_eligible'
  | 'more_information_required';

export interface EligibilityResult {
  scheme_id: string;
  scheme_title: string;
  category: string;
  is_eligible: boolean;
  status: EligibilityStatus;
  match_percentage: number;
  /** Profile parameters the check could not evaluate (missing data). */
  missing_information?: string[];
  criteria_results: CriterionResult[];
  benefits_summary?: string | null;
  application_process?: string | null;
  document_url?: string | null;
  deadline_date?: string | null;
}
