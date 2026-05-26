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
import { isActionableFix } from "../utils/actionableFixes";
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

const labelsMatch = (fixLabel: string, patchLabel: string): boolean => {
  const a = fixLabel.toLowerCase().trim();
  const b = patchLabel.toLowerCase().trim();
  if (!a || !b) {
    return !a && !b;
  }
  const aCompany = a.split("—")[0]?.trim() ?? a;
  const bCompany = b.split("—")[0]?.trim() ?? b;
  const bHead = b.split("|")[0]?.trim() ?? b;
  return (
    a === b ||
    a.includes(bCompany) ||
    b.includes(aCompany) ||
    a.includes(bHead)
  );
};

const resolvePatchForFix = (
  fix: PriorityFix,
  patches: ResumePatch[] | undefined,
  sectionKey: string
): ResumePatch | undefined => {
  if (!patches?.length) {
    return undefined;
  }
  const inSection = patches.filter(
    (patch) => inferSectionKey(patch.section) === sectionKey
  );
  if (!inSection.length) {
    return undefined;
  }
  if (fix.sub_label) {
    const subMatches = inSection.filter((patch) =>
      labelsMatch(fix.sub_label ?? "", patch.sub_entry_label ?? "")
    );
    if (subMatches.length) {
      return (
        subMatches.find((patch) => patch.original_text?.trim()) ?? subMatches[0]
      );
    }
    // sub_label scoped but no matching patch — return undefined rather than
    // falling through to an unrelated entry's patch (cross-contamination bug)
    return undefined;
  }
  const sectionWide = inSection.filter((patch) => !patch.sub_entry_label?.trim());
  const pool = sectionWide.length ? sectionWide : inSection;
  return pool.find((patch) => patch.original_text?.trim()) ?? pool[0];
};

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

const inferSectionFromIssue = (issue: string): string => {
  const lower = issue.toLowerCase();
  if (lower.includes("experience") || lower.includes("bullet") || lower.includes("role")) return "experience";
  if (lower.includes("skill") || lower.includes("keyword")) return "skills";
  if (lower.includes("summary") || lower.includes("objective")) return "summary";
  if (lower.includes("education")) return "education";
  if (lower.includes("certification")) return "certifications";
  return "experience";
};

const inferGapTypeFromText = (text: string): GapType => {
  const lower = text.toLowerCase();
  if (
    /readability|shorter|clearer|concise|scannab|dense|sentence|word.?spacing|runon|filler/.test(
      lower
    )
  ) {
    return "surface";
  }
  if (/missing keyword|typo|spelling|add keyword|include term/.test(lower)) {
    return "surface";
  }
  if (
    /mentor|evidence|collaborat|architectur|roadmap|ownership|quantif|cross-team|stakeholder/.test(
      lower
    ) &&
    /no mention|lacks|missing|share a specific|user input/.test(lower)
  ) {
    return "evidence";
  }
  return "structural";
};

/** One card per section + sub_entry — not per gap_reason or missing keyword. */
const fixLocationKey = (fix: PriorityFix): string =>
  `${inferSectionKey(fix.section)}|${(fix.sub_label ?? "").toLowerCase().trim() || "__section__"}`;

const mergePriorityFix = (existing: PriorityFix, incoming: PriorityFix): PriorityFix => {
  const mergedKeywords = Array.from(
    new Set([...(existing.missing_keywords ?? []), ...(incoming.missing_keywords ?? [])])
  );
  const typeOrder: Record<GapType, number> = { evidence: 0, structural: 1, surface: 2 };
  const existingType = existing.gap_type ?? "structural";
  const incomingType = incoming.gap_type ?? "structural";
  const preferIncoming = typeOrder[incomingType] < typeOrder[existingType];
  return {
    ...existing,
    ...(preferIncoming ? incoming : {}),
    gap_reason: existing.gap_reason,
    missing_keywords: mergedKeywords,
    auto_apply: preferIncoming ? incoming.auto_apply : existing.auto_apply,
  };
};

const mergeFixLists = (...lists: PriorityFix[][]): PriorityFix[] => {
  const mergedMap = new Map<string, PriorityFix>();
  const order: string[] = [];
  for (const list of lists) {
    for (const fix of list) {
      const key = fixLocationKey(fix);
      if (!mergedMap.has(key)) {
        mergedMap.set(key, fix);
        order.push(key);
        continue;
      }
      mergedMap.set(key, mergePriorityFix(mergedMap.get(key)!, fix));
    }
  }
  return order.map((key) => mergedMap.get(key)!);
};

