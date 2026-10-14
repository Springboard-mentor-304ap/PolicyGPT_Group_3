import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subject, Subscription, debounceTime, distinctUntilChanged } from 'rxjs';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './search-bar.component.html',
  styleUrl: './search-bar.component.css',
})
export class SearchBarComponent implements OnInit, OnDestroy {
  @Input() query = '';
  @Input() placeholder = 'Search policies, welfare schemes, grants, or departments...';
  @Input() debounceMs = 350;

  @Output() search = new EventEmitter<string>();
  @Output() clear = new EventEmitter<void>();

  private readonly searchSubject = new Subject<string>();
  private sub?: Subscription;

  ngOnInit(): void {
    this.sub = this.searchSubject
      .pipe(debounceTime(this.debounceMs), distinctUntilChanged())
      .subscribe((val) => {
        this.search.emit(val.trim());
      });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  onInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.query = input.value;
    this.searchSubject.next(this.query);
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this.search.emit(this.query.trim());
    }
  }

  onClear(): void {
    this.query = '';
    this.searchSubject.next('');
    this.clear.emit();
  }

  onSubmit(): void {
    this.search.emit(this.query.trim());
  }
}
