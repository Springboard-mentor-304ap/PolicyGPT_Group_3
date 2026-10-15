import { UserRole } from './auth.models';

/**
 * Admin view of a user account (GET /api/admin/users).
 *
 * Mirrors the backend `AdminUserResponse` allow-list: `password_hash` and
 * token columns exist on the model but are never serialised.
 */
export interface AdminUser {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: UserRole | string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

/** One entry from GET /api/audit-logs (mirrors `AuditLogResponse`). */
export interface AuditLogEntry {
  id: string;
  actor_id: string;
  action: string;
  target_table: string;
  target_id: string;
  changes?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at: string;
}

/** Query parameters accepted by GET /api/admin/users. */
export interface AdminUserListParams {
  role?: UserRole | string;
  is_active?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

/** Query parameters accepted by GET /api/audit-logs. */
export interface AuditLogListParams {
  actor_id?: string;
  action?: string;
  target_table?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}
