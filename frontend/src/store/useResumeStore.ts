import { create } from "zustand";

import { scoreResume } from "../engine/atsScorer";
import { composeResumeText } from "../utils/composeResumeText";
import { hasJobDescription } from "../utils/hasJobDescription";
import { submitAnswerStream, fetchInterviewSessions, fetchModelAnswer } from "../api/interview";
import type {
  AnalysisResult,
  InterviewSession,
  InterviewSessionState,
  FollowUpQuestion,
  InterviewHistoryState,
  ModelAnswer,
  ModelAnswerCardState,
  PerQuestionFeedback,
  QuestionMode,
  RewriteStyle,
  SectionRewrite,
  SSEProgressEvent,
  SessionSummary,
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
  /** JD text from the current analysis session (for live rescoring). */
  analysisJdText: string | null;
  /** Section full_text overrides from applied fixes (for live rescoring). */
  sectionOverrides: Record<string, string>;
  /** User opted in to fixes despite underqualified role fit gate. */
  applyAnywayAccepted: boolean;
  /** Pre-fill role on upload when analysing a recommended role. */
  pendingAnalyseRole: string | null;
  interviewSession: InterviewSession | null;
  interviewLoading: boolean;
  interviewError: string | null;
  interview_history: InterviewHistoryState;
  model_answer_cards: Record<string, ModelAnswerCardState>;
  interviewPrefill: {
    company: string;
    seniority: string;
    recommended_dimension: string | null;
  } | null;
  _cancelStream: (() => void) | null;
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
  setAnalysisJdText: (jdText: string | null) => void;
  resetAnalysis: () => void;
  startInterviewSession: (
    company: string,
    seniority: string,
    questionMode: QuestionMode
  ) => void;
  setInterviewSession: (session: InterviewSession) => void;
  setSessionState: (state: InterviewSessionState) => void;
  setActiveFollowUp: (followUp: FollowUpQuestion | null) => void;
  submitAnswer: (questionId: string, answerText: string) => void;
  submitFollowUpAnswer: (
    questionId: string,
    followUpId: string,
    answerText: string
  ) => void;
  submitAnswerWithStream: (
    questionId: string,
    answerText: string,
    isFollowUp: boolean,
    followUpId?: string
  ) => void;
  advanceQuestion: () => void;
  setInterviewLoading: (loading: boolean) => void;
  setInterviewError: (error: string | null) => void;
  setInterviewSummary: (summary: SessionSummary) => void;
  fetchInterviewHistory: () => Promise<void>;
  fetchModelAnswer: (session_id: string, question_id: string) => Promise<void>;
  setInterviewPrefill: (
    prefill: {
      company: string;
      seniority: string;
      recommended_dimension: string | null;
    } | null
  ) => void;
  retryFromQuestion: (questionIndex: number) => void;
  clearInterviewSession: () => void;
}

