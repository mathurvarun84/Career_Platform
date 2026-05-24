import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";

import { applyPatches, generateCoachingBullet, rollbackPatch } from "../api/client";
import { IS_MOCK } from "../hooks/useMockData";
import { useWindowSize } from "../hooks/useWindowSize";
import { useRescore } from "../hooks/useRescore";
import { pageContainerStyle } from "../utils/pageLayout";
import { hasJobDescription } from "../utils/hasJobDescription";
import { getFixModeBaseline } from "../utils/modeScores";
import { useResumeStore } from "../store/useResumeStore";
import { isEvidenceGap } from "../utils/roleFitEvidence";
import type {
  CareerMemoryEntry,
  GapType,
  PriorityFix,
  ProgressSnapshot,
  ResumePatch,
  RewriteStyle,
} from "../types";
import DataSourceNotice from "./DataSourceNotice";
import EvidenceCoachingCard from "./cards/EvidenceCoachingCard";
import StructuralPatchCard from "./cards/StructuralPatchCard";
import SurfacePatchCard from "./cards/SurfacePatchCard";
import type { ApplyState, CardHandlers } from "./cards/cardTypes";
import FixValidation from "./FixValidation";
import CareerRecordPanel from "./CareerRecordPanel";

interface ActionableFixesProps {
  addSnapshot?: (snapshot: ProgressSnapshot) => void;
  addCareerEntry?: (entry: CareerMemoryEntry) => void;
  totalPatchesApplied?: number;
  totalCoachingAnswers?: number;
}

const GAP_TYPE_ORDER: Record<GapType, number> = {
  surface: 0,
  structural: 1,
  evidence: 2,
};

const scoreDeltaByType: Record<GapType, number> = {
  surface: 2,
  structural: 4,
  evidence: 0,
};

const canonicalSections = [
  "summary",
  "skills",
  "experience",
  "education",
  "certifications",
  "awards",
  "projects",
] as const;

const toTitleCase = (s: string): string =>
  s.replace(/\w\S*/g, (t) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase());

const inferSectionKey = (value: string): string => {
  const lower = value.toLowerCase();
  if (canonicalSections.includes(lower as (typeof canonicalSections)[number])) return lower;
  if (lower.includes("summary")) return "summary";
  if (lower.includes("skill") || lower.includes("keyword")) return "skills";
  if (lower.includes("experience") || lower.includes("bullet")) return "experience";
  if (lower.includes("education")) return "education";
  if (lower.includes("certification")) return "certifications";
  if (lower.includes("award")) return "awards";
  if (lower.includes("project")) return "projects";
  return "summary";
};

const normalizePriorityFixes = (
  priorityFixes: Array<string | PriorityFix> | undefined
): PriorityFix[] => {
  if (!priorityFixes?.length) return [];

  return priorityFixes.flatMap((item): PriorityFix[] => {
    if (typeof item === "string") {
      return [
        {
          section: inferSectionKey(item),
          needs_change: true,
          gap_reason: item,
          rewrite_instruction: item,
          missing_keywords: [],
          gap_type: "structural",
        },
      ];
    }
    if (
      typeof item === "object" &&
      item !== null &&
      "section" in item &&
      "gap_reason" in item
    ) {
      return [item];
    }
    return [];
  });
};

const fixesFromSectionGaps = (
  sectionGaps: Array<{
    section: string;
    needs_change: boolean;
    gap_reason: string;
    rewrite_instruction: string;
    missing_keywords: string[];
    gap_type?: GapType;
    requires_user_input?: boolean;
    coaching_question?: string | null;
    coaching_hint?: string[];
    auto_apply?: boolean;
    sub_label?: string | null;
  }>
): PriorityFix[] =>
  sectionGaps
    .filter((g) => g.needs_change)
    .map((g) => ({
      section: g.section,
      gap_reason: g.gap_reason,
      rewrite_instruction: g.rewrite_instruction,
      missing_keywords: g.missing_keywords ?? [],
      needs_change: true,
      gap_type: g.gap_type ?? "structural",
      requires_user_input: g.requires_user_input,
      coaching_question: g.coaching_question,
      coaching_hint: g.coaching_hint,
      auto_apply: g.auto_apply,
      sub_label: g.sub_label,
    }));

