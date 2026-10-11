import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, tap, throwError } from 'rxjs';
import {
  ChangePasswordRequest,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  LoginRequest,
  MessageResponse,
  RegisterRequest,
  ResetPasswordRequest,
  TokenResponse,
  User,
  UserResponse,
  VerifyEmailRequest,
  ResendVerificationRequest,
  CitizenProfileRequest,
  CitizenProfileResponse,
  GovernmentOfficialProfileResponse,
  RoleRequestSubmit,
  RoleRequestResponse,
} from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  // Storage keys
  private readonly ACCESS_TOKEN_KEY = 'policygpt_access_token';
  private readonly REFRESH_TOKEN_KEY = 'policygpt_refresh_token';

  // Angular Signals for reactive authentication state
  readonly currentUser = signal<User | null>(null);
  readonly isAuthenticated = computed(() => !!this.currentUser());
  readonly userRole = computed(() => this.currentUser()?.role ?? null);
  readonly emailVerified = computed(() => this.currentUser()?.email_verified ?? false);

  constructor() {
    this.initSession();
  }

  // ─── SESSION INIT ────────────────────────────────────────────────────────
  private initSession(): void {
    const accessToken = this.getAccessToken();
    const refreshToken = this.getRefreshToken();
    if (!accessToken || !refreshToken) {
      return;
    }

    // The error interceptor handles 401 → refresh → retry.
    // We swallow errors here so a transient failure doesn't log the user out.
    this.getMe().subscribe({
      error: () => {},
    });
  }

  // ─── REGISTER ────────────────────────────────────────────────────────────
  register(data: RegisterRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/api/auth/register', data).pipe(
      tap((response) => this.saveTokens(response))
    );
  }

  // ─── LOGIN ───────────────────────────────────────────────────────────────
  login(data: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/api/auth/login', data).pipe(
      tap((response) => this.saveTokens(response))
    );
  }

  // ─── EMAIL VERIFICATION ──────────────────────────────────────────────────
  verifyEmail(data: VerifyEmailRequest): Observable<MessageResponse> {
    return this.http.post<MessageResponse>('/api/auth/verify-email', data);
  }

  resendVerification(data: ResendVerificationRequest): Observable<any> {
    return this.http.post<any>('/api/auth/resend-verification', data);
  }

  // ─── FORGOT PASSWORD ────────────────────────────────────────────────────
  forgotPassword(data: ForgotPasswordRequest): Observable<ForgotPasswordResponse> {
    return this.http.post<ForgotPasswordResponse>('/api/auth/forget-password', data);
  }

  // ─── RESET PASSWORD ─────────────────────────────────────────────────────
  resetPassword(data: ResetPasswordRequest): Observable<MessageResponse> {
    return this.http.post<MessageResponse>('/api/auth/reset-password', data);
  }

  // ─── CHANGE PASSWORD ────────────────────────────────────────────────────
  changePassword(data: ChangePasswordRequest): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      '/api/auth/change-password', data,
      { headers: this.getAuthHeaders() }
    );
  }

  // ─── GET ME ──────────────────────────────────────────────────────────────
  getMe(): Observable<UserResponse> {
    return this.http.get<UserResponse>('/api/auth/me', {
      headers: this.getAuthHeaders()
    }).pipe(
      tap((user) => this.currentUser.set(user))
    );
  }

  // ─── CITIZEN PROFILE ────────────────────────────────────────────────────
  getCitizenProfile(): Observable<CitizenProfileResponse> {
    return this.http.get<CitizenProfileResponse>('/api/profile/citizen', {
      headers: this.getAuthHeaders()
    });
  }

  updateCitizenProfile(data: CitizenProfileRequest): Observable<CitizenProfileResponse> {
    return this.http.put<CitizenProfileResponse>('/api/profile/citizen', data, {
      headers: this.getAuthHeaders()
    });
  }

  // ─── GOVERNMENT OFFICIAL PROFILE ────────────────────────────────────────
  /** Read-only official profile (GET /api/profile/government-official). */
  getGovernmentOfficialProfile(): Observable<GovernmentOfficialProfileResponse> {
    return this.http.get<GovernmentOfficialProfileResponse>(
      '/api/profile/government-official',
      { headers: this.getAuthHeaders() }
    );
  }

  // ─── ROLE REQUESTS ──────────────────────────────────────────────────────
  submitRoleRequest(data: RoleRequestSubmit): Observable<RoleRequestResponse> {
    return this.http.post<RoleRequestResponse>('/api/role-requests', data, {
      headers: this.getAuthHeaders()
    });
  }

  getMyRoleRequests(): Observable<RoleRequestResponse[]> {
    return this.http.get<RoleRequestResponse[]>('/api/role-requests', {
      headers: this.getAuthHeaders()
    });
  }

  cancelRoleRequest(requestId: string): Observable<MessageResponse> {
    return this.http.put<MessageResponse>(
      `/api/role-requests/${requestId}/cancel`, {},
      { headers: this.getAuthHeaders() }
    );
  }

  getPendingRoleRequests(): Observable<RoleRequestResponse[]> {
    return this.http.get<RoleRequestResponse[]>('/api/role-requests/pending', {
      headers: this.getAuthHeaders()
    });
  }

  approveRoleRequest(requestId: string): Observable<MessageResponse> {
    return this.http.put<MessageResponse>(
      `/api/role-requests/${requestId}/approve`, {},
      { headers: this.getAuthHeaders() }
    );
  }

  rejectRoleRequest(requestId: string, reason?: string): Observable<MessageResponse> {
    return this.http.put<MessageResponse>(
      `/api/role-requests/${requestId}/reject`,
      { review_reason: reason || null },
      { headers: this.getAuthHeaders() }
    );
  }

  // ─── REFRESH TOKEN ──────────────────────────────────────────────────────
  refreshToken(): Observable<TokenResponse> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      this.clearTokens();
      this.currentUser.set(null);
      return throwError(() => new Error('No refresh token available'));
    }
    // The token travels in the request BODY (query strings leak into logs)
    // and is rotated: the response's refresh_token replaces the one we sent,
    // and reusing the old one would revoke the whole chain. Concurrent
    // callers coalesce into one call through the error interceptor.
    return this.http
      .post<TokenResponse>('/api/auth/refresh', { refresh_token: refreshToken })
      .pipe(
        tap((response) => this.saveTokens(response)),
        catchError((error) => {
          // A rejected refresh ends the session: drop the tokens and the
          // in-memory user so the guards send the caller to login.
          this.clearTokens();
          this.currentUser.set(null);
          return throwError(() => error);
        })
      );
  }

  // ─── LOGOUT ──────────────────────────────────────────────────────────────
  logout(): void {
    this.clearTokens();
    this.currentUser.set(null);
  }

  // ─── TOKEN STORAGE ──────────────────────────────────────────────────────
  saveTokens(tokens: TokenResponse): void {
    if (tokens.access_token) {
      localStorage.setItem(this.ACCESS_TOKEN_KEY, tokens.access_token);
    }
    if (tokens.refresh_token) {
      localStorage.setItem(this.REFRESH_TOKEN_KEY, tokens.refresh_token);
    }
  }

  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_TOKEN_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  clearTokens(): void {
    localStorage.removeItem(this.ACCESS_TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
  }

  getAuthHeaders(): HttpHeaders {
    const token = this.getAccessToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }
}
