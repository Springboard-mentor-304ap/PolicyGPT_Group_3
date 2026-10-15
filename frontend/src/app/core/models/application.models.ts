/**
 * Application models — mapped to `backend/app/applications/schemas.py`.
 *
 *   POST  /api/applications            -> Application
 *   GET   /api/applications            -> Application[]
 *   GET   /api/applications/{id}       -> Application
 *   PATCH /api/applications/{id}/status -> Application
 */

export type ApplicationStatus =
  | 'submitted'
  | 'under_review'
  | 'additional_information_required'
  | 'approved'
  | 'rejected';

/**
 * Advisory eligibility verdict recorded server-side at submission time.
 * NULL means it could not be computed. Never blocks an application.
 */
export type EligibilityVerdict =
  | 'eligible'
  | 'not_eligible'
  | 'more_information_required';

export interface Application {
  id: string;
  user_id: string;
  scheme_id: string;
  status: ApplicationStatus;
  remarks: string | null;
  approved_by: string | null;
  rejection_reason: string | null;
  eligibility_verdict: EligibilityVerdict | null;
  submitted_at: string;
  updated_at: string;
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  remarks?: string | null;
}

/**
 * Staff review row — GET /api/applications/review.
 * Extends the existing Application with applicant/scheme context joined by
 * the backend (backend/app/applications/schemas.py ApplicationReviewResponse).
 */
export interface ApplicationReviewItem extends Application {
  applicant_name: string | null;
  scheme_title: string;
  scheme_department: string | null;
  policy_ministry: string | null;
}
