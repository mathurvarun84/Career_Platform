export interface ATSBreakdown {
  keyword_match: number;
  formatting: number;
  readability: number;
  impact_metrics: number;
}

export interface ATSDimensionDetail {
  score: number;
  benchmark: number;
  gap: number;
  gap_reason: string;
  label: string;
  icon: string;
}

export interface ATSResult {
  score: number;
  breakdown: ATSBreakdown;
  details: ATSDimensionDetail[];
  ats_issues: string[];
}

export interface SubLocationChange {
  sub_id: string;
  sub_label: string;
  needs_change: boolean;
  gap_reason: string;
  rewrite_instruction: string;
  missing_keywords: string[];
}

export interface SectionGap {
  section: string;
  needs_change: boolean;
  gap_reason: string;
  missing_keywords: string[];
  rewrite_instruction: string;
  present_in_resume: boolean;
  sub_changes: SubLocationChange[];
}

export interface ActionableChange {
  change_id: number;
  location: {
    section: string;
    sub_location: string;
  };
  change_type:
    | "rewrite_bullet"
    | "add_keyword"
    | "rewrite_section"
    | "add_section"
    | "remove_content"
    | "strengthen_metric";
  priority: "critical" | "high" | "medium";
  why: string;
  original_text: string;
  suggested_text: string;
  keywords_added: string[];
}

export interface PersonaVerdict {
  persona: string;
  first_impression: string;
  noticed: string[];
  ignored: string[];
  rejection_reason: string;
  shortlist_decision: boolean;
  fit_score: number;
  flip_condition: string;
}

export interface SimResult {
  personas: PersonaVerdict[];
  shortlist_rate: number;
  consensus_strengths: string[];
  consensus_weaknesses: string[];
  most_critical_fix: string;
  probing_persona: string | null;
  probing_dimension: string | null;
}

export interface SectionRewrite {
  balanced: string;
  aggressive: string;
  top_1_percent: string;
}

export interface ResumeUnderstanding {
  experience_years: number;
  seniority: "junior" | "mid" | "senior" | "staff";
  role_family?:
    | "ENGINEERING"
    | "PRODUCT"
    | "MARKETING"
    | "DATA_ANALYST"
    | "HR"
    | "FINANCE"
    | "DESIGN";
  tech_stack: string[];
  domains: string[];
  has_metrics: boolean;
  has_summary: boolean;
  sections_present: string[];
  resume_sections: Record<string, { full_text: string }>;
}

export interface PriorityFix {
  section: string;
  gap_reason: string;
  rewrite_instruction: string;
  missing_keywords: string[];
  needs_change: boolean;
}

export interface GapResult {
  jd_match_score_before: number | null;
  jd_match_score_after: number;
  section_gaps: SectionGap[];
  missing_keywords: string[];
  priority_fixes: string[] | PriorityFix[];
  changes: ActionableChange[];
}

export interface PositioningResult {
  current_tier: string;
  current_tier_label: string;
  current_tier_examples: string;
  next_tier_label: string;
  next_tier_examples: string;
  changes_needed: number;
  current_ctc_min: number;
  current_ctc_max: number;
  potential_ctc_min: number;
  potential_ctc_max: number;
  ctc_delta_min: number;
  ctc_delta_max: number;
  positioning_line: string;
  delta_line: string;
  cta_line: string;
  rank_rationale: string;
  fix_items: string[];
}

export interface PercentileResult {
  score: number;
  label: string;
  percentile: number;
}

export type PatchOp =
  | "replace_text" | "insert_keyword" | "shorten_bullet"
  | "reorder_bullets" | "add_metric" | "add_bullet";

export type PatchRisk = "safe" | "needs_confirmation";
export type PatchStatus = "pending" | "applied" | "rejected" | "rolled_back";

export interface ResumePatch {
  patch_id: string;
  gap_id: string;
  section: string;
  sub_entry_label: string;
  op: PatchOp;
  original_text: string;
  replacement_text: string;
  keyword?: string;
  proposed_text?: string;
  risk: PatchRisk;
  hallucination_risk: boolean;
  issue_detected: string;
  fix_rationale: string;
  status: PatchStatus;
  score_before?: number;
  score_after?: number;
  score_delta?: number;
}

export interface AnalysisResult {
  job_id: string;
  ats: ATSResult;
  resume: ResumeUnderstanding;
  gap: GapResult | null;
  rewrites: Record<string, SectionRewrite> | null;
  sim: SimResult | null;
  percentile: PercentileResult | null;
  positioning: PositioningResult | null;
  patches?: ResumePatch[];
}

export interface SSEProgressEvent {
  step?: number;
  label?: string;
  pct?: number;
  status: "running" | "complete" | "error";
  error?: string;
  type?: "partial";
  partial_result?: Partial<AnalysisResult>;
}

export interface HistoryRun {
  run_id: string;
  timestamp: string;
  ats_score: number;
  jd_match: number | null;
  percentile: number | null;
}

export interface HistoryResponse {
  runs: HistoryRun[];
}

export interface HistoryEntry {
  id: string;
  upload_id: string;
  user_id: string;
  file_name: string;
  target_company: string | null;
  target_role: string | null;
  ats_score: number | null;
  jd_match_score: number | null;
  shortlist_rate: number | null;
  percentile: number | null;
  analyzed_at: string;
  uploaded_at?: string;
}

export interface UsageLimits {
  total_uploads: number;
  uploads_this_month: number;
  last_reset_date?: string;
}

export interface GapCloseRequest {
  job_id: string;
  accepted_sections: Record<string, RewriteStyle>;
  user_id: string;
}

export interface GapCloseResponse {
  docx_id: string;
}

export interface FetchJDResult {
  status: "found" | "not_found" | "multiple" | "error";
  jd_text: string | null;
  source_url: string | null;
  fetched_at: string | null;
  is_cached: boolean;
  company: string;
  role: string;
  alternatives?: Array<{ title: string; level: string; url?: string }>;
  error_message?: string;
}

export type RewriteStyle = "balanced" | "aggressive" | "top_1_percent";

export type TabId = "overview" | "fixes" | "recruiter" | "gap" | "progress";

export interface TopBarProps {
  onOpenAuthModal: () => void;
  onViewProgress?: () => void;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  provider: string | null;
  is_pro: boolean;
  created_at: string;
  updated_at: string;
}
