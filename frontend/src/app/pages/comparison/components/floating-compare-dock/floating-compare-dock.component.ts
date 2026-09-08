import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ComparisonService } from '../../../../core/services/comparison.service';
import { ButtonComponent } from '../../../../shared/components/button/button.component';

@Component({
  selector: 'app-floating-compare-dock',
  standalone: true,
  imports: [CommonModule, ButtonComponent],
  templateUrl: './floating-compare-dock.component.html',
  styleUrl: './floating-compare-dock.component.css',
})
export class FloatingCompareDockComponent {
  readonly comparisonService = inject(ComparisonService);
  private readonly router = inject(Router);

  onRemoveItem(id: string, event: Event): void {
    event.stopPropagation();
    this.comparisonService.removeItem(id);
  }

  onClearAll(): void {
    this.comparisonService.clearAll();
  }

  onNavigateToCompare(): void {
    this.router.navigate(['/compare']);
  }
}
