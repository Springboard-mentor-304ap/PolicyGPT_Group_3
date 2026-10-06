import { FinderRuleResult } from '../../core/models/finder.models';

/**
 * Presentation-only labels for the Finder results.
 *
 * The backend returns raw parameter keys (`annual_income`) and operators
 * (`gte`). These helpers turn them into readable text for the rule list; they
 * never compare values or decide anything — `satisfied` always comes from the
 * backend response.
 */

const PARAMETER_LABELS: Record<string, string> = {
  age: 'Age',
  gender: 'Gender',
  annual_income: 'Annual income',
  income: 'Annual income',
  occupation: 'Occupation',
  education: 'Education',
  state: 'State',
  district: 'District',
  social_category: 'Social category',
  disability_status: 'Disability status',
};

/** `annual_income` -> "Annual income"; unknown keys are humanized. */
export function parameterLabel(parameter: string): string {
  const known = PARAMETER_LABELS[parameter];
  if (known) {
    return known;
  }
  return parameter
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

const OPERATOR_PREFIXES: Record<string, string> = {
  eq: 'Exactly',
  neq: 'Anything except',
  lt: 'Less than',
  lte: 'At most',
  gt: 'More than',
  gte: 'At least',
  in: 'One of',
  not_in: 'None of',
};

/** Render a rule's requirement in plain words (e.g. "At least 18"). */
export function requiredValueText(rule: FinderRuleResult): string {
  const value = (rule.required_value ?? '').replace(/\s*,\s*/g, ', ');
  const prefix = OPERATOR_PREFIXES[rule.operator];
  return prefix ? `${prefix} ${value}` : value;
}
