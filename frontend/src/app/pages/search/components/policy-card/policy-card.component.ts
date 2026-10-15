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

  /**
   * The checkbox is disabled once the shared selection holds MAX_ITEMS
   * items or already contains the other resource type (the backend
   * compares one type per request) — removing still works, adding does
   * not. The caps themselves live in ComparisonService.
   */
  get canAddToCompare(): boolean {
    return (
      this.isComparing ||
      (!this.comparisonService.isFull() &&
        this.comparisonService.canAddType(this.item.itemType))
    );
  }

  get compareToggleTitle(): string {
    if (this.isComparing) {
      return 'Remove from comparison';
    }
    if (this.comparisonService.isFull()) {
      return `Comparison is full (${this.comparisonService.MAX_ITEMS} items) — remove one first`;
    }
    if (!this.comparisonService.canAddType(this.item.itemType)) {
      return 'Policies and schemes are compared separately — clear this selection first';
    }
    return 'Add to comparison';
  }

  get statusVariant(): 'success' | 'warning' | 'info' | 'neutral' {
    const s = this.item.status.toLowerCase();
    if (s === 'active' || s === 'approved') return 'success';
    if (s === 'draft' || s === 'pending') return 'warning';
    return 'neutral';
  }
}
