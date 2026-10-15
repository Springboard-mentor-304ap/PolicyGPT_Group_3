/**
 * Scheme Models
 * Strictly mapped to FastAPI backend schemas
 */

export enum SchemeCategory {
  SCHOLARSHIPS = 'scholarships',
  FARMER_WELFARE = 'farmer_welfare',
  HEALTHCARE = 'healthcare',
  HOUSING = 'housing',
  BUSINESS_SUPPORT = 'business_support',
  WOMEN_EMPOWERMENT = 'women_empowerment',
  SENIOR_CITIZEN_WELFARE = 'senior_citizen_welfare',
  STUDENT_SCHEMES = 'student_schemes',
  EMPLOYMENT_PROGRAMS = 'employment_programs',
  SOCIAL_SECURITY = 'social_security',
}

export enum SchemeStatus {
  DRAFT = 'draft',
  PENDING_APPROVAL = 'pending_approval',
  ACTIVE = 'active',
  REJECTED = 'rejected',
  ARCHIVED = 'archived',
}

export interface Scheme {
  id: string;
  policy_id: string;
  title: string;
  description: string;
  required_documents: string[] | null;
  category: SchemeCategory;
  benefits: string[] | null;
  application_process: string | null;
  department: string | null;
  state: string | null;
  status: SchemeStatus;
  launch_date: string | null;
  deadline_date: string | null;
  document_url: string | null;
  created_by: string;
  approved_by: string | null;
  rejection_reason: string | null;
  view_count: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface SchemeCreateRequest {
  policy_id: string;
  title: string;
  description: string;
  required_documents?: string[] | null;
  category: SchemeCategory;
  benefits?: string[] | null;
  application_process?: string | null;
  department?: string | null;
  state?: string | null;
  launch_date?: string | null;
  deadline_date?: string | null;
  document_url?: string | null;
}

export interface SchemeUpdateRequest {
  title?: string;
  description?: string;
  required_documents?: string[] | null;
  category?: SchemeCategory;
  benefits?: string[] | null;
  application_process?: string | null;
  department?: string | null;
  state?: string | null;
  launch_date?: string | null;
  deadline_date?: string | null;
  document_url?: string | null;
}

export interface SchemeRejectRequest {
  rejection_reason: string;
}

export enum EligibilityParameter {
  AGE = 'age',
  GENDER = 'gender',
  INCOME = 'income',
  OCCUPATION = 'occupation',
  EDUCATION = 'education',
  STATE = 'state',
  DISTRICT = 'district',
  SOCIAL_CATEGORY = 'social_category',
  DISABILITY_STATUS = 'disability_status',
}

export enum EligibilityOperator {
  EQ = 'eq',
  NEQ = 'neq',
  LT = 'lt',
  LTE = 'lte',
  GT = 'gt',
  GTE = 'gte',
  IN = 'in',
  NOT_IN = 'not_in',
}

export interface EligibilityRuleCreateRequest {
  parameter: EligibilityParameter;
  operator: EligibilityOperator;
  value: string;
}

export interface EligibilityRule extends EligibilityRuleCreateRequest {
  id: string;
  scheme_id: string;
  created_at: string;
  updated_at: string;
}

export const ELIGIBILITY_PARAMETER_LABELS: Record<EligibilityParameter, string> = {
  [EligibilityParameter.AGE]: 'Age',
  [EligibilityParameter.GENDER]: 'Gender',
  [EligibilityParameter.INCOME]: 'Annual income',
  [EligibilityParameter.OCCUPATION]: 'Occupation',
  [EligibilityParameter.EDUCATION]: 'Education',
  [EligibilityParameter.STATE]: 'State',
  [EligibilityParameter.DISTRICT]: 'District',
  [EligibilityParameter.SOCIAL_CATEGORY]: 'Social category',
  [EligibilityParameter.DISABILITY_STATUS]: 'Disability status',
};

export const ELIGIBILITY_OPERATOR_LABELS: Record<EligibilityOperator, string> = {
  [EligibilityOperator.EQ]: 'is',
  [EligibilityOperator.NEQ]: 'is not',
  [EligibilityOperator.LT]: 'is less than',
  [EligibilityOperator.LTE]: 'is at most',
  [EligibilityOperator.GT]: 'is greater than',
  [EligibilityOperator.GTE]: 'is at least',
  [EligibilityOperator.IN]: 'is one of',
  [EligibilityOperator.NOT_IN]: 'is not one of',
};

/** One selectable value of a categorical eligibility parameter. */
export interface EligibilityRuleOption {
  value: string;
  label: string;
}

/**
 * Operators offered for each parameter.
 *
 * Mirrors `PARAMETER_OPERATOR_COMPATIBILITY` in
 * backend/app/schemes/service.py exactly: the backend rejects anything else
 * with a 400 when the rule is saved, so offering an unsupported pair here
 * would only fail after the scheme has already been created. Numeric fields
 * get the numeric comparisons (the backend also accepts `in` as a list of
 * numbers, but the form keeps a single number input for them); categorical
 * fields additionally get the multi-value operators, which the backend
 * stores and evaluates as comma-separated lists.
 */
export const ELIGIBILITY_OPERATORS_BY_PARAMETER: Record<
  EligibilityParameter,
  EligibilityOperator[]
> = {
  [EligibilityParameter.AGE]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.LT,
    EligibilityOperator.LTE,
    EligibilityOperator.GT,
    EligibilityOperator.GTE,
  ],
  [EligibilityParameter.INCOME]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.LT,
    EligibilityOperator.LTE,
    EligibilityOperator.GT,
    EligibilityOperator.GTE,
  ],
  [EligibilityParameter.GENDER]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  [EligibilityParameter.OCCUPATION]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  [EligibilityParameter.EDUCATION]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  [EligibilityParameter.STATE]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  [EligibilityParameter.DISTRICT]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  [EligibilityParameter.SOCIAL_CATEGORY]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
    EligibilityOperator.IN,
    EligibilityOperator.NOT_IN,
  ],
  // The evaluator compares this against a Python bool, so only equality and
  // inequality are defined for it.
  [EligibilityParameter.DISABILITY_STATUS]: [
    EligibilityOperator.EQ,
    EligibilityOperator.NEQ,
  ],
};

