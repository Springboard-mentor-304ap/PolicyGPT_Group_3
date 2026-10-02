import {
  Component,
  ElementRef,
  Input,
  OnInit,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ControlValueAccessor,
  FormsModule,
  NG_VALUE_ACCESSOR,
} from '@angular/forms';

import { DepartmentService } from '../../../core/services/department.service';
import { InputComponent } from '../input/input.component';
import { SelectComponent, SelectOption } from '../select/select.component';

/** Sentinel option that reveals the free-text department field. */
export const DEPARTMENT_OTHERS_VALUE = '__others__';

/**
 * Department picker backed by the department values that already exist in the
 * platform data, plus an OTHERS entry.
 *
 * `department` stays a plain string on the backend: selecting an existing
 * option submits that exact value, while OTHERS reveals a required text input
 * whose value is submitted through the same field. Editing a record whose
 * department is not in the list selects OTHERS and pre-fills the input, so no
 * stored value is ever dropped. Used with `formControlName`, this behaves as
 * a single string control.
 */
@Component({
  selector: 'app-department-select',
  standalone: true,
  imports: [CommonModule, FormsModule, InputComponent, SelectComponent],
  templateUrl: './department-select.component.html',
  styleUrl: './department-select.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DepartmentSelectComponent),
      multi: true,
    },
  ],
})
export class DepartmentSelectComponent implements ControlValueAccessor, OnInit {
  private readonly departmentService = inject(DepartmentService);
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  @Input() label = 'Department';
  @Input() id = 'department';
  @Input() name = 'department';
  @Input() required = false;
  @Input() disabled = false;
  @Input() error: string | null = null;
  @Input() hint: string | null = null;
  @Input() placeholder = 'Select department';
  @Input() customLabel = 'Department name';
  @Input() customPlaceholder = 'Enter department name';
  /** Report filters only match existing values, so they hide the OTHERS entry. */
  @Input() allowOthers = true;

  /** Department values returned by the API. */
  readonly knownOptions = signal<string[]>([]);
  /** Current dropdown state: '', an existing department, or the OTHERS entry. */
  readonly selection = signal('');
  /** Free-text value, only meaningful while OTHERS is selected. */
  readonly customValue = signal('');
  readonly optionsFailed = signal(false);

  private lastModelValue = '';

  onChange: (value: string) => void = () => {};
  onTouched: () => void = () => {};

  get options(): SelectOption[] {
    const departments = this.knownOptions().map((department) => ({
      value: department,
      label: department,
    }));

    if (!this.allowOthers) {
      return departments;
    }

    return [...departments, { value: DEPARTMENT_OTHERS_VALUE, label: 'OTHERS' }];
  }

  get isOthers(): boolean {
    return this.selection() === DEPARTMENT_OTHERS_VALUE;
  }

  /** OTHERS validation takes precedence over the form's own message. */
  get displayError(): string | null {
    if (this.isOthers && !this.customValue().trim()) {
      return 'Department name is required when OTHERS is selected';
    }

    return this.error;
  }

  ngOnInit(): void {
    this.departmentService.listDepartments().subscribe({
      next: (departments) => {
        this.knownOptions.set(departments);
        this.syncSelection();
        this.reapplySelectionToDom();
      },
      error: () => {
        // The dropdown still works; only the option list is missing.
        this.optionsFailed.set(true);
        this.syncSelection();
        this.reapplySelectionToDom();
      },
    });
  }

  /**
   * Re-assert the selected value once the option list is in the DOM.
   *
   * The dropdown value is applied while the freshly fetched <option> elements
   * are still being rendered, and a value set before its option exists makes
   * the browser fall back to the first option (the disabled placeholder means
   * that is the first real department). Re-applying it after the render keeps
   * an edited record's stored department selected instead of silently
   * switching it to another department.
   */
  private reapplySelectionToDom(): void {
    requestAnimationFrame(() => {
      const select: HTMLSelectElement | null =
        this.elementRef.nativeElement.querySelector('select');
      const value = this.selection();

      if (select && value && select.value !== value) {
        select.value = value;
      }
    });
  }

  writeValue(value: string | null): void {
    this.lastModelValue = value ?? '';
    this.syncSelection();
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

  onSelectChange(value: string): void {
    this.onTouched();

    if (value === DEPARTMENT_OTHERS_VALUE) {
      this.selection.set(DEPARTMENT_OTHERS_VALUE);
      // An empty custom value clears the control, so the form's own required
      // validation keeps the submission blocked until a name is typed.
      this.commit(this.customValue().trim());
      return;
    }

    this.selection.set(value);
    this.customValue.set('');
    this.commit(value);
  }

  onCustomInput(value: string): void {
    this.customValue.set(value);
    this.commit(value.trim());
  }

  /**
   * Derive the dropdown state from the model value.
   *
   * This also runs once the option list arrives, so a value written before the
   * options were known is classified correctly instead of being mistaken for a
   * custom department.
   */
  private syncSelection(): void {
    const value = this.lastModelValue;

    if (!value) {
      this.selection.set('');
      this.customValue.set('');
      return;
    }

    if (this.knownOptions().includes(value)) {
      this.selection.set(value);
      this.customValue.set('');
      return;
    }

    this.selection.set(DEPARTMENT_OTHERS_VALUE);
    this.customValue.set(value);
  }

  private commit(value: string): void {
    this.lastModelValue = value;
    this.onChange(value);
  }
}
