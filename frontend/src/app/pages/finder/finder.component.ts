import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  FinderProfile,
  FinderResultGroup,
  SchemeMatch,
  SchemeMatchResponse,
} from '../../core/models/finder.models';
import { FinderService } from '../../core/services/finder.service';
import { BackToDashboardComponent } from '../../shared/components/back-to-dashboard/back-to-dashboard.component';
import { BadgeComponent } from '../../shared/components/badge/badge.component';
import { ButtonComponent } from '../../shared/components/button/button.component';
import { CardComponent } from '../../shared/components/card/card.component';
import { InputComponent } from '../../shared/components/input/input.component';
import { SelectComponent, SelectOption } from '../../shared/components/select/select.component';
import { StateSelectComponent } from '../../shared/components/state-select/state-select.component';
import {
  FinderBadgeVariant,
  FinderMatchCardComponent,
} from './components/finder-match-card/finder-match-card.component';

/** Longest description the backend accepts (ProfileExtractionRequest.text). */
const MAX_DESCRIPTION_LENGTH = 5000;

/** Age bounds accepted by the backend schema. */
const MAX_AGE = 120;

type FinderStep = 'input' | 'review' | 'results';

interface ResultSection {
  key: FinderResultGroup;
  title: string;
  shortLabel: string;
  description: string;
  badge: FinderBadgeVariant;
  statusLabel: string;
}

/**
 * The four backend verdicts, in the order they are rendered. Titles, copy and
 * badges are presentation only — the grouping itself comes straight from the
 * match response.
 */
const RESULT_SECTIONS: ResultSection[] = [
  {
    key: 'eligible',
    title: "You're eligible for these schemes",
    shortLabel: 'Eligible',
    description:
      'Your profile satisfies every eligibility criterion these schemes define.',
    badge: 'success',
    statusLabel: 'Eligible',
  },
  {
    key: 'more_information_required',
    title: 'More information required',
    shortLabel: 'Need more information',
    description:
      'We need a little more information before we can determine your eligibility.',
    badge: 'warning',
    statusLabel: 'More information required',
  },
  {
    key: 'not_eligible',
    title: 'Not eligible',
    shortLabel: 'Not eligible',
    description:
      'Your profile does not currently meet the eligibility criteria of these schemes.',
    badge: 'danger',
    statusLabel: 'Not eligible',
  },
  {
    key: 'no_criteria_defined',
    title: 'Eligibility criteria unavailable',
    shortLabel: 'Without criteria',
    description:
      'These schemes do not have eligibility criteria defined in the system yet, so eligibility cannot be determined.',
    badge: 'neutral',
    statusLabel: 'No criteria defined',
  },
];

const RESULT_GROUPS: FinderResultGroup[] = [
  'eligible',
  'more_information_required',
  'not_eligible',
  'no_criteria_defined',
];

/**
 * Natural-Language Scheme Finder.
 *
 * Three states in one page: describe yourself in plain text, review the
 * profile the backend extracted (editable, blanks stay blank), then read the
 * deterministic match results. No eligibility decision is made here — the
 * backend matching engine is the only source of truth.
 */
@Component({
  selector: 'app-finder',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    BackToDashboardComponent,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    InputComponent,
    SelectComponent,
    StateSelectComponent,
    FinderMatchCardComponent,
  ],
  templateUrl: './finder.component.html',
  styleUrl: './finder.component.css',
})
export class FinderComponent {
  private readonly finderService = inject(FinderService);
  private readonly formBuilder = inject(FormBuilder);

  readonly maxDescriptionLength = MAX_DESCRIPTION_LENGTH;
  readonly sections = RESULT_SECTIONS;
  readonly disabilityOptions: SelectOption[] = [
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ];

  /** DOM ids of the review controls, used to focus a missing field. */
  private readonly fieldIds: Record<string, string> = {
    age: 'finder-age',
    gender: 'finder-gender',
    annual_income: 'finder-annual-income',
    occupation: 'finder-occupation',
    education: 'finder-education',
    state: 'finder-state',
    district: 'finder-district',
    social_category: 'finder-social-category',
    disability_status: 'finder-disability-status',
  };

  private readonly genderOptions: SelectOption[] = [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' },
  ];

  private readonly educationOptions: SelectOption[] = [
    { value: 'below_primary', label: 'Below Primary' },
    { value: 'primary', label: 'Primary' },
    { value: 'secondary', label: 'Secondary' },
    { value: 'higher_secondary', label: 'Higher Secondary' },
    { value: 'graduate', label: 'Graduate' },
    { value: 'post_graduate', label: 'Post Graduate' },
    { value: 'doctorate', label: 'Doctorate' },
    { value: 'diploma', label: 'Diploma' },
    { value: 'professional', label: 'Professional Degree' },
  ];

