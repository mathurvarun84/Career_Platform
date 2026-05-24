import { useCallback, useState } from "react";
import axiosInstance from "../api/client";

interface RescoreResponse {
  ats_score: number;
  delta_from_original: number;
  breakdown: Record<string, number>;
  ats_issues: string[];
}

export function useRescore(sessionId: string) {
  const [liveScore, setLiveScore] = useState<number | null>(null);
  const [scoreDelta, setScoreDelta] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(false);

  const rescore = useCallback(async () => {
    if (!sessionId) return null;
    setIsLoading(true);

    try {
      const response = await axiosInstance.get<RescoreResponse>(
        `/api/session/${sessionId}/rescore`
      );
      setLiveScore(response.data.ats_score);
      setScoreDelta(response.data.delta_from_original);
      return response.data;
    } catch (error) {
      console.error("Rescore failed:", error);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return { liveScore, scoreDelta, rescore, isLoading };
}