/**
 * Canonical values for the parameters whose citizen profile value is a fixed
 * set (`UserProfile.gender` / `social_category` / `disability_status` and the
 * education levels both profile forms offer).
 *
 * They must stay identical to the values the citizen profile and finder forms
 * submit — the evaluator compares rule and profile values as plain
 * case-insensitive strings, so a value outside these lists could never match
 * a stored profile.
 */
export const ELIGIBILITY_RULE_OPTIONS: Partial<
  Record<EligibilityParameter, EligibilityRuleOption[]>
> = {
  [EligibilityParameter.GENDER]: [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' },
  ],
  [EligibilityParameter.EDUCATION]: [
    { value: 'below_primary', label: 'Below Primary' },
    { value: 'primary', label: 'Primary' },
    { value: 'secondary', label: 'Secondary' },
    { value: 'higher_secondary', label: 'Higher Secondary' },
    { value: 'graduate', label: 'Graduate' },
    { value: 'post_graduate', label: 'Post Graduate' },
    { value: 'doctorate', label: 'Doctorate' },
    { value: 'diploma', label: 'Diploma' },
    { value: 'professional', label: 'Professional Degree' },
  ],
  [EligibilityParameter.SOCIAL_CATEGORY]: [
    { value: 'general', label: 'General' },
    { value: 'obc', label: 'OBC' },
    { value: 'sc', label: 'SC' },
    { value: 'st', label: 'ST' },
    { value: 'other', label: 'Other' },
  ],
  [EligibilityParameter.DISABILITY_STATUS]: [
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ],
};

/** Display-friendly category labels */
export const SCHEME_CATEGORY_LABELS: Record<SchemeCategory, string> = {
  [SchemeCategory.SCHOLARSHIPS]: 'Scholarships',
  [SchemeCategory.FARMER_WELFARE]: 'Farmer Welfare',
  [SchemeCategory.HEALTHCARE]: 'Healthcare',
  [SchemeCategory.HOUSING]: 'Housing',
  [SchemeCategory.BUSINESS_SUPPORT]: 'Business Support',
  [SchemeCategory.WOMEN_EMPOWERMENT]: 'Women Empowerment',
  [SchemeCategory.SENIOR_CITIZEN_WELFARE]: 'Senior Citizen Welfare',
  [SchemeCategory.STUDENT_SCHEMES]: 'Student Schemes',
  [SchemeCategory.EMPLOYMENT_PROGRAMS]: 'Employment Programs',
  [SchemeCategory.SOCIAL_SECURITY]: 'Social Security',
};

/** Display-friendly status labels */
export const SCHEME_STATUS_LABELS: Record<SchemeStatus, string> = {
  [SchemeStatus.DRAFT]: 'Draft',
  [SchemeStatus.PENDING_APPROVAL]: 'Pending Approval',
  [SchemeStatus.ACTIVE]: 'Active',
  [SchemeStatus.REJECTED]: 'Rejected',
  [SchemeStatus.ARCHIVED]: 'Archived',
};

/** Badge variant for each status */
export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary';

export const SCHEME_STATUS_BADGE: Record<SchemeStatus, BadgeVariant> = {
  [SchemeStatus.DRAFT]: 'neutral',
  [SchemeStatus.PENDING_APPROVAL]: 'warning',
  [SchemeStatus.ACTIVE]: 'success',
  [SchemeStatus.REJECTED]: 'danger',
  [SchemeStatus.ARCHIVED]: 'info',
};
