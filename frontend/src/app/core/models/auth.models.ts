/**
 * Authentication and User Models
 * Strictly mapped to FastAPI backend schemas
 */

export enum UserRole {
  CITIZEN = 'citizen',
  RESEARCHER = 'researcher',
  ORGANIZATION = 'organization',
  GOVERNMENT_OFFICIAL = 'government_official',
  ADMINISTRATOR = 'administrator',
  SUPER_ADMIN = 'super_admin'
}

export enum RequestedRole {
  RESEARCHER = 'researcher',
  ORGANIZATION = 'organization',
  GOVERNMENT_OFFICIAL = 'government_official',
  ADMINISTRATOR = 'administrator'
}

export enum RequestStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  CANCELLED = 'cancelled'
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: UserRole | string;
  is_active: boolean;
  email_verified: boolean;
}

export interface UserResponse {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: string;
  is_active: boolean;
  email_verified: boolean;
}

export interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
  reset_token: string;
}

export interface ResetPasswordRequest {
  reset_token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface MessageResponse {
  message: string;
}

// ─── Email Verification ─────────────────────────────────────────────────────

export interface VerifyEmailRequest {
  token: string;
}

export interface ResendVerificationRequest {
  email: string;
}

// ─── Citizen Profile ────────────────────────────────────────────────────────

export interface CitizenProfileRequest {
  phone?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  occupation?: string | null;
  annual_income?: number | null;
  social_category?: string | null;
  disability_status?: boolean;
  education?: string | null;
  state?: string | null;
  district?: string | null;
}

export interface CitizenProfileResponse {
  user_id: string;
  phone?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  occupation?: string | null;
  annual_income?: number | null;
  social_category?: string | null;
  disability_status?: boolean;
  education?: string | null;
  state?: string | null;
  district?: string | null;
}

// ─── Role Requests ──────────────────────────────────────────────────────────

export interface RoleRequestSubmit {
  requested_role: string;
  details: Record<string, any>;
}

export interface RoleRequestResponse {
  id: string;
  user_id: string;
  requested_role: string;
  status: string;
  details?: Record<string, any> | null;
  review_reason?: string | null;
  reviewer_id?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface RoleRequestReview {
  review_reason?: string | null;
}
