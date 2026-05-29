import type { AntiPatternKey, BehavioralDimension } from "../types";

export const ANTI_PATTERNS: Record<
  AntiPatternKey,
  { label: string; description: string; signal: string }
> = {
  we_default: {
    label: "We Default",
    description:
      'Candidate uses "we" throughout without clearly stating personal contribution.',
    signal:
      'Look for: "we built", "we decided", "our team did" with no "I" ownership claim.',
  },
  vague_quantification: {
    label: "Vague Quantification",
    description: "Impact described with adjectives instead of numbers.",
    signal:
      'Look for: "significantly improved", "greatly reduced", "much faster" with no metric.',
  },
  story_recycling: {
    label: "Story Recycling",
    description: "Same story used to answer a different dimension question.",
    signal: "Compare answer to previous answers in session for overlap.",
  },
  impact_buried: {
    label: "Impact Buried",
    description: "Result mentioned as an afterthought in the final sentence.",
    signal:
      "Result should appear in the first 40% of the answer, not the last sentence.",
  },
  hypothesis_without_proof: {
    label: "Hypothesis Without Proof",
    description: "Claimed impact without causal evidence.",
    signal:
      'Look for: "which probably helped", "I think it improved", "should have resulted in".',
  },
  escalation_default: {
    label: "Escalation Default",
    description:
      "Resolved conflict or ambiguity by going to manager rather than owning resolution.",
    signal:
      'Look for: "so I went to my manager", "we escalated it", "my lead decided".',
  },
  scope_collapse: {
    label: "Scope Collapse",
    description:
      "Senior candidate tells an IC-level story with no organizational leverage.",
    signal:
      "For Staff+/EM: story should show cross-team influence, not just personal execution.",
  },
  no_reflection: {
    label: "No Reflection",
    description:
      "Story ends at the event without stating learning or behavioral change.",
    signal:
      "Look for answers that stop at delivery with no lesson or what changed next time.",
  },
  credit_deflection: {
    label: "Credit Deflection",
    description: "Minimises own agency in the outcome.",
    signal:
      'Look for: "my manager suggested", "lucky timing", "the team handled most of it".',
  },
  recency_bias: {
    label: "Recency Bias",
    description:
      "Can only cite recent examples; no evidence of sustained behavior.",
    signal:
      "Look for a single recent story with no pattern of behavior over time.",
  },
  rehearsed_script: {
    label: "Rehearsed Script",
    description:
      "Answer sounds template-assembled rather than lived-in.",
    signal:
      'Look for: formal transitions, round numbers, no names, no tension or doubt.',
  },
};

export const DIMENSIONS: Record<
  BehavioralDimension,
  { label: string; ic_expectation: string; em_expectation: string }
> = {
  ownership: {
    label: "Ownership",
    ic_expectation:
      "Takes end-to-end accountability for a system or feature, including production issues.",
    em_expectation:
      "Sets direction, removes blockers, holds team accountable without micromanaging.",
  },
  impact_and_scale: {
    label: "Impact & Scale",
    ic_expectation: "Quantified impact on user-facing or infrastructure metrics.",
    em_expectation:
      "Business-level impact; revenue, retention, headcount leverage.",
  },
  influence_without_authority: {
    label: "Influence Without Authority",
    ic_expectation:
      "Drives alignment across teams or stakeholders without formal authority.",
    em_expectation:
      "Shapes org priorities and cross-functional outcomes through leverage, not title.",
  },
  problem_solving: {
    label: "Problem Solving",
    ic_expectation:
      "Structured approach to ambiguity with data, tradeoffs, and course correction.",
    em_expectation:
      "Frames systemic problems and sets the decision framework for multiple teams.",
  },
  collaboration: {
    label: "Collaboration",
    ic_expectation:
      "Works effectively across functions under pressure with clear communication.",
    em_expectation:
      "Builds trust across teams and resolves friction at org level.",
  },
  growth_mindset: {
    label: "Growth Mindset",
    ic_expectation:
      "Shows learning from failure or feedback with concrete behavioral change.",
    em_expectation:
      "Creates learning culture and models receiving hard feedback without defensiveness.",
  },
  conflict_resolution: {
    label: "Conflict Resolution",
    ic_expectation:
      "Handles disagreement directly with data and a clear resolution path.",
    em_expectation:
      "Navigates org-level conflict and commits to decisions after dissent.",
  },
};

export const ALL_BEHAVIORAL_DIMENSIONS: BehavioralDimension[] = [
  "ownership",
  "impact_and_scale",
  "influence_without_authority",
  "problem_solving",
  "collaboration",
  "growth_mindset",
  "conflict_resolution",
];
