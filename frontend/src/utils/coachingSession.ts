import type { AnalysisResult } from "../types";

/** Coaching APIs use the FastAPI job id as session_id (mirrored on analysisResult.session_id). */
export function getCoachingSessionId(
  jobId: string | null | undefined,
  analysisResult: AnalysisResult | null | undefined
): string {
  return (
    analysisResult?.session_id?.trim() ||
    jobId?.trim() ||
    analysisResult?.job_id?.trim() ||
    ""
  );
}
