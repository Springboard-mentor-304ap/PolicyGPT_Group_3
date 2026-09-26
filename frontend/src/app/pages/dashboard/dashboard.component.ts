import { Component, inject, signal, computed, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { AnalyticsService } from '../../core/services/analytics.service';
import { RoleRequestResponse, UserRole } from '../../core/models/auth.models';
import { DashboardAnalyticsResponse } from '../../core/models/analytics.models';
import { FloatingCompareDockComponent } from '../comparison/components/floating-compare-dock/floating-compare-dock.component';
import { DonutChartComponent } from '../../shared/components/donut-chart/donut-chart.component';
import { BarChartComponent } from '../../shared/components/bar-chart/bar-chart.component';
import { TrendChartComponent } from '../../shared/components/trend-chart/trend-chart.component';

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
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  private readonly analyticsService = inject(AnalyticsService);
  private readonly router = inject(Router);

  private pollInterval: ReturnType<typeof setInterval> | null = null;
  private visibilityHandler: (() => void) | null = null;

  readonly analyticsData = signal<DashboardAnalyticsResponse | null>(null);
  readonly isLoading = signal<boolean>(true);
  readonly pendingRequests = signal<RoleRequestResponse[]>([]);

  readonly sidebarOpen = signal<boolean>(true);
  readonly activeMenu = signal<string>('overview');

  readonly isGuest = computed(() => !this.authService.isAuthenticated());

  readonly isAdmin = computed(() => {
    const role = this.authService.userRole();
    return role === UserRole.ADMINISTRATOR || role === UserRole.SUPER_ADMIN;
  });

  readonly isGovOfficial = computed(() => {
    return this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL;
  });

  readonly isResearcher = computed(() => {
    return this.authService.userRole() === UserRole.RESEARCHER;
  });

  readonly isCitizen = computed(() => {
    const role = this.authService.userRole();
    return !role || role === UserRole.CITIZEN;
  });

  // ── Role Permissions for Dashboard Sections ─────────────────────────────
  readonly canViewTotalUsers = computed(() => this.isAdmin());

  readonly canViewTotalSearches = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.GOVERNMENT_OFFICIAL ||
      role === UserRole.RESEARCHER
    );
  });

  readonly canViewStatusBreakdown = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.GOVERNMENT_OFFICIAL
    );
  });

  readonly canViewActivityFeed = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.GOVERNMENT_OFFICIAL
    );
  });

  readonly canViewSearchIntelligence = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.RESEARCHER ||
      role === UserRole.GOVERNMENT_OFFICIAL
    );
  });

  readonly canViewUsageOverTime = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.RESEARCHER ||
      role === UserRole.GOVERNMENT_OFFICIAL
    );
  });

  readonly canViewSchemeUsage = computed(() => {
    const role = this.authService.userRole();
    return (
      role === UserRole.ADMINISTRATOR ||
      role === UserRole.SUPER_ADMIN ||
      role === UserRole.GOVERNMENT_OFFICIAL ||
      role === UserRole.RESEARCHER ||
      role === UserRole.ORGANIZATION
    );
  });

  ngOnInit(): void {
    this.loadAnalytics();

    if (this.authService.getAccessToken()) {
      this.authService.getMe().subscribe({
        next: () => {
          this.loadAnalytics();
          if (this.isAdmin()) {
            this.loadPendingRequests();
            this.startPolling();
          }
        },
        error: () => {},
      });
    }

    this.visibilityHandler = () => {
      if (document.visibilityState === 'visible') {
        this.loadAnalytics();
        if (this.isAdmin()) {
          this.loadPendingRequests();
        }
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

  loadAnalytics(): void {
    this.isLoading.set(true);
    this.analyticsService.getDashboardAnalytics().subscribe({
      next: (data) => {
        this.analyticsData.set(data);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
      },
    });
  }

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
      case 'overview':
      default:
        break;
    }
  }

  onQuickAction(label: string): void {
    const l = label.toLowerCase();
    if (l.includes('search')) {
      this.router.navigate(['/search']);
    } else if (l.includes('eligibility') || l.includes('apply')) {
      this.router.navigate(['/eligibility']);
    } else if (l.includes('compare')) {
      this.router.navigate(['/compare']);
    } else if (l.includes('policy') || l.includes('publish')) {
      this.router.navigate(['/policies']);
    } else if (l.includes('scheme')) {
      this.router.navigate(['/schemes']);
    }
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  navigateToProfile(): void {
    this.router.navigate(['/citizen-profile']);
  }

  formatRole(role: string): string {
    return role.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
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
    return role ? role.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : 'Citizen';
  }

  get userDepartment(): string | null {
    return this.analyticsData()?.user_department ?? null;
  }

  get userInitial(): string {
    return this.userName.charAt(0).toUpperCase();
  }

  readonly menuItems = computed(() => {
    if (this.isGuest()) {
      return [
        { id: 'overview', label: 'Overview', icon: 'home' },
        { id: 'policies', label: 'Policies', icon: 'document' },
        { id: 'schemes', label: 'Schemes', icon: 'gift' },
      ];
    }

    const role = this.authService.userRole() ?? 'citizen';
    const base = [
      { id: 'overview', label: 'Overview', icon: 'home' },
      { id: 'policies', label: 'Policies', icon: 'document' },
      { id: 'schemes', label: 'Schemes', icon: 'gift' },
      { id: 'search', label: 'Search & Explore', icon: 'search' },
      { id: 'eligibility', label: 'Eligibility Checker', icon: 'check-circle' },
      { id: 'compare', label: 'Compare Schemes', icon: 'bookmark' },
    ];

    if (role === 'government_official') {
      return [
        ...base,
        { id: 'policies-create', label: 'Upload Policy', icon: 'file-plus' },
        { id: 'schemes-create', label: 'Create Scheme', icon: 'gift' },
      ];
    }

    if (role === 'researcher') {
      return [
        ...base,
        { id: 'search', label: 'Research Analytics', icon: 'search' },
      ];
    }

    // Citizen
    return [
      ...base,
      { id: 'role-upgrade', label: 'Role Upgrade', icon: 'folder' },
    ];
  });
}
