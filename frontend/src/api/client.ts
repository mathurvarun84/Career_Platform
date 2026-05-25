import axios, { AxiosError } from "axios";

import { IS_MOCK } from "../hooks/useMockData";
import { mockCareerRecord } from "../mocks/mockData";
import type {
  AnalysisResult,
  ATSResult,
  CareerMemoryEntry,
  CareerMemoryResponse,
  DownloadVerification,
  GapCloseRequest,
  GapCloseResponse,
  HistoryResponse,
  PatchApplyResult,
} from "../types/index";

export type { PatchApplyResult };

const normalizeRecruiterSim = (payload: AnalysisResult): AnalysisResult => {
  if (payload.sim) {
    return payload;
  }

  const raw = payload as unknown as Record<string, unknown>;
  const simCandidate =
    raw.sim_result ??
    raw.recruiter_sim ??
    raw.recruiter_simulation ??
    null;
  const sim =
    simCandidate &&
    typeof simCandidate === "object" &&
    "sim" in (simCandidate as Record<string, unknown>)
      ? ((simCandidate as Record<string, unknown>).sim as AnalysisResult["sim"])
      : (simCandidate as AnalysisResult["sim"]);

  return { ...payload, sim: sim ?? null };
};

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
  formData: FormData,
  accessToken?: string | null
): Promise<{ job_id: string }> => {
  const headers: Record<string, string> = {};
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  const response = await axiosInstance.post<{ job_id: string }>(
    "/api/analyze",
    formData,
    { headers }
  );
  return response.data;
};

export const getResult = async (jobId: string): Promise<AnalysisResult> => {
  const response = await axiosInstance.get<AnalysisResult>(
    `/api/result/${jobId}`
  );
  return normalizeRecruiterSim(response.data);
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

export const downloadResumeReport = async (
  jobId: string,
  style: string = "balanced"
): Promise<void> => {
  const downloadUrl = getResumeDownloadUrl(jobId, style);
  const response = await fetch(downloadUrl);

  if (!response.ok) {
    let detail = `Download failed (${response.status}).`;
    try {
      const data = (await response.json()) as { detail?: string | unknown };
      if (typeof data.detail === "string") {
        detail = data.detail;
      }
    } catch {
      /* non-JSON body */
    }
    throw new Error(
      `${detail} Try analyzing your resume again if the server was restarted.`
    );
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "resume.docx";
  link.click();
  URL.revokeObjectURL(url);
};

export const getHistory = async (userId: string): Promise<HistoryResponse> => {
  const response = await axiosInstance.get<HistoryResponse>("/api/history", {
    params: { user_id: userId },
  });
  return response.data;
};

export interface ApplyPatchesResponse {
  applied: string[];
  rejected: string[];
  results: PatchApplyResult[];
  resume_text: string;
  score: ATSResult;
}

export const applyPatches = async (
  jobId: string,
  patchIds: string[],
  userConfirmed = false,
): Promise<ApplyPatchesResponse> => {
  const response = await axiosInstance.post<ApplyPatchesResponse>(
    "/api/patches/apply",
    {
      job_id: jobId,
      patch_ids: patchIds,
      user_confirmed: userConfirmed,
    }
  );
  return response.data;
};

export interface RollbackResponse {
  resume_text: string;
  score: ATSResult;
}

export interface GenerateBulletRequest {
  session_id: string;
  gap_id: string;
  section: string;
  sub_label: string | null;
  raw_answer: string;
  coaching_question: string;
  skill_category: string;
  gap_reason?: string;
}

export interface GenerateBulletResponse {
  generated_bullet: string;
  career_memory_id: string;
  grounding_check?: boolean;
  error?: string | null;
}

const mockCareerMemoryBySession = new Map<string, CareerMemoryEntry[]>();

const normalizeMockSkill = (section: string): CareerMemoryEntry["skill_category"] => {
  const lower = section.toLowerCase();
  if (lower.includes("leader")) return "leadership";
  if (lower.includes("deliver")) return "delivery";
  if (lower.includes("commun")) return "communication";
  return "technical";
};

export const generateCoachingBullet = async (
  req: GenerateBulletRequest
): Promise<GenerateBulletResponse> => {
  if (IS_MOCK) {
    let bullet = `• ${req.raw_answer.trim().replace(/\.$/, "")} — delivering measurable team and delivery outcomes.`;
    if (bullet.length > 200) {
      bullet = `${bullet.slice(0, 197).trimEnd()}…`;
    }
    const entry: CareerMemoryEntry = {
      id: crypto.randomUUID(),
      session_id: req.session_id,
      gap_id: req.gap_id,
      section: req.section,
      sub_label: req.sub_label,
      raw_answer: req.raw_answer,
      generated_bullet: bullet,
      skill_category: normalizeMockSkill(req.skill_category || req.section),
      company: null,
      timestamp: new Date().toISOString(),
      user_approved: false,
    };
    const existing = mockCareerMemoryBySession.get(req.session_id) ?? [];
    mockCareerMemoryBySession.set(req.session_id, [entry, ...existing]);
    return {
      generated_bullet: bullet,
      career_memory_id: entry.id,
      grounding_check: true,
    };
  }

  const response = await axiosInstance.post<GenerateBulletResponse>(
    "/api/coaching/generate-bullet",
    req
  );
  return response.data;
};

export const rollbackPatch = async (
  jobId: string,
  patchId: string = "all",
): Promise<RollbackResponse> => {
  const response = await axiosInstance.post<RollbackResponse>(
    "/api/patches/rollback",
    {
      job_id: jobId,
      patch_id: patchId,
    }
  );
  return response.data;
};

export interface AddBulletRequest {
  session_id: string;
  gap_id: string;
  section: string;
  sub_label: string | null;
  bullet_text: string;
  placement: "start" | "end";
  career_memory_id: string;
}

export interface AddBulletResponse {
  inserted: boolean;
  found_in_doc: boolean;
}

export const addBulletToResume = async (
  req: AddBulletRequest
): Promise<AddBulletResponse> => {
  if (IS_MOCK) {
    const entries = mockCareerMemoryBySession.get(req.session_id) ?? [];
    const updated = entries.map((entry) =>
      entry.id === req.career_memory_id ? { ...entry, user_approved: true } : entry
    );
    mockCareerMemoryBySession.set(req.session_id, updated);
    return { inserted: true, found_in_doc: true };
  }

  const response = await axiosInstance.post<AddBulletResponse>(
    "/api/coaching/add-bullet",
    req
  );
  return response.data;
};

export const getCareerMemory = async (
  sessionId: string
): Promise<CareerMemoryResponse> => {
  if (IS_MOCK) {
    const sessionEntries = mockCareerMemoryBySession.get(sessionId) ?? [];
    const seeded =
      sessionEntries.length > 0
        ? sessionEntries
        : mockCareerRecord.filter((entry) => entry.session_id === sessionId);
    return { entries: seeded, total: seeded.length };
  }

  const response = await axiosInstance.get<CareerMemoryResponse>(
    "/api/coaching/career-memory",
    { params: { session_id: sessionId } }
  );
  return response.data;
};

export const getDownloadVerification = async (
  sessionId: string
): Promise<DownloadVerification> => {
  const response = await axiosInstance.get<DownloadVerification>(
    `/api/session/${sessionId}/download`
  );
  return response.data;
};

export default axiosInstance;
