import type { ResumeUnderstanding } from "../types";

const SECTION_ORDER = [
  "summary",
  "skills",
  "experience",
  "education",
  "certifications",
  "awards",
  "projects",
] as const;

/**
 * Build plain resume text from A1 sections, optionally overriding applied fixes.
 */
export function composeResumeText(
  resume: ResumeUnderstanding,
  sectionOverrides: Record<string, string> = {}
): string {
  const sections = resume.resume_sections ?? {};
  const parts: string[] = [];

  for (const key of SECTION_ORDER) {
    const override = sectionOverrides[key]?.trim();
    const original = sections[key]?.full_text?.trim() ?? "";
    const text = override || original;
    if (text) {
      parts.push(text);
    }
  }

  for (const [key, block] of Object.entries(sections)) {
    if ((SECTION_ORDER as readonly string[]).includes(key)) {
      continue;
    }
    const override = sectionOverrides[key]?.trim();
    const text = override || block?.full_text?.trim() || "";
    if (text) {
      parts.push(text);
    }
  }

  return parts.join("\n\n");
}
