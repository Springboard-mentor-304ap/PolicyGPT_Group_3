import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { EligibilityResult } from '../../core/models/eligibility.models';
import { EligibilityService } from '../../core/services/eligibility.service';
import { AuthService } from '../../core/services/auth.service';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { SkeletonComponent } from '../../shared/components/skeleton/skeleton.component';
import { EligibilityResultComponent } from './components/eligibility-result/eligibility-result.component';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';

@Component({
  selector: 'app-eligibility',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    ButtonComponent,
    BadgeComponent,
    SkeletonComponent,
    EligibilityResultComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './eligibility.component.html',
  styleUrl: './eligibility.component.css',
})
export class EligibilityComponent implements OnInit {
  private readonly eligibilityService = inject(EligibilityService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  evaluating = signal<boolean>(false);
  hasEvaluated = signal<boolean>(false);
  results = signal<EligibilityResult[]>([]);
  activeTab = signal<'eligible' | 'all'>('eligible');
  error = signal<string | null>(null);

  ngOnInit(): void {
    // Auto-evaluate on page load using the user's database profile
    this.onEvaluate();
  }

  onEvaluate(): void {
    this.evaluating.set(true);
    this.error.set(null);

    this.eligibilityService.evaluateAllSchemes().subscribe({
      next: (resList: EligibilityResult[]) => {
        // Sort: eligible first, then higher match score
        const sorted = [...resList].sort((a, b) => b.match_percentage - a.match_percentage);
        this.results.set(sorted);
        this.evaluating.set(false);
        this.hasEvaluated.set(true);
      },
      error: (err) => {
        this.evaluating.set(false);
        if (err.status === 404) {
          this.error.set('No citizen profile found. Please create your profile first.');
        } else {
          this.error.set('Failed to evaluate eligibility. Please try again.');
        }
      },
    });
  }

  get eligibleSchemes(): EligibilityResult[] {
    return this.results().filter((r) => r.is_eligible);
  }

  get allSchemes(): EligibilityResult[] {
    return this.results();
  }

  navigateToProfile(): void {
    this.router.navigate(['/citizen-profile']);
  }

  resetForm(): void {
    this.hasEvaluated.set(false);
    this.results.set([]);
    this.error.set(null);
  }
}
