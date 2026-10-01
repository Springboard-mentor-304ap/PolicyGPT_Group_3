/**
 * FAQ models — mapped to `backend/app/faq/schemas.py`.
 *
 *   POST   /api/faqs        -> Faq (201)   (administrators)
 *   GET    /api/faqs        -> Faq[]       (authenticated; ?search=&category=&include_inactive=)
 *   GET    /api/faqs/{id}   -> Faq
 *   PATCH  /api/faqs/{id}   -> Faq         (administrators)
 *   DELETE /api/faqs/{id}   -> Faq         (administrators — deactivates)
 */

export interface Faq {
  id: string;
  question: string;
  answer: string;
  category: string | null;
  is_active: boolean;
  created_by: string;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface FaqCreate {
  question: string;
  answer: string;
  category?: string | null;
}

export interface FaqUpdate {
  question?: string;
  answer?: string;
  category?: string | null;
  is_active?: boolean;
}
