import axios, { AxiosError } from "axios";

import type { AnalysisResult, PriorityFix, SSEProgressEvent } from "../types";

interface FastAPIErrorDetail {
  msg?: string;
}

interface FastAPIErrorResponse {
  detail?: string | FastAPIErrorDetail | FastAPIErrorDetail[];
}

interface ResultEnvelope {
  status?: string;
  result?: unknown;
  error?: string | null;
  progress?: unknown;
}

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const ANALYZE_TIMEOUT_MS = 60_000;

interface AnalyzeCallbacks {
  onJobCreated?: (jobId: string) => void;
  onProgress?: (progress: SSEProgressEvent) => void;
  onPartial?: (partial: Partial<AnalysisResult>) => void;
}

const inferSectionFromText = (text: string): string => {
  const lower = text.toLowerCase();
  if (lower.includes("summary")) return "summary";
  if (lower.includes("skill") || lower.includes("keyword")) return "skills";
  if (lower.includes("experience") || lower.includes("team") || lower.includes("impact")) return "experience";
  if (lower.includes("education") || lower.includes("degree")) return "education";
  if (lower.includes("certification")) return "certifications";
  if (lower.includes("award")) return "awards";
  return "summary";
};

const extractKeywords = (text: string): string[] =>
  Array.from(
    new Set(
      (text.match(/\b[A-Z][A-Za-z0-9/+#.-]{2,}\b/g) ?? [])
        .map((word) => word.trim())
        .slice(0, 5)
    )
  );

const normalizeAnalysisResult = (payload: unknown): AnalysisResult => {
  const maybeEnvelope = payload as ResultEnvelope;
  const raw =
    maybeEnvelope &&
    typeof maybeEnvelope === "object" &&
    "result" in maybeEnvelope &&
    maybeEnvelope.result
      ? (maybeEnvelope.result as Record<string, unknown>)
      : (payload as Record<string, unknown>);

  const rawGap = (raw.gap as Record<string, unknown> | null | undefined) ?? null;
  const rawRewrites = raw.rewrites as Record<string, unknown> | null | undefined;

  const isPriorityFix = (item: unknown): item is PriorityFix =>
    typeof item === "object" &&
    item !== null &&
    "section" in item &&
    "gap_reason" in item &&
    "rewrite_instruction" in item &&
    "missing_keywords" in item &&
    "needs_change" in item;

  const fixesFromSectionGaps: PriorityFix[] = (
    (rawGap?.section_gaps as Array<Record<string, unknown>> | undefined) ?? []
  )
    .filter((g) => g.needs_change === true)
    .map((g) => ({
      section: String(g.section ?? "summary"),
      gap_reason: String(g.gap_reason ?? "").trim() || "Gap identified for this section",
      rewrite_instruction:
        String(g.rewrite_instruction ?? "").trim() ||
        "Refine wording to reflect JD requirements.",
      missing_keywords: Array.isArray(g.missing_keywords)
        ? (g.missing_keywords as string[])
        : [],
      needs_change: true,
    }));

  const fixesFromDetailedEval: PriorityFix[] = (
    (rawGap?.changes as Array<Record<string, unknown>> | undefined) ?? []
  ).map((c) => {
    const loc = (c.location as Record<string, unknown> | undefined) ?? {};
    const why = String(c.why ?? "").trim();
    const suggested = String(c.suggested_text ?? "").trim();
    return {
      section: String(loc.section ?? "summary"),
      gap_reason: why || "Change suggested for JD alignment",
      rewrite_instruction:
        suggested ||
        why ||
        "Apply the suggested change to strengthen JD fit.",
      missing_keywords: Array.isArray(c.keywords_added)
        ? (c.keywords_added as string[])
        : [],
      needs_change: true,
    };
  });

  const rawPriorityFixes = (rawGap?.priority_fixes as unknown[] | undefined) ?? [];
  const priorityFixObjects = rawPriorityFixes.filter(isPriorityFix);

  const fixesFromLegacyGaps: PriorityFix[] = (
    (rawGap?.gaps as Array<Record<string, unknown>> | undefined) ?? []
  ).map((gapItem) => {
    const description = String(gapItem.description ?? "").trim();
    const suggestion = String(gapItem.suggestion ?? "").trim();
    return {
      section: inferSectionFromText(description),
      gap_reason: description || "Section needs improvement",
      rewrite_instruction:
        suggestion || description || "Refine wording and clarity.",
      missing_keywords: extractKeywords(description),
      needs_change: true,
    };
  });

  let synthesizedFixes: PriorityFix[] = [];
  if (fixesFromSectionGaps.length > 0) {
    synthesizedFixes = fixesFromSectionGaps;
  } else if (priorityFixObjects.length > 0) {
    synthesizedFixes = priorityFixObjects;
  } else if (fixesFromDetailedEval.length > 0) {
    synthesizedFixes = fixesFromDetailedEval;
  } else if (fixesFromLegacyGaps.length > 0) {
    synthesizedFixes = fixesFromLegacyGaps;
  }

  const beforeScoreFromGap =
    (rawGap?.jd_match_score_before as number | null | undefined) ??
    (rawGap?.match_score as number | null | undefined) ??
    (raw.ats as { score?: number } | undefined)?.score ??
    null;
  const afterScoreFromGap =
    (rawGap?.jd_match_score_after as number | undefined) ??
    (rawGap?.estimated_score_after as number | undefined) ??
    (rawGap?.match_score as number | undefined) ??
    (raw.ats as { score?: number } | undefined)?.score ??
    0;

  const normalized = {
    ...(raw as unknown as AnalysisResult),
    gap: rawGap
      ? {
          ...rawGap,
          jd_match_score_before: beforeScoreFromGap,
          jd_match_score_after: afterScoreFromGap,
          section_gaps: (rawGap.section_gaps as unknown[] | undefined) ?? [],
          missing_keywords: (rawGap.missing_keywords as string[] | undefined) ?? [],
          priority_fixes: synthesizedFixes,
          changes: (rawGap.changes as unknown[] | undefined) ?? [],
        }
      : null,
    rewrites:
      rawRewrites && typeof rawRewrites === "object" && "rewrites" in rawRewrites
        ? ((rawRewrites.rewrites as Record<string, unknown>) ?? null)
        : ((rawRewrites as Record<string, unknown> | null) ?? null),
  } as AnalysisResult;

  return normalized;
};

const getErrorMessage = (error: AxiosError<FastAPIErrorResponse>): string => {
  const detail = error.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).filter(Boolean).join(", ");
  }
  if (detail?.msg) {
    return detail.msg;
  }
  if (error.code === "ECONNABORTED") {
    return "Request timed out. Please try again.";
  }
  if (error.message === "Network Error") {
    return `Network Error: cannot reach API at ${API_BASE_URL}. Start backend server and verify VITE_API_URL.`;
  }
  return error.response?.statusText || error.message;
};

const waitForAnalysisCompletion = async (
  jobId: string,
  callbacks?: AnalyzeCallbacks
): Promise<void> =>
  new Promise((resolve, reject) => {
    const source = new EventSource(`${API_BASE_URL}/api/stream/${jobId}`);

    source.onmessage = (event: MessageEvent<string>) => {
      const payload = JSON.parse(event.data) as SSEProgressEvent;
      callbacks?.onProgress?.(payload);
      if (payload.type === "partial" && payload.partial_result) {
        callbacks?.onPartial?.(payload.partial_result);
      }
      if (payload.status === "complete") {
        source.close();
        resolve();
      }
      if (payload.status === "error") {
        source.close();
        reject(new Error(payload.error ?? payload.label ?? "Analysis failed on server."));
      }
    };

    source.onerror = () => {
      source.close();
      reject(new Error("Connection lost while tracking analysis progress."));
    };
  });

export async function analyzeResume(
  file: File,
  jdText?: string,
  callbacks?: AnalyzeCallbacks
): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("resume", file);
  formData.append("jd_text", jdText ?? "");
  formData.append("run_sim", "true");

  try {
    const analyzeResponse = await axios.post<{ job_id: string }>(
      `${API_BASE_URL}/api/analyze`,
      formData,
      { timeout: ANALYZE_TIMEOUT_MS }
    );

    const jobId = analyzeResponse.data.job_id;
    callbacks?.onJobCreated?.(jobId);
    await waitForAnalysisCompletion(jobId, callbacks);

    const resultResponse = await axios.get<unknown>(
      `${API_BASE_URL}/api/result/${jobId}`,
      { timeout: ANALYZE_TIMEOUT_MS }
    );
    const normalized = normalizeAnalysisResult(resultResponse.data);
    return { ...normalized, job_id: jobId };
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = getErrorMessage(error);
      if (error.response?.status === 422) {
        throw new Error(`Validation failed: ${message}`);
      }
      if (error.response?.status === 500) {
        throw new Error(`Server error: ${message}`);
      }
      throw new Error(message);
    }
    throw error;
  }
}
