import { Injectable, signal } from '@angular/core';
import { Observable, of, delay } from 'rxjs';
import {
  SearchParams,
  SearchResponse,
  SearchResultItem,
  SortOption
} from '../models/search.models';

// ╔══════════════════════════════════════════════════════════════════════════════╗
// ║  HOW TO RECONNECT TO THE REAL BACKEND SEARCH API (Kalisetti Bhagyasri)       ║
// ║                                                                            ║
// ║  1. In frontend/src/app/app.config.ts, ensure provideHttpClient() is active ║
// ║  2. Inject HttpClient: private readonly http = inject(HttpClient);          ║
// ║  3. Replace the mock search method below with:                             ║
// ║       return this.http.get<SearchResponse>('/api/search', { params: ... })  ║
// ║  4. Remove the temporary MOCK_ITEMS dataset below                          ║
// ╚══════════════════════════════════════════════════════════════════════════════╝

// ─── MOCK DATA (TEMPORARY — FOR FRONTEND UI DEVELOPMENT ONLY) ─────────────────
const MOCK_ITEMS: SearchResultItem[] = [
  {
    id: 'sch-001',
    itemType: 'scheme',
    title: 'PM Kisan Samman Nidhi Yojana',
    description:
      'Direct income support of ₹6,000 per year in three equal installments to all landholding farmer families across the country.',
    category: 'farmer_welfare',
    categoryLabel: 'Farmer Welfare',
    department: 'Department of Agriculture and Farmers Welfare',
    ministry: 'Ministry of Agriculture',
    state: 'Central',
    status: 'Active',
    benefits: '₹6,000 per year transferred directly to bank account via Direct Benefit Transfer (DBT).',
    application_process: 'Apply online through PM-Kisan portal or nearest Common Service Centre (CSC).',
    launch_date: '2019-02-24',
    deadline_date: '2026-12-31',
    document_url: 'https://pmkisan.gov.in',
    view_count: 1420,
  },
  {
    id: 'sch-002',
    itemType: 'scheme',
    title: 'Post-Matric Scholarship Scheme for SC/ST Students',
    description:
      'Financial assistance to Scheduled Caste and Scheduled Tribe students studying at post-matriculation or post-secondary stages to enable them to complete their education.',
    category: 'scholarships',
    categoryLabel: 'Scholarships',
    department: 'Department of Social Justice and Empowerment',
    ministry: 'Ministry of Social Justice',
    state: 'Central',
    status: 'Active',
    benefits: 'Full tuition fee reimbursement and monthly maintenance allowance up to ₹13,500/year.',
    application_process: 'Submit online application via the National Scholarship Portal (NSP).',
    launch_date: '2020-08-15',
    deadline_date: '2026-10-31',
    document_url: 'https://scholarships.gov.in',
    view_count: 980,
  },
  {
    id: 'sch-003',
    itemType: 'scheme',
    title: 'Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY)',
    description:
      'World’s largest health assurance scheme aiming to provide a health cover of ₹5 lakhs per family per year for secondary and tertiary care hospitalization.',
    category: 'healthcare',
    categoryLabel: 'Healthcare',
    department: 'National Health Authority',
    ministry: 'Ministry of Health and Family Welfare',
    state: 'Central',
    status: 'Active',
    benefits: 'Cashless healthcare coverage of up to ₹5,00,000 per family per year across empaneled hospitals.',
    application_process: 'Check eligibility on PMJAY portal or visit any empaneled public/private hospital.',
    launch_date: '2018-09-23',
    deadline_date: null,
    document_url: 'https://pmjay.gov.in',
    view_count: 3200,
  },
  {
    id: 'sch-004',
    itemType: 'scheme',
    title: 'Pradhan Mantri Awas Yojana (Urban 2.0)',
    description:
      'Provides interest subsidies and financial assistance to urban families belonging to EWS, LIG, and Middle-Income groups for construction or purchase of houses.',
    category: 'housing',
    categoryLabel: 'Housing',
    department: 'Ministry of Housing and Urban Affairs',
    ministry: 'Ministry of Housing',
    state: 'Central',
    status: 'Active',
    benefits: 'Interest subsidy up to 6.5% on housing loans up to ₹35,00,000.',
    application_process: 'Apply through PMAY Urban portal or designated state nodal agencies.',
    launch_date: '2024-09-01',
    deadline_date: '2027-03-31',
    document_url: 'https://pmay-urban.gov.in',
    view_count: 850,
  },
  {
    id: 'sch-005',
    itemType: 'scheme',
    title: 'Beti Bachao Beti Padhao & Sukanya Samriddhi Yojana',
    description:
      'Government initiative and savings scheme aimed at generating awareness and improving the efficiency of welfare services intended for girls.',
    category: 'women_empowerment',
    categoryLabel: 'Women Empowerment',
    department: 'Ministry of Women and Child Development',
    ministry: 'Ministry of Women and Child Development',
    state: 'Central',
    status: 'Active',
    benefits: 'High interest rate savings account (8.2% p.a.) with full tax deduction under Section 80C.',
    application_process: 'Open account at any authorized Post Office or commercial bank branch.',
    launch_date: '2015-01-22',
    deadline_date: null,
    document_url: 'https://wcd.nic.in',
    view_count: 2150,
  },
  {
    id: 'sch-006',
    itemType: 'scheme',
    title: 'National Apprenticeship Promotion Scheme (NAPS)',
    description:
      'Promotes apprenticeship training and incentivizes employers to engage apprentices by sharing stipend costs.',
    category: 'employment_programs',
    categoryLabel: 'Employment Programs',
    department: 'Ministry of Skill Development and Entrepreneurship',
    ministry: 'Ministry of Skill Development',
    state: 'Central',
    status: 'Active',
    benefits: 'Government shares 25% of prescribed stipend up to ₹1,500 per month per apprentice.',
    application_process: 'Register on the Apprenticeship India official web portal.',
    launch_date: '2016-08-19',
    deadline_date: '2026-11-30',
    document_url: 'https://apprenticeshipindia.gov.in',
    view_count: 670,
  },
  {
    id: 'sch-007',
    itemType: 'scheme',
    title: 'Atal Pension Yojana (APY)',
    description:
      'Guaranteed pension scheme for citizens in the unorganized sector to secure their retirement financial security.',
    category: 'social_security',
    categoryLabel: 'Social Security',
    department: 'Pension Fund Regulatory and Development Authority',
    ministry: 'Ministry of Finance',
    state: 'Central',
    status: 'Active',
    benefits: 'Guaranteed minimum monthly pension of ₹1,000 to ₹5,000 starting from age 60.',
    application_process: 'Enroll through your savings bank branch or net banking portal.',
    launch_date: '2015-05-09',
    deadline_date: null,
    document_url: 'https://www.pfrda.org.in',
    view_count: 1290,
  },
  {
    id: 'pol-001',
    itemType: 'policy',
    title: 'National Education Policy 2020',
    description:
      'Comprehensive framework to guide the development of education in the country, transforming school and higher education structure into a 5+3+3+4 multidisciplinary model.',
    category: 'education',
    categoryLabel: 'Education Policy',
    department: 'Department of Higher Education',
    ministry: 'Ministry of Education',
    state: 'Central',
    status: 'Approved',
    benefits: 'Promotes holistic, flexible, and multidisciplinary education, vocational training, and digital learning.',
    application_process: 'Implemented across schools and universities nationwide.',
    launch_date: '2020-07-29',
    deadline_date: null,
    document_url: 'https://www.education.gov.in',
    view_count: 4500,
  },
  {
    id: 'pol-002',
    itemType: 'policy',
    title: 'National Green Hydrogen Mission',
    description:
      'Strategic policy to facilitate production of 5 MMT of green hydrogen per annum by 2030 and establish India as a global clean energy hub.',
    category: 'environment',
    categoryLabel: 'Environment Policy',
    department: 'Ministry of New and Renewable Energy',
    ministry: 'Ministry of New and Renewable Energy',
    state: 'Central',
    status: 'Approved',
    benefits: 'Incentives for electrolyser manufacturing and clean fuel infrastructure development.',
    application_process: 'Tenders and strategic interventions via SECI and designated agencies.',
    launch_date: '2023-01-04',
    deadline_date: '2030-12-31',
    document_url: 'https://mnre.gov.in',
    view_count: 1120,
  },
  {
    id: 'pol-003',
    itemType: 'policy',
    title: 'Digital Personal Data Protection Act Policy Framework',
    description:
      'Legislation and administrative guidelines establishing rights and duties of citizens and obligations of data fiduciaries regarding digital personal data.',
    category: 'digital_governance',
    categoryLabel: 'Digital Governance',
    department: 'Ministry of Electronics and Information Technology',
    ministry: 'MeitY',
    state: 'Central',
    status: 'Approved',
    benefits: 'Protects citizen privacy rights, mandates consent managers, and establishes Data Protection Board.',
    application_process: 'Enforced for all digital platforms operating in India.',
    launch_date: '2023-08-11',
    deadline_date: null,
    document_url: 'https://www.meity.gov.in',
    view_count: 2750,
  }
];
// ──────────────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class SearchService {
  // Reactive signals for active search state
  readonly searchQuery = signal<string>('');
  readonly activeSort = signal<SortOption>('relevance');

  /**
   * Search & Filter Policies and Schemes.
   *
   * Backend Endpoint: GET /api/search
   */
  search(params: SearchParams): Observable<SearchResponse> {
    // ┌──────────────────────────────────────────────────────────────────────┐
    // │ RECONNECT: Replace the mock filtering logic with:                    │
    // │  let httpParams = new HttpParams();                                  │
    // │  if (params.q) httpParams = httpParams.set('q', params.q);           │
    // │  if (params.category) httpParams = httpParams.set('category', params.category); │
    // │  ...                                                                 │
    // │  return this.http.get<SearchResponse>('/api/search', { params: httpParams }); │
    // └──────────────────────────────────────────────────────────────────────┘

    const query = (params.q || '').trim().toLowerCase();
    const type = params.type || 'all';
    const category = params.category || 'all';
    const state = params.state || 'all';
    const status = params.status || 'all';
    const sortBy = params.sort_by || 'relevance';
    const page = params.page || 1;
    const pageSize = params.page_size || 10;

    let filtered = MOCK_ITEMS.filter((item) => {
      // Type match
      if (type !== 'all' && item.itemType !== type) {
        return false;
      }
      // Category match
      if (category !== 'all' && item.category !== category) {
        return false;
      }
      // State match
      if (state !== 'all' && item.state !== state && item.state !== 'Central') {
        return false;
      }
      // Status match
      if (status !== 'all' && item.status.toLowerCase() !== status.toLowerCase()) {
        return false;
      }
      // Text search match
      if (query) {
        const matchesTitle = item.title.toLowerCase().includes(query);
        const matchesDesc = item.description.toLowerCase().includes(query);
        const matchesCat = item.categoryLabel.toLowerCase().includes(query);
        const matchesDept = (item.department || '').toLowerCase().includes(query);
        const matchesMinistry = (item.ministry || '').toLowerCase().includes(query);
        const matchesBenefits = (item.benefits || '').toLowerCase().includes(query);

        if (!matchesTitle && !matchesDesc && !matchesCat && !matchesDept && !matchesMinistry && !matchesBenefits) {
          return false;
        }
      }
      return true;
    });

    // Sorting
    filtered = [...filtered].sort((a, b) => {
      if (sortBy === 'newest') {
        const dateA = new Date(a.launch_date || 0).getTime();
        const dateB = new Date(b.launch_date || 0).getTime();
        return dateB - dateA;
      }
      if (sortBy === 'oldest') {
        const dateA = new Date(a.launch_date || 0).getTime();
        const dateB = new Date(b.launch_date || 0).getTime();
        return dateA - dateB;
      }
      if (sortBy === 'views') {
        return b.view_count - a.view_count;
      }
      if (sortBy === 'deadline') {
        if (!a.deadline_date) return 1;
        if (!b.deadline_date) return -1;
        return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
      }
      // default: relevance
      return 0;
    });

    const total = filtered.length;
    const startIdx = (page - 1) * pageSize;
    const paginated = filtered.slice(startIdx, startIdx + pageSize);

    const response: SearchResponse = {
      total,
      page,
      page_size: pageSize,
      results: paginated,
    };

    return of(response).pipe(delay(300));
  }

  /**
   * Get Scheme/Policy by ID
   */
  getItemById(id: string): Observable<SearchResultItem | undefined> {
    const item = MOCK_ITEMS.find((i) => i.id === id);
    return of(item ? { ...item } : undefined).pipe(delay(200));
  }

  /**
   * Get all items (for quick prefetching / recommendations)
   */
  getAllItems(): Observable<SearchResultItem[]> {
    return of([...MOCK_ITEMS]).pipe(delay(200));
  }
}
