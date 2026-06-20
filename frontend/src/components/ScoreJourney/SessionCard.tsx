import { T } from "../../tokens";
import type { SessionSnapshot } from "../../types";

interface SessionCardProps {
  session: SessionSnapshot;
  isLatest: boolean;
}

const formatDate = (iso: string): string => {
  const date = new Date(iso);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
};

export default function SessionCard({ session, isLatest }: SessionCardProps) {
  const hasCtc = session.current_ctc_min !== null && session.current_ctc_max !== null;

  return (
    <div
      style={{
        background: isLatest ? "#fafafd" : T.bgCard,
        border: `1.5px solid ${isLatest ? T.primary : T.border}`,
        borderRadius: "16px",
        padding: "20px",
        width: "min(180px, calc(50vw - 24px))",
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: "36px",
          fontWeight: 600,
          color: isLatest ? T.primary : T.textPrimary,
          lineHeight: 1,
        }}
      >
        {session.composite_score}
      </div>
      <div style={{ fontSize: "11px", color: T.textMuted }}>
        {formatDate(session.created_at)}
      </div>
      {session.current_tier_label && (
        <div
          style={{
            display: "inline-block",
            fontSize: "11px",
            fontWeight: 700,
            color: T.primary,
            background: T.primaryLight,
            borderRadius: "6px",
            padding: "2px 8px",
            width: "fit-content",
          }}
        >
          {session.current_tier_label}
        </div>
      )}
      {session.percentile_label && (
        <div style={{ fontSize: "12px", color: T.textSecondary }}>
          {session.percentile_label}
        </div>
      )}
      {hasCtc && (
        <div style={{ fontSize: "12px", color: T.textMuted }}>
          {`₹${session.current_ctc_min}–${session.current_ctc_max} LPA`}
        </div>
      )}
    </div>
  );
}
