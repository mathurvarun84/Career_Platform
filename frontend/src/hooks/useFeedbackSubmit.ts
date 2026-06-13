import { supabase } from "../lib/supabase";
import { useResumeStore } from "../store/useResumeStore";
import type { FeedbackRequest } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function getAuthToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export function useFeedbackSubmit() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const feedbackState = useResumeStore((s) => s.feedbackState);

  const submit = async (payload: FeedbackRequest): Promise<boolean> => {
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) {
        return false;
      }

      const res = await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...payload,
          ats_score: analysisResult?.ats?.score ?? undefined,
          role_fit_band: analysisResult?.role_fit?.fitness ?? undefined,
          run_count: feedbackState?.session_count ?? undefined,
        }),
      });
      return res.ok;
    } catch {
      return false;
    }
  };

  return { submit };
}
