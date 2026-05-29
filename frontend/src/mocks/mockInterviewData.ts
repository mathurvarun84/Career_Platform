import type {
  AntiPatternKey,
  InterviewSession,
  PastSessionSummary,
  PerQuestionFeedback,
  SessionSummary,
} from "../types";

export const MOCK_FOLLOW_UP_Q1 = {
  id: "mock_fu_1",
  text: "What specific decision did you personally make during that incident?",
  trigger_reason: "ownership_unclear",
};

export const MOCK_INTERVIEW_QUESTIONS = [
  {
    id: "mock_q1_ownership",
    text: "Tell me about a time when you took end-to-end ownership of a critical backend system that was failing in production.",
    question_type: "behavioral" as const,
    dimension: "ownership" as const,
    why_this_question:
      "Resume shows on-call ownership for payment services — probing personal accountability under pressure.",
    expected_signals: [
      "Clear I-ownership claim",
      "Production incident context",
      "Measurable recovery outcome",
      "Root cause identified",
    ],
    risky_anti_patterns: ["we_default", "vague_quantification"] satisfies AntiPatternKey[],
    answer_risk_note: null,
    company_value_ref: "Amazon LP: Ownership",
    source: "generated" as const,
  },
  {
    id: "mock_q2_impact",
    text: "Describe a project where you drove measurable impact on latency or throughput at scale.",
    question_type: "behavioral" as const,
    dimension: "impact_and_scale" as const,
    why_this_question:
      "Resume cites 40% p99 latency reduction — validating quantified system-level impact.",
    expected_signals: [
      "Baseline and after metrics",
      "Personal technical decisions",
      "Scale context",
      "Business or user impact",
    ],
    risky_anti_patterns: ["vague_quantification", "impact_buried"] satisfies AntiPatternKey[],
    answer_risk_note: null,
    company_value_ref: "Amazon LP: Deliver Results",
    source: "generated" as const,
  },
  {
    id: "mock_q3_scenario",
    text: "Imagine you are leading a team migrating a monolith to microservices and two teams disagree on the cutover strategy. How would you decide?",
    question_type: "scenario" as const,
    dimension: "problem_solving" as const,
    preamble:
      "You are a senior engineer two months into leading a platform migration. Two teams disagree on cutover strategy — one wants big-bang, the other wants strangler pattern.",
    why_this_question:
      "Resume mentions microservices migration — scenario probes structured decision-making.",
    expected_signals: [
      "Decision framework",
      "Risk assessment",
      "Stakeholder alignment",
      "Validation plan",
    ],
    risky_anti_patterns: ["hypothesis_without_proof"] satisfies AntiPatternKey[],
    answer_risk_note: null,
    company_value_ref: "Amazon LP: Dive Deep",
    source: "generated" as const,
  },
];

