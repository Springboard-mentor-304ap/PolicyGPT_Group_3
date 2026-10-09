import { Component, effect, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../../../../core/services/auth.service';
import { isCitizenProfileComplete } from '../../../../core/services/profile-completion';
import { UserRole } from '../../../../core/models/auth.models';
import { ButtonComponent } from '../../../../shared/components/button/button.component';

/**
 * Dashboard card that asks a signed-in user to finish their profile.
 *
 * Completion is read from the existing `GET /api/profile/citizen` endpoint and
 * decided by the same rule the profile page uses, so the card disappears as
 * soon as the profile is saved. Government officials are skipped: their
 * profile is provisioned from an approved role request and is read-only, so
 * there would be nothing for them to complete.
 */
@Component({
  selector: 'app-profile-completion',
  standalone: true,
  imports: [ButtonComponent],
  templateUrl: './profile-completion.component.html',
  styleUrl: './profile-completion.component.css',
})
export class ProfileCompletionComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  /** Guards the one-shot profile fetch (see the effect below). */
  private requested = false;

  readonly showCard = signal(false);

  constructor() {
    // `/auth/me` may still be resolving when the dashboard renders, so wait
    // for a known role before deciding what (if anything) to show.
    effect(() => {
      const role = this.authService.userRole();

      if (!role || this.requested) {
        return;
      }

      this.requested = true;

      if (role === UserRole.GOVERNMENT_OFFICIAL) {
        return;
      }

      this.loadProfile();
    });
  }

  private loadProfile(): void {
    this.authService.getCitizenProfile().subscribe({
      next: (profile) => {
        this.showCard.set(!isCitizenProfileComplete(profile));
      },
      error: () => {
        // Never nag when the profile could not be read: the profile page
        // reports the real problem.
        this.showCard.set(false);
      },
    });
  }

  goToProfile(): void {
    this.router.navigate(['/citizen-profile']);
  }
}
