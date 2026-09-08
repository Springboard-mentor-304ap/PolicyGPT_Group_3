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

export interface EligibilityResult {
  scheme_id: string;
  scheme_title: string;
  category: string;
  is_eligible: boolean;
  match_percentage: number;
  criteria_results: CriterionResult[];
  benefits_summary?: string | null;
  application_process?: string | null;
  document_url?: string | null;
  deadline_date?: string | null;
}
