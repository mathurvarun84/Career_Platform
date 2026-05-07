import { useQuery } from "@tanstack/react-query";
import type { AxiosError } from "axios";

import { getHistory as fetchHistory, getResult } from "../api/client";
import { MOCK_ANALYSIS_RESULT, MOCK_HISTORY } from "../mocks/mockData";
import type { AnalysisResult, HistoryResponse } from "../types";

export const IS_MOCK: boolean = import.meta.env.VITE_USE_MOCK === "true";

export const useAnalysisResult = (jobId: string | null) => {
  if (IS_MOCK) {
    return {
      data: MOCK_ANALYSIS_RESULT,
      isLoading: false,
      error: null as AxiosError | null,
    };
  }

  return useQuery<AnalysisResult, AxiosError>({
    queryKey: ["analysis-result", jobId],
    queryFn: () => getResult(jobId ?? ""),
    enabled: jobId !== null,
  });
};

export const useHistory = (userId: string) => {
  if (IS_MOCK) {
    return {
      data: MOCK_HISTORY,
      isLoading: false,
      error: null as AxiosError | null,
    };
  }

  return useQuery<HistoryResponse, AxiosError>({
    queryKey: ["history", userId],
    queryFn: () => fetchHistory(userId),
    enabled: userId.trim().length > 0,
  });
};
