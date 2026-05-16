import type { AnalysisResult, PriorityFix, SSEProgressEvent } from "../types";

interface ResultEnvelope {
  status?: string;
  result?: unknown;
  error?: string | null;
  progress?: unknown;
}

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Max idle time (ms) without stream data before aborting. Override via VITE_ANALYZE_TIMEOUT_MS. */
export const ANALYZE_TIMEOUT_MS = (() => {
  const raw = import.meta.env.VITE_ANALYZE_TIMEOUT_MS;
  const parsed = raw !== undefined && raw !== "" ? Number.parseInt(String(raw), 10) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 300_000;
})();

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

export const normalizeAnalysisResult = (payload: unknown): AnalysisResult => {
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
  const rawSim =
    (raw.sim as Record<string, unknown> | null | undefined) ??
    (raw.sim_result as Record<string, unknown> | null | undefined) ??
    (raw.recruiter_sim as Record<string, unknown> | null | undefined) ??
    (raw.recruiter_simulation as Record<string, unknown> | null | undefined) ??
    null;

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
    sim:
      rawSim && typeof rawSim === "object" && "sim" in rawSim
        ? ((rawSim.sim as AnalysisResult["sim"]) ?? null)
        : ((rawSim as AnalysisResult["sim"]) ?? null),
  } as AnalysisResult;

  return normalized;
};

/**
 * Legacy path: POST /api/analyze returned JSON job_id + separate SSE stream.
 * Backend now streams from POST /api/analyze directly — prefer AnalysisProgress fetch reader.
 */
export async function analyzeResume(
  file: File,
  jdText?: string,
  callbacks?: AnalyzeCallbacks,
  accessToken?: string | null
): Promise<AnalysisResult> {
  const formData = new FormData();
  formData.append("resume", file);
  formData.append("jd_text", jdText ?? "");
  formData.append("run_sim", "true");

  const controller = new AbortController();
  let timeoutId = window.setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
  const resetStreamTimeout = (): void => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
  };

  const headers: Record<string, string> = {};
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal,
    });

    if (response.status === 402) {
      let detail: Record<string, unknown> = { code: "LIMIT_REACHED" };
      try {
        const text = await response.text();
        const parsed = JSON.parse(text) as Record<string, unknown>;
        detail = typeof parsed.detail === "object" && parsed.detail ? (parsed.detail as Record<string, unknown>) : detail;
      } catch {
        /* fallback to default detail */
      }
      const error = new Error("Monthly limit reached") as Error & { status?: number; detail?: Record<string, unknown> };
      error.status = 402;
      error.detail = detail;
      throw error;
    }

    if (!response.ok || !response.body) {
      const text = await response.text();
      throw new Error(text || `Analyze failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult: AnalysisResult | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      resetStreamTimeout();
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const rawBlock = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of rawBlock.split("\n")) {
          const trimmed = line.trim();
          if (!trimmed.startsWith("data:")) {
            continue;
          }
          const jsonStr = trimmed.replace(/^data:\s*/, "").trim();
          if (!jsonStr) {
            continue;
          }
          const payload = JSON.parse(jsonStr) as Record<string, unknown>;
          if (payload.event === "step_complete" && typeof payload.step === "number") {
            callbacks?.onProgress?.({
              status: "running",
              step: (payload.step as number) + 1,
              label: typeof payload.label === "string" ? payload.label : "",
              pct: 10,
            });
          }
          if (payload.event === "analysis_complete" && payload.result) {
            finalResult = normalizeAnalysisResult(payload.result);
            const jid =
              typeof finalResult.job_id === "string" ? finalResult.job_id : "";
            if (jid) {
              callbacks?.onJobCreated?.(jid);
            }
          }
          if (payload.event === "error") {
            throw new Error(
              typeof payload.message === "string"
                ? payload.message
                : "Analysis failed on server."
            );
          }
        }
      }
    }

    if (!finalResult) {
      throw new Error("Stream ended without analysis result.");
    }
    return finalResult;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(
        `Analysis timed out after ${Math.round(ANALYZE_TIMEOUT_MS / 1000)}s without a response. Try again.`
      );
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(String(error));
  } finally {
    window.clearTimeout(timeoutId);
  }
}
