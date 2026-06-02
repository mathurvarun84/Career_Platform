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
  entry_id?: string;
  sub_label: string;
  needs_change: boolean;
  gap_reason: string;
  rewrite_instruction: string;
  missing_keywords: string[];
}

export type GapType = "surface" | "structural" | "evidence";

export interface SectionGap {
  section: string;
  needs_change: boolean;
  gap_reason: string;
  missing_keywords: string[];
  rewrite_instruction: string;
  present_in_resume: boolean;
  sub_changes: SubLocationChange[];
  gap_type?: GapType;
  requires_user_input?: boolean;
  coaching_question?: string | null;
  coaching_hint?: string[];
  auto_apply?: boolean;
  sub_label?: string | null;
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
  resume_sections: Record<
    string,
    {
      full_text: string;
      sub_entries?: Array<{ label: string; entry_id?: string; verbatim_text: string }>;
    }
  >;
  weaknesses?: string[];
  improvement_areas?: string[];
}

export interface PriorityFix {
  section: string;
  gap_reason: string;
  rewrite_instruction: string;
  missing_keywords: string[];
  needs_change: boolean;
  gap_type?: GapType;
  requires_user_input?: boolean;
  coaching_question?: string | null;
  coaching_hint?: string[];
  auto_apply?: boolean;
  sub_label?: string | null;
  entry_id?: string | null;
}

export interface CoachingAnswer {
  id: string;
  session_id?: string;
  gap_id: string;
  section: string;
  sub_label: string | null;
  raw_answer: string;
  generated_bullet: string | null;
  applied: boolean;
  user_approved?: boolean;
  timestamp: string;
  skill_category: string;
  company: string | null;
}

export interface PatchApplyResult {
  applied: boolean;
  found_in_doc: boolean;
  patch_id: string;
  rejection_reason: string | null;
}

