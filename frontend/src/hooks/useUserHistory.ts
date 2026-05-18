import { useCallback, useEffect, useState } from "react";

import { supabase } from "../lib/supabase";
import { useResumeStore } from "../store/useResumeStore";
import type { HistoryEntry } from "../types";
import { useAuthStore } from "../store/authStore";

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
            percentile_value,
            created_at,
            resume_uploads(file_name, created_at, target_company, target_role)
          `
        )
        .eq("user_id", user.id)
        .order("created_at", { ascending: false });

      if (err) {
        throw err;
      }

      const typed = (data || []).map((row: unknown) => {
        const r = row as Record<string, unknown>;
        const uploads = r.resume_uploads as
          | {
              file_name: string;
              created_at?: string;
              target_company?: string | null;
              target_role?: string | null;
            }
          | {
              file_name: string;
              created_at?: string;
              target_company?: string | null;
              target_role?: string | null;
            }[]
          | null
          | undefined;

        const uploadRow = Array.isArray(uploads) ? uploads[0] : uploads;

        return {
          id: r.id as string,
          upload_id: r.upload_id as string,
          user_id: r.user_id as string,
          file_name: uploadRow?.file_name ?? "Unknown",
          target_company: uploadRow?.target_company ?? null,
          target_role: uploadRow?.target_role ?? null,
          ats_score: (r.ats_score as number | null) ?? null,
          jd_match_score: (r.jd_match_score as number | null) ?? null,
          shortlist_rate: (r.shortlist_rate as number | null) ?? null,
          percentile: (r.percentile_value as number | null) ?? null,
          analyzed_at: (r.created_at as string) ?? "",
          uploaded_at: uploadRow?.created_at,
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