const atsIssuesToFixes = (atsIssues: string[], existingFixes: PriorityFix[]): PriorityFix[] => {
  const existingReasons = new Set(
    existingFixes.map((f) => f.gap_reason.toLowerCase().slice(0, 50))
  );
  return atsIssues
    .filter((issue) => !existingReasons.has(issue.toLowerCase().slice(0, 50)))
    .map((issue) => {
      const gapType = inferGapTypeFromText(issue);
      return {
        section: inferSectionFromIssue(issue),
        gap_reason: issue,
        rewrite_instruction: issue,
        missing_keywords: [],
        needs_change: true,
        gap_type: gapType,
        auto_apply: gapType === "surface",
        requires_user_input: false,
      };
    });
};

const fixesFromPatches = (patches: ResumePatch[] | undefined): PriorityFix[] => {
  if (!patches?.length) return [];

  return patches
    .filter(
      (patch) =>
        patch.op === "replace_text" &&
        Boolean(patch.original_text?.trim()) &&
        Boolean(patch.replacement_text?.trim())
    )
    .map((patch) => {
      const context = `${patch.issue_detected} ${patch.fix_rationale} ${patch.original_text}`;
      const gapType = inferGapTypeFromText(context);
      return {
        section: patch.section,
        gap_reason:
          patch.issue_detected?.trim() ||
          patch.fix_rationale?.trim() ||
          "Intelligent patch suggested for this section",
        rewrite_instruction: patch.replacement_text,
        missing_keywords: patch.keyword ? [patch.keyword] : [],
        needs_change: true,
        gap_type: gapType,
        auto_apply: gapType === "surface",
        requires_user_input: false,
        sub_label: patch.sub_entry_label?.trim() || null,
      };
    });
};

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
    }))
    .filter(isActionableFix);

