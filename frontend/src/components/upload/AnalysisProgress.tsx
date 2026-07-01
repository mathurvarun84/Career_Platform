import type { CSSProperties, ReactElement } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ANALYZE_TIMEOUT_MS,
  extractLimitReached,
  normalizeAnalysisResult,
  parseHttpLimitResponse,
  throwIfSseErrorPayload,
} from "../../api/analyze";
import { getOrCreateSessionId } from "../../utils/analyticsSession";
import UpgradeModal from "../auth/UpgradeModal";
import { useWindowSize } from "../../hooks/useWindowSize";
import { supabase } from "../../lib/supabase";
import { useAuthStore } from "../../store/authStore";
import type { AnalysisResult } from "../../types";
import { T } from "../../tokens";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
/** Use access token as-is while it has this many seconds left; avoid refresh (user / Supabase limits). */
const MIN_ACCESS_TOKEN_VALID_SEC_BEFORE_REFRESH = 120;

const STEP_TARGETS = [20, 45, 72, 88] as const;

const PALETTE = {
  primary:      T.primary,
  text:         T.textPrimary,
  muted:        T.textMuted,
  border:       T.border,
  success:      T.emerald,
  successBg:    T.emeraldLight,
  white:        T.bgCard,
  error:        T.rose,
  activeBg:     T.primaryLight,
  activeBorder: T.primaryMid,
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

interface LiveFindings {
  ats_score: number | null;
  ats_breakdown: Record<string, number> | null;
  seniority: string | null;
  strengths: string[];
  weaknesses: string[];
  tech_stack: string[];
  experience_years: number | null;
  jd_match_score: number | null;
  top_priority_fix: string | null;
  sections_changed: number | null;
  percentile: number | null;
  shortlist_rate: number | null;
}

const INITIAL_FINDINGS: LiveFindings = {
  ats_score: null,
  ats_breakdown: null,
  seniority: null,
  strengths: [],
  weaknesses: [],
  tech_stack: [],
  experience_years: null,
  jd_match_score: null,
  top_priority_fix: null,
  sections_changed: null,
  percentile: null,
  shortlist_rate: null,
};

interface FindingCard {
  id: string;
  label: string;
  value: string;
  accent: string;
}

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

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function mergeLiveFindingsFromPayload(
  prev: LiveFindings,
  payload: Record<string, unknown>
): LiveFindings {
  const partial = asRecord(payload.partial_result) ?? payload;
  let next = { ...prev };

  const ats = asRecord(partial.ats);
  if (ats && typeof ats.score === "number") {
    const breakdown = asRecord(ats.breakdown);
    next = {
      ...next,
      ats_score: ats.score,
      ats_breakdown: breakdown
        ? (Object.fromEntries(
            Object.entries(breakdown).filter(([, v]) => typeof v === "number")
          ) as Record<string, number>)
        : next.ats_breakdown,
    };
  }

  const resume = asRecord(partial.resume);
  if (resume) {
    const rawSeniority = resume.seniority;
    let seniority: string | null = next.seniority;
    if (typeof rawSeniority === "string") {
      seniority = rawSeniority;
    } else if (rawSeniority && typeof rawSeniority === "object") {
      const sv = (rawSeniority as { value?: unknown }).value;
      if (typeof sv === "string") {
        seniority = sv;
      }
    }
    next = {
      ...next,
      seniority,
      strengths: Array.isArray(resume.strengths)
        ? (resume.strengths as string[])
        : next.strengths,
      weaknesses: Array.isArray(resume.weaknesses)
        ? (resume.weaknesses as string[])
        : next.weaknesses,
      tech_stack: Array.isArray(resume.tech_stack)
        ? (resume.tech_stack as string[])
        : next.tech_stack,
      experience_years:
        typeof resume.experience_years === "number"
          ? resume.experience_years
          : next.experience_years,
    };
  }

  const gap = asRecord(partial.gap);
  if (gap) {
    if (Array.isArray(gap.weaknesses) && gap.weaknesses.length > 0) {
      next = { ...next, weaknesses: gap.weaknesses as string[] };
    }
    const rawFixes = gap.priority_fixes;
    let topFix: string | null = null;
    if (Array.isArray(rawFixes) && rawFixes.length > 0) {
      const first = rawFixes[0];
      if (typeof first === "string") {
        topFix = first;
      } else {
        const fixObj = asRecord(first);
        topFix =
          (typeof fixObj?.issue === "string" && fixObj.issue) ||
          (typeof fixObj?.gap_reason === "string" && fixObj.gap_reason) ||
          null;
      }
    }
    const sectionsChanged = gap.sections_changed;
    next = {
      ...next,
      jd_match_score:
        typeof gap.jd_match_score_before === "number"
          ? gap.jd_match_score_before
          : typeof gap.match_score === "number"
            ? gap.match_score
            : next.jd_match_score,
      top_priority_fix: topFix ?? next.top_priority_fix,
      sections_changed: Array.isArray(sectionsChanged)
        ? sectionsChanged.length
        : next.sections_changed,
    };
  }

  const percentile = asRecord(partial.percentile);
  if (percentile && typeof percentile.percentile === "number") {
    next = { ...next, percentile: percentile.percentile };
  }

  const sim = asRecord(partial.sim);
  if (sim && typeof sim.shortlist_rate === "number") {
    next = { ...next, shortlist_rate: sim.shortlist_rate };
  }

  return next;
}

function payloadHasPartialData(payload: Record<string, unknown>): boolean {
  return Boolean(
    payload.partial_result ||
      payload.ats ||
      payload.resume ||
      payload.gap ||
      payload.percentile ||
      payload.sim
  );
}

function waitingStatusMessage(
  activeStepIndex: number,
  completedSteps: Set<number>
): string {
  if (completedSteps.has(3)) {
    return "Finalising your dashboard…";
  }
  if (completedSteps.has(2)) {
    return "Running recruiter simulation and market benchmarks…";
  }
  if (completedSteps.has(1)) {
    return "Scoring JD fit and identifying gaps…";
  }
  if (completedSteps.has(0)) {
    return "Resume parsed — ATS and profile analysis running…";
  }
  if (activeStepIndex === 0) {
    return "Parsing your resume — first results appear in a few seconds";
  }
  if (activeStepIndex === 1) {
    return "Matching your profile to the job description…";
  }
  if (activeStepIndex === 2) {
    return "Calculating ATS score and benchmarks…";
  }
  if (activeStepIndex === 3) {
    return "Generating rewrites and recruiter insights…";
  }
  return "Starting analysis…";
}

function buildFindingCards(f: LiveFindings): FindingCard[] {
  const cards: FindingCard[] = [];

  if (f.ats_score !== null) {
    const score = f.ats_score;
    const quality = score >= 75 ? "strong" : score >= 55 ? "average" : "needs work";
    cards.push({
      id: "ats_score",
      label: "ATS compatibility score",
      value: `${score}/100 — ${quality}`,
      accent: score >= 75 ? PALETTE.success : score >= 55 ? "#d97706" : PALETTE.error,
    });
  }

  if (f.ats_breakdown) {
    const dims = f.ats_breakdown;
    const worst = Object.entries(dims).sort(([, a], [, b]) => a - b)[0];
    if (worst) {
      const dimLabels: Record<string, string> = {
        keyword_match: "Keyword match",
        formatting: "Formatting",
        readability: "Readability",
        impact_metrics: "Impact & metrics",
      };
      const label = dimLabels[worst[0]] ?? worst[0];
      const pct = Math.round((worst[1] / 25) * 100);
      cards.push({
        id: "ats_weak_dim",
        label: "Weakest dimension",
        value: `${label} — ${pct}% of max`,
        accent: PALETTE.error,
      });
    }
  }

  if (f.seniority) {
    const seniorityLabels: Record<string, string> = {
      junior: "Junior (0–2 yrs)",
      mid: "Mid-level (3–5 yrs)",
      senior: "Senior (6–9 yrs)",
      staff: "Staff / Principal",
      lead: "Tech Lead",
      manager: "Engineering Manager",
      director: "Director+",
    };
    cards.push({
      id: "seniority",
      label: "Career level detected",
      value: seniorityLabels[f.seniority] ?? f.seniority,
      accent: PALETTE.primary,
    });
  }

  if (f.experience_years !== null && f.experience_years > 0) {
    cards.push({
      id: "exp_years",
      label: "Total experience found",
      value: `${f.experience_years} year${f.experience_years === 1 ? "" : "s"} across ${
        f.tech_stack.length > 0
          ? `${f.tech_stack.length} technologies`
          : "multiple roles"
      }`,
      accent: PALETTE.primary,
    });
  }

  if (f.weaknesses.length > 0) {
    cards.push({
      id: "top_weakness",
      label: "Key gap to address",
      value: f.weaknesses[0],
      accent: PALETTE.error,
    });
  }

  if (f.jd_match_score !== null) {
    const match = f.jd_match_score;
    const matchLabel =
      match >= 70 ? "strong fit" : match >= 50 ? "partial fit" : "significant gaps";
    cards.push({
      id: "jd_match",
      label: "JD match score",
      value: `${match}% — ${matchLabel}`,
      accent: match >= 70 ? PALETTE.success : match >= 50 ? "#d97706" : PALETTE.error,
    });
  }

  if (f.top_priority_fix) {
    cards.push({
      id: "priority_fix",
      label: "Biggest gap identified",
      value: f.top_priority_fix,
      accent: "#d97706",
    });
  }

  if (f.sections_changed !== null && f.sections_changed > 0) {
    cards.push({
      id: "sections_changed",
      label: "Sections being optimised",
      value: `${f.sections_changed} section${
        f.sections_changed === 1 ? "" : "s"
      } — rewrites generating now`,
      accent: PALETTE.primary,
    });
  }

  if (f.percentile !== null) {
    const pct = Math.round(f.percentile);
    cards.push({
      id: "percentile",
      label: "Market position",
      value: `Top ${100 - pct}% of candidates at your level`,
      accent: pct >= 60 ? PALETTE.success : "#d97706",
    });
  }

  if (f.shortlist_rate !== null) {
    const ratePct = Math.round(f.shortlist_rate * 100);
    cards.push({
      id: "shortlist_rate",
      label: "Recruiter shortlist rate",
      value: `${ratePct}% of simulated recruiters would shortlist`,
      accent: ratePct >= 50 ? PALETTE.success : "#d97706",
    });
  }

  return cards;
}

function FindingCard({ card }: { card: FindingCard }): ReactElement {
  const [visible, setVisible] = useState(false);
  const [flash, setFlash] = useState(true);

  useEffect(() => {
    const t1 = window.setTimeout(() => setVisible(true), 30);
    const t2 = window.setTimeout(() => setFlash(false), 800);
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, []);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "10px",
        paddingTop: "10px",
        paddingBottom: "10px",
        paddingLeft: "12px",
        paddingRight: "12px",
        background: flash ? PALETTE.activeBg : PALETTE.white,
        border: `1px solid ${PALETTE.border}`,
        borderLeft: `3px solid ${card.accent}`,
        borderRadius: "8px",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(6px)",
        transition: "opacity 0.35s ease, transform 0.35s ease, background 0.6s ease",
      }}
    >
      <div>
        <div
          style={{
            fontSize: "11px",
            color: PALETTE.muted,
            marginBottom: "2px",
          }}
        >
          {card.label}
        </div>
        <div
          style={{
            fontSize: "13px",
            fontWeight: 500,
            color: PALETTE.text,
            lineHeight: 1.45,
            wordBreak: "break-word",
          }}
        >
          {card.value}
        </div>
      </div>
    </div>
  );
}

