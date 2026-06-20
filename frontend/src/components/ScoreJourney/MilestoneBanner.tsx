import { T } from "../../tokens";
import type { MilestoneEvent } from "../../types";

interface MilestoneBannerProps {
  milestone: MilestoneEvent;
  onDismiss: () => void;
}

export default function MilestoneBanner({ milestone, onDismiss }: MilestoneBannerProps) {
  if (milestone.type === "first_analysis") {
    return null;
  }

  const icon = milestone.type === "tier_unlock" ? "🎯" : "✦";
  const title =
    milestone.type === "tier_unlock"
      ? `Tier Unlocked: ${milestone.to_value}`
      : "Percentile Milestone";
  const subtitle =
    milestone.type === "tier_unlock"
      ? `Your resume is now competitive for ${milestone.to_value} companies`
      : `You moved from ${milestone.from_value} to ${milestone.to_value}`;

  return (
    <div
      style={{
        background: T.gradientBrand,
        color: "#ffffff",
        borderRadius: "16px",
        padding: "20px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div style={{ fontSize: "24px" }}>{icon}</div>
        <div>
          <div style={{ fontFamily: "inherit", fontSize: "14px", fontWeight: 700, color: "#ffffff" }}>
            {title}
          </div>
          <div style={{ fontSize: "13px", color: "rgba(255,255,255,0.8)", marginTop: "4px" }}>
            {subtitle}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {/* "Share achievement" removed — Shareable Card deferred to Phase 3 per evaluator patch */}
        <button
          type="button"
          onClick={onDismiss}
          style={{
            background: "transparent",
            border: "none",
            color: "rgba(255,255,255,0.7)",
            fontSize: "18px",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          ×
        </button>
      </div>
    </div>
  );
}
