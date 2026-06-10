import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";

import {
  applyPatches,
  generateCoachingBullet,
  getCareerMemory,
  rollbackPatch,
} from "../api/client";
import { IS_MOCK } from "../hooks/useMockData";
import { useWindowSize } from "../hooks/useWindowSize";
import { useRescore } from "../hooks/useRescore";
import { pageContainerStyle } from "../utils/pageLayout";
import { hasJobDescription } from "../utils/hasJobDescription";
import { getCoachingSessionId } from "../utils/coachingSession";
import { getFixModeBaseline } from "../utils/modeScores";
import { useResumeStore } from "../store/useResumeStore";
import {
  deriveExampleHint,
  isNoChangeReplacement,
  isUsableAfterText,
  structuralCardHasNoData,
} from "../utils/fixesCardLogic";
import {
  deriveInfoOnlyScopeLabel,
  fixLocationKey,
  inferSectionKey,
  parseInfoOnlyCardParts,
  partitionFixesByCoachingCap,
} from "../utils/fixesPipeline";
import {
  buildFixesFromPlan,
  resolvePatchFromPlan,
} from "../utils/fixPlanAdapter";
import { isEvidenceGap } from "../utils/roleFitEvidence";
import type {
  CareerMemoryEntry,
  GapType,
  PriorityFix,
  ProgressSnapshot,
  RewriteStyle,
} from "../types";
import { T } from "../tokens";
import DataSourceNotice from "./DataSourceNotice";
import EvidenceCoachingCard from "./cards/EvidenceCoachingCard";
import StructuralPatchCard from "./cards/StructuralPatchCard";
import SurfacePatchCard from "./cards/SurfacePatchCard";
import type { ApplyState, CardHandlers } from "./cards/cardTypes";
import FixValidation from "./FixValidation";

interface ActionableFixesProps {
  addSnapshot?: (snapshot: ProgressSnapshot) => void;
  addCareerEntry?: (entry: CareerMemoryEntry) => void;
  totalPatchesApplied?: number;
  totalCoachingAnswers?: number;
}

const scoreDeltaByType: Record<GapType, number> = {
  surface: 2,
  structural: 4,
  evidence: 0,
};

const toTitleCase = (s: string): string =>
  s.replace(/\w\S*/g, (t) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase());

function InfoOnlyCard({ fix }: { fix: PriorityFix }): ReactElement {
  const { whatPart } = parseInfoOnlyCardParts(fix.gap_reason);
  const scopeLabel = deriveInfoOnlyScopeLabel(fix);
  const exampleHint = deriveExampleHint(fix.gap_reason);

  return (
    <div
      style={{
        border: `1.5px solid ${T.border}`,
        borderRadius: "18px",
        padding: "20px 24px",
        marginBottom: "12px",
        background: T.bgPage,
        transition: "box-shadow 0.2s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowMd; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: "14px", fontWeight: 700, color: T.textPrimary }}>
            {toTitleCase(inferSectionKey(fix.section))}
            {scopeLabel ? ` · ${scopeLabel}` : ""}
          </div>
        </div>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: T.textMuted,
            background: T.bgSubtle,
            border: `1px solid ${T.border}`,
            borderRadius: T.radiusPill,
            padding: "3px 10px",
            whiteSpace: "nowrap",
          }}
        >
          Manual edit
        </div>
      </div>

      <div style={{ fontSize: "13px", color: T.textSecondary, marginTop: "8px", lineHeight: 1.6 }}>
        {whatPart}
      </div>

      {exampleHint ? (
        <div
          style={{
            marginTop: "10px",
            padding: "10px 14px",
            background: T.primaryLight,
            borderRadius: "10px",
            border: `1px solid ${T.primaryMid}`,
            fontSize: "12px",
            color: T.primary,
            lineHeight: 1.6,
          }}
        >
          <span style={{ fontWeight: 600 }}>e.g. </span>
          {exampleHint}
        </div>
      ) : null}
    </div>
  );
}

