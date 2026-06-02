import type { GapType, PriorityFix } from "../types";

const NO_CHANGE_REPLACEMENT_PHRASES = [
  "no change",
  "no changes",
  "not required",
  "not needed",
  "sufficient",
  "looks good",
  "well-optimised",
  "well optimized",
  "original entry contains",
  "no rewrite needed",
] as const;

/** True when LLM patch/rewrite text is a refusal, not actionable replacement. */
export function isNoChangeReplacement(text: string): boolean {
  const lower = text.toLowerCase().trim();
  return NO_CHANGE_REPLACEMENT_PHRASES.some((phrase) => lower.includes(phrase));
}

/** Company token from A1 ("Role | Co — Loc") or LLM ("Co — Role") labels. */
export function extractCompanyTokenFromLabel(label: string): string {
  const lower = label.toLowerCase().trim();
  if (!lower) {
    return "";
  }
  return lower.includes("|")
    ? (lower.split("|")[1] ?? lower).split("—")[0].trim()
    : lower.split("—")[0].trim();
}

/** Leading company name in A3-style gap_reason ("Flipkart EM bullets …"). */
export function companyTokenFromGapReason(gapReason: string): string {
  const head = gapReason.split("→")[0]?.trim() ?? "";
  if (!head) {
    return "";
  }
  const roleLead = head.match(
    /^([A-Z][a-zA-Z0-9]+)\s+(?:EM|Senior|Lead|Engineer|Consultant|Director|Manager|bullets|role)\b/i
  );
  if (roleLead) {
    return roleLead[1].toLowerCase();
  }
  const firstWord = head.match(/^([A-Z][a-zA-Z0-9]{2,})/);
  return firstWord ? firstWord[1].toLowerCase() : "";
}

/** Company scope for a fix card from entry_id slug or sub_label. */
export function fixScopeCompanyToken(fix: {
  entry_id?: string | null;
  sub_label?: string | null;
}): string {
  const fromId = fix.entry_id?.split("_")[0]?.replace(/_/g, " ").trim() ?? "";
  if (fromId.length >= 3) {
    return fromId.toLowerCase();
  }
  return extractCompanyTokenFromLabel(fix.sub_label ?? "");
}

/**
 * True when gap_reason targets the same company as the fix's sub_label / entry_id.
 * Prevents one company's gap from rendering on every experience card.
 */
export function gapReasonMatchesFixScope(fix: {
  gap_reason?: string;
  entry_id?: string | null;
  sub_label?: string | null;
}): boolean {
  const reasonCo = companyTokenFromGapReason(fix.gap_reason ?? "");
  if (!reasonCo || reasonCo.length < 3) {
    return true;
  }
  const fixCo = fixScopeCompanyToken(fix);
  if (!fixCo || fixCo.length < 3) {
    return true;
  }
  return fixCo.includes(reasonCo) || reasonCo.includes(fixCo);
}

/** Match fix sub_label to resume sub_entry label by company, not shared role title. */
export function subEntryLabelMatches(entryLabel: string, subLabel: string): boolean {
  if (entryLabel === subLabel) {
    return true;
  }
  const entryCompanyToken = extractCompanyTokenFromLabel(entryLabel);
  const subCompanyToken = extractCompanyTokenFromLabel(subLabel);
  return (
    (subCompanyToken.length >= 4 && entryCompanyToken.includes(subCompanyToken)) ||
    (entryCompanyToken.length >= 4 && subCompanyToken.includes(entryCompanyToken))
  );
}

/**
 * Stable dedupe key token from any sub_label format.
 * Collapses A1 ("Role | Flipkart — Loc Date") and LLM ("Flipkart — EM (date)") labels.
 */
export function normalizeSubLabelKey(subLabel: string): string {
  if (!subLabel.trim()) {
    return "__section__";
  }
  const token = extractCompanyTokenFromLabel(subLabel);
  const cleaned = token
    .replace(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b.*/i, "")
    .replace(/\b\d{4}\b.*/, "")
    .replace(/\([^)]*\).*/, "")
    .replace(/\b(bengaluru|bangalore|mumbai|delhi|hyderabad|pune|ka|mh|tn|dl)\b.*/, "")
    .trim();
  return cleaned || token || subLabel.toLowerCase().trim();
}

