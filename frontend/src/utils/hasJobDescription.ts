import type { GapResult } from "../types";

/**
 * True only when a job description was uploaded and scored (not resume-only mode).
 */
export function hasJobDescription(gap: GapResult | null | undefined): boolean {
  if (!gap) {
    return false;
  }
  if (gap.resume_only_mode === true) {
    return false;
  }
  const before = gap.jd_match_score_before;
  return typeof before === "number" && before > 0;
}
