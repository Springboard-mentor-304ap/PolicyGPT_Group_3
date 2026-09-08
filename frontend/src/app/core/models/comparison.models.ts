import { SearchResultItem } from './search.models';

export interface ComparisonAttribute {
  key: string;
  label: string;
  category: 'overview' | 'eligibility' | 'benefits' | 'application';
}

export interface ComparisonMatrixRow {
  attribute: ComparisonAttribute;
  values: Record<string, string | null | undefined>; // schemeId -> value
  isDifferent?: boolean;
}

export interface ComparisonMatrix {
  items: SearchResultItem[];
  rows: ComparisonMatrixRow[];
}
