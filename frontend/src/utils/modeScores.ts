import type { AnalysisResult } from "../types";
import { hasJobDescription } from "./hasJobDescription";

export type FixMode = "safe" | "full";

export interface FixModeBaseline {
  baselineAts: number;
  baselineJd: number | null;
  /** Backend-estimated JD match after all fixes (not ATS projection). */
  targetJd: number | null;
  hasJd: boolean;
  jdGain: number;
}

/** Baseline scores for fix mode cards — no ATS projections. */
export function getFixModeBaseline(analysisResult: AnalysisResult): FixModeBaseline {
  const baselineAts = analysisResult.ats.score;
  const hasJd = hasJobDescription(analysisResult.gap);
  const baselineJd = hasJd ? analysisResult.gap?.jd_match_score_before ?? null : null;
  const targetJd = hasJd ? analysisResult.gap?.jd_match_score_after ?? null : null;
  const jdGain =
    baselineJd !== null && targetJd !== null ? Math.max(0, targetJd - baselineJd) : 0;

  return {
    baselineAts,
    baselineJd,
    targetJd,
    hasJd,
    jdGain,
  };
}

export function downloadStyleForMode(mode: FixMode): "balanced" | "aggressive" {
  return mode === "safe" ? "balanced" : "aggressive";
}
