import type { AnalysisResult, GapType, PriorityFix, ResumePatch, TabId } from "../types";
import { isActionableFix } from "./actionableFixes";
import {
  buildFixLocationKey,
  extractCompanyTokenFromLabel,
  gapReasonMatchesFixScope,
  isNoChangeReplacement,
  isUsableAfterText,
  mergeFixLists,
  structuralCardHasNoData,
  subEntryLabelMatches,
} from "./fixesCardLogic";
import { fixesMissingFromOverview, inferEvidenceFromText } from "./overviewFixes";
import { buildCoachingQuestion } from "./coachingQuestions";
import { isEvidenceGap } from "./roleFitEvidence";

const MAX_COACHING_CARDS = 2;

const GAP_TYPE_ORDER: Record<GapType, number> = {
  surface: 0,
  structural: 1,
  evidence: 2,
};

const ROLE_FIT_LOCKED_TABS = new Set<TabId>(["fixes", "gap", "progress"]);

const canonicalSections = [
  "summary",
  "skills",
  "experience",
  "education",
  "certifications",
  "awards",
  "projects",
] as const;

const COMPANY_HEADER_RE =
  /##COMPANY##[^#]*##ROLE##[^#]*##END_HEADER##[ \t]*/g;
const STRAY_MARKER_RE = /##(?:COMPANY|ROLE|END_HEADER)##/g;

const stripRewriteMarkers = (text: string): string =>
  text
    .replace(COMPANY_HEADER_RE, "")
    .replace(STRAY_MARKER_RE, "")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .join("\n")
    .trim();

export function inferSectionKey(value: string): string {
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
}

export function inferGapTypeFromText(text: string): GapType {
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
}

export function normalizePriorityFixes(
  priorityFixes: Array<string | PriorityFix> | undefined
): PriorityFix[] {
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
}

export function fixesFromPatches(patches: ResumePatch[] | undefined): PriorityFix[] {
  if (!patches?.length) return [];

  return patches
    .filter(
      (patch) =>
        patch.op === "replace_text" &&
        Boolean(patch.original_text?.trim()) &&
        Boolean(patch.replacement_text?.trim()) &&
        !isNoChangeReplacement(patch.replacement_text)
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
        entry_id: patch.sub_entry_id?.trim() || null,
      };
    });
}

export const fixLocationKey = (fix: PriorityFix): string =>
  buildFixLocationKey(inferSectionKey(fix.section), fix.sub_label, fix.entry_id);

const labelsMatch = (fixLabel: string, patchLabel: string): boolean => {
  if (!fixLabel.trim() || !patchLabel.trim()) {
    return false;
  }
  if (fixLabel === patchLabel) {
    return true;
  }
  const aCompany = extractCompanyTokenFromLabel(fixLabel);
  const bCompany = extractCompanyTokenFromLabel(patchLabel);
  return (
    aCompany.length >= 4 &&
    bCompany.length >= 4 &&
    (aCompany.includes(bCompany) || bCompany.includes(aCompany))
  );
};

export function resolvePatchForFix(
  fix: PriorityFix,
  patches: ResumePatch[] | undefined,
  sectionKey: string
): ResumePatch | undefined {
  if (!patches?.length) {
    return undefined;
  }
  const inSection = patches.filter(
    (patch) => inferSectionKey(patch.section) === sectionKey
  );
  if (!inSection.length) {
    return undefined;
  }
  if (fix.entry_id) {
    const idMatches = inSection.filter(
      (patch) =>
        patch.sub_entry_id === fix.entry_id &&
        isUsableAfterText(patch.replacement_text ?? "")
    );
    if (idMatches.length) {
      return (
        idMatches.find((patch) => patch.original_text?.trim()) ?? idMatches[0]
      );
    }
    // No id-match (e.g. old session data where sub_entry_id was not set).
    // If sub_label is also absent there is nothing safe to fall back on.
    if (!fix.sub_label?.trim()) {
      return undefined;
    }
    // Fall through to sub_label matching below.
  }
  if (fix.sub_label) {
    const subMatches = inSection.filter(
      (patch) =>
        labelsMatch(fix.sub_label ?? "", patch.sub_entry_label ?? "") &&
        isUsableAfterText(patch.replacement_text ?? "")
    );
    if (subMatches.length) {
      return (
        subMatches.find((patch) => patch.original_text?.trim()) ?? subMatches[0]
      );
    }
    return undefined;
  }
  const sectionWide = inSection.filter((patch) => !patch.sub_entry_label?.trim());
  const pool = sectionWide.length ? sectionWide : inSection;
  return (
    pool.find(
      (patch) =>
        patch.original_text?.trim() && isUsableAfterText(patch.replacement_text ?? "")
    ) ?? pool.find((patch) => patch.original_text?.trim()) ?? pool[0]
  );
}

