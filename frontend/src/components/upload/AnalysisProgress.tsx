import type { CSSProperties, ReactElement } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ANALYZE_TIMEOUT_MS,
  extractLimitReached,
  normalizeAnalysisResult,
  parseHttpLimitResponse,
  throwIfSseErrorPayload,
} from "../../api/analyze";
import UpgradeModal from "../auth/UpgradeModal";
import { useWindowSize } from "../../hooks/useWindowSize";
import { supabase } from "../../lib/supabase";
import { useAuthStore } from "../../store/authStore";
import type { AnalysisResult } from "../../types";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
/** Use access token as-is while it has this many seconds left; avoid refresh (user / Supabase limits). */
const MIN_ACCESS_TOKEN_VALID_SEC_BEFORE_REFRESH = 120;

const STEP_TARGETS = [20, 45, 72, 88] as const;

const PALETTE = {
  primary: "#6366f1",
  text: "#111827",
  muted: "#6b7280",
  border: "#e5e7eb",
  success: "#16a34a",
  successBg: "#dcfce7",
  white: "#ffffff",
  error: "#ef4444",
  activeBg: "#eef2ff",
  activeBorder: "#c7d2fe",
} as const;

const STEPS = [
  {
    label: "Parsing your resume",
    sub: "Extracting sections, skills, and experience",
  },
  {
    label: "Matching against job description",
    sub: "Aligning keywords, skills, and seniority signals",
  },
  {
    label: "Scoring & benchmarking",
    sub: "Calculating ATS score and percentile rank",
  },
  {
    label: "Generating insights",
    sub: "Preparing your personalised recommendations",
  },
] as const;

const INSIGHTS = [
  {
    title: "Resume structure",
    body: "Sections, headings, and skill signals recruiters skim first.",
  },
  {
    title: "JD fit & keywords",
    body: "Overlap between your bullets and the role’s must-have language.",
  },
  {
    title: "ATS & percentile",
    body: "Formatting and impact cues versus similar profiles in our benchmark.",
  },
  {
    title: "Recommendations",
    body: "Prioritised fixes and positioning tailored to this posting.",
  },
] as const;

const TIP_COPY =
  "Career Platform scores four dimensions separately—keyword coverage is only one part of what lands interviews.";

/** Supabase `AuthError`-shaped object without importing the full type graph here. */
interface AuthLikeError {
  readonly message?: string;
  readonly code?: string;
}

function refreshFailureMeansReLogin(err: AuthLikeError | null | undefined): boolean {
  if (!err) {
    return false;
  }
  const code = String(err.code || "").toLowerCase();
  const msg = String(err.message || "").toLowerCase();
  if (code === "refresh_token_not_found") {
    return true;
  }
  if (code === "invalid_grant") {
    return true;
  }
  if (msg.includes("refresh_token_not_found")) {
    return true;
  }
  if (msg.includes("invalid refresh token")) {
    return true;
  }
  if (msg.includes("auth session missing")) {
    return true;
  }
  return false;
}

/** Seconds until JWT exp, or null if unknown (client-side only, no verify). */
function accessTokenSecondsToExpiry(accessToken: string): number | null {
  try {
    const parts = accessToken.split(".");
    if (parts.length < 2) {
      return null;
    }
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(atob(b64 + pad)) as { exp?: number };
    if (typeof payload.exp !== "number") {
      return null;
    }
    return payload.exp - Math.floor(Date.now() / 1000);
  } catch {
    return null;
  }
}

function sessionAccessTokenTtlSec(session: {
  expires_at?: number;
  access_token: string;
}): number | null {
  if (typeof session.expires_at === "number") {
    return session.expires_at - Math.floor(Date.now() / 1000);
  }
  return accessTokenSecondsToExpiry(session.access_token);
}

/**
 * Prefer existing access token while it has enough TTL (no refresh). Refresh only
 * when expiry is known and within MIN_ACCESS_TOKEN_VALID_SEC_BEFORE_REFRESH.
 */