function renderCard(
  fix: PriorityFix,
  fixKey: string,
  handlers: CardHandlers,
  sessionId: string,
  onCoachingDone: (entry: CareerMemoryEntry) => void | Promise<void>,
  onMemoryCreated: () => void
): ReactElement | null {
  const gapType = fix.gap_type ?? "structural";
  if (gapType === "surface") {
    return <SurfacePatchCard key={fixKey} fix={fix} fixKey={fixKey} handlers={handlers} />;
  }
  if (gapType === "structural") {
    const patchDiff = handlers.getPatchDiff(fix);
    const afterText = handlers.getAfterText(fix).trim();
    if (!patchDiff && !afterText) {
      const coachingFix: PriorityFix = {
        ...fix,
        gap_type: "evidence",
        requires_user_input: true,
        coaching_question: fix.coaching_question ?? fix.gap_reason,
      };
      return (
        <EvidenceCoachingCard
          key={fixKey}
          fix={coachingFix}
          fixKey={fixKey}
          sessionId={sessionId}
          onDone={onCoachingDone}
          onMemoryCreated={onMemoryCreated}
        />
      );
    }
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
        onMemoryCreated={onMemoryCreated}
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
  const [coachingAppliedCount, setCoachingAppliedCount] = useState(
    totalCoachingAnswers
  );
  const [quickWinsExpanded, setQuickWinsExpanded] = useState(false);
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

  const fixes = useMemo(() => {
    if (!analysisResult?.gap) return [];

    const fromPriority = normalizePriorityFixes(
      analysisResult.gap.priority_fixes as Array<string | PriorityFix>
    ).filter(isActionableFix);
    const fromSections = fixesFromSectionGaps(analysisResult.gap.section_gaps ?? []);
    const fromPatches = fixesFromPatches(analysisResult.patches).filter(isActionableFix);
    const hasStructured =
      fromPriority.length > 0 &&
      typeof analysisResult.gap.priority_fixes?.[0] === "object";

    const gapAnalyzerFixes = hasStructured ? fromPriority : fromSections;

    let list = mergeFixLists(gapAnalyzerFixes, fromPatches);

    const atsDriven = atsIssuesToFixes(
      analysisResult.ats.ats_issues ?? [],
      list
    ).filter(isActionableFix);
    list = mergeFixLists(list, atsDriven);

    if (suppressedEvidenceGaps) {
      list = list.filter((f) => !isEvidenceGap(f));
    }

    return [...list].sort((a, b) => {
      const orderA = GAP_TYPE_ORDER[a.gap_type ?? "structural"];
      const orderB = GAP_TYPE_ORDER[b.gap_type ?? "structural"];
      return orderA - orderB;
    });
  }, [analysisResult, suppressedEvidenceGaps]);

  const patches = analysisResult?.patches;

  const getSectionKey = (fix: PriorityFix) => inferSectionKey(fix.section);
  const getPatchForFix = useCallback(
    (fix: PriorityFix) => resolvePatchForFix(fix, patches, getSectionKey(fix)),
    [patches]
  );
  const getDisplaySection = (fix: PriorityFix) => toTitleCase(inferSectionKey(fix.section));
  const getFixKey = (fix: PriorityFix, index: number) =>
    `${getDisplaySection(fix)}-${fix.sub_label ?? "main"}-${index}`;

  const getBeforeText = useCallback(
    (fix: PriorityFix): string => {
      const key = getSectionKey(fix);
      const fullText =
        analysisResult?.resume.resume_sections?.[key]?.full_text?.trim() ?? "";

      if (fix.sub_label && fullText) {
        const subEntries =
          analysisResult?.resume.resume_sections?.[key]?.sub_entries ?? [];
        const subLabel = fix.sub_label;
        const match = subEntries.find((entry) => {
          if (!entry.label || !subLabel) {
            return false;
          }
          const labelLower = entry.label.toLowerCase();
          const subLower = subLabel.toLowerCase();
          const subCompany = subLower.split("—")[0]?.trim() ?? subLower;
          const labelHead = labelLower.split("|")[0]?.trim() ?? labelLower;
          return (
            entry.label === subLabel ||
            labelLower.includes(subCompany) ||
            subLower.includes(labelHead)
          );
        });
        if (match?.verbatim_text) {
          return match.verbatim_text.trim();
        }
        if (process.env.NODE_ENV !== "production") {
          console.warn(
            "[getBeforeText] No sub_entry match for sub_label:", fix.sub_label,
            "in section:", key,
            "— available:", subEntries.map((e) => e.label)
          );
        }
      }

      return fullText || "[Original text from your resume]";
    },
    [analysisResult]
  );

  const getAfterText = useCallback(
    (fix: PriorityFix): string => {
      const key = getSectionKey(fix);
      const patch = getPatchForFix(fix);

      if (patch?.replacement_text && patch.original_text) {
        const base =
          analysisResult?.resume.resume_sections?.[key]?.full_text?.trim() ?? "";
        const idx = base.indexOf(patch.original_text);
        if (idx !== -1) {
          return (
            base.slice(0, idx) +
            patch.replacement_text +
            base.slice(idx + patch.original_text.length)
          );
        }
        return patch.replacement_text;
      }

      if (
        patch?.replacement_text &&
        fix.sub_label &&
        labelsMatch(fix.sub_label, patch.sub_entry_label ?? "")
      ) {
        return patch.replacement_text;
      }

      const rewriteBlock =
        analysisResult?.rewrites?.rewrites?.[key]?.balanced;
      if (typeof rewriteBlock === "string" && rewriteBlock.trim()) {
        if (process.env.NODE_ENV !== "production") {
          console.warn(
            "[getAfterText] Fell back to section-level rewrite for fix:",
            fix.section, fix.sub_label ?? "(no sub_label)"
          );
        }
        return rewriteBlock.trim();
      }

      return "";
    },
    [analysisResult, getPatchForFix]
  );

  const getPatchDiff = useCallback(
    (fix: PriorityFix): { original: string; replacement: string } | null => {
      const patch = getPatchForFix(fix);
      if (patch?.original_text && patch.replacement_text) {
        const original = patch.original_text.trim();
        const replacement = patch.replacement_text.trim();
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
      const kw = fix.missing_keywords[0];
      if (kw) {
        return {
          original: `Missing ${kw}`,
          replacement: `Added ${kw}`,
        };
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
      if (!sectionText.trim()) {
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
      const sectionKey = getSectionKey(fix);
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
              coachingSessionId,
              handleCoachingDone,
              handleMemoryCreated
            );
          })
        )}

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
                border: "1.5px solid #e0e7ff",
                borderRadius: "12px",
                padding: "16px 20px",
                marginBottom: "20px",
                background: "#f5f3ff",
              }}
            >
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "#4f46e5",
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
                    color: "#374151",
                    lineHeight: 1.55,
                    paddingLeft: "12px",
                    borderLeft: "3px solid #a5b4fc",
                    marginBottom: "8px",
                  }}
                >
                  {issue}
                </div>
              ))}
            </div>
          );
        })()}

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

        <DataSourceNotice tab="fixes" />
      </div>
    </div>
  );
}
