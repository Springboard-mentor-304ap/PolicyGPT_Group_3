import { Injectable, inject } from '@angular/core';
import { Observable, of, delay } from 'rxjs';
import {
  CriterionResult,
  EligibilityCheckRequest,
  EligibilityResult
} from '../models/eligibility.models';
import { SearchService } from './search.service';

// ╔══════════════════════════════════════════════════════════════════════════════╗
// ║  HOW TO RECONNECT TO THE REAL BACKEND ELIGIBILITY API                        ║
// ║                                                                            ║
// ║  1. In frontend/src/app/app.config.ts, ensure provideHttpClient() is active ║
// ║  2. Inject HttpClient: private readonly http = inject(HttpClient);          ║
// ║  3. Replace the mock methods below with:                                   ║
// ║       return this.http.post<EligibilityResult>('/api/eligibility/check', req)║
// ║  4. Remove the temporary MOCK_SCHEME_RULES mapping below                    ║
// ╚══════════════════════════════════════════════════════════════════════════════╝

// ─── MOCK RULES DEFINITION (MATCHING BACKEND ELIGIBILITY RULE MODELS) ─────────
interface SchemeRuleDefinition {
  scheme_id: string;
  scheme_title: string;
  category: string;
  minAge?: number;
  maxAge?: number;
  maxIncome?: number;
  allowedGenders?: string[];
  allowedOccupations?: string[];
  allowedSocialCategories?: string[];
  requiredDisability?: boolean;
  benefitsSummary: string;
  applicationProcess: string;
}

