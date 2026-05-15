import { useEffect, useState } from "react";

import { supabase } from "../lib/supabase";
import type { UsageLimits } from "../types";
import { useAuthStore } from "../store/authStore";

export function useUsageLimits() {
  const user = useAuthStore((s) => s.user);
  const [limits, setLimits] = useState<UsageLimits | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.id) {
      setLimits(null);
      setLoading(false);
      return;
    }
    const userId = user.id;

    let isMounted = true;

    async function fetchLimits() {
      try {
        setLoading(true);
        setError(null);

        const { data, error: err } = await supabase
          .from("usage_limits")
          .select("total_uploads, uploads_this_month, last_reset_date")
          .eq("user_id", userId)
          .single();

        if (err && err.code !== "PGRST116") {
          throw err;
        }

        if (!isMounted) return;

        if (data) {
          setLimits({
            total_uploads: data.total_uploads ?? 0,
            uploads_this_month: data.uploads_this_month ?? 0,
            last_reset_date: data.last_reset_date,
          });
        } else {
          setLimits({ total_uploads: 0, uploads_this_month: 0 });
        }
      } catch (err) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Failed to fetch usage limits";
        setError(msg);
        setLimits(null);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    void fetchLimits();

    return () => {
      isMounted = false;
    };
  }, [user?.id]);

  return { limits, loading, error };
}
