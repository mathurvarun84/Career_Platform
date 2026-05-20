/**
 * Deterministic ATS scorer — TypeScript port of engine/ats_scorer.py score_resume().
 * No LLM calls. Keep in sync with Python when scoring logic changes.
 */

import type { ATSBreakdown, ATSResult } from "../types";

const ACTION_VERBS = new Set([
  "led", "built", "designed", "reduced", "increased", "owned", "shipped", "scaled",
  "developed", "implemented", "architected", "optimized", "launched", "delivered",
  "managed", "created", "improved", "deployed", "migrated", "automated",
]);

const TECH_KEYWORDS = [
  "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby",
  "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
  "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
  "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
  "rest", "api", "grpc", "graphql", "microservices", "ci/cd", "devops",
  "machine learning", "ml", "deep learning", "nlp", "llm", "pytorch", "tensorflow",
  "git", "linux", "bash", "spark", "hadoop", "airflow", "dbt",
];

const SECTION_HEADERS = [
  "experience", "work experience", "employment", "education", "skills",
  "projects", "summary", "objective", "certifications", "achievements",
];

const LATENCY_RE =
  /\b(\d+\s*ms|\d+\s*seconds?|\d+\s*minutes?|p99|p95|p50|latency|throughput)\b/gi;
const SCALE_RE =
  /\b(\d+[kmb]\+?|\d+\s*(million|billion|thousand)|[kmb]\s*users?|tps|qps|rpm|rps)\b/gi;
const IMPACT_RE =
  /(\d+%|\$[\d,]+|₹[\d,]+|\d+[kmb]\b|\d+\s*(million|billion|thousand|crore))/gi;
const RUNON_WORD_RE = /\b[a-zA-Z]{22,}\b/g;
const WORD_RE = /\b\w+\b/g;
const BULLET_RE = /^[\s]*[•\-*]\s/gm;

