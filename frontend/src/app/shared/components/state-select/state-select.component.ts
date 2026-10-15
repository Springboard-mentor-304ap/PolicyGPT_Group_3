import {
  Component,
  ElementRef,
  Input,
  ViewChild,
  forwardRef,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

import { INDIAN_STATES_AND_UTS } from './indian-states';

/**
 * Searchable dropdown for Indian states and Union Territories.
 *
 * Replaces the free-text `state` inputs: typing filters the 36 options and
 * clicking (or pressing Enter) selects one. The control keeps working with
 * `formControlName` as a plain string control, so the API field name
 * (`state`) and the stored value (the state name) are unchanged; a stored
 * value that is not in the list (legacy free-text data) is still shown and
 * submitted as-is instead of being dropped.
 */
@Component({
  selector: 'app-state-select',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './state-select.component.html',
  styleUrl: './state-select.component.css',
  // `id` belongs on the inner <input> so the rendered <label for> points at
  // it; leaving the attribute on the host as well would create duplicate ids
  // (same convention as app-select).
  host: { '[attr.id]': 'null' },
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => StateSelectComponent),
      multi: true,
    },
  ],
})
export class StateSelectComponent implements ControlValueAccessor {
  @ViewChild('searchInput') searchInput?: ElementRef<HTMLInputElement>;

  @Input() label = 'State';
  @Input() id = '';
  @Input() name = '';
  @Input() placeholder = 'Select a state or Union Territory';
  @Input() searchPlaceholder = 'Type to search…';
  @Input() required = false;
  @Input() disabled = false;
  @Input() error: string | null = null;
  @Input() hint: string | null = null;

  /** Options: the 28 states followed by the 8 Union Territories. */
  readonly options: string[] = INDIAN_STATES_AND_UTS;

  readonly open = signal(false);
  /** Live search text; empty string means "show the selected value". */
  readonly query = signal('');
  /** Selected option — exactly what is submitted to the API. */
  readonly selected = signal('');

  highlightIndex = 0;

  onChange: (value: string) => void = () => {};
  onTouched: (value: string) => void = () => {};

  /** Options matching the current query (case-insensitive substring). */
  get filtered(): string[] {
    const q = this.query().trim().toLowerCase();

    if (!q) {
      return this.options;
    }

    return this.options.filter((option) =>
      option.toLowerCase().includes(q)
    );
  }

  /** Text shown in the input: what is being typed, else the selection. */
  get display(): string {
    return this.query() !== '' ? this.query() : this.selected();
  }

  writeValue(value: string | null): void {
    this.selected.set(value ?? '');
    this.query.set('');
    this.close();
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: (value: string) => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
    if (isDisabled) {
      this.close();
    }
  }

  openList(): void {
    if (this.disabled) {
      return;
    }
    this.open.set(true);
    this.highlightIndex = Math.max(
      0,
      this.filtered.indexOf(this.selected())
    );
  }

  toggleOpen(): void {
    if (this.disabled) {
      return;
    }
    if (this.open()) {
      this.close();
    } else {
      this.openList();
      this.searchInput?.nativeElement.focus();
    }
  }

  onInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.query.set(value);
    this.open.set(true);
    this.highlightIndex = 0;
  }

  onBlur(): void {
    // Typing only filters: commit nothing, restore the field to the stored
    // value so an in-progress query can never leak into the form model.
    this.query.set('');
    this.close();
    this.onTouched(this.selected());
  }

  onKeydown(event: KeyboardEvent): void {
    switch (event.key) {
      case 'ArrowDown':
        if (!this.open()) {
          this.openList();
        } else {
          this.highlightIndex = Math.min(
            this.highlightIndex + 1,
            this.filtered.length - 1
          );
        }
        event.preventDefault();
        break;
      case 'ArrowUp':
        if (this.open()) {
          this.highlightIndex = Math.max(this.highlightIndex - 1, 0);
        }
        event.preventDefault();
        break;
      case 'Enter':
        if (this.open() && this.filtered.length > 0) {
          this.select(this.filtered[this.highlightIndex]);
        }
        event.preventDefault();
        break;
      case 'Escape':
        this.close();
        break;
    }
  }

  select(option: string): void {
    this.selected.set(option);
    this.query.set('');
    this.close();
    this.onChange(option);
    this.onTouched(option);
    this.searchInput?.nativeElement.focus();
  }

  clear(event?: Event): void {
    event?.preventDefault();
    this.selected.set('');
    this.query.set('');
    this.onChange('');
    this.onTouched('');
    this.searchInput?.nativeElement.focus();
  }

  /** Keep mousedown on options/buttons from stealing focus (blur closes). */
  keepFocus(event: Event): void {
    event.preventDefault();
  }

  private close(): void {
    this.open.set(false);
    this.highlightIndex = 0;
  }
}
