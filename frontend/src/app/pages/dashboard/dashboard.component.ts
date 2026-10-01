import { Component, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { AnalyticsService } from '../../core/services/analytics.service';
import { NotificationService } from '../../core/services/notification.service';
import {
  humanize,
  toBreakdownItems,
  toMetricSlices,
  toSchemeUsage,
  toTrendPoints,
} from '../../core/services/analytics.mappers';
import { RoleRequestResponse, UserRole } from '../../core/models/auth.models';
import { DashboardAnalytics } from '../../core/models/analytics.models';
import { NotificationItem } from '../../core/models/notification.models';
import { FloatingCompareDockComponent } from '../comparison/components/floating-compare-dock/floating-compare-dock.component';
import { DonutChartComponent } from '../../shared/components/donut-chart/donut-chart.component';
import { BarChartComponent } from '../../shared/components/bar-chart/bar-chart.component';
import { TrendChartComponent } from '../../shared/components/trend-chart/trend-chart.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';

export type DashboardLoadState = 'idle' | 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    FloatingCompareDockComponent,
    DonutChartComponent,
    BarChartComponent,
    TrendChartComponent,
    SkeletonComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  private readonly analyticsService = inject(AnalyticsService);
  private readonly notificationService = inject(NotificationService);
  private readonly router = inject(Router);

  private pollInterval: ReturnType<typeof setInterval> | null = null;
  private visibilityHandler: (() => void) | null = null;

  /** Role the analytics payload was last requested for (avoids duplicate fetches). */
  private loadedForRole: string | null = null;

  // ── Analytics state ──────────────────────────────────────────────────────
  readonly analytics = signal<DashboardAnalytics | null>(null);
  readonly loadState = signal<DashboardLoadState>('idle');
  readonly loadError = signal<string | null>(null);

  // ── Notifications ────────────────────────────────────────────────────────
  readonly notifications = signal<NotificationItem[]>([]);
  readonly unreadCount = signal<number>(0);
  /** Whether the header notification dropdown is open. */
  readonly showNotifications = signal(false);

  // ── Role approvals (administrators) ──────────────────────────────────────
  readonly pendingRequests = signal<RoleRequestResponse[]>([]);

  // ── Shell ────────────────────────────────────────────────────────────────
  readonly sidebarOpen = signal<boolean>(true);
  readonly activeMenu = signal<string>('overview');

  readonly isGuest = computed(() => !this.authService.isAuthenticated());

  /**
   * A token exists but `/api/auth/me` has not answered yet, so the role (and
   * therefore the dashboard variant) is still unknown.
   */
  readonly isProfilePending = computed(
    () => !this.authService.isAuthenticated() && !!this.authService.getAccessToken()
  );

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly isGovOfficial = computed(
    () => this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL
  );

  readonly isResearcher = computed(
    () => this.authService.userRole() === UserRole.RESEARCHER
  );

  readonly isOrganization = computed(
    () => this.authService.userRole() === UserRole.ORGANIZATION
  );

  readonly isCitizen = computed(() => {
    const role = this.authService.userRole();
    return !role || role === UserRole.CITIZEN;
  });

  // ── Capabilities (mirror the backend analytics RBAC) ─────────────────────
  /** `/api/analytics/*` is reachable by officials, researchers and admins. */
  readonly canViewAnalytics = computed(() =>
    AnalyticsService.isAnalyticsRole(this.authService.userRole())
  );

  /** `/api/analytics/users` is administrator-only. */
  readonly canViewUserAnalytics = computed(() =>
    AnalyticsService.isUserAnalyticsRole(this.authService.userRole())
  );

  /** Policy / scheme lifecycle state is presented to admins and officials. */
  readonly canViewStatusBreakdown = computed(
    () => this.isAdmin() || this.isGovOfficial()
  );

  readonly isLoading = computed(() => this.loadState() === 'loading');
  readonly hasFailed = computed(() => this.loadState() === 'error');
  readonly hasData = computed(
    () => this.loadState() === 'ready' && this.analytics() !== null
  );

  // ── Overview ─────────────────────────────────────────────────────────────
  readonly overview = computed(() => this.analytics()?.overview ?? null);

  readonly failedPanels = computed(() => this.analytics()?.failedPanels ?? []);

  // ── Policy statistics (GET /api/analytics/policies) ──────────────────────
  readonly policyCategorySlices = computed(() =>
    toMetricSlices(this.analytics()?.policies?.policies_by_category)
  );

  readonly policyStatusSlices = computed(() =>
    toMetricSlices(this.analytics()?.policies?.policies_by_status, {
      sortByStatusOrder: true,
    })
  );

  // ── Scheme statistics (GET /api/analytics/schemes) ───────────────────────
  readonly schemeCategorySlices = computed(() =>
    toMetricSlices(this.analytics()?.schemes?.schemes_by_category)
  );

  readonly schemeStatusSlices = computed(() =>
    toMetricSlices(this.analytics()?.schemes?.schemes_by_status, {
      sortByStatusOrder: true,
    })
  );

  readonly schemeUsage = computed(() =>
    toSchemeUsage(this.analytics()?.schemes?.scheme_usage)
  );

  // ── Department statistics (GET /api/analytics/departments) ───────────────
  readonly policiesByDepartment = computed(() =>
    toBreakdownItems(this.analytics()?.departments?.policies_by_department)
  );

  readonly schemesByDepartment = computed(() =>
    toBreakdownItems(this.analytics()?.departments?.schemes_by_department)
  );

  // ── User analytics (GET /api/analytics/users, admin only) ────────────────
  readonly usersByRole = computed(() =>
    toMetricSlices(this.analytics()?.users?.users_by_role)
  );

  readonly activeUsers = computed(() => this.analytics()?.users?.active_users ?? 0);
  readonly inactiveUsers = computed(
    () => this.analytics()?.users?.inactive_users ?? 0
  );

  readonly registrationTrend = computed(() =>
    toTrendPoints(this.analytics()?.users?.user_registrations_over_time)
  );

  readonly searchTrend = computed(() =>
    toTrendPoints(this.analytics()?.users?.searches_over_time)
  );

  // ── Notification analytics (GET /api/analytics/notifications) ────────────
  readonly notificationsByType = computed(() =>
    toMetricSlices(this.analytics()?.notifications?.notifications_by_type)
  );

  readonly notificationsByChannel = computed(() =>
    toBreakdownItems(this.analytics()?.notifications?.notifications_by_channel)
  );

  readonly notificationsByReadStatus = computed(() =>
    toMetricSlices(this.analytics()?.notifications?.notifications_by_read_status, {
      labels: { true: 'Read', false: 'Unread' },
    })
  );

  readonly notificationTrend = computed(() =>
    toTrendPoints(this.analytics()?.notifications?.notifications_over_time)
  );

  /** Platform-wide search volume, available to every analytics role. */
  readonly totalSearches = computed(() => this.overview()?.total_searches ?? 0);

  readonly recentNotifications = computed(() => this.notifications().slice(0, 5));

  // ── Lifecycle ────────────────────────────────────────────────────────────
  ngOnInit(): void {
    // The role decides both the dashboard variant and which analytics
    // endpoints are allowed, so load once with whatever profile is cached and
    // reload after `/auth/me` refreshes it.
    this.loadRoleScopedData();

    if (this.authService.getAccessToken()) {
      this.authService.getMe().subscribe({
        next: () => this.loadRoleScopedData(),
        error: () => {},
      });
    }

    this.visibilityHandler = () => {
      if (document.visibilityState !== 'visible') return;
      this.loadRoleScopedData();
      if (this.isAdmin()) {
        this.loadPendingRequests();
      }
    };
    document.addEventListener('visibilitychange', this.visibilityHandler);
  }

  ngOnDestroy(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
    }
    if (this.visibilityHandler) {
      document.removeEventListener('visibilitychange', this.visibilityHandler);
    }
  }

  /** Load everything the current role is entitled to see. */
  private loadRoleScopedData(force = false): void {
    if (this.isGuest()) {
      this.loadedForRole = null;
      this.analytics.set(null);
      this.loadState.set('idle');
      this.loadError.set(null);
      this.notifications.set([]);
      this.unreadCount.set(0);
      return;
    }

    this.loadUnreadCount();
    if (this.isAdmin()) {
      this.loadPendingRequests();
      this.startPolling();
    }

    if (!this.canViewAnalytics()) {
      // Citizens and organizations have no analytics access: never call the
      // analytics endpoints, show their own notifications instead.
      this.loadedForRole = null;
      this.analytics.set(null);
      this.loadState.set('idle');
      this.loadError.set(null);
      this.loadMyNotifications();
      return;
    }

    const role = this.authService.userRole();
    const alreadyRequested =
      this.loadState() === 'loading' || this.loadState() === 'ready';
    if (!force && this.loadedForRole === role && alreadyRequested) {
      return;
    }
    this.loadedForRole = role;
    this.loadAnalytics();
  }

  loadAnalytics(): void {
    this.loadState.set('loading');
    this.loadError.set(null);

    this.analyticsService.getDashboardAnalytics(this.authService.userRole()).subscribe({
      next: (data) => {
        this.analytics.set(data);
        this.loadState.set('ready');
      },
      error: (error: unknown) => {
        this.analytics.set(null);
        this.loadError.set(this.describeError(error));
        this.loadState.set('error');
      },
    });
  }

  retryAnalytics(): void {
    this.loadedForRole = null;
    this.loadAnalytics();
  }

  // ── Notifications (GET /api/notifications) ───────────────────────────────
  loadMyNotifications(): void {
    this.notificationService.list().subscribe({
      next: (items) => this.notifications.set(items),
      error: () => this.notifications.set([]),
    });
  }

  loadUnreadCount(): void {
    this.notificationService.unreadCount().subscribe({
      next: (response) => this.unreadCount.set(response.unread_count),
      error: () => this.unreadCount.set(0),
    });
  }

  /** Open/close the header dropdown; refresh count and list on open. */
  toggleNotifications(): void {
    this.showNotifications.update((value) => !value);
    if (this.showNotifications()) {
      this.loadUnreadCount();
      this.loadMyNotifications();
    }
  }

  markNotificationAsRead(notification: NotificationItem): void {
    if (notification.is_read) {
      return;
    }

    this.notificationService.markAsRead(notification.id).subscribe({
      next: () => {
        this.notifications.update((items) =>
          items.map((item) =>
            item.id === notification.id ? { ...item, is_read: true } : item
          )
        );
        this.loadUnreadCount();
      },
      error: () => {
        // Keep the notification unchanged if the API call fails.
      },
    });
  }

  markAllNotificationsAsRead(): void {
    this.notificationService.markAllAsRead().subscribe({
      next: () => {
        this.notifications.update((items) =>
          items.map((item) => ({ ...item, is_read: true }))
        );
        this.loadUnreadCount();
      },
      error: () => {
        // Keep the notifications unchanged if the API call fails.
      },
    });
  }

  // ── Role approvals (administrators) ──────────────────────────────────────
  private startPolling(): void {
    if (this.pollInterval) return;
    this.pollInterval = setInterval(() => {
      if (this.isAdmin()) {
        this.loadPendingRequests();
      }
    }, 30000);
  }

  loadPendingRequests(): void {
    this.authService.getPendingRoleRequests().subscribe({
      next: (requests) => this.pendingRequests.set(requests),
      error: () => this.pendingRequests.set([]),
    });
  }

  approveRequest(requestId: string): void {
    this.authService.approveRoleRequest(requestId).subscribe({
      next: () => {
        this.loadPendingRequests();
        this.loadAnalytics();
      },
      error: () => {},
    });
  }

  rejectRequest(requestId: string): void {
    this.authService.rejectRoleRequest(requestId).subscribe({
      next: () => {
        this.loadPendingRequests();
        this.loadAnalytics();
      },
      error: () => {},
    });
  }

  // ── Navigation ───────────────────────────────────────────────────────────
  toggleSidebar(): void {
    this.sidebarOpen.set(!this.sidebarOpen());
  }

  onMenuSelect(menuId: string): void {
    this.activeMenu.set(menuId);
    switch (menuId) {
      case 'policies':
        this.router.navigate(['/policies']);
        break;
      case 'schemes':
        this.router.navigate(['/schemes']);
        break;
      case 'search':
        this.router.navigate(['/search']);
        break;
      case 'eligibility':
        this.router.navigate(['/eligibility']);
        break;
      case 'compare':
        this.router.navigate(['/compare']);
        break;
      case 'policies-create':
        this.router.navigate(['/policies/create']);
        break;
      case 'schemes-create':
        this.router.navigate(['/schemes/create']);
        break;
      case 'role-upgrade':
        this.router.navigate(['/role-request']);
        break;
      case 'applications':
        this.router.navigate(['/applications']);
        break;
      case 'feedback':
        this.router.navigate(['/feedback']);
        break;
      case 'faq':
        this.router.navigate(['/faq']);
        break;
      case 'reports':
        this.router.navigate(['/reports']);
        break;
      case 'approvals':
        this.scrollToSection('pending-approvals');
        break;
      case 'analytics':
        this.scrollToSection('notification-analytics');
        break;
      case 'notifications':
        this.scrollToSection('your-notifications');
        break;
      case 'overview':
      default:
        window.scrollTo({ top: 0, behavior: 'smooth' });
        break;
    }
  }

  private scrollToSection(sectionId: string): void {
    document
      .getElementById(sectionId)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  navigateToProfile(): void {
    this.router.navigate(['/citizen-profile']);
  }

  // ── Formatting helpers ───────────────────────────────────────────────────
  formatRole(value: string): string {
    return humanize(value);
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  formatTime(dateStr: string): string {
    return new Date(dateStr).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  getDetailEntries(details: Record<string, any>): [string, any][] {
    return Object.entries(details).slice(0, 4);
  }

  get userName(): string {
    return this.authService.currentUser()?.full_name ?? 'User';
  }

  get userRole(): string {
    const role = this.authService.userRole();
    return role ? humanize(role) : 'Citizen';
  }

  get userInitial(): string {
    return this.userName.charAt(0).toUpperCase();
  }

  /** Turn an HTTP failure into a message the dashboard can render. */
  private describeError(error: unknown): string {
    const httpError = error as {
      status?: number;
      error?: { detail?: unknown };
    };
    const detail = httpError?.error?.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail;
    }
    if (httpError?.status === 403) {
      return 'Your account does not have permission to view analytics.';
    }
    if (httpError?.status === 401) {
      return 'Your session has expired. Please sign in again.';
    }
    if (httpError?.status === 0) {
      return 'The analytics service is unreachable. Check your connection and try again.';
    }
    return 'Analytics could not be loaded. Please try again.';
  }

  // ── Sidebar menu (every id is unique and wired to a real destination) ────
  readonly menuItems = computed(() => {
    if (this.isGuest()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'policies', label: 'Policies', icon: 'document' },
        { id: 'schemes', label: 'Schemes', icon: 'gift' },
      ];
    }

    const base = [
      { id: 'overview', label: 'Overview', icon: 'home' },
      { id: 'policies', label: 'Policies', icon: 'document' },
      { id: 'schemes', label: 'Schemes', icon: 'gift' },
      { id: 'search', label: 'Search & Explore', icon: 'search' },
      { id: 'eligibility', label: 'Eligibility Checker', icon: 'check-circle' },
      { id: 'compare', label: 'Compare Schemes', icon: 'bookmark' },
      { id: 'feedback', label: 'Feedback', icon: 'chat' },
      { id: 'faq', label: 'FAQ', icon: 'help-circle' },
    ];

    if (this.isGovOfficial()) {
      return [
        ...base,
        { id: 'policies-create', label: 'Upload Policy', icon: 'file-plus' },
        { id: 'schemes-create', label: 'Create Scheme', icon: 'gift' },
        { id: 'reports', label: 'Reports', icon: 'document' },
      ];
    }

    if (this.isAdmin()) {
      return [
        ...base,
        { id: 'approvals', label: 'Role Approvals', icon: 'folder' },
        { id: 'reports', label: 'Reports', icon: 'document' },
      ];
    }

    if (this.isResearcher()) {
      return [
        ...base,
        { id: 'analytics', label: 'Platform Analytics', icon: 'chart' },
      ];
    }

    if (this.isOrganization()) {
      return [
        ...base,
        { id: 'notifications', label: 'Notifications', icon: 'bell' },
        { id: 'applications', label: 'My Applications', icon: 'folder' },
      ];
    }

    return [
      ...base,
      { id: 'notifications', label: 'Notifications', icon: 'bell' },
      { id: 'applications', label: 'My Applications', icon: 'folder' },
      { id: 'role-upgrade', label: 'Role Upgrade', icon: 'folder' },
    ];
  });
}