export function buildFixLocationKey(
  sectionKey: string,
  subLabel?: string | null,
  entryId?: string | null
): string {
  if (entryId?.trim()) {
    return `${sectionKey}|${entryId.trim()}`;
  }
  return `${sectionKey}|${normalizeSubLabelKey(subLabel ?? "")}`;
}

/** Fuzzy dedupe when normalized keys differ but company tokens subsume each other. */
export function findFuzzyFixLocationKey(
  incomingKey: string,
  existingKeys: string[]
): string | undefined {
  const pipeIdx = incomingKey.indexOf("|");
  if (pipeIdx < 0) {
    return undefined;
  }
  const sectionPrefix = `${incomingKey.slice(0, pipeIdx)}|`;
  const incomingToken = incomingKey.slice(pipeIdx + 1);

  return existingKeys.find((existingKey) => {
    if (!existingKey.startsWith(sectionPrefix) || existingKey === incomingKey) {
      return false;
    }
    const existingToken = existingKey.slice(sectionPrefix.length);
    if (existingToken === "__section__" || incomingToken === "__section__") {
      return false;
    }
    return (
      existingToken.length >= 4 &&
      incomingToken.length >= 4 &&
      (existingToken.includes(incomingToken) || incomingToken.includes(existingToken))
    );
  });
}

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

export function mergeFixLists(
  getLocationKey: (fix: PriorityFix) => string,
  ...lists: PriorityFix[][]
): PriorityFix[] {
  const mergedMap = new Map<string, PriorityFix>();
  const order: string[] = [];
  for (const list of lists) {
    for (const fix of list) {
      const key = getLocationKey(fix);
      if (mergedMap.has(key)) {
        mergedMap.set(key, mergePriorityFix(mergedMap.get(key)!, fix));
        continue;
      }
      const fuzzyMatch = findFuzzyFixLocationKey(key, order);
      if (fuzzyMatch) {
        mergedMap.set(fuzzyMatch, mergePriorityFix(mergedMap.get(fuzzyMatch)!, fix));
        continue;
      }
      mergedMap.set(key, fix);
      order.push(key);
    }
  }
  return order.map((key) => mergedMap.get(key)!);
}

export function resolveSubChangeGapReason(
  sub: {
    gap_reason?: string;
    rewrite_instruction?: string;
    sub_label?: string;
  },
  sectionGapReason: string
): string {
  return (
    sub.gap_reason ??
    sub.rewrite_instruction ??
    (sub.sub_label ? "Review and strengthen this entry" : sectionGapReason)
  );
}

export function deriveExampleHint(gapReason: string): string {
  const lower = gapReason.toLowerCase();
  if (lower.includes("quantified") || lower.includes("metric") || lower.includes("revenue")) {
    return '"Reduced deployment time by 40%" or "Grew user base from 10K to 85K in 6 months"';
  }
  if (lower.includes("technology") || lower.includes("tech stack") || lower.includes("specific tech")) {
    return '"Built using React, Node.js, and PostgreSQL deployed on AWS ECS"';
  }
  if (lower.includes("leadership") || lower.includes("mentorship")) {
    return '"Mentored 4 junior engineers; 2 promoted to senior within 18 months"';
  }
  if (lower.includes("architectural") || lower.includes("decision")) {
    return '"Chose event-driven architecture over REST polling to reduce latency by 60ms"';
  }
  if (lower.includes("cross-team") || lower.includes("collaboration")) {
    return '"Partnered with Data and Product to ship ML-based recommendation feature in Q3"';
  }
  if (lower.includes("narrative") || lower.includes("growth") || lower.includes("consistent")) {
    return "Connect each role with a progression thread: scope, team size, or ownership growth";
  }
  return "";
}

export function isUsableAfterText(text: string): boolean {
  const trimmed = text.trim();
  return Boolean(trimmed) && !isNoChangeReplacement(trimmed);
}

export function structuralCardHasNoData(
  afterText: string,
  patchDiff: { original: string; replacement: string } | null
): boolean {
  if (isUsableAfterText(afterText)) {
    return false;
  }
  if (patchDiff && !isNoChangeReplacement(patchDiff.replacement)) {
    return false;
  }
  return true;
}