function LiveFindingsPanel({
  findings,
  activeStepIndex,
  completedSteps,
  barPct,
}: {
  findings: LiveFindings;
  activeStepIndex: number;
  completedSteps: Set<number>;
  barPct: number;
}): ReactElement {
  const cards = buildFindingCards(findings);
  const visibleCards = cards.slice(-5);

  return (
    <div
      style={{
        border: `1px solid ${PALETTE.activeBorder}`,
        borderRadius: "12px",
        background: PALETTE.activeBg,
        paddingTop: "14px",
        paddingBottom: "14px",
        paddingLeft: "14px",
        paddingRight: "14px",
        width: "100%",
        minHeight: "140px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "10px",
        }}
      >
        <div
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: PALETTE.text,
          }}
        >
          Live findings
        </div>
        <div style={{ fontSize: "12px", fontWeight: 700, color: PALETTE.primary }}>
          {Math.round(barPct)}%
        </div>
      </div>
      <div
        style={{
          fontSize: "12px",
          color: PALETTE.muted,
          marginBottom: visibleCards.length > 0 ? "10px" : "12px",
          lineHeight: 1.45,
        }}
      >
        {visibleCards.length > 0
          ? "From your resume — more results appear as analysis continues."
          : waitingStatusMessage(activeStepIndex, completedSteps)}
      </div>

      {visibleCards.length === 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {[0, 1].map((i) => (
            <div
              key={i}
              aria-hidden
              style={{
                height: "52px",
                borderRadius: "8px",
                border: `1px solid ${PALETTE.border}`,
                background: `linear-gradient(90deg, ${T.bgPage} 0%, ${T.primaryLight} 50%, ${T.bgPage} 100%)`,
                backgroundSize: "200% 100%",
                animation: "ripFindingShimmer 1.4s ease-in-out infinite",
                animationDelay: `${i * 0.2}s`,
              }}
            />
          ))}
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            maxHeight: "280px",
            overflowY: "auto",
            paddingRight: "2px",
          }}
        >
          {visibleCards.map((card) => (
            <FindingCard key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
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
  const [findings, setFindings] = useState<LiveFindings>(INITIAL_FINDINGS);
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
    setFindings(INITIAL_FINDINGS);
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
          "X-Session-ID": getOrCreateSessionId(),
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
            const normalized = normalizeAnalysisResult(raw);
            setFindings((f) =>
              mergeLiveFindingsFromPayload(f, normalized as unknown as Record<string, unknown>)
            );
            onCompleteRef.current(normalized);
          }
          if (ev === "error") {
            throwIfSseErrorPayload(payload);
          }

          if (ev === "partial" || payloadHasPartialData(payload)) {
            setFindings((f) => mergeLiveFindingsFromPayload(f, payload));
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
    setFindings(INITIAL_FINDINGS);
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
        background: T.bgPage,
      }}
    >
      <style>{`
        @keyframes ripProgressSpin {
          to { transform: rotate(360deg); }
        }
        @keyframes ripFindingShimmer {
          0% { background-position: 100% 0; }
          100% { background-position: -100% 0; }
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
              boxShadow: T.shadowPrimarySm,
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
                background: `linear-gradient(90deg, ${T.primary}, ${T.violet})`,
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
            width: isMobile ? "100%" : "340px",
            flex: isMobile ? "1 1 auto" : "0 0 340px",
            minWidth: isMobile ? 0 : "300px",
            alignSelf: "flex-start",
            position: isMobile ? "static" : "sticky",
            top: isMobile ? undefined : "72px",
          }}
        >
          <LiveFindingsPanel
            findings={findings}
            activeStepIndex={activeStepIndex}
            completedSteps={completedSteps}
            barPct={barPct}
          />
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
