import { MOCK_ANALYSIS_RESULT } from "../mocks/mockData";
import type { AnalysisResult } from "../types";

export interface FallbackResult {
  analysis: AnalysisResult;
  debugByTab: Record<string, string[]>;
}

const isRoleFitGate = (analysis: AnalysisResult): boolean =>
  analysis.role_fit?.fitness === "underqualified";

export const hydrateWithFallback = (analysis: AnalysisResult): FallbackResult => {
  const debugByTab: Record<string, string[]> = {
    overview: [],
    fixes: [],
    recruiter: [],
    gap: [],
  };

  let next = { ...analysis };
  const roleFitGate = isRoleFitGate(analysis);

  if (!analysis.rewrites) {
    if (!roleFitGate) {
      next = { ...next, rewrites: MOCK_ANALYSIS_RESULT.rewrites };
      debugByTab.fixes.push("`rewrites` missing from API");
    }
  }
  if (!analysis.sim) {
    if (roleFitGate) {
      debugByTab.recruiter.push(
        "Recruiter simulation skipped — role fit pre-check flagged underqualified."
      );
      debugByTab.overview.push(
        "Recruiter shortlist estimate unavailable (role fit gate)."
      );
    } else {
      next = { ...next, sim: MOCK_ANALYSIS_RESULT.sim };
      debugByTab.recruiter.push("`sim` missing from API");
      debugByTab.overview.push("`sim` missing from API");
    }
  }
  if (!analysis.gap) {
    if (!roleFitGate) {
      next = { ...next, gap: MOCK_ANALYSIS_RESULT.gap };
      debugByTab.gap.push("`gap` missing from API");
      debugByTab.overview.push("`gap` missing from API");
      debugByTab.fixes.push("`gap` missing from API");
    }
  }
  if (!analysis.positioning) {
    if (!roleFitGate) {
      next = { ...next, positioning: MOCK_ANALYSIS_RESULT.positioning };
      debugByTab.overview.push("`positioning` missing from API");
    }
  }
  if (!analysis.percentile) {
    if (!roleFitGate) {
      next = { ...next, percentile: MOCK_ANALYSIS_RESULT.percentile };
      debugByTab.overview.push("`percentile` missing from API");
    }
  }

  return { analysis: next, debugByTab };
};
