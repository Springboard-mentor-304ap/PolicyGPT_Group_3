/**
 * AI Helpdesk models — these mirror the backend Helpdesk API exactly:
 *   POST /api/helpdesk/chat -> HelpdeskChatResponse
 *
 * The backend generates the answer from the PolicyGPT knowledge base and is
 * the only source of policy/scheme content. The frontend never composes
 * answers itself.
 */

/** Source kinds the helpdesk knowledge base can return. */
export type HelpdeskSourceType = 'policy' | 'scheme';

/** Body of POST /api/helpdesk/chat. `question` is 1–2000 characters. */
export interface HelpdeskChatRequest {
  question: string;
}

/**
 * One knowledge-base chunk that was used to answer the question.
 * `id` is the id of the retrieved chunk (not a policy/scheme id), so it is
 * only ever used as a list key and never shown to the user.
 */
export interface HelpdeskSource {
  id: string;
  source_type: HelpdeskSourceType | string;
  title: string;
  similarity: number;
}

/** Response of POST /api/helpdesk/chat. */
export interface HelpdeskChatResponse {
  answer: string;
  sources: HelpdeskSource[];
}
