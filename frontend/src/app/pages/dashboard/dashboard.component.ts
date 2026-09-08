import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { FloatingCompareDockComponent } from '../comparison/components/floating-compare-dock/floating-compare-dock.component';

interface DashboardData {
  stats: { label: string; value: string; icon: string; color: string }[];
  recentItems: { title: string; category: string; date: string; status: string }[];
  quickActions: { label: string; icon: string }[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, FloatingCompareDockComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  sidebarOpen = signal(true);
  activeMenu = signal('overview');

  private readonly roleData: Record<string, DashboardData> = {
    citizen: {
      stats: [
        { label: 'Active Policies', value: '24', icon: 'document', color: 'blue' },
        { label: 'My Applications', value: '8', icon: 'folder', color: 'green' },
        { label: 'Notifications', value: '3', icon: 'bell', color: 'amber' },
        { label: 'Saved Items', value: '12', icon: 'bookmark', color: 'purple' },
      ],
      recentItems: [
        { title: 'PM Kisan Samman Nidhi Yojana', category: 'Farmer Welfare', date: '2026-09-01', status: 'Active' },
        { title: 'National Education Policy 2020', category: 'Education', date: '2026-08-28', status: 'Active' },
        { title: 'Ayushman Bharat PM-JAY', category: 'Healthcare', date: '2026-08-25', status: 'Active' },
        { title: 'Pradhan Mantri Awas Yojana', category: 'Housing', date: '2026-08-20', status: 'Active' },
      ],
      quickActions: [
        { label: 'Search Policies', icon: 'search' },
        { label: 'Check Scheme Eligibility', icon: 'file-plus' },
        { label: 'Compare Schemes', icon: 'bookmark' },
        { label: 'AI Assistant', icon: 'chat' },
      ],
    },
    researcher: {
      stats: [
        { label: 'Policies Analyzed', value: '156', icon: 'document', color: 'blue' },
        { label: 'Reports Generated', value: '34', icon: 'folder', color: 'green' },
        { label: 'Data Sources', value: '12', icon: 'database', color: 'amber' },
        { label: 'Bookmarks', value: '47', icon: 'bookmark', color: 'purple' },
      ],
      recentItems: [
        { title: 'Policy Impact Analysis: Education', category: 'Research Report', date: '2026-09-02', status: 'Published' },
        { title: 'Healthcare Spending Trends 2025', category: 'Data Analysis', date: '2026-08-30', status: 'Draft' },
        { title: 'Rural Development Scheme Review', category: 'Review', date: '2026-08-27', status: 'Published' },
        { title: 'Digital Literacy Program Audit', category: 'Audit', date: '2026-08-22', status: 'In Progress' },
      ],
      quickActions: [
        { label: 'Search Policies', icon: 'search' },
        { label: 'Compare Schemes', icon: 'bookmark' },
        { label: 'AI Analysis', icon: 'chat' },
        { label: 'Export Data', icon: 'download' },
      ],
    },
    government_official: {
      stats: [
        { label: 'Active Policies', value: '42', icon: 'document', color: 'blue' },
        { label: 'Pending Reviews', value: '15', icon: 'folder', color: 'green' },
        { label: 'Public Queries', value: '28', icon: 'bell', color: 'amber' },
        { label: 'Published', value: '89', icon: 'bookmark', color: 'purple' },
      ],
      recentItems: [
        { title: 'National Green Hydrogen Mission', category: 'Environment', date: '2026-09-03', status: 'Active' },
        { title: 'Digital Data Protection Policy', category: 'Governance', date: '2026-09-01', status: 'Approved' },
        { title: 'Public Health Emergency Guidelines', category: 'Healthcare', date: '2026-08-29', status: 'Active' },
        { title: 'PM Awas Yojana Urban 2.0', category: 'Housing', date: '2026-08-24', status: 'Active' },
      ],
      quickActions: [
        { label: 'Search Policies', icon: 'search' },
        { label: 'Compare Schemes', icon: 'bookmark' },
        { label: 'AI Copilot', icon: 'chat' },
        { label: 'Manage Queries', icon: 'edit' },
      ],
    },
  };

  dashboardData = computed<DashboardData>(() => {
    const role = this.authService.userRole() ?? 'citizen';
    return this.roleData[role] ?? this.roleData['citizen'];
  });

  stats = computed(() => this.dashboardData().stats);
  recentItems = computed(() => this.dashboardData().recentItems);
  quickActions = computed(() => this.dashboardData().quickActions);

  menuItems = computed(() => {
    const role = this.authService.userRole() ?? 'citizen';
    const base = [
      { id: 'overview', label: 'Overview', icon: 'home' },
      { id: 'search', label: 'Search & Explore', icon: 'search' },
      { id: 'policies', label: 'Policies', icon: 'document' },
      { id: 'schemes', label: 'Schemes', icon: 'gift' },
      { id: 'eligibility', label: 'Eligibility Checker', icon: 'check-circle' },
      { id: 'compare', label: 'Compare Schemes', icon: 'bookmark' },
    ];

    if (role === 'government_official') {
      return [
        ...base,
        { id: 'reviews', label: 'Pending Reviews', icon: 'folder' },
        { id: 'queries', label: 'Public Queries', icon: 'bell' },
      ];
    }

    if (role === 'researcher') {
      return [
        ...base,
        { id: 'reports', label: 'My Reports', icon: 'folder' },
        { id: 'datasets', label: 'Datasets', icon: 'database' },
      ];
    }

    // citizen
    return [
      ...base,
      { id: 'applications', label: 'Applications', icon: 'folder' },
      { id: 'notifications', label: 'Notifications', icon: 'bell' },
    ];
  });

  ngOnInit(): void {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
    }
  }

  toggleSidebar(): void {
    this.sidebarOpen.set(!this.sidebarOpen());
  }

  onMenuSelect(menuId: string): void {
    this.activeMenu.set(menuId);

    switch (menuId) {
      case 'search':
        this.router.navigate(['/search']);
        break;
      case 'policies':
        this.router.navigate(['/search'], { queryParams: { type: 'policy' } });
        break;
      case 'schemes':
        this.router.navigate(['/search'], { queryParams: { type: 'scheme' } });
        break;
      case 'eligibility':
        this.router.navigate(['/eligibility']);
        break;
      case 'compare':
        this.router.navigate(['/compare']);
        break;
      case 'overview':
      default:
        // remain on overview
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
    }
  }

  logout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  get userName(): string {
    return this.authService.currentUser()?.full_name ?? 'User';
  }

  get userRole(): string {
    const role = this.authService.userRole();
    return role ? role.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()) : 'Citizen';
  }

  get userInitial(): string {
    return this.userName.charAt(0).toUpperCase();
  }
}
