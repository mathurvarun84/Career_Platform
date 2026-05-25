import type { PriorityFix } from "../types";

/** Sections the gap analyzer marks as OK — never show as fix cards. */
const NO_CHANGE_RE =
  /no change(s)? needed|no change required|unchanged|looks good|well[- ]?optimi(s|z)ed/i;

/**
 * True when this item should appear on the Actionable Fixes tab.
 * Shared rules with backend gap_analyzer._is_actionable_gap.
 */
export function isActionableFix(fix: PriorityFix): boolean {
  const reason = (fix.gap_reason ?? "").trim();
  const instruction = (fix.rewrite_instruction ?? "").trim();

  if (!reason || NO_CHANGE_RE.test(reason)) {
    return false;
  }

  if (fix.needs_change) {
    return Boolean(instruction || fix.missing_keywords?.length);
  }

  if (fix.gap_type === "surface" && fix.auto_apply) {
    return Boolean(instruction);
  }

  return false;
}
