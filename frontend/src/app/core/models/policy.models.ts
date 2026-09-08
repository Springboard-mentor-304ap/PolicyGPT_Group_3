export type PolicyCategory =
  | 'education'
  | 'healthcare'
  | 'agriculture'
  | 'employment'
  | 'finance'
  | 'women_child_welfare'
  | 'housing'
  | 'environment'
  | 'digital_governance'
  | 'infrastructure';

export type PolicyStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'archived';

export interface Policy {
  id: string;
  title: string;
  description: string;
  category: PolicyCategory;
  department: string;
  ministry?: string | null;
  state?: string | null;
  status: PolicyStatus;
  document_url?: string | null;
  published_date?: string | null;
  view_count: number;
  created_at: string;
  updated_at: string;
}

export type SchemeCategory =
  | 'scholarships'
  | 'farmer_welfare'
  | 'healthcare'
  | 'housing'
  | 'business_support'
  | 'women_empowerment'
  | 'senior_citizen_welfare'
  | 'student_schemes'
  | 'employment_programs'
  | 'social_security';

export type SchemeStatus = 'draft' | 'active' | 'archived';

export interface Scheme {
  id: string;
  policy_id: string;
  title: string;
  description: string;
  category: SchemeCategory;
  benefits?: string | null;
  application_process?: string | null;
  department?: string | null;
  state?: string | null;
  status: SchemeStatus;
  launch_date?: string | null;
  deadline_date?: string | null;
  document_url?: string | null;
  view_count: number;
  created_at: string;
  updated_at: string;
}