function renderCard(
  fix: PriorityFix,
  fixKey: string,
  handlers: CardHandlers,
  sessionId: string,
  onCoachingDone: (entry: CareerMemoryEntry) => void | Promise<void>,
  onMemoryCreated: () => void
): ReactElement | null {
  const gapType = fix.gap_type ?? "structural";

  // Evidence/coaching items must be checked FIRST — before surface and structural branches.
  // fix_plan items with gap_type=evidence may also have rewrite_instruction set (A3 always
  // emits one), which would cause structuralCardHasNoData to return false and route them
  // to StructuralPatchCard where getPatchDiff falls back to the keyword diff.
  // requires_user_input=true items (regardless of gap_type) also belong here.
  if (gapType === "evidence" || fix.requires_user_input) {
    return (
      <EvidenceCoachingCard
        key={fixKey}
        fix={fix}
        fixKey={fixKey}
        sessionId={sessionId}
        onDone={onCoachingDone}
        onMemoryCreated={onMemoryCreated}
      />
    );
  }

  if (gapType === "surface") {
    return <SurfacePatchCard key={fixKey} fix={fix} fixKey={fixKey} handlers={handlers} />;
  }

  if (gapType === "structural") {
    const afterText = handlers.getAfterText(fix);
    const patchDiff = handlers.getPatchDiff(fix);
    const hasNoData = structuralCardHasNoData(afterText, patchDiff);

    if (hasNoData) {
      if (isEvidenceGap(fix)) {
        return (
          <EvidenceCoachingCard
            key={fixKey}
            fix={fix}
            fixKey={fixKey}
            sessionId={sessionId}
            onDone={onCoachingDone}
            onMemoryCreated={onMemoryCreated}
          />
        );
      }
      return <InfoOnlyCard key={fixKey} fix={fix} />;
    }

    return (
      <StructuralPatchCard key={fixKey} fix={fix} fixKey={fixKey} handlers={handlers} />
    );
  }

  return null;
}

