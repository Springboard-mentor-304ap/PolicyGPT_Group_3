/**
 * Feedback models — mapped to `backend/app/feedback/schemas.py`.
 *
 *   POST  /api/feedback       -> Feedback (201)
 *   GET   /api/feedback       -> Feedback[]          (administrators)
 *   GET   /api/feedback/my    -> Feedback[]          (current user)
 *   GET   /api/feedback/{id}  -> Feedback            (owner or admin)
 *   PATCH /api/feedback/{id}  -> Feedback            (administrators)
 */

export type FeedbackType = 'feedback' | 'issue' | 'query';

export type FeedbackStatus = 'open' | 'in_progress' | 'resolved';

export interface Feedback {
  id: string;
  user_id: string;
  type: FeedbackType;
  subject: string;
  message: string;
  status: FeedbackStatus;
  resolved_by: string | null;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackCreate {
  type: FeedbackType;
  subject: string;
  message: string;
}

export interface FeedbackUpdate {
  status?: FeedbackStatus;
  resolution_note?: string | null;
}
