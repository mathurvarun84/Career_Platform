import { create } from "zustand";

import { scoreResume } from "../engine/atsScorer";
import { composeResumeText } from "../utils/composeResumeText";
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
  /** ATS score at end of analysis — frozen until reset. */
  baselineAts: number | null;
  /** Section full_text overrides from applied fixes (for live rescoring). */
  sectionOverrides: Record<string, string>;
  /** User opted in to fixes despite underqualified role fit gate. */
  applyAnywayAccepted: boolean;
  /** Pre-fill role on upload when analysing a recommended role. */
  pendingAnalyseRole: string | null;
  setJobId: (jobId: string | null) => void;
  setAnalysisResult: (analysisResult: AnalysisResult | null) => void;
  setIsFullAnalysisReady: (ready: boolean) => void;
  mergePartialResult: (partial: Partial<AnalysisResult>) => void;
  setSelectedStyle: (style: RewriteStyle) => void;
  acceptSection: (section: string, style: RewriteStyle) => void;
  /** Apply a section rewrite and re-score ATS in-browser (deterministic). */
  applySectionFix: (
    section: string,
    style: RewriteStyle,
    sectionText: string
  ) => void;
  setActiveTab: (tab: TabId) => void;
  setIsAnalyzing: (isAnalyzing: boolean) => void;
  setIsLoading: (isLoading: boolean) => void;
  setAnalysisError: (analysisError: string | null) => void;
  setCurrentProgress: (progress: SSEProgressEvent | null) => void;
  setDocxId: (docxId: string | null) => void;
  setFallbackInfo: (fallbackInfo: Record<string, string[]>) => void;
  bumpHistoryRefresh: () => void;
  setApplyAnywayAccepted: (accepted: boolean) => void;
  setPendingAnalyseRole: (role: string | null) => void;
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
  baselineAts: null,
  sectionOverrides: {},
  applyAnywayAccepted: false,
  pendingAnalyseRole: null,

  setJobId: (jobId) => set({ jobId }),
  setAnalysisResult: (analysisResult) =>
    set({
      analysisResult,
      baselineAts: analysisResult?.ats.score ?? null,
      sectionOverrides: {},
      applyAnywayAccepted: false,
    }),
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
            patches: normalizedPartial.patches ?? undefined,
            validation: normalizedPartial.validation ?? null,
            jd_intelligence: normalizedPartial.jd_intelligence ?? null,
            role_fit: normalizedPartial.role_fit ?? null,
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
          patches:
            normalizedPartial.patches ?? state.analysisResult.patches,
          validation:
            normalizedPartial.validation ?? state.analysisResult.validation,
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
  applySectionFix: (section, style, sectionText) =>
    set((state) => {
      if (!state.analysisResult) {
        return {};
      }
      const sectionOverrides = {
        ...state.sectionOverrides,
        [section]: sectionText,
      };
      const mergedText = composeResumeText(
        state.analysisResult.resume,
        sectionOverrides
      );
      const scored = scoreResume(mergedText);
      return {
        acceptedSections: {
          ...state.acceptedSections,
          [section]: style,
        },
        sectionOverrides,
        analysisResult: {
          ...state.analysisResult,
          ats: {
            ...state.analysisResult.ats,
            score: scored.score,
            breakdown: scored.breakdown,
            ats_issues: scored.ats_issues,
          },
        },
      };
    }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setAnalysisError: (analysisError) => set({ analysisError }),
  setCurrentProgress: (currentProgress) => set({ currentProgress }),
  setDocxId: (docxId) => set({ docxId }),
  setFallbackInfo: (fallbackInfo) => set({ fallbackInfo }),
  bumpHistoryRefresh: () =>
    set((state) => ({ historyRefreshKey: state.historyRefreshKey + 1 })),
  setApplyAnywayAccepted: (applyAnywayAccepted) => set({ applyAnywayAccepted }),
  setPendingAnalyseRole: (pendingAnalyseRole) => set({ pendingAnalyseRole }),
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
      baselineAts: null,
      sectionOverrides: {},
      applyAnywayAccepted: false,
    }),
}));
