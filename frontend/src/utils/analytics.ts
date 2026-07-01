import { getOrCreateSessionId } from "./analyticsSession";
import { useAuthStore } from "../store/authStore";
import { useResumeStore } from "../store/useResumeStore";

interface TrackOptions {
  runId?: string;
  properties?: Record<string, unknown>;
}

export async function track(
  eventName: string,
  options: TrackOptions = {}
): Promise<void> {
  try {
    const state = useResumeStore.getState();
    const result = state.analysisResult;

    const payload = {
      event_name: eventName,
      session_id: getOrCreateSessionId(),
      run_id: options.runId ?? result?.session_id ?? null,
      properties: options.properties ?? {},
      ats_score: result?.ats?.score ?? null,
      jd_match_score: result?.gap?.jd_match_score_before ?? null,
      role_fit_band:
        (result?.role_fit as { band?: string; fitness?: string } | null | undefined)
          ?.band ?? result?.role_fit?.fitness ?? null,
      has_jd: result ? !!(result.gap && !result.gap.resume_only_mode) : null,
      seniority: result?.resume?.seniority ?? null,
    };

    const accessToken = useAuthStore.getState().session?.access_token;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }

    // Fire-and-forget — never await, never throw
    fetch("/api/analytics", {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    }).catch(() => {
      // Silently drop — analytics must never affect UX
    });

  } catch {
    // Silently drop
  }
}