function renderCard(
  fix: PriorityFix,
  fixKey: string,
  handlers: CardHandlers,
  sessionId: string,
  onCoachingDone: (entry: CareerMemoryEntry) => void | Promise<void>
): ReactElement | null {
  const gapType = fix.gap_type ?? "structural";
  if (gapType === "surface") {
    return <SurfacePatchCard key={fixKey} fix={fix} fixKey={fixKey} handlers={handlers} />;
  }
  if (gapType === "structural") {
    return (
      <StructuralPatchCard key={fixKey} fix={fix} fixKey={fixKey} handlers={handlers} />
    );
  }
  if (gapType === "evidence") {
    return (
      <EvidenceCoachingCard
        key={fixKey}
        fix={fix}
        fixKey={fixKey}
        sessionId={sessionId}
        onDone={onCoachingDone}
      />
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
  const [quickWinsExpanded, setQuickWinsExpanded] = useState(false);
  const [careerMemoryVersion, setCareerMemoryVersion] = useState(0);
  const autoAppliedRef = useRef<Set<string>>(new Set());
  const patchCountRef = useRef(totalPatchesApplied);
  const coachingCountRef = useRef(totalCoachingAnswers);
  const { isMobile } = useWindowSize();
  const { rescore } = useRescore(jobId ?? analysisResult?.job_id ?? "");

  useEffect(() => {
    patchCountRef.current = totalPatchesApplied;
  }, [totalPatchesApplied]);

  useEffect(() => {
    coachingCountRef.current = totalCoachingAnswers;
  }, [totalCoachingAnswers]);

  const suppressedEvidenceGaps =
    applyAnywayAccepted && analysisResult?.role_fit?.fitness === "underqualified";

  const fixes = useMemo(() => {
    if (!analysisResult?.gap) return [];

    const fromPriority = normalizePriorityFixes(
      analysisResult.gap.priority_fixes as Array<string | PriorityFix>
    );
    const hasStructured =
      fromPriority.length > 0 &&
      typeof analysisResult.gap.priority_fixes?.[0] === "object";

    let list = hasStructured
      ? fromPriority.filter((f) => f.needs_change)
      : fixesFromSectionGaps(analysisResult.gap.section_gaps ?? []);

    if (suppressedEvidenceGaps) {
      list = list.filter((f) => !isEvidenceGap(f));
    }

    return [...list].sort((a, b) => {
      const orderA = GAP_TYPE_ORDER[a.gap_type ?? "structural"];
      const orderB = GAP_TYPE_ORDER[b.gap_type ?? "structural"];
      return orderA - orderB;
    });
  }, [analysisResult, suppressedEvidenceGaps]);

  const patchBySection = useMemo(() => {
    const acc: Record<string, ResumePatch> = {};
    for (const patch of analysisResult?.patches ?? []) {
      if (!acc[patch.section]) {
        acc[patch.section] = patch;
      }
    }
    return acc;
  }, [analysisResult?.patches]);

  const getSectionKey = (fix: PriorityFix) => inferSectionKey(fix.section);
  const getDisplaySection = (fix: PriorityFix) => toTitleCase(inferSectionKey(fix.section));
  const getFixKey = (fix: PriorityFix, index: number) =>
    `${getDisplaySection(fix)}-${fix.sub_label ?? "main"}-${index}`;

  const getBeforeText = useCallback(
    (fix: PriorityFix): string => {
      const key = getSectionKey(fix);
      return (
        analysisResult?.resume.resume_sections?.[key]?.full_text?.trim() ??
        "[Original text from your resume]"
      );
    },
    [analysisResult]
  );

  const getAfterText = useCallback(
    (fix: PriorityFix): string => {
      const key = getSectionKey(fix);
      const patch = patchBySection[key];

      if (patch?.replacement_text && patch.original_text) {
        const base = analysisResult?.resume.resume_sections?.[key]?.full_text?.trim() ?? "";
        const idx = base.indexOf(patch.original_text);
        if (idx !== -1) {
          return base.slice(0, idx) + patch.replacement_text + base.slice(idx + patch.original_text.length);
        }
        return patch.replacement_text;
      }

      return fix.rewrite_instruction || "[Rewrite not available for this section]";
    },
    [analysisResult, patchBySection]
  );

  const getPatchDiff = useCallback(
    (fix: PriorityFix): { original: string; replacement: string } | null => {
      const patch = patchBySection[getSectionKey(fix)];
      if (patch?.original_text && patch.replacement_text) {
        return { original: patch.original_text, replacement: patch.replacement_text };
      }
      const kw = fix.missing_keywords[0];
      if (kw) {
        return {
          original: `Missing ${kw}`,
          replacement: `Added ${kw}`,
        };
      }
      return null;
    },
    [patchBySection]
  );

  const scoreDelta = useCallback(
    (fix: PriorityFix) => scoreDeltaByType[fix.gap_type ?? "structural"],
    []
  );

  const onApply = useCallback(
    async (fix: PriorityFix, fixKey: string) => {
      setApplyState((s) => ({ ...s, [fixKey]: "loading" }));
      const sectionKey = getSectionKey(fix);
      const style: RewriteStyle = "balanced";
      const sectionText = getAfterText(fix);

      if (IS_MOCK) {
        applySectionFix(sectionKey, style, sectionText);
        setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
        return;
      }

      if (jobId) {
        const patch = patchBySection[sectionKey];
        if (patch?.patch_id) {
          try {
            const result = await applyPatches(
              jobId,
              [patch.patch_id],
              patch.risk === "needs_confirmation"
            );
            const outcome = result.results?.find((r) => r.patch_id === patch.patch_id);
            if (!outcome?.applied || !outcome.found_in_doc) {
              setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
              return;
            }
            applySectionFix(sectionKey, style, sectionText);
            if (result.score) {
              mergePartialResult({ ats: result.score });
            }
            setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
            const rescored = await rescore();
            const nextPatchCount = patchCountRef.current + 1;
            patchCountRef.current = nextPatchCount;
            addSnapshot?.({
              timestamp: new Date().toISOString(),
              ats_score:
                rescored?.ats_score ??
                result.score?.score ??
                analysisResult?.ats.score ??
                0,
              jd_match: null,
              percentile: null,
              label: `After Fix #${nextPatchCount}`,
              patches_applied: nextPatchCount,
              coaching_answers: coachingCountRef.current,
              session_id: jobId ?? analysisResult?.job_id ?? "",
            });
            return;
          } catch (error) {
            console.error("Failed to apply patch:", error);
            setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
            return;
          }
        }
      }

      if ((fix.gap_type ?? "structural") === "structural") {
        setApplyState((s) => ({ ...s, [fixKey]: "failed" }));
        return;
      }

      applySectionFix(sectionKey, style, sectionText);
      setApplyState((s) => ({ ...s, [fixKey]: "applied" }));
    },
    [
      addSnapshot,
      analysisResult?.ats.score,
      analysisResult?.job_id,
      applySectionFix,
      getAfterText,
      jobId,
      mergePartialResult,
      patchBySection,
      rescore,
    ]
  );

  const onUndo = useCallback(
    async (fix: PriorityFix, fixKey: string) => {
      const sectionKey = getSectionKey(fix);
      if (jobId) {
        const patch = patchBySection[sectionKey];
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
    [jobId, mergePartialResult, patchBySection]
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
    addSnapshot?.({
      timestamp: new Date().toISOString(),
      ats_score: rescored?.ats_score ?? analysisResult?.ats.score ?? 0,
      jd_match: null,
      percentile: null,
      label: "After Coaching",
      patches_applied: patchCountRef.current,
      coaching_answers: nextCoachingCount,
      session_id: jobId ?? analysisResult?.job_id ?? "",
    });
  }, [
    addCareerEntry,
    addSnapshot,
    analysisResult?.ats,
    analysisResult?.ats.score,
    analysisResult?.job_id,
    jobId,
    mergePartialResult,
    rescore,
  ]);

  useEffect(() => {
    fixes.forEach((fix, index) => {
      if (!fix.auto_apply) return;
      const fixKey = getFixKey(fix, index);
      if (autoAppliedRef.current.has(fixKey)) return;
      autoAppliedRef.current.add(fixKey);
      void onApply(fix, fixKey);
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
  const appliedCount = Object.values(applyState).filter((s) => s === "applied").length;

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={pageContainerStyle(isMobile, isMobile ? 88 : 72)}>
        <div style={{ marginBottom: "32px", textAlign: "center" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              borderRadius: "999px",
              background: "#eef2ff",
              border: "1px solid #c7d2fe",
              color: "#4f46e5",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            ✦ Intelligent Patches
          </div>
          <div
            style={{
              fontSize: isMobile ? "22px" : "28px",
              fontWeight: 800,
              color: "#111827",
              letterSpacing: "-0.02em",
              marginTop: "14px",
            }}
          >
            Actionable Fixes
          </div>
          <div style={{ fontSize: "15px", color: "#6b7280", marginTop: "8px" }}>
            Surface patches, surgical rewrites, and coaching for evidence gaps.
          </div>
        </div>

        {surfaceFixes.length > 0 ? (
          <div
            style={{
              background: "#f0fdf4",
              border: "1.5px solid #bbf7d0",
              borderRadius: "12px",
              padding: "14px 18px",
              marginBottom: "20px",
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
                {surfaceFixes.map((fix) => {
                  const diff = getPatchDiff(fix);
                  return (
                    <div
                      key={`${fix.section}-${fix.sub_label ?? "main"}`}
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

        {fixes.length === 0 ? (
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "48px 32px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "17px", fontWeight: 700, color: "#111827" }}>
              No fixes needed
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "4px" }}>
              No fixes needed — your resume is well-optimised for this role.
            </div>
          </div>
        ) : (
          fixes.map((fix, index) => {
            const displayFix: PriorityFix = {
              ...fix,
              section: getDisplaySection(fix),
            };
            const fixKey = getFixKey(fix, index);
            return renderCard(
              displayFix,
              fixKey,
              handlers,
              jobId ?? analysisResult.job_id,
              handleCoachingDone
            );
          })
        )}

        <CareerRecordPanel
          sessionId={jobId ?? analysisResult.job_id}
          version={careerMemoryVersion}
        />

        <FixValidation
          selectedMode={"safe"}
          originalAts={originalAts}
          liveAts={liveAts}
          appliedCount={appliedCount}
          originalJd={originalJd}
          afterJd={afterJd}
          hasJd={hasJd}
          jobId={jobId ?? analysisResult.job_id}
          onSwitchMode={() => {}}
        />

        <DataSourceNotice tab="fixes" />
      </div>
    </div>
  );
}
