const EVIDENCE_SIGNALS = [
  "mentor",
  "coach",
  "1:1",
  "performance management",
  "promotion",
  "stakeholder",
  "executive",
  "p&l",
  "budget",
  "hiring decision",
  "org design",
  "succession",
  "board",
  "vision",
  "strategy",
] as const;

export function isEvidenceGap(fix: {
  gap_type?: string;
  requires_user_input?: boolean;
  gap_reason?: string;
}): boolean {
  if (fix.gap_type === "evidence") {
    return true;
  }
  if (fix.requires_user_input === true) {
    return true;
  }
  const reason = (fix.gap_reason ?? "").toLowerCase();
  return EVIDENCE_SIGNALS.some((sig) => reason.includes(sig));
}