export function getBeforeTextForFix(
  analysisResult: AnalysisResult,
  fix: PriorityFix
): string {
  const key = inferSectionKey(fix.section);
  const fullText =
    analysisResult.resume.resume_sections?.[key]?.full_text?.trim() ?? "";
  const subEntries =
    analysisResult.resume.resume_sections?.[key]?.sub_entries ?? [];

  if (fix.entry_id && subEntries.length) {
    const byId = subEntries.find((entry) => entry.entry_id === fix.entry_id);
    if (byId?.verbatim_text) {
      return byId.verbatim_text.trim();
    }
  }

  if (fix.sub_label && fullText) {
    const match = subEntries.find(
      (entry) =>
        entry.label &&
        fix.sub_label &&
        subEntryLabelMatches(entry.label, fix.sub_label)
    );
    if (match?.verbatim_text) {
      return match.verbatim_text.trim();
    }
  }

  return fullText || "[Original text from your resume]";
}

const isExperienceRoleHeaderLine = (line: string): boolean => {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("•") || trimmed.startsWith("-")) {
    return false;
  }
  if (/^tech\s+stack:/i.test(trimmed)) {
    return false;
  }
  return /[|—–-]/.test(trimmed) && /^[A-Z]/.test(trimmed);
};

const isForeignRoleHeader = (line: string, companyToken: string): boolean => {
  if (!isExperienceRoleHeaderLine(line)) {
    return false;
  }
  if (line.toLowerCase().includes(companyToken)) {
    return false;
  }
  const lineCo = extractCompanyTokenFromLabel(line);
  return (
    lineCo.length >= 3 &&
    !lineCo.includes(companyToken) &&
    !companyToken.includes(lineCo)
  );
};

const patchMatchesFixScope = (fix: PriorityFix, patch: ResumePatch): boolean => {
  if (fix.entry_id?.trim() && patch.sub_entry_id?.trim()) {
    return patch.sub_entry_id === fix.entry_id;
  }
  if (fix.sub_label?.trim() && patch.sub_entry_label?.trim()) {
    return labelsMatch(fix.sub_label, patch.sub_entry_label);
  }
  return true;
};

export function extractSubEntryFromRewrite(
  rewriteText: string,
  subLabel: string
): string {
  const companyToken = extractCompanyTokenFromLabel(subLabel);
  if (!companyToken || companyToken.length < 2) {
    return "";
  }
  const lines = rewriteText.split("\n");
  let startIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toLowerCase().includes(companyToken)) {
      startIdx = i;
      break;
    }
  }
  if (startIdx < 0) {
    return "";
  }
  const block: string[] = [];
  for (let i = startIdx; i < lines.length; i++) {
    const trimmed = lines[i].trim();

    if (i > startIdx && /##COMPANY##/.test(lines[i])) {
      break;
    }

    if (i > startIdx && isForeignRoleHeader(lines[i], companyToken)) {
      break;
    }

    if (i > startIdx && block.length >= 2 && trimmed === "") {
      break;
    }
    block.push(lines[i]);
  }
  return stripRewriteMarkers(block.join("\n"));
}