export const MOCK_INTERVIEW_FEEDBACK: PerQuestionFeedback[] = [
  {
    question_id: "mock_q1_ownership",
    dimension_score: {
      dimension: "ownership",
      signal_strength: "developing",
      score_delta: "-1 on Ownership",
      what_was_missing:
        "Interviewers leave the ownership box blank when they hear team language without a follow-up I-decision — they cannot score what they cannot attribute to you.",
      what_was_strong:
        "The line 'I was primary on-call when error rates spiked to 4.2% on the payment API' is exactly the first-person accountability signal they score positively.",
    },
    anti_patterns_fired: [
      {
        key: "we_default",
        label: "We Default",
        triggered_excerpt:
          "We noticed the queue was backing up and our team rolled out a hotfix.",
        interviewer_reads_as:
          "Ownership: unclear — the interviewer will ask what you specifically did, and a blank box is a miss at senior level.",
        rewrite_suggestion:
          "I noticed the queue backing up, wrote the hotfix myself, and owned the rollout through verification.",
      },
      {
        key: "vague_quantification",
        label: "Vague Quantification",
        triggered_excerpt: "Performance improved significantly after the fix.",
        interviewer_reads_as:
          "I cannot put an adjective in the impact field on my scorecard — only numbers count as evidence.",
        rewrite_suggestion:
          "p99 latency dropped from 920ms to 410ms within 30 minutes of the fix.",
      },
    ],
    level_signal: {
      signaled_level: "mid",
      declared_level: "senior",
      match: false,
      note:
        "The incident context is senior-appropriate, but collective language signals mid-level execution — name your personal decision in the first two sentences.",
    },
    executive_presence: "developing",
    authenticity_note:
      "The on-call opener feels lived-in; the hotfix sentence sounds like team shorthand rather than your personal narrative.",
    overall_verdict:
      "This signals a capable engineer who was present during a real incident, but the committee would flag unclear personal ownership and missing hard metrics before advancing.",
    best_line:
      "I was primary on-call when error rates spiked to 4.2% on the payment API.",
    coaching_close:
      "The ownership gap here is a language pattern, not a capability gap — most strong engineers default to 'we' under pressure. Practice leading with one I-decision and one number in your first three sentences; two mock runs usually fix this.",
  },
  {
    question_id: "mock_q2_impact",
    dimension_score: {
      dimension: "impact_and_scale",
      signal_strength: "strong",
      score_delta: "+1 on Impact & Scale",
      what_was_missing: "None — quantified outcome with clear scope and personal ownership.",
      what_was_strong:
        "Personal ownership, baseline metric, and measurable latency improvement at scale — this is what senior interviewers highlight in debrief.",
    },
    anti_patterns_fired: [],
    level_signal: {
      signaled_level: "senior",
      declared_level: "senior",
      match: true,
      note: "Story scope, cross-team buy-in, and system-level metrics align with senior expectations.",
    },
    executive_presence: "strong",
    authenticity_note:
      "Specific p99 numbers and request volume read as measured from production, not rehearsed.",
    overall_verdict:
      "Strong hire signal on impact: you owned the migration, quantified the outcome, and showed system-level scope — this is the bar for senior IC.",
    best_line:
      "I led the microservices migration and cut p99 latency from 800ms to 480ms across 12M daily requests.",
    coaching_close:
      "Keep this story in your top three — it already hits ownership, scale, and metrics. Use it as the template for weaker answers: same structure, same precision.",
  },
  {
    question_id: "mock_q3_scenario",
    dimension_score: {
      dimension: "problem_solving",
      signal_strength: "weak",
      score_delta: "-1 on Problem Solving",
      what_was_missing:
        "Interviewers need decision criteria and a validation plan — without them, hypothetical answers read as untested instinct, not structured judgment.",
      what_was_strong:
        "Dependency mapping as a first step shows you think about blast radius before cutover — a credible opening move.",
    },
    anti_patterns_fired: [
      {
        key: "hypothesis_without_proof",
        label: "Hypothesis Without Proof",
        triggered_excerpt:
          "I would probably start with the highest-risk service first since that should reduce blast radius.",
        interviewer_reads_as:
          "This person is guessing impact without a framework — I cannot tell if they would validate before committing.",
        rewrite_suggestion:
          "I would rank services by dependency fan-out and error budget burn, then pilot cutover on the lowest-traffic service and measure rollback time.",
      },
    ],
    level_signal: {
      signaled_level: "mid",
      declared_level: "senior",
      match: false,
      note:
        "Senior scenario answers need explicit tradeoff framing (strangler vs big-bang) and how you would measure success before cutover.",
    },
    executive_presence: "low",
    authenticity_note:
      "'Probably' and 'should' hedge the answer — it sounds tentative rather than decisive under ambiguity.",
    overall_verdict:
      "The committee would see structured thinking starting but no proof of how you validate tradeoffs — add criteria, stakeholders, and a pilot metric.",
    best_line: "I would map service dependencies before choosing a cutover order.",
    coaching_close:
      "Scenario questions reward a decision framework, not the 'right' answer. Practice a 4-step template: criteria → options → pilot → metric — one rehearsal makes this feel natural.",
  },
];

