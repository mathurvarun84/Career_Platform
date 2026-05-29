import type { SessionSummary, InterviewProgressSnapshot, BehavioralDimension } from "../types";

const STORAGE_KEY = "rip_v2_interview_progress";

export function persistProgressSnapshot(
  summary: SessionSummary,
  company: string,
  seniority: string
): void {
  const SIGNAL_RANK: Record<string, number> = { weak: 0, developing: 1, strong: 2 };

  const scores = summary.dimension_scorecard.map((d) => SIGNAL_RANK[d.signal_strength] ?? 0);
  const average_signal_strength =
    scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;

  const snapshot: InterviewProgressSnapshot = {
    timestamp: new Date().toISOString(),
    company,
    seniority,
    dimensions_covered: summary.dimension_scorecard.map(
      (d) => d.dimension
    ) as BehavioralDimension[],
    average_signal_strength,
    anti_patterns_count: summary.anti_pattern_report.reduce((sum, ap) => sum + ap.count, 0),
  };

  const existing = readProgressSnapshots();
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...existing, snapshot]));
}

export function readProgressSnapshots(): InterviewProgressSnapshot[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as InterviewProgressSnapshot[]) : [];
  } catch {
    return [];
  }
}