export function getAfterTextForFix(
  analysisResult: AnalysisResult,
  fix: PriorityFix,
  patch?: ResumePatch
): string {
  const key = inferSectionKey(fix.section);
  const resolvedPatch =
    patch ?? resolvePatchForFix(fix, analysisResult.patches, key);

  if (
    resolvedPatch?.replacement_text &&
    resolvedPatch.original_text &&
    patchMatchesFixScope(fix, resolvedPatch)
  ) {
    if (isUsableAfterText(resolvedPatch.replacement_text)) {
      const base =
        analysisResult.resume.resume_sections?.[key]?.full_text?.trim() ?? "";
      const idx = base.indexOf(resolvedPatch.original_text);
      if (idx !== -1) {
        return (
          base.slice(0, idx) +
          resolvedPatch.replacement_text +
          base.slice(idx + resolvedPatch.original_text.length)
        );
      }
      return resolvedPatch.replacement_text;
    }
  }

  if (
    resolvedPatch?.replacement_text &&
    fix.sub_label &&
    labelsMatch(fix.sub_label, resolvedPatch.sub_entry_label ?? "") &&
    isUsableAfterText(resolvedPatch.replacement_text)
  ) {
    return resolvedPatch.replacement_text;
  }

  // Sub-entry fix (has entry_id or sub_label) → extract only that company's block from
  // the rewrite text. Never fall through to the full section rewrite: that would return
  // Flipkart's content (the first entry) for every company that lacks a patch.
  const isSubEntryFix = Boolean(fix.entry_id?.trim() || fix.sub_label?.trim());
  if (isSubEntryFix) {
    const rewriteBlock = analysisResult.rewrites?.[key]?.balanced;
    if (typeof rewriteBlock === "string" && rewriteBlock.trim()) {
      if (fix.sub_label) {
        const excerpt = extractSubEntryFromRewrite(rewriteBlock, fix.sub_label);
        if (excerpt.trim()) {
          return excerpt;
        }
      }
      if (fix.entry_id) {
        const companySlug = fix.entry_id.split("_")[0] ?? "";
        if (companySlug.length >= 3) {
          const excerpt = extractSubEntryFromRewrite(rewriteBlock, companySlug);
          if (excerpt.trim()) {
            return excerpt;
          }
        }
      }
    }
    return "";
  }

  // Section-level fix (no entry_id, no sub_label) — return the full rewrite block.
  const rewriteBlock = analysisResult.rewrites?.[key]?.balanced;
  if (typeof rewriteBlock === "string" && rewriteBlock.trim()) {
    return rewriteBlock
      .replace(COMPANY_HEADER_RE, "")
      .replace(STRAY_MARKER_RE, "")
      .trim();
  }

  // Phase 2: if fix has suggested_text from auto-suggestion, use it.
  if (fix.suggested_text?.trim()) {
    return fix.suggested_text;
  }

  return "";
}

export function parseInfoOnlyCardParts(gapReason: string): {
  wherePart: string | null;
  whatPart: string;
} {
  if (gapReason.includes("→")) {
    const [wherePart, whatPart] = gapReason.split("→", 2).map((s) => s.trim());
    return { wherePart, whatPart };
  }
  return { wherePart: null, whatPart: gapReason.trim() };
}

export function deriveInfoOnlyScopeLabel(fix: PriorityFix): string | null {
  const { wherePart } = parseInfoOnlyCardParts(fix.gap_reason);
  return fix.sub_label ?? wherePart;
}

export function isTabRoleFitLocked(
  tabId: TabId,
  fitness: AnalysisResult["role_fit"] | null | undefined,
  applyAnywayAccepted = false
): boolean {
  if (applyAnywayAccepted) {
    return false;
  }
  return fitness?.fitness === "underqualified" && ROLE_FIT_LOCKED_TABS.has(tabId);
}

export function shouldRenderStructuralApplyButton(
  _fix: PriorityFix,
  afterText: string,
  patchDiff: { original: string; replacement: string } | null
): boolean {
  return !structuralCardHasNoData(afterText, patchDiff);
}

/** Structural cards with no patch/rewrite data would render useless "Manual edit" labels. */
export function wouldRenderAsManualEdit(
  fix: PriorityFix,
  analysisResult: AnalysisResult
): boolean {
  const gapType = fix.gap_type ?? "structural";
  if (gapType !== "structural") {
    return false;
  }
  if (isEvidenceGap(fix)) {
    return false;
  }
  const sectionKey = inferSectionKey(fix.section);
  const patch = resolvePatchForFix(fix, analysisResult.patches, sectionKey);
  const after = getAfterTextForFix(analysisResult, fix, patch);
  return structuralCardHasNoData(after, null);
}

const demoteIdenticalInstructionFix = (fix: PriorityFix): PriorityFix => {
  const reason = (fix.gap_reason ?? "").trim();
  const instruction = (fix.rewrite_instruction ?? "").trim();
  if (!reason || reason.toLowerCase() !== instruction.toLowerCase()) {
    return fix;
  }
  if (fix.gap_type === "evidence" && fix.coaching_question) {
    return fix;
  }
  const coaching = buildCoachingQuestion(reason);
  return {
    ...fix,
    gap_type: "evidence",
    requires_user_input: true,
    coaching_question: coaching.question,
    coaching_hint: coaching.hints,
    auto_apply: false,
  };
};

const resolveFixForManualEdit = (
  fix: PriorityFix,
  analysisResult: AnalysisResult
): PriorityFix | null => {
  const updated = demoteIdenticalInstructionFix(fix);
  if (!wouldRenderAsManualEdit(updated, analysisResult)) {
    return updated;
  }
  const reason = updated.gap_reason ?? "";
  if (inferEvidenceFromText(reason)) {
    const coaching = buildCoachingQuestion(reason);
    return {
      ...updated,
      gap_type: "evidence",
      requires_user_input: true,
      coaching_question: coaching.question,
      coaching_hint: coaching.hints,
      auto_apply: false,
    };
  }
  return updated;
};

