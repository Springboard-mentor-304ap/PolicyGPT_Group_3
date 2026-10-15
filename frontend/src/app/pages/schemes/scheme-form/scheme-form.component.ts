import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import {
  AbstractControl,
  FormBuilder,
  FormArray,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { forkJoin } from 'rxjs';
import { SchemeService } from '../../../core/services/scheme.service';
import { PolicyService } from '../../../core/services/policy.service';
import { AuthService } from '../../../core/services/auth.service';
import { Policy, PolicyStatus } from '../../../core/models/policy.models';
import { UserRole } from '../../../core/models/auth.models';
import {
  SchemeCategory,
  SCHEME_CATEGORY_LABELS,
  SchemeCreateRequest,
  SchemeUpdateRequest,
  EligibilityParameter,
  EligibilityOperator,
  ELIGIBILITY_PARAMETER_LABELS,
  ELIGIBILITY_OPERATOR_LABELS,
  ELIGIBILITY_OPERATORS_BY_PARAMETER,
  ELIGIBILITY_RULE_OPTIONS,
  EligibilityRuleOption,
} from '../../../core/models/scheme.models';
import { ButtonComponent } from '../../../shared/components/button/button.component';
import { DepartmentSelectComponent } from '../../../shared/components/department-select/department-select.component';
import { StateSelectComponent } from '../../../shared/components/state-select/state-select.component';
import { INDIAN_STATES_AND_UTS } from '../../../shared/components/state-select/indian-states';
import { BackToDashboardComponent } from '../../../shared/components/back-to-dashboard/back-to-dashboard.component';

/**
 * How a rule's value is entered for the selected parameter and operator.
 *
 * `number` – one non-negative number (age, income).
 * `text`   – one free-text value, or a comma-separated list for the
 *            multi-value operators (occupation, district).
 * `select` – a dropdown of the parameter's canonical values.
 * `state`  – the searchable state / Union Territory picker.
 * `multi`  – checkboxes over the parameter's canonical values.
 */
type RuleControlKind = 'number' | 'text' | 'select' | 'state' | 'multi';

/** `eligibility_rules.value` is a VARCHAR(255) column; no migration wanted. */
const MAX_RULE_VALUE_LENGTH = 255;

/** Operators whose value is a comma-separated list rather than one value. */
const MULTI_VALUE_OPERATORS: EligibilityOperator[] = [
  EligibilityOperator.IN,
  EligibilityOperator.NOT_IN,
];

const STATE_OPTIONS: EligibilityRuleOption[] = INDIAN_STATES_AND_UTS.map(
  (name) => ({ value: name, label: name }),
);

interface RuleParameterConfig {
  /** Control used when the operator takes a single value. */
  control: 'number' | 'text' | 'select' | 'state';
  /** Canonical values; empty means the parameter is free text. */
  options: EligibilityRuleOption[];
  placeholder: string;
  hint: string;
}

/**
 * Field-aware configuration: the value control and the option set each
 * parameter uses. The operators themselves come from
 * `ELIGIBILITY_OPERATORS_BY_PARAMETER` (kept next to the enums so it can be
 * compared against the backend matrix in one place).
 */
const RULE_PARAMETER_CONFIG: Record<EligibilityParameter, RuleParameterConfig> = {
  [EligibilityParameter.AGE]: {
    control: 'number',
    options: [],
    placeholder: 'e.g. 18',
    hint: 'Whole number of years, 0 or more',
  },
  [EligibilityParameter.INCOME]: {
    control: 'number',
    options: [],
    placeholder: 'e.g. 500000',
    hint: 'Annual income in ₹, 0 or more',
  },
  [EligibilityParameter.GENDER]: {
    control: 'select',
    options: ELIGIBILITY_RULE_OPTIONS[EligibilityParameter.GENDER] ?? [],
    placeholder: 'Select gender',
    hint: '',
  },
  [EligibilityParameter.OCCUPATION]: {
    control: 'text',
    options: [],
    placeholder: 'e.g. Farmer',
    hint: 'Free text, matched case-insensitively against the profile value.',
  },
  [EligibilityParameter.EDUCATION]: {
    control: 'select',
    options: ELIGIBILITY_RULE_OPTIONS[EligibilityParameter.EDUCATION] ?? [],
    placeholder: 'Select education level',
    hint: '',
  },
  [EligibilityParameter.STATE]: {
    control: 'state',
    options: STATE_OPTIONS,
    placeholder: 'Select a state or Union Territory',
    hint: '',
  },
  [EligibilityParameter.DISTRICT]: {
    control: 'text',
    options: [],
    placeholder: 'e.g. Mysuru',
    hint: 'Free text — no district list exists yet, so type it as citizens do.',
  },
  [EligibilityParameter.SOCIAL_CATEGORY]: {
    control: 'select',
    options: ELIGIBILITY_RULE_OPTIONS[EligibilityParameter.SOCIAL_CATEGORY] ?? [],
    placeholder: 'Select social category',
    hint: '',
  },
  [EligibilityParameter.DISABILITY_STATUS]: {
    control: 'select',
    options: ELIGIBILITY_RULE_OPTIONS[EligibilityParameter.DISABILITY_STATUS] ?? [],
    placeholder: 'Select yes or no',
    hint: '',
  },
};

function isMultiValueOperator(
  operator: EligibilityOperator | null | undefined,
): boolean {
  return MULTI_VALUE_OPERATORS.includes(operator as EligibilityOperator);
}

/** Split a stored rule value into entries; blanks are kept for validation. */
function splitRuleValue(value: string): string[] {
  if (!value.includes(',')) {
    return [value];
  }

  return value.split(',').map((entry) => entry.trim());
}

function isNonNegativeNumber(entry: string, wholeNumberOnly: boolean): boolean {
  // Rejected on purpose: signs, exponents and decimals for age. The backend
  // parses age with `int()` and income with `Decimal()`, so anything this
  // refuses would be refused there too.
  if (wholeNumberOnly) {
    return /^\d+$/.test(entry);
  }

  if (!/^\d+(\.\d+)?$/.test(entry)) {
    return false;
  }

  return Number.isFinite(Number(entry));
}

/** Validate a rule's value the way the backend will, before it is sent. */
function validateRuleValue(
  parameter: EligibilityParameter,
  operator: EligibilityOperator,
  raw: unknown,
): ValidationErrors | null {
  const value =
    typeof raw === 'number' ? String(raw) : String(raw ?? '').trim();

  if (!value) {
    return { valueRequired: true };
  }

  if (value.length > MAX_RULE_VALUE_LENGTH) {
    return { valueTooLong: true };
  }

  const config = RULE_PARAMETER_CONFIG[parameter];

  if (!config) {
    return { unknownParameter: true };
  }

  const entries = isMultiValueOperator(operator)
    ? splitRuleValue(value)
    : [value];

  if (entries.some((entry) => !entry)) {
    return { invalidList: true };
  }

  if (config.control === 'number') {
    const wholeNumbers = parameter === EligibilityParameter.AGE;

    if (entries.some((entry) => !isNonNegativeNumber(entry, wholeNumbers))) {
      return { invalidNumber: true, integerOnly: wholeNumbers };
    }

    return null;
  }

  if (config.options.length) {
    const allowed = new Set(
      config.options.map((option) => option.value.toLowerCase()),
    );

    if (entries.some((entry) => !allowed.has(entry.toLowerCase()))) {
      return { notInOptions: true };
    }
  }

  return null;
}

/**
 * Group validator for one rule row: field + operator + value must be a
 * combination the backend's `PARAMETER_OPERATOR_COMPATIBILITY` accepts.
 */
const eligibilityRuleValidator: ValidatorFn = (
  control: AbstractControl,
): ValidationErrors | null => {
  const group = control as FormGroup;
  const parameter = group.get('parameter')?.value as EligibilityParameter | null;
  const operator = group.get('operator')?.value as EligibilityOperator | null;

  if (!parameter) {
    return { parameterRequired: true };
  }

  const allowed = ELIGIBILITY_OPERATORS_BY_PARAMETER[parameter];

  if (!allowed || !operator || !allowed.includes(operator)) {
    return { operatorNotAllowed: true };
  }

  return validateRuleValue(parameter, operator, group.get('value')?.value);
};

@Component({
  selector: 'app-scheme-form',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    ButtonComponent,
    DepartmentSelectComponent,
    StateSelectComponent,
    BackToDashboardComponent,
  ],
  templateUrl: './scheme-form.component.html',
  styleUrl: './scheme-form.component.css',
})
export class SchemeFormComponent implements OnInit {
  private readonly schemeService = inject(SchemeService);
  private readonly policyService = inject(PolicyService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly fb = inject(FormBuilder);

  /**
   * Department/ministry a government official is limited to. The API rejects
   * a scheme outside this scope, so the form pre-fills and locks it instead
   * of letting the user fill in something that cannot be saved.
   */
  readonly officialScope = signal<string | null>(null);
  readonly isGovernmentOfficial = computed(
    () => this.authService.userRole() === UserRole.GOVERNMENT_OFFICIAL
  );

  readonly isEditMode = signal(false);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly success = signal<string | null>(null);
  readonly policies = signal<Policy[]>([]);
  readonly policiesLoading = signal(false);
  private schemeId: string | null = null;

  readonly categories = Object.values(SchemeCategory).map((c) => ({
    value: c,
    label: SCHEME_CATEGORY_LABELS[c],
  }));
  readonly eligibilityParameters = Object.values(EligibilityParameter).map((value) => ({ value, label: ELIGIBILITY_PARAMETER_LABELS[value] }));

  /** Set once a submit has been attempted, so invalid rule rows show why. */
  readonly submitted = signal(false);

  schemeForm: FormGroup = this.fb.group({
    policy_id: ['', Validators.required],
    title: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(255)]],
    description: ['', [Validators.required, Validators.minLength(1)]],
    category: ['', Validators.required],
    benefits: [''],
    application_process: [''],
    department: [''],
    state: [''],
    required_documents: [''],
    launch_date: [''],
    deadline_date: [''],
    document_url: [''],
    eligibilityRules: this.fb.array([]),
  });

  get eligibilityRules(): FormArray {
    return this.schemeForm.get('eligibilityRules') as FormArray;
  }

  addEligibilityRule(): void {
    // The group validator keeps field/operator/value consistent with the
    // backend matrix, so an impossible rule never reaches the API.
    const group = this.fb.group(
      {
        parameter: [EligibilityParameter.AGE, Validators.required],
        operator: [EligibilityOperator.GTE, Validators.required],
        value: ['', Validators.required],
      },
      { validators: eligibilityRuleValidator },
    );

    // No programmatic markAsTouched here: every value control marks the row
    // touched when the user actually interacts with it (blur), while the
    // resets below stay silent — changing a field does not instantly flag
    // its not-yet-filled value as an error. `ruleError` also honours the
    // submitted flag for the case where nobody touched the row.
    group
      .get('parameter')
      ?.valueChanges.subscribe(() => this.onParameterChange(group));
    group
      .get('operator')
      ?.valueChanges.subscribe(() => this.onOperatorChange(group));

    this.eligibilityRules.push(group);
  }

  removeEligibilityRule(index: number): void {
    this.eligibilityRules.removeAt(index);
  }

  // ── Field-aware rule row ─────────────────────────────────────────────
  /** The rule group at `index`, or null when the row is already gone. */
  private ruleAt(index: number): FormGroup | null {
    const control = this.eligibilityRules.at(index);

    return control instanceof FormGroup ? control : null;
  }

  private parameterAt(index: number): EligibilityParameter {
    return (
      this.ruleAt(index)?.get('parameter')?.value ?? EligibilityParameter.AGE
    ) as EligibilityParameter;
  }

  private operatorAt(index: number): EligibilityOperator {
    return (
      this.ruleAt(index)?.get('operator')?.value ?? EligibilityOperator.EQ
    ) as EligibilityOperator;
  }

  private configAt(index: number): RuleParameterConfig {
    return (
      RULE_PARAMETER_CONFIG[this.parameterAt(index)] ??
      RULE_PARAMETER_CONFIG[EligibilityParameter.AGE]
    );
  }

  parameterLabel(index: number): string {
    return ELIGIBILITY_PARAMETER_LABELS[this.parameterAt(index)];
  }

  /** Only the operators the backend accepts for this row's field. */
  operatorsFor(index: number): EligibilityRuleOption[] {
    return (ELIGIBILITY_OPERATORS_BY_PARAMETER[this.parameterAt(index)] ?? [])
      .map((value) => ({ value, label: ELIGIBILITY_OPERATOR_LABELS[value] }));
  }

  /** Which control renders this row's value. */
  controlFor(index: number): RuleControlKind {
    const config = this.configAt(index);

    if (isMultiValueOperator(this.operatorAt(index))) {
      return config.options.length ? 'multi' : 'text';
    }

    return config.control;
  }

  optionsFor(index: number): EligibilityRuleOption[] {
    return this.configAt(index).options;
  }

  placeholderFor(index: number): string {
    const config = this.configAt(index);

    if (isMultiValueOperator(this.operatorAt(index)) && !config.options.length) {
      return 'Comma-separated, e.g. Engineer, Teacher';
    }

    return config.placeholder;
  }

  hintFor(index: number): string | null {
    const config = this.configAt(index);

    if (isMultiValueOperator(this.operatorAt(index))) {
      return config.options.length
        ? 'Select every value that matches.'
        : 'Separate each value with a comma.';
    }

    return config.hint || null;
  }

  /** Step for the number input: whole years for age, decimals for income. */
  stepFor(index: number): string {
    return this.parameterAt(index) === EligibilityParameter.AGE ? '1' : 'any';
  }

  /** Current multi-value selection of a row. */
  private selectedFor(index: number): Set<string> {
    const raw = String(this.ruleAt(index)?.get('value')?.value ?? '');

    return new Set(splitRuleValue(raw).filter(Boolean));
  }

  isSelected(index: number, optionValue: string): boolean {
    return this.selectedFor(index).has(optionValue);
  }

  /** Add or remove one checkbox, storing the list in the option order. */
  toggleOption(index: number, optionValue: string, checked: boolean): void {
    const valueControl = this.ruleAt(index)?.get('value');

    if (!valueControl) {
      return;
    }

    const selected = this.selectedFor(index);

    if (checked) {
      selected.add(optionValue);
    } else {
      selected.delete(optionValue);
    }

    // Storing the list in option order keeps the saved value stable and
    // readable instead of depending on the order boxes were ticked.
    const ordered = this.optionsFor(index)
      .filter((option) => selected.has(option.value))
      .map((option) => option.value);

    valueControl.setValue(ordered.join(','));
    valueControl.markAsDirty();
  }

  /** Human-readable reason a rule row is invalid, or null when it is fine. */
  ruleError(index: number): string | null {
    const group = this.ruleAt(index);

    if (!group || group.valid) {
      return null;
    }

    // Visible once somebody actually worked on this row (any of its own
    // controls was touched or changed) or a submit was attempted. Read from
    // the leaf controls rather than the group so the message does not depend
    // on touched/dirty propagating upward.
    const engaged = ['parameter', 'operator', 'value'].some((name) => {
      const child = group.get(name);
      return !!child && (child.touched || child.dirty);
    });

    if (!engaged && !this.submitted()) {
      return null;
    }

    const errors: ValidationErrors = {
      ...(group.get('value')?.errors ?? {}),
      ...(group.errors ?? {}),
    };

    if (errors['parameterRequired']) {
      return 'Select a field for this rule.';
    }
    if (errors['operatorNotAllowed']) {
      return 'That comparison does not apply to the selected field.';
    }
    if (errors['valueRequired'] || errors['required']) {
      return 'Enter or select a value for this rule.';
    }
    if (errors['valueTooLong']) {
      return (
        `Rule values are limited to ${MAX_RULE_VALUE_LENGTH} characters — ` +
        'select fewer values.'
      );
    }
    if (errors['invalidList']) {
      return 'Separate values with commas, with no blank entries.';
    }
    if (errors['invalidNumber']) {
      return errors['integerOnly']
        ? 'Age must be a whole number of 0 or more.'
        : 'Enter a number of 0 or more.';
    }
    if (errors['notInOptions']) {
      return 'Choose one of the listed values.';
    }
    if (errors['min'] || errors['max']) {
      return 'Enter a number of 0 or more.';
    }

    return 'This rule is incomplete.';
  }

  /** Field changed: keep a compatible operator, always drop the old value. */
  private onParameterChange(group: FormGroup): void {
    const parameter = group.get('parameter')?.value as EligibilityParameter;
    const operatorControl = group.get('operator');
    const valueControl = group.get('value');

    if (!operatorControl || !valueControl) {
      return;
    }

    // Clear first so the operator reset below cannot re-run
    // `onOperatorChange` against a stale value.
    // The old value described the previous field's type or option set, so it
    // is never safe to carry over. Emission stays on: the value controls are
    // custom components that only re-render from valueChanges, and the row
    // has not been touched yet, so no error appears here.
    valueControl.setValue('');

    const allowed = ELIGIBILITY_OPERATORS_BY_PARAMETER[parameter] ?? [];

    if (!allowed.includes(operatorControl.value)) {
      operatorControl.setValue(allowed[0] ?? EligibilityOperator.EQ);
    }
  }

  /**
   * Operator changed: keep the value when it still fits the new control and
   * clear it when it does not — a list cannot become a single value, and a
   * value outside the field's option set cannot be kept.
   */
  private onOperatorChange(group: FormGroup): void {
    const parameter = group.get('parameter')?.value as EligibilityParameter;
    const operator = group.get('operator')?.value as EligibilityOperator;
    const valueControl = group.get('value');

    if (!valueControl) {
      return;
    }

    const raw = String(valueControl.value ?? '').trim();

    if (!raw) {
      return;
    }

    const entries = splitRuleValue(raw).filter(Boolean);
    const config = RULE_PARAMETER_CONFIG[parameter];
    const allowedValues = new Set(
      (config?.options ?? []).map((option) => option.value),
    );

    const kept = isMultiValueOperator(operator)
      ? config?.options.length
        ? entries.filter((entry) => allowedValues.has(entry))
        : entries
      : entries.length === 1
        ? entries
        : [];

    const next = kept.join(',');

    if (next !== String(valueControl.value ?? '').trim()) {
      valueControl.setValue(next);
    }
  }

  ngOnInit(): void {
    this.loadApprovedPolicies();
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.schemeId = id;
      this.isEditMode.set(true);
      this.loadScheme(id);
    }

    this.loadOfficialScope();
  }

  /**
   * New schemes are created inside the official's own department, so the form
   * pre-fills the scope. Editing keeps the record's stored value.
   */
  private loadOfficialScope(): void {
    if (!this.isGovernmentOfficial()) {
      return;
    }

    this.authService.getGovernmentOfficialProfile().subscribe({
      next: (profile) => {
        this.officialScope.set(profile.department);

        if (!this.isEditMode()) {
          this.schemeForm.patchValue({ department: profile.department });
        }
      },
      error: (error) => {
        this.officialScope.set(null);

        if (!this.isEditMode()) {
          this.error.set(
            error?.error?.detail ||
              'Your department could not be loaded, so a scheme cannot be created right now.'
          );
        }
      },
    });
  }

  /** Officials always file inside their scope, so the field is locked. */
  isOfficialScopeLocked(): boolean {
    return this.isGovernmentOfficial() && !!this.officialScope();
  }

  get scopeHint(): string {
    const scope = this.officialScope();

    return scope ? `Locked to your department/ministry: ${scope}` : '';
  }

  loadApprovedPolicies(): void {
    this.policiesLoading.set(true);
    this.policyService.listPolicies().subscribe({
      next: (policies) => {
        this.policies.set(policies.filter((policy) => policy.status === PolicyStatus.APPROVED));
        this.policiesLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load approved policies');
        this.policiesLoading.set(false);
      },
    });
  }

  loadScheme(id: string): void {
    this.loading.set(true);
    this.schemeService.getScheme(id).subscribe({
      next: (scheme) => {
        this.schemeForm.patchValue({
          policy_id: scheme.policy_id,
          title: scheme.title,
          description: scheme.description,
          category: scheme.category,
          benefits: Array.isArray(scheme.benefits) ? scheme.benefits.join('\n') : '',
          application_process: scheme.application_process || '',
          department: scheme.department || '',
          state: scheme.state || '',
          required_documents: Array.isArray(scheme.required_documents) ? scheme.required_documents.join('\n') : '',
          launch_date: scheme.launch_date || '',
          deadline_date: scheme.deadline_date || '',
          document_url: scheme.document_url || '',
        });
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'Failed to load scheme');
        this.loading.set(false);
      },
    });
  }

  onSubmit(): void {
    this.submitted.set(true);

    if (this.schemeForm.invalid) {
      this.schemeForm.markAllAsTouched();

      if (this.eligibilityRules.invalid) {
        this.error.set(
          'Some eligibility rules are incomplete or invalid — check the highlighted rows.'
        );
      }

      return;
    }

    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);

    const formValue = this.schemeForm.value;

    // Parse comma/newline separated strings into arrays
    const parseList = (val: string): string[] | null => {
      if (!val || !val.trim()) return null;
      return val.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    };

    if (this.isEditMode() && this.schemeId) {
      const data: SchemeUpdateRequest = {
        title: formValue.title,
        description: formValue.description,
        category: formValue.category,
        benefits: parseList(formValue.benefits),
        application_process: formValue.application_process || null,
        department: formValue.department || null,
        state: formValue.state || null,
        required_documents: parseList(formValue.required_documents),
        launch_date: formValue.launch_date || null,
        deadline_date: formValue.deadline_date || null,
        document_url: formValue.document_url || null,
      };

      this.schemeService.updateScheme(this.schemeId, data).subscribe({
        next: () => {
          this.saving.set(false);
          this.success.set('Scheme updated successfully');
          setTimeout(() => this.router.navigate(['/schemes', this.schemeId]), 1000);
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to update scheme');
          this.saving.set(false);
        },
      });
    } else {
      const data: SchemeCreateRequest = {
        policy_id: formValue.policy_id,
        title: formValue.title,
        description: formValue.description,
        category: formValue.category,
        benefits: parseList(formValue.benefits),
        application_process: formValue.application_process || null,
        department: formValue.department || null,
        state: formValue.state || null,
        required_documents: parseList(formValue.required_documents),
        launch_date: formValue.launch_date || null,
        deadline_date: formValue.deadline_date || null,
        document_url: formValue.document_url || null,
      };

      this.schemeService.createScheme(data).subscribe({
        next: (scheme) => {
          const rules = this.eligibilityRules.getRawValue().map((rule) => ({
            parameter: rule.parameter,
            operator: rule.operator,
            // The value control can hand back a number; the API stores the
            // string form (`eligibility_rules.value` is a VARCHAR column).
            value: String(rule.value ?? '').trim(),
          }));

          if (!rules.length) {
            this.finishCreation(scheme.id);
            return;
          }
          forkJoin(rules.map((rule) => this.schemeService.createEligibilityRule(scheme.id, rule))).subscribe({
            next: () => this.finishCreation(scheme.id),
            error: (err) => {
              this.error.set(err.error?.detail || 'Scheme was created, but its eligibility rules could not be saved. You can add them from the scheme page.');
              this.saving.set(false);
            },
          });
        },
        error: (err) => {
          this.error.set(err.error?.detail || 'Failed to create scheme');
          this.saving.set(false);
        },
      });
    }
  }

  private finishCreation(schemeId: string): void {
    this.saving.set(false);
    this.success.set('Scheme and eligibility rules created successfully');
    setTimeout(() => this.router.navigate(['/schemes', schemeId]), 1000);
  }

  cancel(): void {
    if (this.isEditMode() && this.schemeId) {
      this.router.navigate(['/schemes', this.schemeId]);
    } else {
      this.router.navigate(['/schemes']);
    }
  }

  goBack(): void {
    this.router.navigate(['/schemes']);
  }

}
