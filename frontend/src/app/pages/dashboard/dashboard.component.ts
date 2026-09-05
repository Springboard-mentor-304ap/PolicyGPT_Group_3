import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

interface DashboardData {
  stats: { label: string; value: string; icon: string; color: string }[];
  recentItems: { title: string; category: string; date: string; status: string }[];
  quickActions: { label: string; icon: string }[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent {
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
        { title: 'Digital India Initiative', category: 'Technology', date: '2026-09-01', status: 'Active' },
        { title: 'National Education Policy', category: 'Education', date: '2026-08-28', status: 'Active' },
        { title: 'Healthcare Access Program', category: 'Health', date: '2026-08-20', status: 'Active' },
      ],
      quickActions: [
        { label: 'Search Policies', icon: 'search' },
        { label: 'Apply for Scheme', icon: 'file-plus' },
        { label: 'AI Assistant', icon: 'chat' },
        { label: 'Track Application', icon: 'edit' },
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
        { label: 'Policy Search', icon: 'search' },
        { label: 'Generate Report', icon: 'file-plus' },
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
        { title: 'New Tax Reform Proposal', category: 'Policy Draft', date: '2026-09-03', status: 'Pending Review' },
        { title: 'Infrastructure Bill 2026', category: 'Legislation', date: '2026-09-01', status: 'Approved' },
        { title: 'Public Health Emergency Guidelines', category: 'Guidelines', date: '2026-08-29', status: 'Active' },
        { title: 'Water Conservation Initiative', category: 'Initiative', date: '2026-08-24', status: 'Under Review' },
      ],
      quickActions: [
        { label: 'Review Policies', icon: 'search' },
        { label: 'Publish Policy', icon: 'file-plus' },
        { label: 'AI Copilot', icon: 'chat' },
        { label: 'Manage Queries', icon: 'edit' },
      ],
    },
  };

  readonly isGuest = computed(() => !this.authService.isAuthenticated());

  dashboardData = computed<DashboardData>(() => {
    const role = this.authService.userRole() ?? 'citizen';
    return this.roleData[role] ?? this.roleData['citizen'];
  });

  stats = computed(() => this.dashboardData().stats);
  recentItems = computed(() => this.dashboardData().recentItems);
  quickActions = computed(() => this.dashboardData().quickActions);

  menuItems = computed(() => {
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
    ];

    if (role === 'government_official') {
      return [
        ...base,
        { id: 'reviews', label: 'Pending Reviews', icon: 'folder' },
        { id: 'queries', label: 'Public Queries', icon: 'bell' },
        { id: 'analytics', label: 'Analytics', icon: 'bookmark' },
      ];
    }

    if (role === 'researcher') {
      return [
        ...base,
        { id: 'reports', label: 'My Reports', icon: 'folder' },
        { id: 'datasets', label: 'Datasets', icon: 'bookmark' },
        { id: 'analytics', label: 'Analytics', icon: 'bell' },
      ];
    }

    // citizen
    return [
      ...base,
      { id: 'applications', label: 'Applications', icon: 'folder' },
      { id: 'schemes', label: 'Schemes', icon: 'gift' },
      { id: 'notifications', label: 'Notifications', icon: 'bell' },
    ];
  });

  toggleSidebar(): void {
    this.sidebarOpen.set(!this.sidebarOpen());
  }

  setActiveMenu(menuId: string): void {
    this.activeMenu.set(menuId);
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
    return role ? role.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Citizen';
  }

  get userInitial(): string {
    return this.userName.charAt(0).toUpperCase();
  }
}
