import { useResumeStore } from "../store/useResumeStore";
import { T } from "../tokens";

export default function UploadReturnBanner() {
  const scoreJourney = useResumeStore((state) => state.scoreJourney);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);

  if (!scoreJourney || scoreJourney.total_sessions < 2) {
    return null;
  }

  const { latest_score, first_score, total_sessions } = scoreJourney;
  const sessionsAgo = total_sessions - 1;

  return (
    <div
      style={{
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: "16px",
        padding: "16px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        maxWidth: 900,
        margin: "0 auto 24px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div style={{ fontSize: "18px", color: T.primary }}>↗</div>
        <div style={{ fontSize: "13px", color: T.textSecondary, fontFamily: "inherit" }}>
          Your last score:{" "}
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "16px",
              color: T.primary,
              fontWeight: 600,
            }}
          >
            {latest_score}
          </span>
          {" · Up from "}
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: "16px",
              color: T.primary,
              fontWeight: 600,
            }}
          >
            {first_score}
          </span>
          {` (${sessionsAgo} session${sessionsAgo === 1 ? "" : "s"} ago)`}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <button
          type="button"
          onClick={() => setActiveTab("score_journey")}
          style={{
            background: "transparent",
            border: "none",
            cursor: "pointer",
            fontFamily: "inherit",
            fontSize: "13px",
            fontWeight: 600,
            color: T.primary,
            textDecoration: "none",
          }}
        >
          View Score Journey →
        </button>
        <button
          type="button"
          style={{
            border: `1.5px solid ${T.border}`,
            borderRadius: "8px",
            padding: "8px 16px",
            fontSize: "13px",
            fontWeight: 600,
            color: T.textSecondary,
            background: "transparent",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Continue
        </button>
      </div>
    </div>
  );
}
