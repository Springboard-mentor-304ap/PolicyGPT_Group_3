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

export interface Application {
  id: string;
  user_id: string;
  scheme_id: string;
  status: ApplicationStatus;
  remarks: string | null;
  approved_by: string | null;
  rejection_reason: string | null;
  submitted_at: string;
  updated_at: string;
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  remarks?: string | null;
}
