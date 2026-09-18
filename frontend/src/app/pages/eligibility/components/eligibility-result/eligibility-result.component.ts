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

  @Output() modifyProfile = new EventEmitter<void>();
  @Output() apply = new EventEmitter<EligibilityResult>();

  onModifyProfile(): void {
    this.modifyProfile.emit();
  }

  onApply(): void {
    this.apply.emit(this.result);
  }
}