  private readonly socialCategoryOptions: SelectOption[] = [
    { value: 'general', label: 'General' },
    { value: 'obc', label: 'OBC' },
    { value: 'sc', label: 'SC' },
    { value: 'st', label: 'ST' },
    { value: 'other', label: 'Other' },
  ];

  // ── State ────────────────────────────────────────────────────────────────
  readonly step = signal<FinderStep>('input');
  readonly description = signal('');
  readonly descriptionError = signal<string | null>(null);
  readonly descriptionNotice = signal<string | null>(null);
  readonly extracting = signal(false);
  readonly extractionError = signal<string | null>(null);

  readonly matching = signal(false);
  readonly matchError = signal<string | null>(null);
  readonly matchResult = signal<SchemeMatchResponse | null>(null);

  readonly profileForm: FormGroup = this.formBuilder.group({
    age: [null, [Validators.min(0), Validators.max(MAX_AGE)]],
    gender: [''],
    annual_income: [null, [Validators.min(0)]],
    occupation: [''],
    education: [''],
    state: [''],
    district: [''],
    social_category: [''],
    disability_status: [''],
  });

  // ── State 1: natural-language input ──────────────────────────────────────
  /** Submit handler (the form has no FormGroupDirective, so prevent default). */
  onFindSubmit(event: Event): void {
    event.preventDefault();
    this.findSchemes();
  }

  onDescriptionInput(event: Event): void {
    const value = (event.target as HTMLTextAreaElement).value;
    this.description.set(value);
    if (value.trim().length > 0) {
      this.descriptionError.set(null);
      this.descriptionNotice.set(null);
    }
  }

  findSchemes(): void {
    if (this.extracting()) {
      return;
    }

    const text = this.description().trim();
    if (text.length === 0) {
      this.descriptionError.set(
        'Tell us a little about yourself before searching — for example your age, income, occupation, education, or location.',
      );
      return;
    }

    this.descriptionError.set(null);
    this.descriptionNotice.set(null);
    this.extractionError.set(null);
    this.extracting.set(true);

    this.finderService.extractProfile(text).subscribe({
      next: (response) => {
        this.extracting.set(false);
        const profile = this.normalizeProfile(response);
        if (this.isProfileEmpty(profile)) {
          this.descriptionNotice.set(
            'We could not find any profile details in that description. Add details like your age, income, occupation, education, or location and try again.',
          );
          return;
        }
        this.applyProfileToForm(profile);
        this.step.set('review');
        this.scrollToTop();
      },
      error: () => {
        this.extracting.set(false);
        this.extractionError.set(
          'We could not extract your information right now. Please try again.',
        );
      },
    });
  }

  // ── State 2: review & confirm ────────────────────────────────────────────
  checkEligibility(): void {
    if (this.matching()) {
      return;
    }
    if (this.profileForm.invalid) {
      this.profileForm.markAllAsTouched();
      return;
    }

    this.matching.set(true);
    this.matchError.set(null);

    this.finderService.matchProfile(this.buildProfilePayload()).subscribe({
      next: (response) => {
        this.matching.set(false);
        const result = this.normalizeMatchResponse(response);
        if (!result) {
          this.matchError.set(
            'We could not check the schemes right now. Please try again.',
          );
          return;
        }
        this.matchResult.set(result);
        this.step.set('results');
        this.scrollToTop();
      },
      error: () => {
        this.matching.set(false);
        this.matchError.set(
          'We could not check the schemes right now. Please try again.',
        );
      },
    });
  }

  /** Back to the description, keeping the text the user already wrote. */
  startOver(): void {
    this.matchError.set(null);
    this.step.set('input');
    this.scrollToTop();
  }

  // ── State 3: results ─────────────────────────────────────────────────────
  /** Return to the review form, preserving every value the user entered. */
  editInformation(field?: string): void {
    this.matchError.set(null);
    this.step.set('review');

    const elementId = field ? this.fieldIds[field] : undefined;
    if (elementId) {
      setTimeout(() => document.getElementById(elementId)?.focus());
      return;
    }
    this.scrollToTop();
  }

  matchesFor(group: FinderResultGroup): SchemeMatch[] {
    return this.matchResult()?.[group] ?? [];
  }

  totalMatches(): number {
    return RESULT_GROUPS.reduce(
      (total, group) => total + this.matchesFor(group).length,
      0,
    );
  }

  /** First field the backend reported as missing, used to focus the review form. */
  missingFieldFor(group: FinderResultGroup): string | undefined {
    return this.matchesFor(group)[0]?.missing_information[0];
  }

  // ── Review form helpers ──────────────────────────────────────────────────
  isBlank(field: string): boolean {
    const value = this.profileForm.get(field)?.value;
    return value === null || value === undefined || value === '';
  }

