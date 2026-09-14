import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-skeleton',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './skeleton.component.html',
  styleUrl: './skeleton.component.css',
})
export class SkeletonComponent {
  @Input() type: 'card' | 'text' | 'table-row' | 'badge' = 'card';
  @Input() count = 1;

  get countArray(): number[] {
    return Array.from({ length: this.count }, (_, i) => i);
  }
}
