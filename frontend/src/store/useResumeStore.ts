import { create } from "zustand";

import type {
  AnalysisResult,
  RewriteStyle,
  SectionRewrite,
  SSEProgressEvent,
  TabId,
} from "../types";

interface ResumeStoreState {
  jobId: string | null;
  analysisResult: AnalysisResult | null;
  /** True only after full analyze pipeline returns hydrated output (not partial SSE merges). */
  isFullAnalysisReady: boolean;
  selectedStyle: RewriteStyle;
  acceptedSections: Record<string, RewriteStyle>;
  activeTab: TabId;
  isAnalyzing: boolean;
  isLoading: boolean;
  analysisError: string | null;
  currentProgress: SSEProgressEvent | null;
  docxId: string | null;
  fallbackInfo: Record<string, string[]>;
  historyRefreshKey: number;
  userId: string;
  setJobId: (jobId: string | null) => void;
  setAnalysisResult: (analysisResult: AnalysisResult | null) => void;
  setIsFullAnalysisReady: (ready: boolean) => void;
  mergePartialResult: (partial: Partial<AnalysisResult>) => void;
  setSelectedStyle: (style: RewriteStyle) => void;
  acceptSection: (section: string, style: RewriteStyle) => void;
  setActiveTab: (tab: TabId) => void;
  setIsAnalyzing: (isAnalyzing: boolean) => void;
  setIsLoading: (isLoading: boolean) => void;
  setAnalysisError: (analysisError: string | null) => void;
  setCurrentProgress: (progress: SSEProgressEvent | null) => void;
  setDocxId: (docxId: string | null) => void;
  setFallbackInfo: (fallbackInfo: Record<string, string[]>) => void;
  bumpHistoryRefresh: () => void;
  resetAnalysis: () => void;
}

const getOrCreateUserId = (): string => {
  const storageKey = "rip_user_id";
  const stored = localStorage.getItem(storageKey);
  if (stored) {
    return stored;
  }

  const generated = crypto.randomUUID();
  localStorage.setItem(storageKey, generated);
  return generated;
};

export const useResumeStore = create<ResumeStoreState>((set) => ({
  jobId: null,
  analysisResult: null,
  isFullAnalysisReady: false,
  selectedStyle: "balanced",
  acceptedSections: {},
  activeTab: "overview",
  isAnalyzing: false,
  isLoading: false,
  analysisError: null,
  currentProgress: null,
  docxId: null,
  fallbackInfo: {},
  historyRefreshKey: 0,
  userId: getOrCreateUserId(),

  setJobId: (jobId) => set({ jobId }),
  setAnalysisResult: (analysisResult) => set({ analysisResult }),
  setIsFullAnalysisReady: (ready) => set({ isFullAnalysisReady: ready }),
  mergePartialResult: (partial) =>
    set((state) => {
      const normalizedPartial: Partial<AnalysisResult> = {
        ...partial,
        rewrites:
          partial.rewrites &&
          typeof partial.rewrites === "object" &&
          "rewrites" in (partial.rewrites as Record<string, unknown>)
            ? (((partial.rewrites as Record<string, unknown>).rewrites as Record<
                string,
                SectionRewrite
              >) ?? null)
            : partial.rewrites,
      };
      if (!state.analysisResult) {
        if (!normalizedPartial.ats || !normalizedPartial.resume) {
          return {};
        }
        return {
          analysisResult: {
            job_id: state.jobId ?? "",
            ats: normalizedPartial.ats,
            resume: normalizedPartial.resume,
            gap: normalizedPartial.gap ?? null,
            rewrites: normalizedPartial.rewrites ?? null,
            sim: normalizedPartial.sim ?? null,
            percentile: normalizedPartial.percentile ?? null,
            positioning: normalizedPartial.positioning ?? null,
          },
        };
      }
      return {
        analysisResult: {
          ...state.analysisResult,
          ...normalizedPartial,
          gap: normalizedPartial.gap
            ? { ...(state.analysisResult.gap ?? {}), ...normalizedPartial.gap }
            : state.analysisResult.gap,
          resume: normalizedPartial.resume
            ? { ...state.analysisResult.resume, ...normalizedPartial.resume }
            : state.analysisResult.resume,
        },
      };
    }),
  setSelectedStyle: (selectedStyle) => set({ selectedStyle }),
  acceptSection: (section, style) =>
    set((state) => ({
      acceptedSections: {
        ...state.acceptedSections,
        [section]: style,
      },
    })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setAnalysisError: (analysisError) => set({ analysisError }),
  setCurrentProgress: (currentProgress) => set({ currentProgress }),
  setDocxId: (docxId) => set({ docxId }),
  setFallbackInfo: (fallbackInfo) => set({ fallbackInfo }),
  bumpHistoryRefresh: () =>
    set((state) => ({ historyRefreshKey: state.historyRefreshKey + 1 })),
  resetAnalysis: () =>
    set({
      jobId: null,
      analysisResult: null,
      isFullAnalysisReady: false,
      acceptedSections: {},
      isAnalyzing: false,
      isLoading: false,
      analysisError: null,
      currentProgress: null,
      docxId: null,
      fallbackInfo: {},
      historyRefreshKey: 0,
    }),
}));