  fieldError(field: string): string | null {
    const control = this.profileForm.get(field);
    if (!control || !control.touched || control.valid) {
      return null;
    }
    if (control.hasError('min')) {
      return 'Enter 0 or more.';
    }
    if (control.hasError('max')) {
      return `Enter a value of ${MAX_AGE} or less.`;
    }
    return 'Please check this value.';
  }

  /**
   * Options for a select, extended with the extracted value when the backend
   * returned something that is not one of the standard choices. The value is
   * preserved and stays visible/editable instead of being silently dropped.
   */
  genderOptionsFor(): SelectOption[] {
    return this.optionsWithCurrent(this.genderOptions, 'gender');
  }

  educationOptionsFor(): SelectOption[] {
    return this.optionsWithCurrent(this.educationOptions, 'education');
  }

  socialCategoryOptionsFor(): SelectOption[] {
    return this.optionsWithCurrent(this.socialCategoryOptions, 'social_category');
  }

  // ── Internal helpers ─────────────────────────────────────────────────────
  private optionsWithCurrent(base: SelectOption[], field: string): SelectOption[] {
    const value = this.profileForm.get(field)?.value;
    if (typeof value !== 'string' || value.length === 0) {
      return base;
    }
    if (base.some((option) => option.value === value)) {
      return base;
    }
    return [...base, { value, label: value }];
  }

  private applyProfileToForm(profile: FinderProfile): void {
    this.profileForm.reset({
      age: profile.age,
      gender: this.normalizeChoice(profile.gender, this.genderOptions) ?? '',
      annual_income: profile.annual_income,
      occupation: profile.occupation ?? '',
      education: this.normalizeChoice(profile.education, this.educationOptions) ?? '',
      state: profile.state ?? '',
      district: profile.district ?? '',
      social_category:
        this.normalizeChoice(profile.social_category, this.socialCategoryOptions) ?? '',
      disability_status:
        profile.disability_status === null ? '' : String(profile.disability_status),
    });
  }

  /** Match a returned choice to a known option (case-insensitive), else keep it. */
  private normalizeChoice(value: string | null, options: SelectOption[]): string | null {
    if (!value) {
      return null;
    }
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return null;
    }
    const known = options.find(
      (option) =>
        option.value.toLowerCase() === trimmed.toLowerCase() ||
        option.label.toLowerCase() === trimmed.toLowerCase(),
    );
    return known ? known.value : trimmed;
  }

  private buildProfilePayload(): FinderProfile {
    const value = this.profileForm.getRawValue() as Record<string, unknown>;
    return {
      age: this.toNullableNumber(value['age']),
      gender: this.toNullableString(value['gender']),
      annual_income: this.toNullableNumber(value['annual_income']),
      occupation: this.toNullableString(value['occupation']),
      education: this.toNullableString(value['education']),
      state: this.toNullableString(value['state']),
      district: this.toNullableString(value['district']),
      social_category: this.toNullableString(value['social_category']),
      disability_status: this.toDisabilityStatus(value['disability_status']),
    };
  }

  private normalizeProfile(profile: FinderProfile | null): FinderProfile {
    return {
      age: this.toNullableNumber(profile?.age),
      gender: this.toNullableString(profile?.gender),
      annual_income: this.toNullableNumber(profile?.annual_income),
      occupation: this.toNullableString(profile?.occupation),
      education: this.toNullableString(profile?.education),
      state: this.toNullableString(profile?.state),
      district: this.toNullableString(profile?.district),
      social_category: this.toNullableString(profile?.social_category),
      disability_status: this.toDisabilityStatus(profile?.disability_status),
    };
  }

  private normalizeMatchResponse(
    response: SchemeMatchResponse | null,
  ): SchemeMatchResponse | null {
    if (!response || typeof response !== 'object') {
      return null;
    }
    const hasGroups = RESULT_GROUPS.some((group) => Array.isArray(response[group]));
    if (!hasGroups) {
      return null;
    }
    return {
      eligible: response.eligible ?? [],
      more_information_required: response.more_information_required ?? [],
      not_eligible: response.not_eligible ?? [],
      no_criteria_defined: response.no_criteria_defined ?? [],
    };
  }

  private isProfileEmpty(profile: FinderProfile): boolean {
    return (
      profile.age === null &&
      profile.gender === null &&
      profile.annual_income === null &&
      profile.occupation === null &&
      profile.education === null &&
      profile.state === null &&
      profile.district === null &&
      profile.social_category === null &&
      profile.disability_status === null
    );
  }

  private toNullableString(value: unknown): string | null {
    if (typeof value !== 'string') {
      return null;
    }
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }

  private toNullableNumber(value: unknown): number | null {
    if (value === null || value === undefined || value === '') {
      return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  private toDisabilityStatus(value: unknown): boolean | null {
    if (value === true || value === 'true') {
      return true;
    }
    if (value === false || value === 'false') {
      return false;
    }
    return null;
  }

  private scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
