/**
 * Policy Models
 * Strictly mapped to FastAPI backend schemas
 */

export enum PolicyCategory {
  EDUCATION = 'education',
  HEALTHCARE = 'healthcare',
  AGRICULTURE = 'agriculture',
  EMPLOYMENT = 'employment',
  FINANCE = 'finance',
  WOMEN_CHILD_WELFARE = 'women_child_welfare',
  HOUSING = 'housing',
  ENVIRONMENT = 'environment',
  DIGITAL_GOVERNANCE = 'digital_governance',
  INFRASTRUCTURE = 'infrastructure',
}

export enum PolicyStatus {
  DRAFT = 'draft',
  PENDING_APPROVAL = 'pending_approval',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  ARCHIVED = 'archived',
}

export interface Policy {
  id: string;
  title: string;
  description: string;
  required_documents: string[] | null;
  category: PolicyCategory;
  department: string;
  ministry: string | null;
  state: string | null;
  status: PolicyStatus;
  document_url: string | null;
  published_date: string | null;
  uploaded_by: string;
  approved_by: string | null;
  rejection_reason: string | null;
  view_count: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface PolicyCreateRequest {
  title: string;
  description: string;
  required_documents?: string[] | null;
  category: PolicyCategory;
  department: string;
  ministry?: string | null;
  state?: string | null;
  document_url?: string | null;
  published_date?: string | null;
}

export interface PolicyUpdateRequest {
  title?: string;
  description?: string;
  required_documents?: string[] | null;
  category?: PolicyCategory;
  department?: string;
  ministry?: string | null;
  state?: string | null;
  document_url?: string | null;
  published_date?: string | null;
}

export interface PolicyRejectRequest {
  rejection_reason: string;
}

/** Display-friendly category labels */
export const POLICY_CATEGORY_LABELS: Record<PolicyCategory, string> = {
  [PolicyCategory.EDUCATION]: 'Education',
  [PolicyCategory.HEALTHCARE]: 'Healthcare',
  [PolicyCategory.AGRICULTURE]: 'Agriculture',
  [PolicyCategory.EMPLOYMENT]: 'Employment',
  [PolicyCategory.FINANCE]: 'Finance',
  [PolicyCategory.WOMEN_CHILD_WELFARE]: 'Women & Child Welfare',
  [PolicyCategory.HOUSING]: 'Housing',
  [PolicyCategory.ENVIRONMENT]: 'Environment',
  [PolicyCategory.DIGITAL_GOVERNANCE]: 'Digital Governance',
  [PolicyCategory.INFRASTRUCTURE]: 'Infrastructure',
};

/** Display-friendly status labels */
export const POLICY_STATUS_LABELS: Record<PolicyStatus, string> = {
  [PolicyStatus.DRAFT]: 'Draft',
  [PolicyStatus.PENDING_APPROVAL]: 'Pending Approval',
  [PolicyStatus.APPROVED]: 'Approved',
  [PolicyStatus.REJECTED]: 'Rejected',
  [PolicyStatus.ARCHIVED]: 'Archived',
};

/** Badge variant for each status */
export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary';

export const POLICY_STATUS_BADGE: Record<PolicyStatus, BadgeVariant> = {
  [PolicyStatus.DRAFT]: 'neutral',
  [PolicyStatus.PENDING_APPROVAL]: 'warning',
  [PolicyStatus.APPROVED]: 'success',
  [PolicyStatus.REJECTED]: 'danger',
  [PolicyStatus.ARCHIVED]: 'info',
};
