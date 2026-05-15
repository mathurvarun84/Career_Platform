import { useCallback, useEffect, useState } from "react";

import { MOCK_HISTORY } from "../mocks/mockData";
import { supabase } from "../lib/supabase";
import { useResumeStore } from "../store/useResumeStore";
import type { HistoryEntry } from "../types";
import { useAuthStore } from "../store/authStore";
import { IS_MOCK } from "./useMockData";

function mockEntriesFromRuns(): HistoryEntry[] {
  return MOCK_HISTORY.runs.map((run) => ({
    id: run.run_id,
    upload_id: run.run_id,
    user_id: "mock-user",
    file_name: `resume-${run.run_id}.pdf`,
    target_company: null,
    target_role: null,
    ats_score: run.ats_score,
    jd_match_score: run.jd_match,
    shortlist_rate: null,
    percentile: run.percentile,
    analyzed_at: run.timestamp,
  }));
}

export function useUserHistory() {
  const user = useAuthStore((s) => s.user);
  const historyRefreshKey = useResumeStore((s) => s.historyRefreshKey);
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!user?.id) {
      setEntries([]);
      setLoading(false);
      return;
    }

    if (IS_MOCK) {
      setEntries(mockEntriesFromRuns());
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const { data, error: err } = await supabase
        .from("analysis_results")
        .select(
          `
            id,
            upload_id,
            user_id,
            ats_score,
            jd_match_score,
            shortlist_rate,
            percentile,
            target_company,
            target_role,
            analyzed_at,
            resume_uploads(file_name, uploaded_at)
          `
        )
        .eq("user_id", user.id)
        .order("analyzed_at", { ascending: false });

      if (err) {
        throw err;
      }

      const typed = (data || []).map((row: unknown) => {
        const r = row as Record<string, unknown>;
        const uploads = r.resume_uploads as
          | { file_name: string; uploaded_at?: string }
          | { file_name: string; uploaded_at?: string }[]
          | null
          | undefined;

        const uploadRow = Array.isArray(uploads) ? uploads[0] : uploads;

        return {
          id: r.id as string,
          upload_id: r.upload_id as string,
          user_id: r.user_id as string,
          file_name: uploadRow?.file_name ?? "Unknown",
          target_company: (r.target_company as string | null) ?? null,
          target_role: (r.target_role as string | null) ?? null,
          ats_score: (r.ats_score as number | null) ?? null,
          jd_match_score: (r.jd_match_score as number | null) ?? null,
          shortlist_rate: (r.shortlist_rate as number | null) ?? null,
          percentile: (r.percentile as number | null) ?? null,
          analyzed_at: r.analyzed_at as string,
          uploaded_at: uploadRow?.uploaded_at,
        } as HistoryEntry;
      });

      setEntries(typed);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to fetch history";
      setError(msg);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void fetchHistory();
  }, [fetchHistory, historyRefreshKey]);

  return { entries, loading, error, refetch: fetchHistory };
}
