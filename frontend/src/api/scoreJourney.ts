import { IS_MOCK } from "../hooks/useMockData";
import { supabase } from "../lib/supabase";
import { mockScoreJourney } from "../mocks/mockScoreJourneyData";
import type { ScoreJourneyResult } from "../types";

export const fetchScoreJourneyFromApi = async (): Promise<ScoreJourneyResult> => {
  if (IS_MOCK) {
    await new Promise((r) => setTimeout(r, 300));
    return mockScoreJourney;
  }

  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch("/api/score-journey", { headers });
  if (!res.ok) {
    throw new Error(`Score journey fetch failed: ${res.status}`);
  }
  return (await res.json()) as ScoreJourneyResult;
};
