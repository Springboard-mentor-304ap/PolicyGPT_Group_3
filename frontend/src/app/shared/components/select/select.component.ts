import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  forwardRef,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

@Component({
  selector: 'app-select',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './select.component.html',
  styleUrl: './select.component.css',
  // `id` belongs on the inner <select> so the rendered <label for> points at it;
  // leaving the attribute on the host as well would create duplicate ids.
  host: { '[attr.id]': 'null' },
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectComponent),
      multi: true,
    },
  ],
})
export class SelectComponent implements ControlValueAccessor, AfterViewInit {
  @ViewChild('selectEl') selectEl?: ElementRef<HTMLSelectElement>;

  @Input() label = '';
  @Input() id = '';
  @Input() name = '';
  @Input() options: SelectOption[] = [];
  @Input() placeholder = 'Select an option';
  @Input() error: string | null = null;
  @Input() hint: string | null = null;
  @Input() required = false;
  @Input() disabled = false;
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
  @Input() value = '';

  @Output() selectionChange = new EventEmitter<string>();

  onChange: (value: string) => void = () => {};
  onTouched: () => void = () => {};

  writeValue(val: string): void {
    this.value = val ?? '';
  }

  /**
   * A value set before the first render (e.g. a reactive form filled from an
   * API response) is written while the options are still being created, so the
   * browser cannot select it yet. Re-apply it once the view exists.
   */
  ngAfterViewInit(): void {
    if (this.value && this.selectEl) {
      this.selectEl.nativeElement.value = this.value;
    }
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  handleChange(event: Event): void {
    const select = event.target as HTMLSelectElement;
    this.value = select.value;
    this.onChange(this.value);
    this.selectionChange.emit(this.value);
  }

  handleBlur(): void {
    this.onTouched();
  }
}
