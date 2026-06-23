import assert from "node:assert/strict";

import type { FixPlanItem, PriorityFix } from "../types";
import { buildFixesFromPlan, hasAdequateData } from "./fixPlanAdapter";
import { isCoachingCard } from "./fixesPipeline";

function makeCoachingItem(
  issue: string,
  coachingQuestion?: string | null
): FixPlanItem {
  return {
    fix_id: "coaching-1",
    kind: "coaching",
    section: "experience",
    issue,
    missing_keywords: [],
    coaching_hints: [],
    resume_grounded_hints: [],
    requires_user_input: true,
    gap_type: "evidence",
    risk: "safe",
    auto_apply: false,
    status: "pending",
    coaching_question: coachingQuestion ?? null,
  };
}

function coachingFixFromItem(item: FixPlanItem): PriorityFix {
  return {
    section: item.section,
    gap_reason: item.issue,
    rewrite_instruction: item.after_text ?? "",
    missing_keywords: item.missing_keywords,
    needs_change: true,
    gap_type: item.gap_type,
    requires_user_input: item.requires_user_input,
    coaching_question: item.coaching_question ?? undefined,
  };
}

// Bug 2 lock: hasAdequateData accepts gap_reason-only coaching items
{
  const item = makeCoachingItem("Overall seniority and domain fit gap: 12y vs 15y required");
  const fix = coachingFixFromItem(item);
  assert.equal(hasAdequateData(fix, item), true);
}

{
  const item = makeCoachingItem("Missing team scope", "What was your team size?");
  const fix = coachingFixFromItem(item);
  assert.equal(hasAdequateData(fix, item), true);
}

{
  const item = makeCoachingItem("", null);
  const fix = coachingFixFromItem(item);
  assert.equal(hasAdequateData(fix, item), false);
}

// Bug 2 lock: buildFixesFromPlan must not fall back when only gap_reason is present
{
  const result = {
    api_version: 2,
    fix_plan: [
      makeCoachingItem("Overall seniority and domain fit gap: 12y vs 15y required"),
    ],
    ats: {
      score: 55,
      breakdown: { keyword_match: 14, formatting: 14, readability: 14, impact_metrics: 13 },
      details: [],
      ats_issues: [],
    },
    resume: {
      experience_years: 8,
      seniority: "senior",
      tech_stack: [],
      domains: [],
      has_metrics: true,
      has_summary: true,
      sections_present: ["experience"],
      resume_sections: {},
    },
    gap: {
      resume_only_mode: true,
      jd_match_score_before: 0,
      jd_match_score_after: null,
      section_gaps: [],
      missing_keywords: [],
      priority_fixes: [],
    },
    patches: [],
  } as import("../types").AnalysisResult;

  const fixes = buildFixesFromPlan(result);
  assert.equal(fixes.length, 1, "coaching item with gap_reason only must not trigger legacy fallback");
  assert.equal(fixes[0]?.gap_reason?.includes("seniority"), true);
}

// Bug 3 lock: structural + requires_user_input → coaching card
{
  const structuralEvidence = {
    gap_type: "structural" as const,
    requires_user_input: true,
    coaching_question: "What was your ownership scope?",
    rewrite_instruction: "some instruction",
    patch_text: "some text",
    section: "experience",
    gap_reason: "Missing ownership scope",
    missing_keywords: [],
    needs_change: true,
  };
  assert.equal(isCoachingCard(structuralEvidence), true);

  const surface = {
    gap_type: "surface" as const,
    requires_user_input: false,
    section: "skills",
    gap_reason: "Missing Kafka",
    missing_keywords: ["Kafka"],
    needs_change: true,
  };
  assert.equal(isCoachingCard(surface), false);
}

console.log("fixPlanAdapter.test.ts: all assertions passed");