async function resolveAccessTokenForAnalyze(): Promise<string> {
  const setSession = useAuthStore.getState().setSession;

  const { data: withSession, error: getError } =
    await supabase.auth.getSession();
  if (getError) {
    throw new Error(getError.message);
  }

  const session = withSession.session;
  if (!session?.access_token) {
    throw new Error("Sign in to run analysis.");
  }

  const ttl = sessionAccessTokenTtlSec(session);
  const mustRefresh =
    ttl !== null && ttl < MIN_ACCESS_TOKEN_VALID_SEC_BEFORE_REFRESH;

  if (!mustRefresh) {
    setSession(session);
    return session.access_token;
  }

  const { data: refreshed, error: refreshError } =
    await supabase.auth.refreshSession();

  if (!refreshError && refreshed.session?.access_token) {
    setSession(refreshed.session);
    return refreshed.session.access_token;
  }

  if (ttl > 0) {
    setSession(session);
    return session.access_token;
  }

  if (refreshError && refreshFailureMeansReLogin(refreshError)) {
    throw new Error("Session expired. Please sign in again.");
  }
  if (refreshError?.message) {
    throw new Error(refreshError.message);
  }
  throw new Error("Session expired. Please sign in again.");
}

export interface AnalysisProgressProps {
  resumeFile: File;
  jdText: string;
  onComplete: (result: AnalysisResult) => void;
  /** Called when user dismisses the monthly-limit modal (e.g. Maybe later). */
  onLimitDismiss?: () => void;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Max bar % for cosmetic crawl before next milestone (or 98 before final packet). */
function computeCrawlCap(completed: Set<number>, awaitingFinal: boolean): number {
  if (awaitingFinal) {
    return 98;
  }
  for (let i = 0; i < 4; i++) {
    if (!completed.has(i)) {
      return STEP_TARGETS[i] - 2;
    }
  }
  return 98;
}

type InsightBadge = "pending" | "scanning" | "done";

function badgeStyles(kind: InsightBadge): CSSProperties {
  if (kind === "done") {
    return {
      background: PALETTE.successBg,
      color: PALETTE.success,
      border: `1px solid ${PALETTE.success}`,
    };
  }
  if (kind === "scanning") {
    return {
      background: PALETTE.activeBg,
      color: PALETTE.primary,
      border: `1px solid ${PALETTE.primary}`,
    };
  }
  return {
    background: "#f3f4f6",
    color: PALETTE.muted,
    border: `1px solid ${PALETTE.border}`,
  };
}

function badgeLabel(kind: InsightBadge): string {
  if (kind === "done") {
    return "Done";
  }
  if (kind === "scanning") {
    return "Scanning";
  }
  return "Pending";
}

async function pollAnalysisResult(
  jobId: string,
  bearer: string
): Promise<AnalysisResult | null> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const resp = await fetch(`${API_BASE_URL}/api/result/${jobId}`, {
      headers: { Authorization: `Bearer ${bearer}` },
    });
    if (!resp.ok) {
      return null;
    }
    const envelope = (await resp.json()) as {
      status?: string;
      result?: unknown;
      error?: string | null;
    };
    if (envelope.status === "complete" && envelope.result) {
      return normalizeAnalysisResult(envelope.result);
    }
    if (envelope.status === "error") {
      return null;
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, 1500);
    });
  }
  return null;
}

function parseAndDispatchSseBuffer(
  buffer: string,
  onLine: (obj: Record<string, unknown>) => void,
  flush = false
): string {
  let rest = flush && buffer.trim() ? `${buffer}\n\n` : buffer;
  let sep: number;
  while ((sep = rest.indexOf("\n\n")) >= 0) {
    const block = rest.slice(0, sep);
    rest = rest.slice(sep + 2);
    for (const line of block.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) {
        continue;
      }
      const jsonStr = trimmed.replace(/^data:\s*/, "").trim();
      if (!jsonStr) {
        continue;
      }
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(jsonStr) as Record<string, unknown>;
      } catch {
        continue;
      }
      onLine(parsed);
    }
  }
  return flush ? "" : rest;
}

