import { Injectable, computed, signal } from '@angular/core';
import { Observable, of, tap, delay } from 'rxjs';
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

// ─── MOCK DATA ────────────────────────────────────────────────────────────────
// Used for frontend-only development. Remove when reconnecting to the backend.
const MOCK_USER: UserResponse = {
  id: 'mock-user-id-001',
  full_name: 'Demo User',
  email: 'demo@policygpt.com',
  phone: null,
  role: 'citizen',
  is_active: true,
};

const MOCK_TOKENS: TokenResponse = {
  access_token: 'mock-access-token',
  refresh_token: 'mock-refresh-token',
  token_type: 'bearer',
};
// ──────────────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class AuthService {
  // ╔══════════════════════════════════════════════════════════════════════════╗
  // ║  HOW TO RECONNECT TO THE BACKEND                                       ║
  // ║                                                                        ║
  // ║  1. Uncomment the HttpClient import and inject below                   ║
  // ║  2. Restore the original HTTP-based method bodies (see each method)    ║
  // ║  3. Uncomment the interceptors in app.config.ts                        ║
  // ║  4. Ensure the backend is running and proxy.conf.json routes to it     ║
  // ╚══════════════════════════════════════════════════════════════════════════╝

  // import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
  // import { catchError } from 'rxjs';
  // private readonly http = inject(HttpClient);

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
    const token = this.getAccessToken();
    if (token) {
      // ┌──────────────────────────────────────────────────────────────────┐
      // │ RECONNECT: Restore the getMe() call to validate stored tokens   │
      // │  this.getMe().subscribe({                                        │
      // │    error: () => this.clearTokens()                               │
      // │  });                                                             │
      // └──────────────────────────────────────────────────────────────────┘

      // MOCK: Simulate a logged-in user from stored token
      this.currentUser.set({ ...MOCK_USER, role: MOCK_USER.role as User['role'] });
    }
  }

  // ─── REGISTER ────────────────────────────────────────────────────────────
  /**
   * Registers a new citizen user.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.post<TokenResponse>('/auth/register', data).pipe( │
   * │    tap((response) => this.saveTokens(response))                     │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/register
   */
  register(data: RegisterRequest): Observable<TokenResponse> {
    const mockResponse = { ...MOCK_TOKENS };
    return of(mockResponse).pipe(
      delay(500),
      tap((response) => {
        this.saveTokens(response);
        this.currentUser.set({ ...MOCK_USER, full_name: data.full_name, email: data.email });
      })
    );
  }

  // ─── LOGIN ───────────────────────────────────────────────────────────────
  /**
   * Authenticates user with email and password.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.post<TokenResponse>('/auth/login', data).pipe(    │
   * │    tap((response) => this.saveTokens(response))                     │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/login
   */
  login(data: LoginRequest): Observable<TokenResponse> {
    const mockResponse = { ...MOCK_TOKENS };
    return of(mockResponse).pipe(
      delay(500),
      tap((response) => {
        this.saveTokens(response);
        this.currentUser.set({ ...MOCK_USER, email: data.email });
      })
    );
  }

  // ─── UPDATE ROLE ─────────────────────────────────────────────────────────
  /**
   * Updates the current user's role.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.put<MessageResponse & { role: string }>(          │
   * │    '/auth/update-role', data,                                        │
   * │    { headers: this.getAuthHeaders() }                               │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: PUT /auth/update-role
   */
  updateRole(data: UpdateRoleRequest): Observable<MessageResponse & { role: string }> {
    const mockResponse = { message: 'Role updated successfully', role: data.role };
    return of(mockResponse).pipe(
      delay(500),
      tap(() => {
        const user = this.currentUser();
        if (user) {
          this.currentUser.set({ ...user, role: data.role as User['role'] });
        }
      })
    );
  }

  // ─── FORGOT PASSWORD ────────────────────────────────────────────────────
  /**
   * Requests password reset token for given email.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.post<ForgotPasswordResponse>(                     │
   * │    '/auth/forget-password', data                                     │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/forget-password
   */
  forgotPassword(data: ForgotPasswordRequest): Observable<ForgotPasswordResponse> {
    return of({ message: 'Password reset token generated', reset_token: 'mock-reset-token' }).pipe(delay(500));
  }

  // ─── RESET PASSWORD ─────────────────────────────────────────────────────
  /**
   * Resets password using reset token.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.post<MessageResponse>(                            │
   * │    '/auth/reset-password', data                                      │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/reset-password
   */
  resetPassword(data: ResetPasswordRequest): Observable<MessageResponse> {
    return of({ message: 'Password Reset Successfully' }).pipe(delay(500));
  }

  // ─── CHANGE PASSWORD ────────────────────────────────────────────────────
  /**
   * Changes password for authenticated user.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.post<MessageResponse>(                            │
   * │    '/auth/change-password', data,                                    │
   * │    { headers: this.getAuthHeaders() }                               │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/change-password
   */
  changePassword(data: ChangePasswordRequest): Observable<MessageResponse> {
    return of({ message: 'Password changed successfully' }).pipe(delay(500));
  }

  // ─── GET ME ──────────────────────────────────────────────────────────────
  /**
   * Retrieves profile of current authenticated user.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  return this.http.get<UserResponse>('/auth/me', {                   │
   * │    headers: this.getAuthHeaders()                                   │
   * │  }).pipe(                                                           │
   * │    tap((user) => this.currentUser.set(user))                        │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: GET /auth/me
   */
  getMe(): Observable<UserResponse> {
    const user = this.currentUser() ?? MOCK_USER;
    return of({ ...user }).pipe(
      delay(300),
      tap((u) => this.currentUser.set(u))
    );
  }

  // ─── REFRESH TOKEN ──────────────────────────────────────────────────────
  /**
   * Refreshes access token using refresh token.
   *
   * ┌──────────────────────────────────────────────────────────────────────┐
   * │ RECONNECT: Replace the method body with:                            │
   * │  const refreshToken = this.getRefreshToken();                       │
   * │  if (!refreshToken) {                                               │
   * │    this.clearTokens();                                              │
   * │    return throwError(() => new Error('No refresh token available')); │
   * │  }                                                                  │
   * │  const params = new HttpParams().set('refresh_token', refreshToken);│
   * │  return this.http.post<TokenResponse>(                              │
   * │    '/auth/refresh', null, { params }                                │
   * │  ).pipe(                                                            │
   * │    tap((response) => this.saveTokens(response)),                    │
   * │    catchError((error) => {                                          │
   * │      this.clearTokens();                                            │
   * │      return throwError(() => error);                                │
   * │    })                                                               │
   * │  );                                                                 │
   * └──────────────────────────────────────────────────────────────────────┘
   *
   * Backend endpoint: POST /auth/refresh?refresh_token=...
   */
  refreshToken(): Observable<TokenResponse> {
    return of({ ...MOCK_TOKENS }).pipe(
      delay(300),
      tap((response) => this.saveTokens(response))
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

  // ┌──────────────────────────────────────────────────────────────────────────┐
  // │ RECONNECT: Uncomment the getAuthHeaders() method below when restoring   │
  // │ the HttpClient. It is used by updateRole, changePassword, getMe, and    │
  // │ the interceptors.                                                       │
  // │                                                                         │
  // │  private getAuthHeaders(): HttpHeaders {                                │
  // │    const token = this.getAccessToken();                                 │
  // │    return token                                                         │
  // │      ? new HttpHeaders({ Authorization: `Bearer ${token}` })            │
  // │      : new HttpHeaders();                                               │
  // │  }                                                                      │
  // └──────────────────────────────────────────────────────────────────────────┘
}