function countSyllables(word: string): number {
  const cleaned = word.toLowerCase().replace(/[.,;:!?"'()-]/g, "");
  if (!cleaned) {
    return 1;
  }
  const vowels = "aeiouy";
  let count = 0;
  let prevVowel = false;
  for (const ch of cleaned) {
    const isVowel = vowels.includes(ch);
    if (isVowel && !prevVowel) {
      count += 1;
    }
    prevVowel = isVowel;
  }
  if (cleaned.endsWith("e") && count > 1) {
    count -= 1;
  }
  return Math.max(1, count);
}

function countRunonWords(resumeText: string): number {
  return (resumeText.match(RUNON_WORD_RE) ?? []).length;
}

function scoreKeywordMatch(resumeText: string, jdText?: string | null): number {
  const textLower = resumeText.toLowerCase();
  const words = new Set((textLower.match(WORD_RE) ?? []));
  const verbHits = [...ACTION_VERBS].filter((v) => words.has(v)).length;
  const techHits = TECH_KEYWORDS.filter((kw) => textLower.includes(kw)).length;

  let jdBoost = 0;
  if (jdText?.trim()) {
    const jdLower = jdText.toLowerCase();
    const jdWords = new Set(jdLower.match(WORD_RE) ?? []);
    let overlap = 0;
    for (const w of words) {
      if (jdWords.has(w)) {
        overlap += 1;
      }
    }
    jdBoost = Math.min(5, Math.floor((overlap / Math.max(jdWords.size, 1)) * 20));
  }

  const raw = verbHits * 1.5 + techHits * 0.8 + jdBoost;
  return Math.min(25, Math.floor(raw));
}

function scoreFormatting(resumeText: string): number {
  let score = 0;
  const textLower = resumeText.toLowerCase();
  const headersFound = SECTION_HEADERS.filter((h) => textLower.includes(h)).length;
  score += Math.min(10, headersFound * 2);

  const bulletLines = (resumeText.match(BULLET_RE) ?? []).length;
  if (bulletLines >= 5) {
    score += 8;
  } else if (bulletLines >= 2) {
    score += 4;
  }

  const wordCount = resumeText.split(/\s+/).filter(Boolean).length;
  if (wordCount >= 300 && wordCount <= 900) {
    score += 7;
  } else if (wordCount >= 200 && wordCount <= 1200) {
    score += 4;
  }

  return Math.min(25, score);
}

function scoreReadability(resumeText: string): number {
  const sentences = resumeText
    .split(/[.!?]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 10);
  if (sentences.length === 0) {
    return 10;
  }

  const wordCounts = sentences.map((s) => s.split(/\s+/).filter(Boolean).length);
  const totalWords = wordCounts.reduce((a, b) => a + b, 0);
  const totalSentences = sentences.length;
  const avgWords = totalWords / totalSentences;

  let totalSyllables = 0;
  for (const sentence of sentences) {
    for (const word of sentence.split(/\s+/).filter(Boolean)) {
      totalSyllables += countSyllables(word);
    }
  }

  if (totalWords === 0) {
    return 10;
  }

  const fk =
    206.835 -
    1.015 * (totalWords / totalSentences) -
    84.6 * (totalSyllables / totalWords);

  let score: number;
  if (fk >= 40 && fk <= 70) {
    score = 25;
  } else if ((fk >= 30 && fk < 40) || (fk > 70 && fk <= 80)) {
    score = 18;
  } else if ((fk >= 20 && fk < 30) || (fk > 80 && fk <= 90)) {
    score = 12;
  } else {
    score = 6;
  }

  if (avgWords > 30) {
    score = Math.max(0, score - 5);
  }

  const runon = countRunonWords(resumeText);
  if (runon >= 3) {
    score = Math.max(0, score - 10);
  } else if (runon >= 1) {
    score = Math.max(0, score - 5);
  }

  return Math.min(25, score);
}

function scoreImpactMetrics(resumeText: string): number {
  let score = 0;
  const impactHits = (resumeText.match(IMPACT_RE) ?? []).length;
  score += Math.min(12, impactHits * 2);
  const latencyHits = (resumeText.match(LATENCY_RE) ?? []).length;
  score += Math.min(7, latencyHits * 2);
  const scaleHits = (resumeText.match(SCALE_RE) ?? []).length;
  score += Math.min(6, scaleHits * 2);
  return Math.min(25, score);
}

function collectIssues(resumeText: string, breakdown: ATSBreakdown): string[] {
  const issues: string[] = [];
  const textLower = resumeText.toLowerCase();

  if (breakdown.keyword_match < 10) {
    issues.push(
      "Low action verb and tech keyword density — add measurable achievements with strong verbs."
    );
  }

  const headersFound = SECTION_HEADERS.filter((h) => textLower.includes(h)).length;
  if (headersFound < 2) {
    issues.push("Missing standard section headers (Experience, Education, Skills).");
  }

  const bulletLines = (resumeText.match(BULLET_RE) ?? []).length;
  if (bulletLines < 3) {
    issues.push("Insufficient bullet points — use consistent bullets for achievements.");
  }

  const wordCount = resumeText.split(/\s+/).filter(Boolean).length;
  if (wordCount < 200) {
    issues.push(`Resume is too short (${wordCount} words) — aim for 300–900 words.`);
  } else if (wordCount > 1200) {
    issues.push(`Resume may be too long (${wordCount} words) — aim for 1–2 pages.`);
  }

  if (breakdown.impact_metrics < 8) {
    issues.push("Few quantified achievements — add numbers, percentages, or scale metrics.");
  }

  if (breakdown.readability < 12) {
    issues.push("Readability needs improvement — use shorter, clearer sentences.");
  }

  if (countRunonWords(resumeText) >= 1) {
    issues.push(
      "PDF word-spacing issues detected — words are merged. Re-upload or re-parse the resume."
    );
  }

  return issues;
}

/** Score resume text deterministically (mirrors Python score_resume). */
export function scoreResume(
  resumeText: string,
  jdText?: string | null
): Pick<ATSResult, "score" | "breakdown" | "ats_issues"> {
  const breakdown: ATSBreakdown = {
    keyword_match: scoreKeywordMatch(resumeText, jdText),
    formatting: scoreFormatting(resumeText),
    readability: scoreReadability(resumeText),
    impact_metrics: scoreImpactMetrics(resumeText),
  };
  const score =
    breakdown.keyword_match +
    breakdown.formatting +
    breakdown.readability +
    breakdown.impact_metrics;
  const ats_issues = collectIssues(resumeText, breakdown);
  return { score, breakdown, ats_issues };
}
