import axios, { AxiosError } from "axios";

import type {
  AnalysisResult,
  GapCloseRequest,
  GapCloseResponse,
  HistoryResponse,
} from "../types/index";

interface FastAPIErrorDetail {
  msg?: string;
}

interface FastAPIErrorResponse {
  detail?: string | FastAPIErrorDetail | FastAPIErrorDetail[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const axiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

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

  return error.response?.statusText || error.message;
};

axiosInstance.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }

  return config;
});

axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError<FastAPIErrorResponse>) =>
    Promise.reject(new Error(getErrorMessage(error)))
);

export const postAnalyze = async (
  formData: FormData
): Promise<{ job_id: string }> => {
  const response = await axiosInstance.post<{ job_id: string }>(
    "/api/analyze",
    formData
  );
  return response.data;
};

export const getResult = async (jobId: string): Promise<AnalysisResult> => {
  const response = await axiosInstance.get<AnalysisResult>(
    `/api/result/${jobId}`
  );
  return response.data;
};

export const postGapClose = async (
  req: GapCloseRequest
): Promise<GapCloseResponse> => {
  const response = await axiosInstance.post<GapCloseResponse>(
    "/api/gap-close",
    req
  );
  return response.data;
};

export const getDownloadUrl = (docxId: string): string =>
  `${API_BASE_URL}/api/download/${docxId}`;

/** Completed analyze job id → DOCX download URL (FastAPI GET /api/download/{job_id}). */
export const getResumeDownloadUrl = (
  jobId: string,
  style: string = "balanced"
): string =>
  `${API_BASE_URL}/api/download/${encodeURIComponent(jobId)}?${new URLSearchParams({
    style,
  }).toString()}`;

export const getHistory = async (userId: string): Promise<HistoryResponse> => {
  const response = await axiosInstance.get<HistoryResponse>("/api/history", {
    params: { user_id: userId },
  });
  return response.data;
};

export default axiosInstance;
