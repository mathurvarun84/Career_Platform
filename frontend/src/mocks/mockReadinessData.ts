import type { CompanyReadinessResult } from '../types'

export const mockCompanyReadiness: CompanyReadinessResult = {
  company_key: 'flipkart',
  company_display_name: 'Flipkart',
  readiness_score: 61,
  readiness_label: 'Partially Ready',
  readiness_pct_string: '61% Ready',
  dimensions: [
    {
      dimension_id: 'ownership',
      label: 'Ownership Language',
      company_expectation:
        'Flipkart expects end-to-end product ownership including post-launch metrics and iteration.',
      resume_evidence: 'Ownership signals found in resume_health.',
      signal_strength: 'strong',
      passes: true,
      fix_hint: null,
      display_label: 'Signal Found',
    },
    {
      dimension_id: 'impact_and_scale',
      label: 'Impact & Scale',
      company_expectation:
        'Features shipped must show user-scale impact — MAU, conversion, GMV language expected.',
      resume_evidence: 'Impact metrics present and ATS sub-score ≥ 18.',
      signal_strength: 'strong',
      passes: true,
      fix_hint: null,
      display_label: 'Signal Found',
    },
    {
      dimension_id: 'data_driven',
      label: 'Data-Driven Decisions',
      company_expectation:
        'Experiment ownership (A/B tests), SQL-level analysis, and metric ownership are strong signals.',
      resume_evidence: 'No data-driven signals found.',
      signal_strength: 'weak',
      passes: false,
      fix_hint:
        'Add a bullet mentioning an A/B test or experiment you owned and the metric outcome.',
      display_label: 'Signal Not Found',
    },
    {
      dimension_id: 'cross_functional',
      label: 'Cross-Functional Scope',
      company_expectation:
        'SPM-level candidates own roadmap across engineering, design, data, and ops — 3+ teams expected.',
      resume_evidence: '1 cross-functional bullet found.',
      signal_strength: 'developing',
      passes: false,
      fix_hint:
        'Rewrite a bullet to show you influenced 2+ teams — not just executed within your team.',
      display_label: 'Partial Signal',
    },
    {
      dimension_id: 'consumer_intuition',
      label: 'Consumer Intuition',
      company_expectation:
        'Consumer product intuition; evidence of user research, feedback loops, or NPS ownership.',
      resume_evidence: 'Partial consumer signal: nps.',
      signal_strength: 'developing',
      passes: false,
      fix_hint:
        'Add a line about user research you conducted or a feedback mechanism you built.',
      display_label: 'Partial Signal',
    },
  ],
  dimensions_passing: 2,
  dimensions_total: 5,
  ats_component: 72,
  jd_component: 61,
  seniority_component: 100,
  company_signal_component: 40,
  current_ctc_min: 22,
  current_ctc_max: 28,
  target_ctc_min: 28,
  target_ctc_max: 36,
  ctc_delta_min: 6,
  ctc_delta_max: 8,
  top_fix: {
    dimension_id: 'data_driven',
    label: 'Data-Driven Decisions',
    company_expectation:
      'Experiment ownership (A/B tests), SQL-level analysis, and metric ownership are strong signals.',
    resume_evidence: 'No data-driven signals found.',
    signal_strength: 'weak',
    passes: false,
    fix_hint:
      'Add a bullet mentioning an A/B test or experiment you owned and the metric outcome.',
    display_label: 'Signal Not Found',
  },
  disclaimer:
    'Based on language patterns in your resume — not a guarantee of interview outcome.',
}
