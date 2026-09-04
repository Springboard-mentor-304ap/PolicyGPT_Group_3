/**
 * Authentication and User Models
 * Strictly mapped to FastAPI backend schemas in backend/app/auth/schemas.py and backend/app/models/user.py
 */

export enum UserRole {
  ADMIN = 'admin',
  GOVERNMENT_OFFICIAL = 'government_official',
  CITIZEN = 'citizen',
  RESEARCHER = 'researcher',
  ORGANIZATION = 'organization'
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: UserRole | string;
  is_active: boolean;
}

export interface UserResponse {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
  role: string;
  is_active: boolean;
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

export interface UpdateRoleRequest {
  role: string;
}

export interface MessageResponse {
  message: string;
}
