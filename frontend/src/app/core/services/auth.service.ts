import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
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
  UpdateRoleRequest,
  User,
  UserResponse
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

    // The error interceptor already handles 401 → refresh → retry for ALL
    // requests, so we just call getMe() and let it do its job.
    this.getMe().subscribe();
  }

  // ─── REGISTER ────────────────────────────────────────────────────────────
  /**
   * Registers a new citizen user.
   * Backend endpoint: POST /auth/register
   */
  register(data: RegisterRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/auth/register', data).pipe(
      tap((response) => this.saveTokens(response))
    );
  }

  // ─── LOGIN ───────────────────────────────────────────────────────────────
  /**
   * Authenticates user with email and password.
   * Backend endpoint: POST /auth/login
   */
  login(data: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>('/auth/login', data).pipe(
      tap((response) => this.saveTokens(response))
    );
  }

  // ─── UPDATE ROLE ─────────────────────────────────────────────────────────
  /**
   * Updates the current user's role.
   * Backend endpoint: PUT /auth/update-role
   */
  updateRole(data: UpdateRoleRequest): Observable<MessageResponse & { role: string }> {
    return this.http.put<MessageResponse & { role: string }>(
      '/auth/update-role', data,
      { headers: this.getAuthHeaders() }
    );
  }

  // ─── FORGOT PASSWORD ────────────────────────────────────────────────────
  /**
   * Requests password reset token for given email.
   * Backend endpoint: POST /auth/forget-password
   */
  forgotPassword(data: ForgotPasswordRequest): Observable<ForgotPasswordResponse> {
    return this.http.post<ForgotPasswordResponse>('/auth/forget-password', data);
  }

  // ─── RESET PASSWORD ─────────────────────────────────────────────────────
  /**
   * Resets password using reset token.
   * Backend endpoint: POST /auth/reset-password
   */
  resetPassword(data: ResetPasswordRequest): Observable<MessageResponse> {
    return this.http.post<MessageResponse>('/auth/reset-password', data);
  }

  // ─── CHANGE PASSWORD ────────────────────────────────────────────────────
  /**
   * Changes password for authenticated user.
   * Backend endpoint: POST /auth/change-password
   */
  changePassword(data: ChangePasswordRequest): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(
      '/auth/change-password', data,
      { headers: this.getAuthHeaders() }
    );
  }

  // ─── GET ME ──────────────────────────────────────────────────────────────
  /**
   * Retrieves profile of current authenticated user.
   * Backend endpoint: GET /auth/me
   */
  getMe(): Observable<UserResponse> {
    return this.http.get<UserResponse>('/auth/me', {
      headers: this.getAuthHeaders()
    }).pipe(
      tap((user) => this.currentUser.set(user))
    );
  }

  // ─── REFRESH TOKEN ──────────────────────────────────────────────────────
  /**
   * Refreshes access token using refresh token.
   * Backend endpoint: POST /auth/refresh?refresh_token=...
   */
  refreshToken(): Observable<TokenResponse> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      this.clearTokens();
      return throwError(() => new Error('No refresh token available'));
    }
    const params = new HttpParams().set('refresh_token', refreshToken);
    return this.http.post<TokenResponse>('/auth/refresh', null, { params }).pipe(
      tap((response) => this.saveTokens(response)),
      catchError((error) => {
        this.clearTokens();
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

  private getAuthHeaders(): HttpHeaders {
    const token = this.getAccessToken();
    return token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : new HttpHeaders();
  }
}
