import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { SearchResultItem } from '../../../../core/models/search.models';
import { BadgeComponent } from '../../../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../../../shared/components/button/button.component';
import { ComparisonService } from '../../../../core/services/comparison.service';

@Component({
  selector: 'app-policy-card',
  standalone: true,
  imports: [CommonModule, BadgeComponent, ButtonComponent],
  templateUrl: './policy-card.component.html',
  styleUrl: './policy-card.component.css',
})
export class PolicyCardComponent {
  readonly comparisonService = inject(ComparisonService);

  @Input({ required: true }) item!: SearchResultItem;

  @Output() checkEligibility = new EventEmitter<SearchResultItem>();
  @Output() viewDetails = new EventEmitter<SearchResultItem>();

  onViewDetails(): void {
    this.viewDetails.emit(this.item);
  }

  onCheckEligibility(): void {
    this.checkEligibility.emit(this.item);
  }

  onToggleCompare(): void {
    this.comparisonService.toggleItem(this.item);
  }

  get isComparing(): boolean {
    return this.comparisonService.isSelected(this.item.id);
  }

  get statusVariant(): 'success' | 'warning' | 'info' | 'neutral' {
    const s = this.item.status.toLowerCase();
    if (s === 'active' || s === 'approved') return 'success';
    if (s === 'draft' || s === 'pending') return 'warning';
    return 'neutral';
  }
}