export default function AnalysisProgress({
  resumeFile,
  jdText,
  onComplete,
  onLimitDismiss,
}: AnalysisProgressProps): ReactElement {
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [barPct, setBarPct] = useState(0);
  const [analysisFinal, setAnalysisFinal] = useState(false);
  const [awaitingFinalPacket, setAwaitingFinalPacket] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [runKey, setRunKey] = useState(0);
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  const [upgradeData, setUpgradeData] = useState<{ uploadsThisMonth: number; limit: number } | null>(null);
  const [limitBlocked, setLimitBlocked] = useState(false);
  const { isMobile } = useWindowSize();

  const onCompleteRef = useRef(onComplete);
  const completedRef = useRef(completedSteps);
  completedRef.current = completedSteps;
  const awaitingFinalRef = useRef(false);
  awaitingFinalRef.current = awaitingFinalPacket;

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    if (analysisFinal || errorMessage) {
      return;
    }
    const id = window.setInterval(() => {
      setBarPct((prev) => {
        const cap = computeCrawlCap(completedRef.current, awaitingFinalRef.current);
        const next = prev + 0.3;
        return clamp(next, 0, cap);
      });
    }, 800);
    return () => window.clearInterval(id);
  }, [analysisFinal, errorMessage, completedSteps, awaitingFinalPacket]);

  useEffect(() => {
    let aborted = false;
    const controller = new AbortController();
    let timeoutId = window.setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
    const resetStreamTimeout = (): void => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
    };

    const applyStepComplete = (step: number): void => {
      if (step === 3) {
        setBarPct((prev) => Math.max(prev, 88));
        return;
      }
      setCompletedSteps((prev) => {
        const next = new Set(prev);
        next.add(step);
        return next;
      });
      setBarPct((prev) => {
        const target =
          step >= 0 && step < STEP_TARGETS.length ? STEP_TARGETS[step] : prev;
        return clamp(Math.max(prev, target), 0, 100);
      });
    };

    async function runStream(): Promise<void> {
      const formData = new FormData();
      formData.append("resume", resumeFile);
      formData.append("jd_text", jdText);
      formData.append("run_sim", "true");

      let gotFinalPacket = false;
      let limitReached = false;
      let trackedJobId: string | null = null;

      try {
        const bearer = await resolveAccessTokenForAnalyze();
        const headers: Record<string, string> = {
          Authorization: `Bearer ${bearer}`,
        };
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
          method: "POST",
          headers,
          body: formData,
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const text = await response.text();
          const limitErr = parseHttpLimitResponse(response.status, text);
          if (limitErr) {
            throw limitErr;
          }
          throw new Error(text || `Server returned ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        const dispatchPayload = (payload: Record<string, unknown>): void => {
          if (aborted) {
            return;
          }
          const ev = payload.event;
          if (ev === "started" && typeof payload.job_id === "string") {
            trackedJobId = payload.job_id;
          }
          if (ev === "heartbeat") {
            resetStreamTimeout();
            return;
          }
          if (ev === "step_complete" && typeof payload.step === "number") {
            const s = payload.step as number;
            if (s === 3) {
              setAwaitingFinalPacket(true);
            }
            applyStepComplete(s);
          }
          if (ev === "analysis_complete" && payload.result) {
            const all = new Set([0, 1, 2, 3]);
            setCompletedSteps(all);
            setBarPct(100);
            setAnalysisFinal(true);
            setAwaitingFinalPacket(false);
            gotFinalPacket = true;
            const raw = payload.result as unknown;
            if (
              raw &&
              typeof raw === "object" &&
              "job_id" in raw &&
              typeof (raw as { job_id?: unknown }).job_id === "string"
            ) {
              trackedJobId = (raw as { job_id: string }).job_id;
            }
            onCompleteRef.current(normalizeAnalysisResult(raw));
          }
          if (ev === "error") {
            throwIfSseErrorPayload(payload);
          }
        };

        while (!aborted) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          resetStreamTimeout();
          buffer += decoder.decode(value, { stream: true });
          buffer = parseAndDispatchSseBuffer(buffer, dispatchPayload);
        }

        if (!gotFinalPacket && buffer.trim()) {
          parseAndDispatchSseBuffer(buffer, dispatchPayload, true);
        }

        // Stream closed early — poll persisted job if the worker finished server-side.
        if (!aborted && !gotFinalPacket && trackedJobId) {
          const polled = await pollAnalysisResult(trackedJobId, bearer);
          if (polled) {
            const all = new Set([0, 1, 2, 3]);
            setCompletedSteps(all);
            setBarPct(100);
            setAnalysisFinal(true);
            setAwaitingFinalPacket(false);
            gotFinalPacket = true;
            onCompleteRef.current(polled);
          }
        }

        // If the server stream ended without sending the final packet, avoid
        // leaving the user on a "spinning" UI with no next action.
        if (!aborted && !gotFinalPacket && !limitReached) {
          setErrorMessage(
            "We couldn't finish loading your results. Please try again."
          );
        }
      } catch (err) {
        if (aborted) {
          return;
        }

        if (err instanceof DOMException && err.name === "AbortError") {
          setErrorMessage(
            "Analysis took too long and was stopped. Please try again."
          );
          return;
        }

        const isUpgradeError =
          err instanceof Error && (err as Error & { status?: number }).status === 402;
        if (isUpgradeError) {
          limitReached = true;
          setLimitBlocked(true);
          const errWithDetail = err as Error & { detail?: Record<string, unknown> };
          const detail = errWithDetail.detail || {};
          const fromDetail = extractLimitReached({ event: "error", status: 402, detail });
          setUpgradeData({
            uploadsThisMonth:
              fromDetail?.uploadsThisMonth ??
              (detail.uploads_this_month as number) ??
              2,
            limit: fromDetail?.limit ?? (detail.limit as number) ?? 2,
          });
          setUpgradeModalOpen(true);
          return;
        } else {
          const msg =
            err instanceof Error ? err.message : "Unable to complete analysis.";
          setErrorMessage(msg);
        }
      } finally {
        window.clearTimeout(timeoutId);
      }
    }

    void runStream();

    return () => {
      aborted = true;
      controller.abort();
    };
  }, [resumeFile, jdText, runKey]);

  const handleRetry = useCallback((): void => {
    setErrorMessage(null);
    setCompletedSteps(new Set());
    setBarPct(0);
    setAnalysisFinal(false);
    setAwaitingFinalPacket(false);
    setRunKey((k) => k + 1);
  }, []);

  const activeStepIndex = ((): number => {
    if (analysisFinal) {
      return -1;
    }
    for (let i = 0; i < 4; i++) {
      if (!completedSteps.has(i)) {
        return i;
      }
    }
    return awaitingFinalPacket ? 3 : -1;
  })();

  function stepRowComplete(index: number): boolean {
    return completedSteps.has(index);
  }

  function stepRowActive(index: number): boolean {
    if (analysisFinal || activeStepIndex < 0) {
      return false;
    }
    return index === activeStepIndex && !completedSteps.has(index);
  }

  function stepRowPending(index: number): boolean {
    if (analysisFinal || activeStepIndex < 0) {
      return false;
    }
    return !completedSteps.has(index) && index > activeStepIndex;
  }

  const insightBadge = (index: number): InsightBadge => {
    if (completedSteps.has(index)) {
      return "done";
    }
    if (activeStepIndex >= 0 && index === activeStepIndex) {
      return "scanning";
    }
    return "pending";
  };

  const showTip = completedSteps.has(1);

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        flex: 1,
        width: "100%",
        minHeight: 0,
        maxWidth: "1120px",
        margin: "0 auto",
        paddingLeft: isMobile ? "16px" : "24px",
        paddingRight: isMobile ? "16px" : "24px",
        paddingTop: isMobile ? "20px" : "28px",
        paddingBottom: isMobile ? "32px" : "40px",
        background: PALETTE.white,
      }}
    >
      <style>{`
        @keyframes ripProgressSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      {errorMessage ? (
        <div
          style={{
            border: `1px solid ${PALETTE.error}`,
            background: "#fef2f2",
            borderRadius: "12px",
            paddingTop: "16px",
            paddingBottom: "16px",
            paddingLeft: "18px",
            paddingRight: "18px",
            marginBottom: "20px",
          }}
        >
          <div
            style={{
              fontSize: "14px",
              fontWeight: 700,
              color: PALETTE.error,
              marginBottom: "8px",
            }}
          >
            Something went wrong
          </div>
          <div
            style={{
              fontSize: "13px",
              color: PALETTE.text,
              marginBottom: "14px",
              lineHeight: 1.5,
            }}
          >
            {errorMessage}
          </div>
          <button
            type="button"
            onClick={handleRetry}
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: PALETTE.white,
              background: PALETTE.primary,
              border: "none",
              borderRadius: "10px",
              paddingTop: "10px",
              paddingBottom: "10px",
              paddingLeft: "18px",
              paddingRight: "18px",
              cursor: "pointer",
              boxShadow: "0 3px 0 #4338ca",
            }}
          >
            Try again
          </button>
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          flexWrap: "wrap",
          alignItems: "flex-start",
          gap: isMobile ? "24px" : "0",
        }}
      >
        <div
          style={{
            flex: isMobile ? "1 1 auto" : "1 1 320px",
            minWidth: isMobile ? 0 : "280px",
            width: isMobile ? "100%" : undefined,
            paddingRight: isMobile ? 0 : "24px",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: PALETTE.muted,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: "12px",
            }}
          >
            Analysis progress
          </div>

          <div
            style={{
              height: "8px",
              width: "100%",
              borderRadius: "999px",
              background: PALETTE.border,
              overflow: "hidden",
              marginBottom: "10px",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${barPct}%`,
                borderRadius: "999px",
                background: `linear-gradient(90deg, ${PALETTE.primary}, #4f46e5)`,
              }}
            />
          </div>

          <div
            style={{
              fontSize: "13px",
              color: PALETTE.muted,
              marginBottom: "20px",
            }}
          >
            Live progress from the server — steps advance when each agent finishes.
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            {STEPS.map((step, index) => {
              const isComplete = stepRowComplete(index);
              const isActive = stepRowActive(index);
              const isPending = stepRowPending(index);

              const rowStyle: CSSProperties = {
                display: "flex",
                flexDirection: "row",
                alignItems: "flex-start",
                borderRadius: "12px",
                opacity: isPending ? 0.55 : 1,
                background: isActive ? PALETTE.activeBg : PALETTE.white,
                border: isActive
                  ? `0.5px solid ${PALETTE.activeBorder}`
                  : `1px solid ${PALETTE.border}`,
                paddingTop: "14px",
                paddingBottom: "14px",
                paddingLeft: "14px",
                paddingRight: "14px",
                marginBottom: index < STEPS.length - 1 ? "12px" : "0",
              };

              return (
                <div key={step.label} style={rowStyle}>
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      marginRight: "12px",
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: "999px",
                      background: isComplete ? PALETTE.successBg : PALETTE.white,
                      border: `1px solid ${isComplete ? PALETTE.success : PALETTE.border}`,
                    }}
                  >
                    {isComplete ? (
                      <span
                        style={{
                          color: PALETTE.success,
                          fontSize: "18px",
                          fontWeight: 700,
                          lineHeight: 1,
                        }}
                        aria-hidden
                      >
                        ✓
                      </span>
                    ) : isActive ? (
                      <div
                        aria-hidden
                        style={{
                          width: "18px",
                          height: "18px",
                          borderRadius: "50%",
                          border: `2px solid ${PALETTE.primary}`,
                          borderTopColor: "transparent",
                          animation: "ripProgressSpin 0.8s linear infinite",
                        }}
                      />
                    ) : (
                      <div
                        aria-hidden
                        style={{
                          width: "18px",
                          height: "18px",
                          borderRadius: "50%",
                          border: `1px solid ${PALETTE.border}`,
                          background: "#f9fafb",
                        }}
                      />
                    )}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: "15px",
                        fontWeight: 700,
                        color: PALETTE.text,
                        lineHeight: 1.35,
                      }}
                    >
                      {step.label}
                    </div>
                    <div
                      style={{
                        fontSize: "12px",
                        color: PALETTE.muted,
                        marginTop: "4px",
                        lineHeight: 1.45,
                      }}
                    >
                      {step.sub}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div
          style={{
            width: isMobile ? "100%" : "280px",
            flex: isMobile ? "1 1 auto" : "0 0 280px",
            minWidth: isMobile ? 0 : "260px",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: PALETTE.muted,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: "12px",
            }}
          >
            What we&apos;re checking
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            {INSIGHTS.map((insight, index) => {
              const kind = insightBadge(index);
              return (
                <div
                  key={insight.title}
                  style={{
                    border: `1px solid ${PALETTE.border}`,
                    borderRadius: "12px",
                    paddingTop: "12px",
                    paddingBottom: "12px",
                    paddingLeft: "12px",
                    paddingRight: "12px",
                    marginBottom: "10px",
                    background: PALETTE.white,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: "8px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "14px",
                        fontWeight: 700,
                        color: PALETTE.text,
                      }}
                    >
                      {insight.title}
                    </div>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                        borderRadius: "999px",
                        paddingLeft: "8px",
                        paddingRight: "8px",
                        paddingTop: "3px",
                        paddingBottom: "3px",
                        ...badgeStyles(kind),
                      }}
                    >
                      {badgeLabel(kind)}
                    </span>
                  </div>
                  <div style={{ fontSize: "12px", color: PALETTE.muted, lineHeight: 1.5 }}>
                    {insight.body}
                  </div>
                </div>
              );
            })}
          </div>

          {showTip ? (
            <div
              style={{
                marginTop: "8px",
                borderRadius: "12px",
                border: `1px dashed ${PALETTE.primary}`,
                background: PALETTE.activeBg,
                paddingTop: "12px",
                paddingBottom: "12px",
                paddingLeft: "14px",
                paddingRight: "14px",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: PALETTE.primary,
                  marginBottom: "6px",
                }}
              >
                Did you know?
              </div>
              <div style={{ fontSize: "12px", color: PALETTE.text, lineHeight: 1.55 }}>
                {TIP_COPY}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {upgradeModalOpen && upgradeData && (
        <UpgradeModal
          uploadsThisMonth={upgradeData.uploadsThisMonth}
          limit={upgradeData.limit}
          onClose={() => {
            setUpgradeModalOpen(false);
            if (limitBlocked) {
              onLimitDismiss?.();
            }
          }}
        />
      )}
    </div>
  );
}