export const MOCK_INTERVIEW_SUMMARY: SessionSummary = {
  dimension_scorecard: [
    {
      dimension: "ownership",
      signal_strength: "developing",
      expected_for_seniority: "strong",
      gap: true,
      note: "Replace collective language with explicit I-decisions during the incident.",
    },
    {
      dimension: "impact_and_scale",
      signal_strength: "strong",
      expected_for_seniority: "strong",
      gap: false,
      note: "Migration story with 800ms→480ms p99 is a credible senior-level signal.",
    },
    {
      dimension: "problem_solving",
      signal_strength: "weak",
      expected_for_seniority: "strong",
      gap: true,
      note: "Scenario answer lacked validation criteria and proof for the chosen strategy.",
    },
  ],
  anti_pattern_report: [
    {
      key: "we_default",
      label: "We Default",
      count: 1,
      worst_excerpt:
        "We noticed the queue was backing up and our team rolled out a hotfix.",
      fix: 'Lead with "I" and name the specific decision you owned.',
    },
    {
      key: "vague_quantification",
      label: "Vague Quantification",
      count: 1,
      worst_excerpt: "Performance improved significantly after the fix.",
      fix: "Replace adjectives with before/after metrics tied to your action.",
    },
    {
      key: "hypothesis_without_proof",
      label: "Hypothesis Without Proof",
      count: 1,
      worst_excerpt:
        "I would probably start with the highest-risk service first since that should reduce blast radius.",
      fix: "State the decision criteria and how you would validate the cutover plan.",
    },
  ],
  top_strength:
    "Your microservices migration answer showed strong personal ownership with a quantified p99 improvement.",
  top_gap:
    "Ownership answers still default to 'we' — make your personal decisions explicit in the first two sentences.",
  recommended_next_dimension: "influence_without_authority",
};

export const MOCK_PAST_SESSIONS: PastSessionSummary[] = [
  {
    session_id: "mock-past-session-001",
    company: "amazon",
    seniority: "senior",
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    top_strength: MOCK_INTERVIEW_SUMMARY.top_strength,
    top_gap: MOCK_INTERVIEW_SUMMARY.top_gap,
    recommended_next_dimension: MOCK_INTERVIEW_SUMMARY.recommended_next_dimension,
    dimension_scorecard: MOCK_INTERVIEW_SUMMARY.dimension_scorecard,
    anti_pattern_report: MOCK_INTERVIEW_SUMMARY.anti_pattern_report,
  },
];

export const MOCK_MODEL_ANSWER = {
  text:
    "In Q2 2023, our payment API error rate spiked to 4.2% during peak checkout hours. I was primary on-call and owned the incident bridge. I decided to disable the batch consumer and reroute traffic to the fallback queue while I patched the dedup bug in the ingestion worker. Within 45 minutes, error rates dropped back under 0.1%, and we documented a runbook change so the next on-call could catch the pattern faster.",
  what_changed:
    'Replaced "we noticed" with your ownership moment and moved the measurable result to the final sentence.',
};

export const MOCK_INTERVIEW_SESSION: InterviewSession = {
  session_id: "mock-interview-session-001",
  company: "amazon",
  seniority: "senior",
  question_mode: "mixed",
  questions: MOCK_INTERVIEW_QUESTIONS,
  answers: [
    {
      question_id: "mock_q1_ownership",
      answer_text:
        "I was primary on-call when error rates spiked to 4.2% on the payment API. We noticed the queue was backing up and our team rolled out a hotfix. Performance improved significantly after the fix.",
      follow_ups: [
        {
          question: {
            id: "mock_fu_1",
            text: "What specific decision did you personally make during that incident?",
            trigger_reason: "ownership_unclear",
          },
          answer_text:
            "I decided to disable the batch consumer and reroute traffic to the fallback queue while I patched the dedup bug.",
        },
      ],
    },
    {
      question_id: "mock_q2_impact",
      answer_text:
        "I led the microservices migration and cut p99 latency from 800ms to 480ms across 12M daily requests. I wrote the architecture doc, got buy-in from four teams, and we shipped in three months.",
      follow_ups: [],
    },
    {
      question_id: "mock_q3_scenario",
      answer_text:
        "I would map service dependencies before choosing a cutover order. I would probably start with the highest-risk service first since that should reduce blast radius.",
      follow_ups: [],
    },
  ],
  feedback: MOCK_INTERVIEW_FEEDBACK,
  current_question_index: 3,
  current_follow_up_count: 0,
  active_follow_up: null,
  summary: MOCK_INTERVIEW_SUMMARY,
  state: "summary",
};
