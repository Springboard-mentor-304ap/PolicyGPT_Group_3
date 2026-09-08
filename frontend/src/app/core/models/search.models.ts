import { PolicyCategory, SchemeCategory } from './policy.models';

export type SearchItemType = 'all' | 'policy' | 'scheme';

export type SortOption = 'relevance' | 'newest' | 'oldest' | 'views' | 'deadline';

export interface SearchFilters {
  type: SearchItemType;
  category: string; // 'all' or specific PolicyCategory / SchemeCategory
  state: string; // 'all' or specific State
  department: string;
  status: string; // 'all' | 'active' | 'approved' | etc.
}

export interface SearchParams {
  q?: string;
  type?: SearchItemType;
  category?: string;
  state?: string;
  department?: string;
  status?: string;
  sort_by?: SortOption;
  page?: number;
  page_size?: number;
}

export interface SearchResultItem {
  id: string;
  itemType: 'policy' | 'scheme';
  title: string;
  description: string;
  category: PolicyCategory | SchemeCategory | string;
  categoryLabel: string;
  department?: string | null;
  ministry?: string | null;
  state?: string | null;
  status: string;
  benefits?: string | null;
  application_process?: string | null;
  launch_date?: string | null;
  deadline_date?: string | null;
  document_url?: string | null;
  view_count: number;
}

export interface SearchResponse {
  total: number;
  page: number;
  page_size: number;
  results: SearchResultItem[];
}
