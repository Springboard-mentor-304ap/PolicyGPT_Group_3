import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { EligibilityResult } from '../../../../core/models/eligibility.models';
import { BadgeComponent } from '../../../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../../../shared/components/button/button.component';

@Component({
  selector: 'app-eligibility-result',
  standalone: true,
  imports: [CommonModule, ButtonComponent],
  templateUrl: './eligibility-result.component.html',
  styleUrl: './eligibility-result.component.css',
})
export class EligibilityResultComponent {
  @Input({ required: true }) result!: EligibilityResult;

  @Output() recheck = new EventEmitter<void>();
  @Output() apply = new EventEmitter<EligibilityResult>();

  onRecheck(): void {
    this.recheck.emit();
  }

  onApply(): void {
    this.apply.emit(this.result);
  }
}
