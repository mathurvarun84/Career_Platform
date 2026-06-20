import { T } from "../../tokens";
import type { ScoreJourneyResult } from "../../types";

interface ProgressSummaryProps {
  journey: ScoreJourneyResult;
}

type DeltaTone = "positive" | "negative" | "neutral";

function DeltaBadge({ tone, label }: { tone: DeltaTone; label: string }) {
  const styles: Record<DeltaTone, { background: string; color: string }> = {
    positive: { background: T.emeraldLight, color: T.emerald },
    negative: { background: T.roseLight, color: T.rose },
    neutral: { background: T.bgSubtle, color: T.textMuted },
  };

  return (
    <span
      style={{
        ...styles[tone],
        borderRadius: "6px",
        padding: "2px 8px",
        fontSize: "12px",
        fontWeight: 700,
      }}
    >
      {label}
    </span>
  );
}

function Row({
  label,
  values,
  badge,
}: {
  label: string;
  values: string;
  badge: { tone: DeltaTone; label: string };
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 0",
        borderBottom: `1px solid ${T.border}`,
      }}
    >
      <div style={{ fontSize: "13px", color: T.textMuted }}>{label}</div>
      <div style={{ fontSize: "13px", color: T.textPrimary, fontWeight: 600 }}>{values}</div>
      <DeltaBadge tone={badge.tone} label={badge.label} />
    </div>
  );
}

export default function ProgressSummary({ journey }: ProgressSummaryProps) {
  const {
    first_score,
    latest_score,
    score_delta,
    first_tier,
    latest_tier,
    first_ctc_min,
    latest_ctc_min,
    ctc_delta_min,
    sessions,
  } = journey;

  const firstPercentile = sessions[0]?.percentile_label ?? "—";
  const latestPercentile = sessions[sessions.length - 1]?.percentile_label ?? "—";
  const firstTierLabel = sessions[0]?.current_tier_label ?? first_tier ?? "—";
  const latestTierLabel =
    sessions[sessions.length - 1]?.current_tier_label ?? latest_tier ?? "—";

  const percentileOrder = ["Bottom 25%", "Below Average", "Above Average", "Top 25%", "Top 10%"];
  const percentileDelta: DeltaTone =
    percentileOrder.indexOf(latestPercentile) > percentileOrder.indexOf(firstPercentile)
      ? "positive"
      : percentileOrder.indexOf(latestPercentile) < percentileOrder.indexOf(firstPercentile)
        ? "negative"
        : "neutral";
  const percentileLabel =
    percentileDelta === "positive" ? "↑ improved" : percentileDelta === "negative" ? "↓ dropped" : "–";

  return (
    <div
      style={{
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: "16px",
        padding: "24px",
      }}
    >
      <Row
        label="Composite score"
        values={`${first_score} → ${latest_score}`}
        badge={{
          tone: score_delta > 0 ? "positive" : score_delta < 0 ? "negative" : "neutral",
          label: `${score_delta > 0 ? "+" : ""}${score_delta} pts`,
        }}
      />
      <Row
        label="Percentile"
        values={`${firstPercentile} → ${latestPercentile}`}
        badge={{ tone: percentileDelta, label: percentileLabel }}
      />
      {first_tier !== latest_tier && (
        <Row
          label="Market tier"
          values={`${firstTierLabel} → ${latestTierLabel}`}
          badge={{ tone: "positive", label: "↑ improved" }}
        />
      )}
      {ctc_delta_min !== null && ctc_delta_min !== 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 0",
          }}
        >
          <div style={{ fontSize: "13px", color: T.textMuted }}>Salary positioning</div>
          <div style={{ fontSize: "13px", color: T.textPrimary, fontWeight: 600 }}>
            {`₹${first_ctc_min}–${sessions[0]?.current_ctc_max ?? ""} LPA → ₹${latest_ctc_min}–${
              sessions[sessions.length - 1]?.current_ctc_max ?? ""
            } LPA`}
          </div>
          <DeltaBadge
            tone={ctc_delta_min > 0 ? "positive" : ctc_delta_min < 0 ? "negative" : "neutral"}
            label={ctc_delta_min > 0 ? `+₹${ctc_delta_min} LPA` : `-₹${Math.abs(ctc_delta_min)} LPA`}
          />
        </div>
      )}
    </div>
  );
}
