export interface Feedback {
  id: string;
  type: string;
  subject: string;
  description: string;
  status: string;
  createdAt: string;
}

export interface CreateFeedbackRequest {
  type: string;
  subject: string;
  description: string;
}