export interface GapResult {
  /** Set by backend when analysis ran without a job description. */
  resume_only_mode?: boolean;
  jd_match_score_before: number | null;
  jd_match_score_after: number | null;
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

export interface ModeValidation {
  ats_check: "pass" | "fail";
  jd_check: "pass" | "warn" | "fail" | "no_jd";
  placeholder_check: "pass" | "fail";
  truncation_check: "pass" | "fail";
  overall: "pass" | "warn" | "fail";
  download_enabled: boolean;
}

export interface ModeScores {
  ats_score: number;
  ats_breakdown: ATSBreakdown;
  delta_ats: number;
}

export interface ValidationSummary {
  safe_fix: ModeValidation;
  full_rewrite: ModeValidation;
  scores: {
    safe_fix: ModeScores;
    full_rewrite: ModeScores;
    original_ats: number;
  };
}

export interface ResumePatch {
  patch_id: string;
  gap_id: string;
  section: string;
  sub_entry_label: string;
  sub_entry_id?: string;
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
  found_in_doc?: boolean;
}

export type FitnessBand = "qualified" | "stretch" | "underqualified";

export interface RoleFit {
  fitness: FitnessBand;
  score: number;
  experience_gap: number;
  seniority_gap: number;
  unanswerable_evidence_gaps: number;
  candidate_years: number;
  jd_min_years: number;
  recommended_roles: string[];
  next_step_roles: string[];
}

export interface JDIntelligence {
  role_title: string;
  must_have_skills?: string[];
  nice_to_have_skills?: string[];
  seniority_expected?: string;
  min_years_required?: number;
  jd_seniority_level?: string;
}

export interface AnalysisResult {
  job_id: string;
  /** FastAPI job id — same value used for coaching session_id after analyze completes. */
  session_id?: string;
  /** Corpus spine ids — returned after analysis completes. */
  run_id?: string | null;
  resume_id?: string | null;
  jd_id?: string | null;
  ats: ATSResult;
  resume: ResumeUnderstanding;
  gap: GapResult | null;
  rewrites: Record<string, SectionRewrite> | null;
  sim: SimResult | null;
  percentile: PercentileResult | null;
  positioning: PositioningResult | null;
  patches?: ResumePatch[];
  validation: ValidationSummary | null;
  jd_intelligence?: JDIntelligence | null;
  role_fit?: RoleFit | null;
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

export type BehavioralDimension =
  | "ownership"
  | "impact_and_scale"
  | "influence_without_authority"
  | "problem_solving"
  | "collaboration"
  | "growth_mindset"
  | "conflict_resolution";

export type AntiPatternKey =
  | "we_default"
  | "vague_quantification"
  | "story_recycling"
  | "impact_buried"
  | "hypothesis_without_proof"
  | "escalation_default"
  | "scope_collapse"
  | "no_reflection"
  | "credit_deflection"
  | "recency_bias"
  | "rehearsed_script";

export interface InterviewQuestion {
  id: string;
  text: string;
  question_type: QuestionType;
  dimension: BehavioralDimension;
  why_this_question: string;
  expected_signals: string[];
  risky_anti_patterns: AntiPatternKey[];
  /** Free-text risk note for candidate-specific risks outside the taxonomy. Null when taxonomy covers it. */
  answer_risk_note: string | null;
  company_value_ref: string;
  source: "generated" | "bank";
  /** Scenario setup text injected by backend. Only present for scenario questions. */
  preamble?: string;
}

export type SignalStrength = "weak" | "developing" | "strong";

export interface FollowUpQuestion {
  id: string;
  text: string;
  trigger_reason: string;
}

export interface AnswerTurn {
  question_id: string;
  answer_text: string;
  follow_ups: Array<{
    question: FollowUpQuestion;
    answer_text: string;
  }>;
}

export type SeniorityLevel = "junior" | "mid" | "senior" | "staff" | "em";

export type ExecutivePresenceLevel =
  | "strong"
  | "developing"
  | "low"
  | "not_assessable";

export interface AntiPatternFired {
  key: AntiPatternKey;
  label: string;
  triggered_excerpt: string;
  interviewer_reads_as: string;
  rewrite_suggestion: string;
}

export interface DimensionScore {
  dimension: BehavioralDimension;
  signal_strength: SignalStrength;
  score_delta: string;
  what_was_missing: string;
  what_was_strong: string;
}

export interface LevelSignal {
  signaled_level: SeniorityLevel;
  declared_level: SeniorityLevel;
  match: boolean;
  note: string;
}

export interface PerQuestionFeedback {
  question_id: string;
  dimension_score: DimensionScore;
  anti_patterns_fired: AntiPatternFired[];
  level_signal: LevelSignal;
  executive_presence: ExecutivePresenceLevel;
  authenticity_note: string;
  overall_verdict: string;
  best_line: string;
  coaching_close: string;
}

export interface DimensionSummary {
  dimension: BehavioralDimension;
  signal_strength: SignalStrength;
  expected_for_seniority: SignalStrength;
  gap: boolean;
  note: string;
}

export interface SessionSummary {
  dimension_scorecard: DimensionSummary[];
  anti_pattern_report: Array<{
    key: AntiPatternKey;
    label: string;
    count: number;
    worst_excerpt: string;
    fix: string;
  }>;
  top_strength: string;
  top_gap: string;
  recommended_next_dimension: BehavioralDimension;
}

export interface PastSessionSummary {
  session_id: string;
  company: string;
  seniority: string;
  created_at: string;
  top_strength: string;
  top_gap: string;
  recommended_next_dimension: BehavioralDimension;
  dimension_scorecard: DimensionSummary[];
  anti_pattern_report: Array<{
    key: AntiPatternKey;
    label: string;
    count: number;
    worst_excerpt: string;
    fix: string;
  }>;
}

export interface InterviewHistoryState {
  past_sessions: PastSessionSummary[];
  is_loading: boolean;
  fetch_error: string | null;
}

export interface ModelAnswer {
  text: string;
  what_changed: string;
  skipped?: boolean;
}

export interface ModelAnswerCardState {
  status: "idle" | "loading" | "loaded" | "error" | "skipped";
  data: ModelAnswer | null;
}

export interface InterviewProgressSnapshot {
  timestamp: string;
  company: string;
  seniority: string;
  dimensions_covered: BehavioralDimension[];
  average_signal_strength: number;
  anti_patterns_count: number;
}

export type QuestionMode = "behavioral" | "scenario" | "mixed";

export type QuestionType = "behavioral" | "scenario";

export type InterviewSessionState =
  | "idle"
  | "configuring"
  | "in_progress"
  | "awaiting_follow_up"
  | "evaluating"
  | "feedback_shown"
  | "summary";

export interface InterviewSession {
  session_id: string;
  company: string;
  seniority: string;
  question_mode: QuestionMode;
  questions: InterviewQuestion[];
  answers: AnswerTurn[];
  feedback: PerQuestionFeedback[];
  current_question_index: number;
  current_follow_up_count: number;
  active_follow_up: FollowUpQuestion | null;
  summary: SessionSummary | null;
  state: InterviewSessionState;
  partialFeedback?: Partial<PerQuestionFeedback> | null;
}

export interface SubmitAnswerResponse {
  feedback: PerQuestionFeedback;
  follow_up: FollowUpQuestion | null;
  session_complete: boolean;
}

export interface StartInterviewResponse {
  session_id: string;
  questions: InterviewQuestion[];
}

export type RewriteStyle = "balanced" | "aggressive" | "top_1_percent";

export type TabId =
  | "overview"
  | "fixes"
  | "recruiter"
  | "gap"
  | "progress"
  | "mock_interview";

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

export interface CareerMemoryEntry {
  id: string;
  session_id: string;
  gap_id: string;
  section: string;
  sub_label: string | null;
  raw_answer: string;
  generated_bullet: string;
  skill_category: "leadership" | "technical" | "delivery" | "communication";
  company: string | null;
  timestamp: string;
  user_approved?: boolean;
}

export interface CareerMemoryResponse {
  entries: CareerMemoryEntry[];
  total: number;
}

export interface ProgressSnapshot {
  timestamp: string;
  ats_score: number;
  jd_match: number | null;
  percentile: number | null;
  label: string;
  patches_applied: number;
  coaching_answers: number;
  session_id: string;
}

export interface ProgressStore {
  snapshots: ProgressSnapshot[];
  career_record: CareerMemoryEntry[];
  last_updated: string;
}

export interface DownloadVerification {
  clean: boolean;
  missing_patches: string[];
  missing_bullets: string[];
  total_applied: number;
  total_verified: number;
}

export interface DownloadState {
  patchesApplied: number;
  coachingBulletsAdded: number;
  atsScoreOriginal: number;
  atsScoreAfterFixes: number;
  verified: boolean;
  missingCount: number;
}
