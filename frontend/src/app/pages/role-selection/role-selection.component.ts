import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { CardComponent } from '../../shared/components/card/card.component';
import { ButtonComponent } from '../../shared/components/button/button.component';

interface RoleOption {
  id: string;
  title: string;
  description: string;
  icon: string;
}

@Component({
  selector: 'app-role-selection',
  standalone: true,
  imports: [CommonModule, CardComponent, ButtonComponent],
  templateUrl: './role-selection.component.html',
  styleUrl: './role-selection.component.css',
})
export class RoleSelectionComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  selectedRole = signal<string | null>(null);
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  roles: RoleOption[] = [
    {
      id: 'citizen',
      title: 'Citizen',
      description: 'Access government policies, schemes, and track your applications',
      icon: 'citizen',
    },
    {
      id: 'researcher',
      title: 'Researcher',
      description: 'Analyze policy data, generate reports, and access research tools',
      icon: 'researcher',
    },
    {
      id: 'government_official',
      title: 'Government Official',
      description: 'Manage policies, review applications, and publish announcements',
      icon: 'government',
    },
    {
      id: 'organization',
      title: 'Organization',
      description: 'Access bulk services, manage team accounts, and submit proposals',
      icon: 'organization',
    },
  ];

  selectRole(roleId: string): void {
    this.selectedRole.set(roleId);
  }

  onConfirm(): void {
    const role = this.selectedRole();
    if (!role) {
      this.errorMessage.set('Please select a role to continue');
      return;
    }

    this.loading.set(false);
    this.router.navigate(['/login']);
  }

  private routeByRole(role: string): void {
    this.router.navigate(['/login']);
  }
}
