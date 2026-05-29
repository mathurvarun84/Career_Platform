import type { AnalysisResult, GapType, PriorityFix } from "../types";
import { hasJobDescription } from "./hasJobDescription";

const canonicalSections = [
  "summary",
  "skills",
  "experience",
  "education",
  "certifications",
  "awards",
  "projects",
] as const;

const inferSectionKey = (value: string): string => {
  const lower = value.toLowerCase();
  if (canonicalSections.includes(lower as (typeof canonicalSections)[number])) {
    return lower;
  }
  if (lower.includes("summary")) return "summary";
  if (lower.includes("skill") || lower.includes("keyword")) return "skills";
  if (lower.includes("experience") || lower.includes("bullet") || lower.includes("role")) {
    return "experience";
  }
  if (lower.includes("education")) return "education";
  if (lower.includes("certification")) return "certifications";
  if (lower.includes("award")) return "awards";
  if (lower.includes("project")) return "projects";
  return "experience";
};

const compact = (text: string): string => text.toLowerCase().replace(/[^a-z0-9]/g, "");

/** Company/role head from A1 weakness format: "Flipkart EM bullets …" */
export const extractCompanyFromWeakness = (weakness: string): string => {
  const head = weakness.split("→")[0]?.trim() ?? weakness;
  const match = head.match(
    /^([A-Za-z][A-Za-z0-9\s.&-]{1,48}?)(?:\s+(?:EM|role|bullets|bullet|section|lacks|lack|missing|needs))/i
  );
  if (match?.[1]) {
    return match[1].trim();
  }
  const words = head.split(/\s+/).filter(Boolean);
  return words.slice(0, Math.min(3, words.length)).join(" ");
};

const labelMatchesCompany = (label: string, company: string): boolean => {
  const labelLower = label.toLowerCase();
  const companyLower = company.toLowerCase().trim();
  if (!companyLower || companyLower.length < 2) {
    return false;
  }
  if (labelLower.includes(companyLower)) {
    return true;
  }
  const firstWord = companyLower.split(/\s+/)[0] ?? "";
  if (firstWord.length > 2 && labelLower.includes(firstWord)) {
    return true;
  }
  return compact(label).includes(compact(company)) || compact(company).includes(compact(label));
};

export const resolveSubLabelForWeakness = (
  weakness: string,
  analysisResult: AnalysisResult
): string | null => {
  const company = extractCompanyFromWeakness(weakness);
  const section = inferSectionKey(weakness.split("→")[0] ?? weakness);
  const entries = analysisResult.resume?.resume_sections?.[section]?.sub_entries ?? [];
  for (const entry of entries) {
    if (entry.label && labelMatchesCompany(entry.label, company)) {
      return entry.label;
    }
  }
  if (company) {
    return company;
  }
  return null;
};

export const weaknessCoveredByFix = (weakness: string, fix: PriorityFix): boolean => {
  const w = weakness.toLowerCase().trim();
  const reason = (fix.gap_reason ?? "").toLowerCase().trim();
  const instruction = (fix.rewrite_instruction ?? "").toLowerCase().trim();
  if (!w) {
    return false;
  }
  if (reason === w || instruction === w) {
    return true;
  }
  const wHead = w.slice(0, 55);
  if (reason.includes(wHead) || w.includes(reason.slice(0, 55))) {
    return true;
  }
  const company = extractCompanyFromWeakness(weakness).toLowerCase();
  if (company.length > 2) {
    if (reason.includes(company) || instruction.includes(company)) {
      return true;
    }
    if ((fix.sub_label ?? "").toLowerCase().includes(company.split(/\s+/)[0] ?? "")) {
      return true;
    }
  }
  return false;
};

export const collectOverviewWeaknessSources = (
  analysisResult: AnalysisResult
): string[] => {
  return [
    ...(analysisResult.resume?.weaknesses ?? []),
    ...(analysisResult.resume?.improvement_areas ?? []),
  ].filter(Boolean);
};

export const buildOverviewWeaknessFix = (
  weakness: string,
  analysisResult: AnalysisResult
): PriorityFix => {
  const parts = weakness.split("→");
  const gapReason = (parts[0] ?? weakness).trim();
  const rewriteInstruction = (parts[1] ?? parts[0] ?? weakness).trim();
  const resumeOnly = analysisResult.gap?.resume_only_mode === true;
  const section = inferSectionKey(gapReason);
  const sub_label = resolveSubLabelForWeakness(weakness, analysisResult);
  const gapType: GapType = resumeOnly ? "structural" : "evidence";
  const isCoaching = !resumeOnly && gapType === "evidence";

  return {
    section,
    gap_reason: gapReason,
    rewrite_instruction: rewriteInstruction,
    missing_keywords: [],
    needs_change: true,
    gap_type: gapType,
    requires_user_input: isCoaching,
    coaching_question: isCoaching
      ? `How would you address: ${gapReason}?`
      : undefined,
    coaching_hint: isCoaching ? [rewriteInstruction] : undefined,
    auto_apply: false,
    sub_label,
  };
};

export const fixesMissingFromOverview = (
  list: PriorityFix[],
  analysisResult: AnalysisResult
): PriorityFix[] => {
  if (hasJobDescription(analysisResult.gap)) {
    return [];
  }
  const sources = collectOverviewWeaknessSources(analysisResult);
  const unique = Array.from(new Set(sources));
  return unique
    .filter((w) => !list.some((fix) => weaknessCoveredByFix(w, fix)))
    .map((w) => buildOverviewWeaknessFix(w, analysisResult));
};