export function buildActionableFixesList(
  analysisResult: AnalysisResult | null,
  options: { suppressedEvidenceGaps?: boolean } = {}
): PriorityFix[] {
  if (!analysisResult?.gap) return [];

  const fromPriority = normalizePriorityFixes(
    analysisResult.gap.priority_fixes as Array<string | PriorityFix>
  ).filter(isActionableFix);
  const fromPatches = fixesFromPatches(analysisResult.patches).filter(isActionableFix);

  let list = mergeFixLists(fixLocationKey, fromPriority, fromPatches);

  // Drop sub-entry fix cards whose gap_reason explicitly names a DIFFERENT company.
  // Evidence/coaching cards (no patch, no rewrite) must pass through — they rely on user input.
  list = list.filter((fix) => {
    if (!fix.sub_label?.trim() && !fix.entry_id?.trim()) {
      return true;
    }
    return gapReasonMatchesFixScope(fix);
  });

  // Overview weaknesses/improvement_areas → one fix card each (JD + resume-only).
  list = mergeFixLists(
    fixLocationKey,
    list,
    fixesMissingFromOverview(list, analysisResult)
  );

  list = list
    .map((fix) => resolveFixForManualEdit(fix, analysisResult))
    .filter((fix): fix is PriorityFix => fix !== null);

  if (options.suppressedEvidenceGaps) {
    list = list.filter((f) => !isEvidenceGap(f));
  }

  const sorted = [...list].sort((a, b) => {
    const orderA = GAP_TYPE_ORDER[a.gap_type ?? "structural"];
    const orderB = GAP_TYPE_ORDER[b.gap_type ?? "structural"];
    return orderA - orderB;
  });

  // Deduplicate coaching cards by coaching_question — same question across different
  // companies renders identically. Includes both gap_type:"evidence" and
  // requires_user_input:true structural cards (both render as EvidenceCoachingCard).
  const seenCoachingQuestions = new Set<string>();
  return sorted.filter((fix) => {
    if (!isCoachingCard(fix)) return true;
    const q = (fix.coaching_question ?? fix.gap_reason ?? "").trim().toLowerCase();
    if (!q) return true;
    if (seenCoachingQuestions.has(q)) return false;
    seenCoachingQuestions.add(q);
    return true;
  });
}

/**
 * A fix renders as EvidenceCoachingCard when gap_type is "evidence" OR when
 * requires_user_input is true (structural cards with no patch data also land here).
 * This mirrors the renderCard() dispatch logic in ActionableFixes.
 */
function isCoachingCard(fix: PriorityFix): boolean {
  return fix.gap_type === "evidence" || fix.requires_user_input === true;
}

/**
 * Splits a flat fix list into visible (up to MAX_COACHING_CARDS coaching cards + all
 * non-coaching) and hidden (excess coaching cards). Used by ActionableFixes to enforce
 * the coaching card cap without losing gap data.
 */
export function partitionFixesByCoachingCap(
  fixes: PriorityFix[]
): { visible: PriorityFix[]; hidden: PriorityFix[] } {
  let coachingCount = 0;
  const visible: PriorityFix[] = [];
  const hidden: PriorityFix[] = [];

  for (const fix of fixes) {
    if (isCoachingCard(fix)) {
      if (coachingCount < MAX_COACHING_CARDS) {
        visible.push(fix);
        coachingCount++;
      } else {
        hidden.push(fix);
      }
    } else {
      visible.push(fix);
    }
  }

  return { visible, hidden };
}

export function companyMarkersForEntryId(entryId: string): string[] {
  const firstToken = entryId.split("_")[0]?.replace(/_/g, " ") ?? entryId;
  return [firstToken];
}

export function foreignCompanyMentioned(
  text: string,
  ownEntryId: string,
  peerEntryIds: string[] = []
): string | null {
  const lower = text.toLowerCase();
  for (const entryId of peerEntryIds) {
    if (!entryId || entryId === ownEntryId) {
      continue;
    }
    for (const marker of companyMarkersForEntryId(entryId)) {
      if (marker.length >= 4 && lower.includes(marker)) {
        return marker;
      }
    }
  }
  return null;
}

/** Tab badge and list use the same pipeline so counts stay aligned. */
export function countActionableFixes(
  analysisResult: AnalysisResult | null,
  options: { suppressedEvidenceGaps?: boolean } = {}
): number {
  return buildActionableFixesList(analysisResult, options).length;
}

export { MAX_COACHING_CARDS, GAP_TYPE_ORDER };
