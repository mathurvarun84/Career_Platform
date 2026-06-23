/**
 * fixPlanAdapter.ts
 *
 * Translates FixPlanItem → PriorityFix so existing card components need no changes.
 * This is the only file that does this translation. No inferGapTypeFromText.
 * No resolvePatchForFix. No label heuristics.
 */

import type { AnalysisResult, FixPlanItem, PriorityFix, ResumePatch } from "../types";
import { buildActionableFixesList } from "./fixesPipeline";

/**
 * Convert a FixPlanItem into the PriorityFix shape card components consume.
 * entry_id and sub_label are passed through as-is (opaque on the frontend).
 */
export function fixPlanItemToPriorityFix(item: FixPlanItem): PriorityFix {
  return {
    section:              item.section,
    gap_reason:           item.issue,
    rewrite_instruction:  item.after_text ?? "",
    missing_keywords:     item.missing_keywords,
    needs_change:         true,
    gap_type:             item.gap_type,
    requires_user_input:  item.requires_user_input,
    coaching_question:    item.coaching_question ?? undefined,
    coaching_hint:        item.coaching_hints,
    resume_grounded_hints: item.resume_grounded_hints,
    auto_apply:           item.auto_apply,
    sub_label:            item.sub_label ?? undefined,
    entry_id:             item.entry_id ?? undefined,
    original_text:        item.before_text ?? "",
    patch_text:           item.after_text ?? "",
    // Bridge fields — opaque, used only by ActionableFixes for patch lookup
    _fix_plan_id:         item.fix_id,
    _patch_id:            item.patch_id ?? undefined,
  };
}

/**
 * Check if a converted fix has adequate data for proper card rendering.
 * Returns false only when data is genuinely missing for the item kind.
 */
export function hasAdequateData(fix: PriorityFix, item: FixPlanItem): boolean {
  if (item.kind === "coaching") {
    // coaching_question is ideal but absence doesn't mean bad data — EvidenceCoachingCard
    // can display gap_reason as the question. A null coaching_question from a single item
    // must NOT cause the entire fix_plan to fall back to the legacy pipeline.
    return Boolean(fix.coaching_question?.trim() || fix.gap_reason?.trim());
  }
  // Surgical/surface patches: having any rewrite text is enough — a missing patch_id is
  // NOT sparse data, it means the card renders from rewrite_instruction as before/after.
  if (item.kind === "surgical_patch" || item.kind === "surface_keyword") {
    return Boolean(fix.rewrite_instruction?.trim() || fix.patch_text?.trim());
  }
  // Rewrite blocks need rewrite_instruction
  if (item.kind === "rewrite_block") {
    return Boolean(fix.rewrite_instruction?.trim());
  }
  // Info-only and unknown kinds are always adequate
  return true;
}

/**
 * Read fix_plan from AnalysisResult and return as PriorityFix[].
 *
 * Hybrid approach:
 * 1. Try fix_plan if api_version >= 2 and data looks complete
 * 2. Fall back to legacy pipeline if fix_plan data is sparse or incomplete
 * 3. For old sessions (api_version < 2), always use legacy pipeline
 */
export function buildFixesFromPlan(
  analysisResult: AnalysisResult | null,
  options: { suppressEvidenceGaps?: boolean } = {}
): PriorityFix[] {
  if (!analysisResult) return [];

  const hasFixPlan =
    Array.isArray(analysisResult.fix_plan) &&
    analysisResult.fix_plan.length > 0;
  const isNewSession = (analysisResult.api_version ?? 1) >= 2;

  // Old session or no fix_plan: use legacy pipeline
  if (!hasFixPlan) {
    if (isNewSession && !hasFixPlan) {
      // New session but empty plan — respect it (e.g. underqualified early exit)
      return [];
    }
    // Old session shape — use legacy pipeline
    console.warn(
      "[fixPlanAdapter] fix_plan absent or api_version < 2 — falling back to buildActionableFixesList. " +
      "This should only happen for sessions analysed before the FixPlan migration."
    );
    return buildActionableFixesList(analysisResult, {
      suppressedEvidenceGaps: options.suppressEvidenceGaps,
    });
  }

  // At this point, hasFixPlan is true and isNewSession is true
  const fixPlan = analysisResult.fix_plan;
  if (!fixPlan) return [];

  // Convert and filter fix_plan items
  const converted = fixPlan
    .filter((item) => item.kind !== "info_only")
    .filter((item) => !options.suppressEvidenceGaps || item.kind !== "coaching")
    .map((item) => ({ item, fix: fixPlanItemToPriorityFix(item) }));

  // Check if converted items have adequate data
  const hasAdequateItems = converted.every((c) => hasAdequateData(c.fix, c.item));

  // Fall back only when data is genuinely sparse — structural-only plans are valid
  if (!hasAdequateItems) {
    console.warn(
      "[fixPlanAdapter] fix_plan data sparse — falling back to buildActionableFixesList."
    );
    return buildActionableFixesList(analysisResult, {
      suppressedEvidenceGaps: options.suppressEvidenceGaps,
    });
  }

  // fix_plan has good data — use it
  return converted.map((c) => c.fix);
}

/**
 * Look up a ResumePatch by fix_plan item's pre-resolved patch_id.
 * This replaces resolvePatchForFix() for new sessions.
 * Returns undefined for coaching items (they have no patch_id by contract).
 */
export function resolvePatchFromPlan(
  fix: PriorityFix,
  patches: ResumePatch[] | undefined
): ResumePatch | undefined {
  const patchId = fix._patch_id;
  if (!patchId || !patches?.length) return undefined;
  return patches.find((p) => p.patch_id === patchId);
}

/**
 * Get the count of actionable fixes from fix_plan (or fallback).
 * Used for tab badge — must stay in sync with buildFixesFromPlan.
 */
export function countFixesFromPlan(
  analysisResult: AnalysisResult | null,
  options: { suppressEvidenceGaps?: boolean } = {}
): number {
  return buildFixesFromPlan(analysisResult, options).length;
}

/**
 * Return all fix_plan items for the Gap tab — includes info_only items
 * (diagnostic-only gaps that have no fix action).
 * Returns empty array for old sessions (no fix_plan).
 */
export function buildGapDiagnostics(
  analysisResult: AnalysisResult | null
): FixPlanItem[] {
  if (!analysisResult) return [];
  const isNewSession = (analysisResult.api_version ?? 1) >= 2;
  if (!isNewSession || !Array.isArray(analysisResult.fix_plan)) return [];
  return analysisResult.fix_plan;
}