const MOCK_SCHEME_RULES: SchemeRuleDefinition[] = [
  {
    scheme_id: 'sch-001',
    scheme_title: 'PM Kisan Samman Nidhi Yojana',
    category: 'Farmer Welfare',
    minAge: 18,
    maxAge: 75,
    allowedOccupations: ['farmer', 'agriculture', 'any'],
    benefitsSummary: '₹6,000 per year transferred directly in 3 installments of ₹2,000 each.',
    applicationProcess: 'Register at PM-Kisan Portal with Aadhaar and Land Ownership records.',
  },
  {
    scheme_id: 'sch-002',
    scheme_title: 'Post-Matric Scholarship Scheme for SC/ST Students',
    category: 'Scholarships',
    minAge: 15,
    maxAge: 35,
    maxIncome: 250000,
    allowedSocialCategories: ['sc', 'st'],
    benefitsSummary: '100% Tuition fee reimbursement + Monthly maintenance allowance.',
    applicationProcess: 'Apply online through the National Scholarship Portal (NSP).',
  },
  {
    scheme_id: 'sch-003',
    scheme_title: 'Ayushman Bharat Pradhan Mantri Jan Arogya Yojana (PM-JAY)',
    category: 'Healthcare',
    maxIncome: 300000,
    benefitsSummary: 'Cashless hospital health cover up to ₹5,00,000 per family per year.',
    applicationProcess: 'Check entitlement via Ayushman portal or visit any empaneled hospital.',
  },
  {
    scheme_id: 'sch-004',
    scheme_title: 'Pradhan Mantri Awas Yojana (Urban 2.0)',
    category: 'Housing',
    minAge: 21,
    maxAge: 65,
    maxIncome: 600000,
    benefitsSummary: 'Interest subsidy of up to 6.5% on housing loans up to ₹35 Lakhs.',
    applicationProcess: 'Apply online at PMAY Urban portal with Income and Residence proof.',
  },
  {
    scheme_id: 'sch-005',
    scheme_title: 'Beti Bachao Beti Padhao & Sukanya Samriddhi Yojana',
    category: 'Women Empowerment',
    allowedGenders: ['female'],
    maxAge: 21,
    benefitsSummary: 'High interest savings account (8.2% p.a.) with tax exemption under Sec 80C.',
    applicationProcess: 'Open account at any Post Office or Bank with Girl child birth certificate.',
  },
  {
    scheme_id: 'sch-006',
    scheme_title: 'National Apprenticeship Promotion Scheme (NAPS)',
    category: 'Employment Programs',
    minAge: 18,
    maxAge: 30,
    benefitsSummary: '25% Government stipend share up to ₹1,500/month during skill apprenticeship.',
    applicationProcess: 'Register at Apprenticeship India official portal.',
  },
  {
    scheme_id: 'sch-007',
    scheme_title: 'Atal Pension Yojana (APY)',
    category: 'Social Security',
    minAge: 18,
    maxAge: 40,
    benefitsSummary: 'Guaranteed minimum monthly pension of ₹1,000 to ₹5,000 after age 60.',
    applicationProcess: 'Enroll via your bank branch or Net Banking savings account.',
  },
];
// ──────────────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class EligibilityService {
  private readonly searchService = inject(SearchService);

  /**
   * Evaluates eligibility of a citizen against a SINGLE scheme.
   *
   * Backend Endpoint: POST /api/eligibility/check
   */
  checkSchemeEligibility(
    schemeId: string,
    req: EligibilityCheckRequest
  ): Observable<EligibilityResult> {
    // ┌──────────────────────────────────────────────────────────────────────┐
    // │ RECONNECT: Replace the mock rule engine with:                        │
    // │  return this.http.post<EligibilityResult>('/api/eligibility/check',  │
    // │    { scheme_id: schemeId, ...req }                                  │
    // │  );                                                                  │
    // └──────────────────────────────────────────────────────────────────────┘

    const ruleDef = MOCK_SCHEME_RULES.find((r) => r.scheme_id === schemeId);

    if (!ruleDef) {
      // Fallback generic result
      const fallbackResult: EligibilityResult = {
        scheme_id: schemeId,
        scheme_title: 'Government Scheme',
        category: 'General',
        is_eligible: true,
        match_percentage: 100,
        criteria_results: [
          {
            parameter: 'general',
            label: 'General Eligibility',
            passed: true,
            ruleDescription: 'Criteria satisfied',
            userValue: 'Eligible',
          },
        ],
        benefits_summary: 'Financial assistance and support under standard guidelines.',
        application_process: 'Apply through the official portal.',
      };
      return of(fallbackResult).pipe(delay(350));
    }

    const result = this.evaluateSingleRule(ruleDef, req);
    return of(result).pipe(delay(350));
  }

  /**
   * Evaluates eligibility of a citizen against ALL available schemes.
   *
   * Backend Endpoint: POST /api/eligibility/evaluate-all
   */
  evaluateAllSchemes(req: EligibilityCheckRequest): Observable<EligibilityResult[]> {
    // ┌──────────────────────────────────────────────────────────────────────┐
    // │ RECONNECT: Replace the mock evaluation loop with:                    │
    // │  return this.http.post<EligibilityResult[]>('/api/eligibility/all', req);│
    // └──────────────────────────────────────────────────────────────────────┘

    const results = MOCK_SCHEME_RULES.map((ruleDef) => this.evaluateSingleRule(ruleDef, req));
    return of(results).pipe(delay(500));
  }

  // ─── PRIVATE EVALUATION LOGIC (MOCK ENGINE) ─────────────────────────────────
  private evaluateSingleRule(
    ruleDef: SchemeRuleDefinition,
    req: EligibilityCheckRequest
  ): EligibilityResult {
    const criteria: CriterionResult[] = [];
    let totalCriteria = 0;
    let passedCriteria = 0;

    // 1. Age Check
    if (ruleDef.minAge !== undefined || ruleDef.maxAge !== undefined) {
      totalCriteria++;
      let passed = true;
      let reason: string | undefined;

      if (ruleDef.minAge !== undefined && req.age < ruleDef.minAge) {
        passed = false;
        reason = `Applicant age (${req.age} yrs) is below minimum requirement (${ruleDef.minAge} yrs).`;
      } else if (ruleDef.maxAge !== undefined && req.age > ruleDef.maxAge) {
        passed = false;
        reason = `Applicant age (${req.age} yrs) exceeds maximum limit (${ruleDef.maxAge} yrs).`;
      }

      if (passed) passedCriteria++;

      criteria.push({
        parameter: 'age',
        label: 'Age Eligibility',
        passed,
        ruleDescription:
          ruleDef.minAge && ruleDef.maxAge
            ? `Between ${ruleDef.minAge} and ${ruleDef.maxAge} years`
            : ruleDef.minAge
            ? `Minimum ${ruleDef.minAge} years`
            : `Maximum ${ruleDef.maxAge} years`,
        userValue: `${req.age} years`,
        failureReason: reason,
      });
    }

    // 2. Gender Check
    if (ruleDef.allowedGenders && ruleDef.allowedGenders.length > 0) {
      totalCriteria++;
      const passed = ruleDef.allowedGenders.includes(req.gender.toLowerCase());
      if (passed) passedCriteria++;

      criteria.push({
        parameter: 'gender',
        label: 'Gender Requirement',
        passed,
        ruleDescription: `Eligible for: ${ruleDef.allowedGenders.join(', ').toUpperCase()}`,
        userValue: req.gender.toUpperCase(),
        failureReason: passed
          ? undefined
          : `This scheme is exclusively reserved for ${ruleDef.allowedGenders.join(', ')} applicants.`,
      });
    }

    // 3. Income Check
    if (ruleDef.maxIncome !== undefined) {
      totalCriteria++;
      const passed = req.annual_income <= ruleDef.maxIncome;
      if (passed) passedCriteria++;

      criteria.push({
        parameter: 'income',
        label: 'Annual Income Threshold',
        passed,
        ruleDescription: `Annual income must be under ₹${ruleDef.maxIncome.toLocaleString('en-IN')}`,
        userValue: `₹${req.annual_income.toLocaleString('en-IN')}`,
        failureReason: passed
          ? undefined
          : `Annual income ₹${req.annual_income.toLocaleString(
              'en-IN'
            )} exceeds ceiling of ₹${ruleDef.maxIncome.toLocaleString('en-IN')}.`,
      });
    }

    // 4. Social Category Check
    if (ruleDef.allowedSocialCategories && ruleDef.allowedSocialCategories.length > 0) {
      totalCriteria++;
      const passed = ruleDef.allowedSocialCategories.includes(req.social_category.toLowerCase());
      if (passed) passedCriteria++;

      criteria.push({
        parameter: 'social_category',
        label: 'Social Category Criteria',
        passed,
        ruleDescription: `Reserved for ${ruleDef.allowedSocialCategories
          .map((c) => c.toUpperCase())
          .join(', ')} categories`,
        userValue: req.social_category.toUpperCase(),
        failureReason: passed
          ? undefined
          : `Applicant category (${req.social_category.toUpperCase()}) does not match scheme target category.`,
      });
    }

    // 5. Occupation Check
    if (ruleDef.allowedOccupations && ruleDef.allowedOccupations.length > 0) {
      totalCriteria++;
      const reqOcc = req.occupation.toLowerCase();
      const passed =
        ruleDef.allowedOccupations.includes('any') ||
        ruleDef.allowedOccupations.some((o) => reqOcc.includes(o));
      if (passed) passedCriteria++;

      criteria.push({
        parameter: 'occupation',
        label: 'Occupation Eligibility',
        passed,
        ruleDescription: `Intended for: ${ruleDef.allowedOccupations.join(', ')}`,
        userValue: req.occupation,
        failureReason: passed
          ? undefined
          : `Scheme requires occupation matching ${ruleDef.allowedOccupations.join(', ')}.`,
      });
    }

    const matchPercentage =
      totalCriteria > 0 ? Math.round((passedCriteria / totalCriteria) * 100) : 100;
    const isEligible = matchPercentage === 100;

    return {
      scheme_id: ruleDef.scheme_id,
      scheme_title: ruleDef.scheme_title,
      category: ruleDef.category,
      is_eligible: isEligible,
      match_percentage: matchPercentage,
      criteria_results: criteria,
      benefits_summary: ruleDef.benefitsSummary,
      application_process: ruleDef.applicationProcess,
      document_url: 'https://india.gov.in',
    };
  }
}