export default function ActionableFixes({
  addSnapshot,
  addCareerEntry,
  totalPatchesApplied = 0,
  totalCoachingAnswers = 0,
}: ActionableFixesProps) {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const jobId = useResumeStore((s) => s.jobId);
  const applySectionFix = useResumeStore((s) => s.applySectionFix);
  const mergePartialResult = useResumeStore((s) => s.mergePartialResult);
  const baselineAts = useResumeStore((s) => s.baselineAts);
  const applyAnywayAccepted = useResumeStore((s) => s.applyAnywayAccepted);

  const [applyState, setApplyState] = useState<Record<string, ApplyState>>({});
  const [coachingAppliedCount, setCoachingAppliedCount] = useState(
    totalCoachingAnswers
  );
  const [quickWinsExpanded, setQuickWinsExpanded] = useState(false);
  const [showAllEvidence, setShowAllEvidence] = useState(false);
  const [careerMemoryVersion, setCareerMemoryVersion] = useState(0);
  const autoAppliedRef = useRef<Set<string>>(new Set());
  const patchCountRef = useRef(totalPatchesApplied);
  const coachingCountRef = useRef(totalCoachingAnswers);
  const { isMobile } = useWindowSize();
  const coachingSessionId = getCoachingSessionId(jobId, analysisResult);
  const { rescore } = useRescore(coachingSessionId);

  useEffect(() => {
    patchCountRef.current = totalPatchesApplied;
  }, [totalPatchesApplied]);

  useEffect(() => {
    coachingCountRef.current = totalCoachingAnswers;
    setCoachingAppliedCount(totalCoachingAnswers);
  }, [totalCoachingAnswers]);

  useEffect(() => {
    if (!coachingSessionId) return;
    getCareerMemory(coachingSessionId)
      .then((res) => {
        const approved = res.entries.filter((e) => e.user_approved).length;
        if (approved > 0) {
          setCoachingAppliedCount((prev) => Math.max(prev, approved));
          coachingCountRef.current = Math.max(coachingCountRef.current, approved);
        }
      })
      .catch(() => {
        /* career memory optional */
      });
  }, [coachingSessionId, careerMemoryVersion]);

  const suppressedEvidenceGaps =
    applyAnywayAccepted && analysisResult?.role_fit?.fitness === "underqualified";

  const fixes = useMemo(
    () => buildFixesFromPlan(analysisResult, { suppressEvidenceGaps: suppressedEvidenceGaps }),
    [analysisResult, suppressedEvidenceGaps]
  );

  const patches = analysisResult?.patches;

  const getSectionKey = (fix: PriorityFix) => inferSectionKey(fix.section);
  const getPatchForFix = useCallback(
    (fix: PriorityFix) => resolvePatchFromPlan(fix, patches),
    [patches]
  );
  const getDisplaySection = (fix: PriorityFix) => toTitleCase(inferSectionKey(fix.section));
  const getFixKey = (fix: PriorityFix, index: number) =>
    `${getDisplaySection(fix)}-${fix.entry_id ?? fix.sub_label ?? "main"}-${index}`;

  const getBeforeText = useCallback(
    (fix: PriorityFix): string =>
      (fix.original_text || "").trim() || "[Original text from your resume]",
    []
  );

  const getAfterText = useCallback(
    (fix: PriorityFix): string =>
      (fix.rewrite_instruction || "").trim(),
    []
  );

  const getPatchDiff = useCallback(
    (fix: PriorityFix): { original: string; replacement: string } | null => {
      const patch = getPatchForFix(fix);
      if (patch?.original_text && patch.replacement_text) {
        const original = patch.original_text.trim();
        const replacement = patch.replacement_text.trim();
        if (isNoChangeReplacement(replacement)) {
          // skip unusable LLM refusal patches
        } else {
        // Patches anchor on a bullet substring but replacement is often the full entry.
        if (replacement.startsWith(original)) {
          const delta = replacement.slice(original.length).trim();
          if (delta) {
            return { original, replacement: delta };
          }
        }
        if (original.length > 20 && replacement.includes(original)) {
          const delta = replacement.replace(original, "").trim();
          if (delta) {
            return { original, replacement: delta };
          }
        }
        return { original, replacement };
        }
      }
      // fix_plan rewrite_block items have before/after text but no patch_id.
      // Return the full diff so StructuralPatchCard shows the real before/after
      // text instead of falling through to the keyword one-liner fallback.
      const before = (fix.original_text || "").trim();
      const after = (fix.rewrite_instruction || "").trim();
      if (before && after && after !== before && !isNoChangeReplacement(after)) {
        return { original: before, replacement: after };
      }
      const kw = fix.missing_keywords[0];
      if (kw) {
        console.warn("[ActionableFixes] getPatchDiff: falling back to keyword diff for", fix.sub_label ?? fix.section);
        return { original: `Missing: ${kw}`, replacement: `Add: ${kw}` };
      }
      return null;
    },
    [getPatchForFix]
  );

  const scoreDelta = useCallback(
    (fix: PriorityFix) => scoreDeltaByType[fix.gap_type ?? "structural"],
    []
  );

  const recordPatchApplied = useCallback(
    async (atsScore?: number) => {
      const rescored = await rescore();
      const nextPatchCount = patchCountRef.current + 1;
      patchCountRef.current = nextPatchCount;
      addSnapshot?.({
        timestamp: new Date().toISOString(),
        ats_score:
          rescored?.ats_score ??
          atsScore ??
          analysisResult?.ats.score ??
          0,
        jd_match: null,
        percentile: null,
        label: `After Fix #${nextPatchCount}`,
        patches_applied: nextPatchCount,
        coaching_answers: coachingCountRef.current,
        session_id: coachingSessionId,
      });
    },
    [addSnapshot, analysisResult?.ats.score, coachingSessionId, rescore]
  );

  const applyLocally = useCallback(
    (
      fix: PriorityFix,
      fixKey: string,
      sectionKey: string,
      style: RewriteStyle
    ): boolean => {
      const sectionText = getAfterText(fix);
      if (!isUsableAfterText(sectionText)) {
        return false;
      }
      applySectionFix(sectionKey, style, sectionText);
      setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
      return true;
    },
    [applySectionFix, getAfterText]
  );

  const onApply = useCallback(
    async (fix: PriorityFix, fixKey: string) => {
      setApplyState((s) => ({ ...s, [fixKey]: "loading" }));
      const sectionKey = getSectionKey(fix);
      const style: RewriteStyle = "balanced";
      const sectionText = getAfterText(fix);
      const patch = getPatchForFix(fix);
      const canUseApi =
        Boolean(jobId) &&
        Boolean(patch?.patch_id) &&
        Boolean(patch?.original_text?.trim());

      if (IS_MOCK) {
        applySectionFix(sectionKey, style, sectionText);
        setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
        return;
      }

      if (canUseApi && jobId && patch?.patch_id) {
        try {
          const result = await applyPatches(
            jobId,
            [patch.patch_id],
            patch.risk === "needs_confirmation"
          );
          const outcome = result.results?.find((r) => r.patch_id === patch.patch_id);
          if (outcome?.applied && outcome.found_in_doc) {
            applySectionFix(sectionKey, style, sectionText);
            if (result.score) {
              mergePartialResult({ ats: result.score });
            }
            setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
            await recordPatchApplied(result.score?.score);
            return;
          }
          if (applyLocally(fix, fixKey, sectionKey, style)) {
            await recordPatchApplied(result.score?.score);
            return;
          }
          setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
          return;
        } catch (error) {
          console.error("Failed to apply patch:", error);
          if (applyLocally(fix, fixKey, sectionKey, style)) {
            await recordPatchApplied();
            return;
          }
          setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
          return;
        }
      }

      if (applyLocally(fix, fixKey, sectionKey, style)) {
        await recordPatchApplied();
        return;
      }

      setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
    },
    [
      applyLocally,
      applySectionFix,
      getAfterText,
      getPatchForFix,
      jobId,
      mergePartialResult,
      recordPatchApplied,
    ]
  );

  const onUndo = useCallback(
    async (fix: PriorityFix, fixKey: string) => {
      if (jobId) {
        const patch = getPatchForFix(fix);
        if (patch?.patch_id) {
          try {
            const rollbackResult = await rollbackPatch(jobId, patch.patch_id);
            mergePartialResult({ ats: rollbackResult.score });
          } catch (error) {
            console.error("Rollback failed:", error);
          }
        }
      }
      setApplyState((s) => ({ ...s, [fixKey]: "idle" }));
      autoAppliedRef.current.delete(fixKey);
    },
    [getPatchForFix, jobId, mergePartialResult]
  );

  const onCoachingSubmit = useCallback(
    async (fix: PriorityFix, rawAnswer: string, fixKey: string): Promise<string | null> => {
      if (IS_MOCK) {
        return `• ${rawAnswer.trim().replace(/\.$/, "")} — delivering measurable team and delivery outcomes.`;
      }
      if (!jobId) return null;
      try {
        const res = await generateCoachingBullet({
          session_id: jobId,
          gap_id: fixKey,
          section: fix.section,
          sub_label: fix.sub_label ?? null,
          raw_answer: rawAnswer,
          coaching_question: fix.coaching_question ?? fix.gap_reason,
          skill_category: fix.section,
        });
        return res.generated_bullet;
      } catch (error) {
        console.error("Coaching bullet generation failed:", error);
        return null;
      }
    },
    [jobId]
  );

  const handlers: CardHandlers = {
    applyState,
    getBeforeText,
    getAfterText,
    getPatchDiff,
    scoreDelta,
    onApply,
    onUndo,
    onCoachingSubmit,
  };

  const handleMemoryCreated = useCallback(() => {
    setCareerMemoryVersion((v) => v + 1);
  }, []);

  const handleCoachingDone = useCallback(async (entry: CareerMemoryEntry) => {
    addCareerEntry?.(entry);
    setCareerMemoryVersion((v) => v + 1);
    const rescored = await rescore();
    if (analysisResult?.ats) {
      mergePartialResult({
        ats: {
          ...analysisResult.ats,
          score: rescored?.ats_score ?? analysisResult.ats.score,
          breakdown: rescored
            ? {
                keyword_match:
                  rescored.breakdown.keyword_match ??
                  analysisResult.ats.breakdown.keyword_match,
                formatting:
                  rescored.breakdown.formatting ??
                  analysisResult.ats.breakdown.formatting,
                readability:
                  rescored.breakdown.readability ??
                  analysisResult.ats.breakdown.readability,
                impact_metrics:
                  rescored.breakdown.impact_metrics ??
                  analysisResult.ats.breakdown.impact_metrics,
              }
            : analysisResult.ats.breakdown,
          ats_issues: rescored?.ats_issues ?? analysisResult.ats.ats_issues,
        },
      });
    }
    const nextCoachingCount = coachingCountRef.current + 1;
    coachingCountRef.current = nextCoachingCount;
    setCoachingAppliedCount(nextCoachingCount);
    addSnapshot?.({
      timestamp: new Date().toISOString(),
      ats_score: rescored?.ats_score ?? analysisResult?.ats.score ?? 0,
      jd_match: null,
      percentile: null,
      label: "After Coaching",
      patches_applied: patchCountRef.current,
      coaching_answers: nextCoachingCount,
      session_id: coachingSessionId,
    });
  }, [
    addCareerEntry,
    addSnapshot,
    analysisResult?.ats,
    analysisResult?.ats.score,
    coachingSessionId,
    mergePartialResult,
    rescore,
  ]);

  useEffect(() => {
    fixes.forEach((fix, index) => {
      if (!fix.auto_apply) return;
      const locationKey = fixLocationKey(fix);
      if (autoAppliedRef.current.has(locationKey)) return;
      autoAppliedRef.current.add(locationKey);
      void onApply(fix, getFixKey(fix, index));
    });
  }, [fixes, getFixKey, onApply]);

  if (!analysisResult) {
    return null;
  }

  const surfaceFixes = fixes.filter((f) => (f.gap_type ?? "structural") === "surface");
  const quickWinPts = surfaceFixes.reduce((sum, f) => sum + scoreDelta(f), 0);
  const appliedSurfaceCount = surfaceFixes.filter((f) => {
    const idx = fixes.indexOf(f);
    const fixKey = getFixKey(f, idx);
    return applyState[fixKey] === "applied";
  }).length;

  const modeBaseline = getFixModeBaseline(analysisResult);
  const originalAts = baselineAts ?? modeBaseline.baselineAts;
  const liveAts = analysisResult.ats.score ?? 0;
  const hasJd = hasJobDescription(analysisResult.gap);
  const originalJd = hasJd ? analysisResult.gap?.jd_match_score_before ?? null : null;
  const afterJd = hasJd ? analysisResult.gap?.jd_match_score_after ?? null : null;
  const patchAppliedCount = Object.values(applyState).filter(
    (s) => s === "applied"
  ).length;
  const appliedCount = patchAppliedCount + coachingAppliedCount;

  const handleApplyAll = () => {
    fixes.forEach((fix, index) => {
      const fixKey = getFixKey(fix, index);
      if (applyState[fixKey] !== "applied" && applyState[fixKey] !== "loading") {
        void onApply(fix, fixKey);
      }
    });
  };

  return (
    <div style={{ minHeight: "100vh", background: T.bgPage }}>
      <div style={pageContainerStyle(isMobile, isMobile ? 88 : 72)}>

        {/* HERO */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              background: T.emeraldLight,
              border: `1px solid ${T.emeraldBorder}`,
              color: T.emerald,
              borderRadius: T.radiusPill,
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
              marginBottom: 16,
            }}
          >
            ✨ AI-Powered Fixes
          </div>
          <div
            style={{
              fontFamily: "'DM Serif Display', serif",
              fontSize: isMobile ? "32px" : "44px",
              fontWeight: 400,
              color: T.textPrimary,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              marginBottom: 12,
            }}
          >
            Before → After Fixes
          </div>
          <div
            style={{
              fontSize: "16px",
              color: T.textSecondary,
              maxWidth: 480,
              margin: "0 auto",
              lineHeight: 1.6,
              marginBottom: 20,
            }}
          >
            Surface patches, surgical rewrites, and coaching for evidence gaps.
          </div>
          {quickWinPts > 0 ? (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: T.primaryLight,
                border: `1px solid ${T.primaryMid}`,
                borderRadius: T.radiusPill,
                padding: "8px 18px",
                fontSize: "14px",
                fontWeight: 700,
                color: T.primary,
              }}
            >
              ↑ Total potential gain: +{quickWinPts} pts
            </div>
          ) : null}
        </div>

        {/* QUICK WINS BANNER */}
        {surfaceFixes.length > 0 ? (
          <div
            style={{
              background: T.emeraldLight,
              border: `1.5px solid ${T.emeraldBorder}`,
              borderRadius: "14px",
              padding: "16px 20px",
              marginBottom: "24px",
            }}
          >
            <button
              type="button"
              onClick={() => setQuickWinsExpanded((v) => !v)}
              style={{
                width: "100%",
                border: "none",
                background: "transparent",
                cursor: "pointer",
                textAlign: "left",
                padding: 0,
                fontSize: "14px",
                fontWeight: 700,
                color: "#166534",
              }}
            >
              ✓ {appliedSurfaceCount || surfaceFixes.length} quick fixes auto-applied · +
              {quickWinPts} ATS points {quickWinsExpanded ? "▼" : "▶"}
            </button>
            {quickWinsExpanded ? (
              <div style={{ marginTop: "12px" }}>
                {surfaceFixes.map((fix, idx) => {
                  const diff = getPatchDiff(fix);
                  return (
                    <div
                      key={fixLocationKey(fix) || `surface-${idx}`}
                      style={{
                        fontSize: "12px",
                        color: "#166534",
                        marginBottom: "6px",
                        lineHeight: 1.5,
                      }}
                    >
                      {diff
                        ? `${diff.original} → ${diff.replacement}`
                        : fix.gap_reason}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* FIXES LIST / EMPTY STATE */}
        {fixes.length === 0 ? (
          <div
            style={{
              border: `1.5px solid ${T.border}`,
              borderRadius: "18px",
              padding: "48px 32px",
              textAlign: "center",
              background: T.bgCard,
            }}
          >
            <div style={{ fontSize: "17px", fontWeight: 700, color: T.textPrimary }}>
              No fixes needed
            </div>
            <div style={{ fontSize: "13px", color: T.textSecondary, marginTop: "4px" }}>
              No fixes needed — your resume is well-optimised for this role.
            </div>
          </div>
        ) : (() => {
          const { visible: visibleFixes, hidden: hiddenEvidenceFixes } = partitionFixesByCoachingCap(fixes);
          return (
            <>
              {visibleFixes.map((fix, index) => {
                const displayFix: PriorityFix = {
                  ...fix,
                  section: getDisplaySection(fix),
                };
                const fixKey = getFixKey(fix, index);
                return renderCard(
                  displayFix,
                  fixKey,
                  handlers,
                  coachingSessionId,
                  handleCoachingDone,
                  handleMemoryCreated
                );
              })}

              {hiddenEvidenceFixes.length > 0 && (
                <>
                  {showAllEvidence && hiddenEvidenceFixes.map((fix, index) => {
                    const displayFix: PriorityFix = {
                      ...fix,
                      section: getDisplaySection(fix),
                    };
                    const fixKey = getFixKey(fix, visibleFixes.length + index);
                    return renderCard(
                      displayFix,
                      fixKey,
                      handlers,
                      coachingSessionId,
                      handleCoachingDone,
                      handleMemoryCreated
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => setShowAllEvidence((v) => !v)}
                    style={{
                      display: "block",
                      width: "100%",
                      border: "1.5px dashed #c4b5fd",
                      borderRadius: "10px",
                      padding: "12px 20px",
                      background: "transparent",
                      color: "#5b5fc7",
                      fontSize: "14px",
                      fontWeight: 600,
                      cursor: "pointer",
                      marginBottom: "16px",
                      textAlign: "left",
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                  >
                    {showAllEvidence
                      ? `▲ Collapse extra gaps`
                      : `▼ Show ${hiddenEvidenceFixes.length} more gap${hiddenEvidenceFixes.length > 1 ? "s" : ""} →`}
                  </button>
                </>
              )}
            </>
          );
        })()}

        {/* ATS INSIGHTS */}
        {(() => {
          const atsIssues = analysisResult.ats.ats_issues ?? [];
          const existingReasons = new Set(fixes.map((f) => f.gap_reason.toLowerCase().slice(0, 50)));
          const unaddressed = atsIssues.filter(
            (issue) => !existingReasons.has(issue.toLowerCase().slice(0, 50))
          );
          if (!unaddressed.length) return null;
          return (
            <div
              style={{
                border: `1.5px solid ${T.primaryMid}`,
                borderRadius: "14px",
                padding: "16px 20px",
                marginBottom: "20px",
                background: T.primaryLight,
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: T.primary,
                  marginBottom: "10px",
                  letterSpacing: "0.02em",
                  textTransform: "uppercase",
                }}
              >
                ATS Insights
              </div>
              {unaddressed.map((issue) => (
                <div
                  key={issue}
                  style={{
                    fontSize: "13px",
                    color: T.textSecondary,
                    lineHeight: 1.55,
                    paddingLeft: "12px",
                    borderLeft: `3px solid ${T.primary}`,
                    marginBottom: "8px",
                  }}
                >
                  {issue}
                </div>
              ))}
            </div>
          );
        })()}

        {/* FIX VALIDATION */}
        <FixValidation
          selectedMode={"safe"}
          originalAts={originalAts}
          liveAts={liveAts}
          appliedCount={appliedCount}
          patchAppliedCount={patchAppliedCount}
          coachingAppliedCount={coachingAppliedCount}
          originalJd={originalJd}
          afterJd={afterJd}
          hasJd={hasJd}
          jobId={coachingSessionId}
          onSwitchMode={() => {}}
        />

        {/* BOTTOM CTA */}
        {fixes.length > 0 ? (
          <div style={{ marginTop: 40, marginBottom: 8 }}>
            <div
              style={{
                borderRadius: "24px",
                padding: isMobile ? "32px 24px" : "48px",
                textAlign: "center",
                background: T.gradientBrand,
                boxShadow: T.shadowXl,
              }}
            >
              <div
                style={{
                  fontFamily: "'DM Serif Display', serif",
                  fontSize: isMobile ? "26px" : "36px",
                  fontWeight: 400,
                  color: "#ffffff",
                  marginBottom: 12,
                }}
              >
                Ready to transform your resume?
              </div>
              <div
                style={{
                  fontSize: "16px",
                  color: "rgba(255, 255, 255, 0.78)",
                  marginBottom: 28,
                  lineHeight: 1.6,
                }}
              >
                Apply all {fixes.length} fix{fixes.length === 1 ? "" : "es"} above to maximize your ATS score.
              </div>
              <button
                type="button"
                onClick={handleApplyAll}
                style={{
                  background: "#ffffff",
                  color: T.primary,
                  border: "none",
                  borderRadius: "12px",
                  padding: "14px 32px",
                  fontSize: "15px",
                  fontWeight: 700,
                  cursor: "pointer",
                  boxShadow: T.shadowLg,
                  transition: "transform 0.1s, box-shadow 0.1s",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-2px)";
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 16px 40px rgba(0,0,0,0.15)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.transform = "";
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = T.shadowLg;
                }}
                onMouseDown={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.transform = "translateY(3px)";
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.1)";
                }}
                onMouseUp={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-2px)";
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 16px 40px rgba(0,0,0,0.15)";
                }}
              >
                Apply All Fixes →
              </button>
            </div>
          </div>
        ) : null}

        {/* DATA SOURCE NOTICE — always last */}
        <DataSourceNotice tab="fixes" />

      </div>
    </div>
  );
}
