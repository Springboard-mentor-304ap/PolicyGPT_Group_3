import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { SearchResultItem } from '../../../../core/models/search.models';
import { EligibilityResult } from '../../../../core/models/eligibility.models';
import { EligibilityService } from '../../../../core/services/eligibility.service';
import { ModalComponent } from '../../../../shared/components/modal/modal.component';
import { ButtonComponent } from '../../../../shared/components/button/button.component';
import { EligibilityResultComponent } from '../eligibility-result/eligibility-result.component';

@Component({
  selector: 'app-eligibility-modal',
  standalone: true,
  imports: [
    CommonModule,
    ModalComponent,
    ButtonComponent,
    EligibilityResultComponent,
  ],
  templateUrl: './eligibility-modal.component.html',
  styleUrl: './eligibility-modal.component.css',
})
export class EligibilityModalComponent implements OnInit {
  private readonly eligibilityService = inject(EligibilityService);
  private readonly router = inject(Router);

  @Input({ required: true }) scheme!: SearchResultItem;
  @Output() close = new EventEmitter<void>();

  evaluating = signal<boolean>(false);
  result = signal<EligibilityResult | null>(null);
  error = signal<string | null>(null);

  ngOnInit(): void {
    // Auto-check eligibility when modal opens
    this.checkEligibility();
  }

  checkEligibility(): void {
    this.evaluating.set(true);
    this.error.set(null);
    this.result.set(null);

    this.eligibilityService.checkSchemeEligibility(this.scheme.id).subscribe({
      next: (res) => {
        this.result.set(res);
        this.evaluating.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to check eligibility');
        this.evaluating.set(false);
      },
    });
  }

  onModifyProfile(): void {
    this.router.navigate(['/citizen-profile']);
  }

  onClose(): void {
    this.close.emit();
  }
}