const capAtsAtBaseline = (score: number, baseline: number | null): number =>
  baseline !== null ? Math.max(baseline, score) : score;

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
  analysisJdText: null,
  sectionOverrides: {},
  applyAnywayAccepted: false,
  pendingAnalyseRole: null,
  interviewSession: null,
  interviewLoading: false,
  interviewError: null,
  interview_history: {
    past_sessions: [],
    is_loading: false,
    fetch_error: null,
  },
  model_answer_cards: {},
  interviewPrefill: null,
  _cancelStream: null,

  setJobId: (jobId) => set({ jobId }),
  setAnalysisJdText: (analysisJdText) => set({ analysisJdText }),
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
            run_id: normalizedPartial.run_id ?? state.jobId ?? null,
            resume_id: normalizedPartial.resume_id ?? null,
            jd_id: normalizedPartial.jd_id ?? null,
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
      const mergedAts = normalizedPartial.ats
        ? {
            ...normalizedPartial.ats,
            score: capAtsAtBaseline(
              normalizedPartial.ats.score,
              state.baselineAts
            ),
          }
        : undefined;
      return {
        analysisResult: {
          ...state.analysisResult,
          ...normalizedPartial,
          ...(mergedAts ? { ats: mergedAts } : {}),
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
          role_fit:
            normalizedPartial.role_fit !== undefined
              ? normalizedPartial.role_fit
              : state.analysisResult.role_fit,
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
      const scored = scoreResume(mergedText, state.analysisJdText);
      const cappedScore = capAtsAtBaseline(scored.score, state.baselineAts);
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
            score: cappedScore,
            breakdown: scored.breakdown,
            ats_issues: scored.ats_issues,
          },
        },
      };
    }),
  setActiveTab: (activeTab) =>
    set((state) => {
      const { analysisResult, applyAnywayAccepted } = state;
      if (activeTab === "gap" && analysisResult && !hasJobDescription(analysisResult.gap)) {
        return {};
      }
      const roleFitLocked =
        analysisResult?.role_fit?.fitness === "underqualified" &&
        !applyAnywayAccepted;
      const roleFitLockedTabs = new Set<TabId>(["fixes", "gap", "progress"]);
      if (roleFitLocked && roleFitLockedTabs.has(activeTab)) {
        return {};
      }
      return { activeTab };
    }),
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
      analysisJdText: null,
      sectionOverrides: {},
      applyAnywayAccepted: false,
    }),
  startInterviewSession: (company, seniority, questionMode) =>
    set({
      interviewSession: {
        session_id: "",
        company,
        seniority,
        question_mode: questionMode,
        questions: [],
        answers: [],
        feedback: [],
        current_question_index: 0,
        current_follow_up_count: 0,
        active_follow_up: null,
        summary: null,
        state: "configuring",
      },
      interviewLoading: false,
      interviewError: null,
    }),
  setInterviewSession: (interviewSession) =>
    set({ interviewSession, interviewError: null }),
  setSessionState: (state) =>
    set((current) =>
      current.interviewSession
        ? { interviewSession: { ...current.interviewSession, state } }
        : {}
    ),
  setActiveFollowUp: (active_follow_up) =>
    set((current) =>
      current.interviewSession
        ? {
            interviewSession: {
              ...current.interviewSession,
              active_follow_up,
              state:
                active_follow_up !== null
                  ? "awaiting_follow_up"
                  : current.interviewSession.state,
            },
          }
        : {}
    ),
  submitAnswer: (questionId, answerText) =>
    set((current) => {
      if (!current.interviewSession) {
        return {};
      }
      const existing = current.interviewSession.answers.find(
        (turn) => turn.question_id === questionId
      );
      const answers = existing
        ? current.interviewSession.answers.map((turn) =>
            turn.question_id === questionId
              ? { ...turn, answer_text: answerText }
              : turn
          )
        : [
            ...current.interviewSession.answers,
            { question_id: questionId, answer_text: answerText, follow_ups: [] },
          ];
      return {
        interviewSession: {
          ...current.interviewSession,
          answers,
          active_follow_up: null,
          state: "evaluating",
        },
      };
    }),
  submitFollowUpAnswer: (questionId, followUpId, answerText) =>
    set((current) => {
      if (!current.interviewSession?.active_follow_up) {
        return {};
      }
      const followUp = current.interviewSession.active_follow_up;
      if (followUp.id !== followUpId) {
        return {};
      }
      return {
        interviewSession: {
          ...current.interviewSession,
          answers: current.interviewSession.answers.map((turn) =>
            turn.question_id === questionId
              ? {
                  ...turn,
                  follow_ups: [
                    ...turn.follow_ups,
                    { question: followUp, answer_text: answerText },
                  ],
                }
              : turn
          ),
          active_follow_up: null,
          current_follow_up_count:
            current.interviewSession.current_follow_up_count + 1,
          state: "evaluating",
          partialFeedback: null,
        },
      };
    }),
  submitAnswerWithStream: (questionId, answerText, isFollowUp, followUpId) => {
    const state = useResumeStore.getState();
    if (!state.interviewSession) {
      return;
    }
    const session = state.interviewSession;
    const sessionId = session.session_id;
    const questionIndex = session.current_question_index;

    if (state._cancelStream) {
      state._cancelStream();
    }

    if (!isFollowUp) {
      const existing = session.answers.find(
        (turn) => turn.question_id === questionId
      );
      const answers = existing
        ? session.answers.map((turn) =>
            turn.question_id === questionId
              ? { ...turn, answer_text: answerText }
              : turn
          )
        : [
            ...session.answers,
            {
              question_id: questionId,
              answer_text: answerText,
              follow_ups: [],
            },
          ];
      set({
        interviewLoading: true,
        interviewSession: {
          ...session,
          answers,
          active_follow_up: null,
          state: "evaluating",
          partialFeedback: null,
        },
      });
    } else {
      set({
        interviewLoading: true,
        interviewSession: {
          ...session,
          state: "evaluating",
          partialFeedback: null,
        },
      });
    }

    const cancel = submitAnswerStream(
      sessionId,
      questionId,
      answerText,
      isFollowUp,
      followUpId,
      (chunk) => {
        set((current) => {
          const activeSession = current.interviewSession;
          if (!activeSession) {
            return {};
          }
          const partial = activeSession.partialFeedback ?? {};

          switch (chunk.type) {
            case "verdict":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    overall_verdict: chunk.content,
                  },
                },
              };
            case "best_line":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    best_line: chunk.content,
                  },
                },
              };
            case "level_signal":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    level_signal: chunk.content,
                  },
                },
              };
            case "presence":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    executive_presence: chunk.content.executive_presence,
                    authenticity_note: chunk.content.authenticity_note,
                  },
                },
              };
            case "coaching_close":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    coaching_close: chunk.content,
                  },
                },
              };
            case "dimension":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    dimension_score: chunk.content,
                  },
                },
              };
            case "missing":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    dimension_score: partial.dimension_score
                      ? {
                          ...partial.dimension_score,
                          what_was_missing: chunk.content,
                        }
                      : undefined,
                  },
                },
              };
            case "ap_fired":
              return {
                interviewSession: {
                  ...activeSession,
                  partialFeedback: {
                    ...partial,
                    anti_patterns_fired: [
                      ...(partial.anti_patterns_fired ?? []),
                      chunk.content,
                    ],
                  },
                },
              };
            default:
              return {};
          }
        });
      },
      (meta) => {
        set((current) => {
          const activeSession = current.interviewSession;
          if (!activeSession) {
            return { interviewLoading: false, _cancelStream: null };
          }

          const followUp = meta?.followUp ?? null;
          if (followUp && !isFollowUp) {
            return {
              interviewLoading: false,
              _cancelStream: null,
              interviewSession: {
                ...activeSession,
                partialFeedback: null,
                active_follow_up: followUp,
                state: "awaiting_follow_up",
              },
            };
          }

          const partial = activeSession.partialFeedback ?? {};
          const seniority = activeSession.seniority as PerQuestionFeedback["level_signal"]["declared_level"];
          const full: PerQuestionFeedback = {
            question_id: questionId,
            overall_verdict: partial.overall_verdict ?? "",
            best_line: partial.best_line ?? "",
            coaching_close: partial.coaching_close ?? "",
            level_signal: partial.level_signal ?? {
              signaled_level: seniority,
              declared_level: seniority,
              match: true,
              note: "",
            },
            executive_presence: partial.executive_presence ?? "not_assessable",
            authenticity_note: partial.authenticity_note ?? "",
            dimension_score: partial.dimension_score ?? {
              dimension: "ownership",
              signal_strength: "developing",
              score_delta: "",
              what_was_missing: "",
              what_was_strong: "",
            },
            anti_patterns_fired: partial.anti_patterns_fired ?? [],
          };

          return {
            interviewLoading: false,
            _cancelStream: null,
            interviewSession: {
              ...activeSession,
              feedback: [...activeSession.feedback, full],
              partialFeedback: null,
              active_follow_up: null,
              state: "feedback_shown",
            },
          };
        });
      },
      (msg) =>
        set({ interviewLoading: false, interviewError: msg, _cancelStream: null }),
      questionIndex,
      session.current_follow_up_count
    );

    set({ _cancelStream: cancel });
  },
  advanceQuestion: () =>
    set((current) => {
      if (!current.interviewSession) {
        return {};
      }
      return {
        interviewSession: {
          ...current.interviewSession,
          current_question_index:
            current.interviewSession.current_question_index + 1,
          current_follow_up_count: 0,
          active_follow_up: null,
          state: "in_progress",
        },
      };
    }),
  setInterviewLoading: (interviewLoading) => set({ interviewLoading }),
  setInterviewError: (interviewError) => set({ interviewError }),
  setInterviewSummary: (summary) =>
    set((current) =>
      current.interviewSession
        ? {
            interviewSession: {
              ...current.interviewSession,
              summary,
              state: "summary",
            },
          }
        : {}
    ),
  fetchInterviewHistory: async () => {
    set((state) => ({
      interview_history: {
        ...state.interview_history,
        is_loading: true,
        fetch_error: null,
      },
    }));
    try {
      const sessions = await fetchInterviewSessions();
      set(() => ({
        interview_history: {
          past_sessions: sessions,
          is_loading: false,
          fetch_error: null,
        },
      }));
    } catch {
      set((state) => ({
        interview_history: {
          ...state.interview_history,
          is_loading: false,
          fetch_error: "Could not load history",
        },
      }));
    }
  },
  fetchModelAnswer: async (session_id, question_id) => {
    set((state) => ({
      model_answer_cards: {
        ...state.model_answer_cards,
        [question_id]: { status: "loading", data: null },
      },
    }));
    try {
      const data: ModelAnswer = await fetchModelAnswer(session_id, question_id);
      set((state) => ({
        model_answer_cards: {
          ...state.model_answer_cards,
          [question_id]: {
            status: data.skipped ? "skipped" : "loaded",
            data: data.skipped ? null : data,
          },
        },
      }));
    } catch {
      set((state) => ({
        model_answer_cards: {
          ...state.model_answer_cards,
          [question_id]: { status: "error", data: null },
        },
      }));
    }
  },
  setInterviewPrefill: (interviewPrefill) => set({ interviewPrefill }),
  retryFromQuestion: (questionIndex) =>
    set((current) => {
      if (!current.interviewSession) {
        return {};
      }
      const session = current.interviewSession;
      return {
        interviewSession: {
          ...session,
          state: "in_progress",
          current_question_index: questionIndex,
          answers: session.answers.slice(0, questionIndex),
          feedback: session.feedback.slice(0, questionIndex),
          active_follow_up: null,
          current_follow_up_count: 0,
          summary: null,
          partialFeedback: null,
        },
      };
    }),
  clearInterviewSession: () => {
    const cancel = useResumeStore.getState()._cancelStream;
    if (cancel) {
      cancel();
    }
    set({
      interviewSession: null,
      interviewLoading: false,
      interviewError: null,
      model_answer_cards: {},
      _cancelStream: null,
    });
  },
}));
