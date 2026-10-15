import { Component, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { SearchService } from '../../core/services/search.service';
import { AnalyticsService } from '../../core/services/analytics.service';
import { ApplicationService } from '../../core/services/application.service';
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
import { DashboardSidebarComponent } from './components/dashboard-sidebar/dashboard-sidebar.component';
import { NotificationBellComponent } from './components/notification-bell/notification-bell.component';
import { PendingApprovalsComponent } from './components/pending-approvals/pending-approvals.component';
import { UsageLeaderboardComponent } from './components/usage-leaderboard/usage-leaderboard.component';
import {
  QuickActionsComponent,
  QuickActionItem,
} from './components/quick-actions/quick-actions.component';
import { RoleRequestCardsComponent } from './components/role-request-cards/role-request-cards.component';
import { ProfileCompletionComponent } from './components/profile-completion/profile-completion.component';
import { ApplicationApprovalsComponent } from './application-approvals/application-approvals.component';

export type DashboardLoadState = 'idle' | 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    FloatingCompareDockComponent,
    DonutChartComponent,
    BarChartComponent,
    TrendChartComponent,
    SkeletonComponent,
    DashboardSidebarComponent,
    NotificationBellComponent,
    PendingApprovalsComponent,
    UsageLeaderboardComponent,
    QuickActionsComponent,
    RoleRequestCardsComponent,
    ProfileCompletionComponent,
    ApplicationApprovalsComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  private readonly analyticsService = inject(AnalyticsService);
  private readonly notificationService = inject(NotificationService);
  private readonly searchService = inject(SearchService);
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

  // ── Hero search (GET /api/search, public endpoint) ───────────────────────
  /** Text bound to the hero search box. */
  heroQuery = '';

  /**
   * Catalogue totals for the compact statistics row. They come from the
   * public search endpoint (`search_type` only, no query or filters, so the
   * API never records them as search history). `null` renders as “—” while
   * loading or when the API is unreachable — never a fabricated number.
   */
  readonly policyTotal = signal<number | null>(null);
  readonly schemeTotal = signal<number | null>(null);

  /** Stats row: catalogue totals for everyone, platform totals for admins. */
  readonly platformStats = computed(() => {
    const official = this.isGovOfficial();
    const overview = this.overview();

    // When the role can read /api/analytics/overview, prefer its ministry-
    // scoped totals so this row agrees with the analytics cards below;
    // everyone else uses the public catalogue totals.
    const policyValue = overview?.total_policies ?? this.policyTotal();
    const schemeValue = overview?.total_schemes ?? this.schemeTotal();

    const stats: {
      label: string;
      value: number | null;
      icon: string;
      tone: string;
    }[] = [
      {
        icon: 'document',
        tone: 'blue',
        label: official ? 'Ministry Policies' : 'Policies',
        value: policyValue,
      },
      {
        icon: 'gift',
        tone: 'green',
        label: official ? 'Ministry Schemes' : 'Schemes',
        value: schemeValue,
      },
    ];

    if (overview && overview.total_users !== null) {
      stats.push({
        icon: 'users',
        tone: 'navy',
        label: 'Registered Users',
        value: overview.total_users,
      });
    }
    if (overview && overview.total_searches !== null) {
      stats.push({
        icon: 'search',
        tone: 'saffron',
        label: 'Searches Recorded',
        value: overview.total_searches,
      });
    }

    return stats;
  });

  // ── Hero chips & category grid (canonical /api/search filter values) ─────
  readonly popularChips: { label: string; value: string }[] = [
    { label: 'Education', value: 'education' },
    { label: 'Health', value: 'healthcare' },
    { label: 'Housing', value: 'housing' },
    { label: 'Employment', value: 'employment_programs' },
    { label: 'Agriculture', value: 'farmer_welfare' },
    { label: 'Social Welfare', value: 'social_security' },
  ];

  readonly categoryChips: {
    label: string;
    value: string;
    icon: string;
    tone: string;
  }[] = [
    { label: 'Education', value: 'education', icon: 'book', tone: 'navy' },
    { label: 'Health', value: 'healthcare', icon: 'heart', tone: 'rose' },
    { label: 'Housing', value: 'housing', icon: 'home', tone: 'green' },
    {
      label: 'Employment',
      value: 'employment_programs',
      icon: 'briefcase',
      tone: 'saffron',
    },
    { label: 'Agriculture', value: 'farmer_welfare', icon: 'leaf', tone: 'green' },
    {
      label: 'Social Welfare',
      value: 'social_security',
      icon: 'users',
      tone: 'blue',
    },
    { label: 'Scholarships', value: 'scholarships', icon: 'award', tone: 'navy' },
    {
      label: 'Women & Child',
      value: 'women_empowerment',
      icon: 'user',
      tone: 'rose',
    },
    {
      label: 'Business Support',
      value: 'business_support',
      icon: 'trending-up',
      tone: 'blue',
    },
    { label: 'Environment', value: 'environment', icon: 'globe', tone: 'green' },
  ];

  // ── Feature grid: role-aware shortcuts to real routes ────────────────────
  readonly quickAccess = computed<QuickActionItem[]>(() => {
    if (this.isGuest()) {
      return [
        {
          icon: 'document',
          tone: 'blue',
          label: 'Browse Policies',
          hint: 'Central and state policy repository',
          link: '/policies',
        },
        {
          icon: 'gift',
          tone: 'green',
          label: 'Browse Schemes',
          hint: 'Welfare schemes and their benefits',
          link: '/schemes',
        },
        {
          icon: 'compass',
          tone: 'saffron',
          label: 'Scheme Finder',
          hint: 'Describe your need in plain language',
          link: '/finder',
        },
      ];
    }

    const discovery: QuickActionItem[] = [
      {
        icon: 'search',
        tone: 'blue',
        label: 'Search & Explore',
        hint: 'Find policies and schemes',
        link: '/search',
      },
      {
        icon: 'check-circle',
        tone: 'green',
        label: 'Eligibility Checker',
        hint: 'See which schemes you qualify for',
        link: '/eligibility',
      },
      {
        icon: 'compass',
        tone: 'saffron',
        label: 'Scheme Finder',
        hint: 'Describe your need in plain language',
        link: '/finder',
      },
      {
        icon: 'columns',
        tone: 'navy',
        label: 'Compare Schemes',
        hint: 'Compare benefits side by side',
        link: '/compare',
      },
      {
        icon: 'helpdesk',
        tone: 'blue',
        label: 'AI Helpdesk',
        hint: 'Ask questions about policies and schemes',
        link: '/helpdesk',
      },
      {
        icon: 'folder',
        tone: 'saffron',
        label: 'My Applications',
        hint: 'Track your scheme applications',
        link: '/applications',
      },
    ];

    if (this.isGovOfficial() || this.isAdmin()) {
      if (this.isAdmin()) {
        // Administrative destinations only — citizen tools stay off this list.
        return [
          {
            icon: 'user',
            tone: 'blue',
            label: this.isSuperAdmin()
              ? 'User & Role Management'
              : 'User Management',
            hint: 'Search accounts, review roles and account status',
            link: '/admin/users',
          },
          {
            icon: 'folder',
            tone: 'saffron',
            label: this.isSuperAdmin()
              ? 'Administrator Approvals'
              : 'Role Approvals',
            hint: this.isSuperAdmin()
              ? 'Review administrator access requests'
              : 'Review pending role upgrade requests',
            link: '/role-approvals',
          },
          {
            icon: 'chart',
            tone: 'navy',
            label: 'Reports',
            hint: 'Generate downloadable reports',
            link: '/reports',
          },
          {
            icon: 'document',
            tone: 'green',
            label: 'Audit Logs',
            hint: 'Review recorded administrative events',
            link: '/admin/audit-logs',
          },
        ];
      }

      return [
        {
          icon: 'document',
          tone: 'blue',
          label: 'Policies',
          hint: 'Upload and manage policies',
          link: '/policies',
        },
        {
          icon: 'gift',
          tone: 'green',
          label: 'Schemes',
          hint: 'Create and manage welfare schemes',
          link: '/schemes',
        },
        {
          icon: 'folder',
          tone: 'saffron',
          label: 'Application Approvals',
          hint: 'Review citizen applications',
          link: '/applications/review',
        },
        {
          icon: 'chart',
          tone: 'navy',
          label: 'Reports',
          hint: 'Generate downloadable reports',
          link: '/reports',
        },
      ];
    }

    if (this.isResearcher()) {
      return [
        discovery[0],
        {
          icon: 'document',
          tone: 'blue',
          label: 'Policies',
          hint: 'Browse the policy repository',
          link: '/policies',
        },
        {
          icon: 'gift',
          tone: 'green',
          label: 'Schemes',
          hint: 'Browse welfare schemes',
          link: '/schemes',
        },
        {
          icon: 'chart',
          tone: 'navy',
          label: 'Reports',
          hint: 'Generate downloadable reports',
          link: '/reports',
        },
      ];
    }

    return discovery;
  });

  /** Right-hand “A Unified Platform” tiles: real destinations per role. */
  readonly platformTiles = computed(() => {
    if (this.isGuest()) {
      return [
        {
          icon: 'document',
          tone: 'blue',
          label: 'Discover Policies',
          hint: 'Central and state policy repository',
          link: '/policies',
        },
        {
          icon: 'gift',
          tone: 'green',
          label: 'Explore Schemes',
          hint: 'Welfare schemes and their benefits',
          link: '/schemes',
        },
        {
          icon: 'compass',
          tone: 'saffron',
          label: 'Scheme Finder',
          hint: 'Get matched to the right scheme',
          link: '/finder',
        },
      ];
    }

    if (this.isGovOfficial() || this.isAdmin()) {
      if (this.isAdmin()) {
        return [
          {
            icon: 'users',
            tone: 'blue',
            label: 'User Management',
            hint: 'Search accounts and review role status',
            link: '/admin/users',
          },
          {
            icon: 'user',
            tone: 'saffron',
            label: this.isSuperAdmin()
              ? 'Administrator Approvals'
              : 'Access Requests',
            hint: this.isSuperAdmin()
              ? 'Approve or reject administrator access'
              : 'Approve or reject role upgrade requests',
            link: '/role-approvals',
          },
          {
            icon: 'book',
            tone: 'green',
            label: 'Audit Logs',
            hint: 'Trace administrative activity',
            link: '/admin/audit-logs',
          },
        ];
      }

      return [
        {
          icon: 'document',
          tone: 'blue',
          label: 'Policy Management',
          hint: 'Upload and maintain department policies',
          link: '/policies',
        },
        {
          icon: 'gift',
          tone: 'green',
          label: 'Scheme Management',
          hint: 'Create and maintain welfare schemes',
          link: '/schemes',
        },
        {
          icon: 'briefcase',
          tone: 'saffron',
          label: 'Application Review',
          hint: 'Process citizen applications',
          link: '/applications/review',
        },
      ];
    }

    return [
      {
        icon: 'search',
        tone: 'blue',
        label: 'Discover',
        hint: 'Find relevant policies and schemes',
        link: '/search',
      },
      {
        icon: 'check-circle',
        tone: 'saffron',
        label: 'Check Eligibility',
        hint: 'Understand if you qualify',
        link: '/eligibility',
      },
      {
        icon: 'columns',
        tone: 'green',
        label: 'Compare & Apply',
        hint: 'Make informed decisions',
        link: '/compare',
      },
    ];
  });

  readonly isGuest = computed(() => !this.authService.isAuthenticated());

  // ── Hero copy, per role ─────────────────────────────────────────────────
  // Guests and citizens keep the discovery message; staff roles get copy
  // that matches what the platform actually lets them do.
  readonly heroEyebrow = computed(() => {
    if (this.isGuest() || this.isCitizen() || this.isOrganization()) {
      return 'Government Policies & Schemes';
    }
    if (this.isGovOfficial()) {
      return 'Government Operations';
    }
    if (this.isResearcher()) {
      return 'Policy Research';
    }
    return 'Platform Administration';
  });

  readonly heroTitleLead = computed(() => {
    if (this.isGuest() || this.isCitizen() || this.isOrganization()) {
      return 'Find Government Schemes';
    }
    if (this.isGovOfficial()) {
      return 'Manage Policies & Schemes';
    }
    if (this.isResearcher()) {
      return 'Explore & Analyze';
    }
    if (this.isSuperAdmin()) {
      return 'Oversee Platform Access';
    }
    return 'Manage the Platform';
  });

  readonly heroTitleTail = computed(() => {
    if (this.isGuest() || this.isCitizen() || this.isOrganization()) {
      return 'that';
    }
    if (this.isGovOfficial()) {
      return 'for your';
    }
    if (this.isResearcher()) {
      return 'government';
    }
    if (this.isSuperAdmin()) {
      return 'and';
    }
    return 'with';
  });

  readonly heroTitleEm = computed(() => {
    if (this.isGuest() || this.isCitizen() || this.isOrganization()) {
      return 'work for you';
    }
    if (this.isGovOfficial()) {
      return 'department';
    }
    if (this.isResearcher()) {
      return 'initiatives';
    }
    if (this.isSuperAdmin()) {
      return 'security';
    }
    return 'confidence';
  });

  readonly heroSubtitle = computed(() => {
    if (this.isGuest() || this.isCitizen() || this.isOrganization()) {
      return (
        'Search, explore and understand government policies and schemes ' +
        'across central and state departments.'
      );
    }
    if (this.isGovOfficial()) {
      return (
        'Manage policies and schemes and monitor departmental activity ' +
        'across your department.'
      );
    }
    if (this.isResearcher()) {
      return (
        'Explore government policies, compare initiatives and analyze ' +
        'trends with platform-wide data.'
      );
    }
    if (this.isSuperAdmin()) {
      return (
        'Oversee administrator access, security and platform-wide ' +
        'operations.'
      );
    }
    return (
      'Manage users, access requests, feedback and platform activity ' +
      'across the portal.'
    );
  });

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

  readonly isSuperAdmin = computed(
    () => this.authService.userRole() === UserRole.SUPER_ADMIN
  );

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

  /** Application review is staff-only, mirroring the backend RBAC. */
  readonly canReviewApplications = computed(() =>
    ApplicationService.canReviewApplications(this.authService.userRole())
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

  /** Platform-wide search volume, administrators only (null otherwise). */
  readonly totalSearches = computed(() => this.overview()?.total_searches ?? 0);

  readonly recentNotifications = computed(() => this.notifications().slice(0, 5));

  // ── Lifecycle ────────────────────────────────────────────────────────────
  ngOnInit(): void {
    // Catalogue totals are public, so every dashboard variant loads them.
    this.loadCatalogueTotals();

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

  /**
   * Load the policy / scheme totals shown in the statistics row.
   *
   * Uses `GET /api/search` with `search_type` only: the response carries the
   * count in its body (no CORS-exposed header needed) and the backend skips
   * history logging when no query or filter is present.
   */
  private loadCatalogueTotals(): void {
    this.searchService
      .search({ type: 'policy', page: 1, page_size: 1 })
      .subscribe({
        next: (res) => this.policyTotal.set(res.total),
        error: () => this.policyTotal.set(null),
      });

    this.searchService
      .search({ type: 'scheme', page: 1, page_size: 1 })
      .subscribe({
        next: (res) => this.schemeTotal.set(res.total),
        error: () => this.schemeTotal.set(null),
      });
  }

  /** Hero search: jump to the existing Search page with the query. */
  submitHeroSearch(): void {
    const q = this.heroQuery.trim();
    this.router.navigate(['/search'], {
      queryParams: q ? { q } : {},
    });
  }

  /** Popular chip / category card: same Search page, category filter. */
  searchCategory(value: string): void {
    this.router.navigate(['/search'], {
      queryParams: { category: value },
    });
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
    // Every signed-in role has an inbox section on the dashboard, so every
    // signed-in role loads its list here — including analytics roles
    // (officials, researchers, admins), whose sidebar "Notifications" item
    // used to find an empty, unrendered section.
    this.loadMyNotifications();
    if (this.isAdmin()) {
      this.loadPendingRequests();
      this.startPolling();
    }

    if (!this.canViewAnalytics()) {
      // Citizens and organizations have no analytics access: never call the
      // analytics endpoints — their notifications (loaded above) are what
      // their dashboard shows.
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

  /** Dismiss the dropdown (outside clicks, navigation). */
  closeNotifications(): void {
    this.showNotifications.set(false);
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
    // Leaving the overview (or scrolling within it) must not leave the header
    // dropdown hanging over the next page.
    this.closeNotifications();
    switch (menuId) {
      case 'profile':
        this.router.navigate(['/citizen-profile']);
        break;
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
      case 'finder':
        this.router.navigate(['/finder']);
        break;
      case 'helpdesk':
        this.router.navigate(['/helpdesk']);
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
      case 'applications-review':
        this.router.navigate(['/applications/review']);
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
        // Role approvals live on their own admin-only page so the item
        // always navigates somewhere, even with an empty pending queue.
        this.router.navigate(['/role-approvals']);
        break;
      case 'users':
        // Administrator-only user management page (guarded route).
        this.router.navigate(['/admin/users']);
        break;
      case 'audit-logs':
        // Administrator-only audit trail page (guarded route).
        this.router.navigate(['/admin/audit-logs']);
        break;
      case 'analytics':
        // The dashboard IS the analytics destination: land on the overview
        // stats grid that every analytics role renders (the admin-only
        // #notification-analytics panel is not on screen for officials).
        this.scrollToSection('analytics-overview');
        break;
      case 'notifications':
        // The "Your Notifications" inbox section renders for every
        // signed-in role, so the anchor always exists.
        this.scrollToSection('your-notifications');
        break;
      case 'overview':
      default:
        window.scrollTo({ top: 0, behavior: 'smooth' });
        break;
    }
  }

  private scrollToSection(sectionId: string): void {
    const section = document.getElementById(sectionId);

    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }

    // The analytics block can still be loading (or failed) on the first
    // click — fall back to the top of the page instead of doing nothing.
    window.scrollTo({ top: 0, behavior: 'smooth' });
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
      // Guests only get the two public destinations. Every other sidebar
      // feature (Scheme Finder, Search, Eligibility, Helpdesk, Compare…)
      // sits behind authGuard, so linking it here would dead-end at /login.
      return [
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
      { id: 'finder', label: 'Scheme Finder', icon: 'compass' },
      { id: 'helpdesk', label: 'AI Helpdesk', icon: 'helpdesk' },
      { id: 'compare', label: 'Compare Schemes', icon: 'columns' },
      { id: 'feedback', label: 'Feedback', icon: 'chat' },
      { id: 'faq', label: 'FAQ', icon: 'help-circle' },
    ];

    // Government officials get management destinations only — the citizen
    // tools (eligibility, finder, compare, helpdesk) are deliberately absent.
    if (this.isGovOfficial()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'policies', label: 'Policies', icon: 'document' },
        { id: 'schemes', label: 'Schemes', icon: 'gift' },
        // Global search stays available to officials (already implemented).
        { id: 'search', label: 'Search & Explore', icon: 'search' },
        { id: 'applications-review', label: 'Applications', icon: 'folder' },
        { id: 'analytics', label: 'Analytics', icon: 'chart' },
        { id: 'reports', label: 'Reports', icon: 'chart' },
        { id: 'notifications', label: 'Notifications', icon: 'bell' },
        { id: 'profile', label: 'Government Profile', icon: 'user' },
      ];
    }

    // Super admins own administrator access: their approvals queue only ever
    // contains administrator requests (the API filters by reviewer role).
    if (this.isSuperAdmin()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'users', label: 'User & Role Management', icon: 'users' },
        {
          id: 'approvals',
          label: 'Administrator Approvals',
          icon: 'folder',
        },
        { id: 'analytics', label: 'Platform Analytics', icon: 'chart' },
        { id: 'audit-logs', label: 'Audit Logs', icon: 'shield' },
        { id: 'reports', label: 'Reports', icon: 'document' },
        { id: 'notifications', label: 'Notifications', icon: 'bell' },
      ];
    }

    // Administrators manage the platform except administrator access —
    // approving an administrator request is the super admin's prerogative.
    if (this.isAdmin()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'users', label: 'User Management', icon: 'users' },
        { id: 'approvals', label: 'Role Approvals', icon: 'folder' },
        { id: 'analytics', label: 'Platform Analytics', icon: 'chart' },
        { id: 'reports', label: 'Reports', icon: 'document' },
        { id: 'feedback', label: 'Feedback', icon: 'chat' },
        { id: 'audit-logs', label: 'Audit Logs', icon: 'shield' },
        { id: 'notifications', label: 'Notifications', icon: 'bell' },
      ];
    }

    if (this.isResearcher()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'search', label: 'Search & Explore', icon: 'search' },
        { id: 'policies', label: 'Policies', icon: 'document' },
        { id: 'schemes', label: 'Schemes', icon: 'gift' },
        { id: 'compare', label: 'Compare Schemes', icon: 'columns' },
        { id: 'helpdesk', label: 'AI Helpdesk', icon: 'helpdesk' },
        { id: 'analytics', label: 'Platform Analytics', icon: 'chart' },
        { id: 'reports', label: 'Reports', icon: 'document' },
        { id: 'notifications', label: 'Notifications', icon: 'bell' },
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
      { id: 'profile', label: 'My Profile', icon: 'user' },
      { id: 'role-upgrade', label: 'Role Upgrade', icon: 'folder' },
    ];
  });
}
