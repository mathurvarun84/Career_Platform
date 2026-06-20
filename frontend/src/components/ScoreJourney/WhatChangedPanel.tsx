import { T } from "../../tokens";
import type { SessionSnapshot } from "../../types";

interface WhatChangedPanelProps {
  latest: SessionSnapshot;
  previous: SessionSnapshot;
  isPro?: boolean;
  onShowPaywall?: () => void;
}

const SUB_SCORES: Array<{ key: keyof SessionSnapshot; label: string }> = [
  { key: "ats_keyword_match", label: "ATS Keyword Match" },
  { key: "ats_formatting", label: "Formatting" },
  { key: "ats_readability", label: "Readability" },
  { key: "ats_impact_metrics", label: "Impact Metrics" },
];

export default function WhatChangedPanel({
  latest,
  previous,
  isPro = true,
  onShowPaywall,
}: WhatChangedPanelProps) {
  const rows = SUB_SCORES.filter(
    ({ key }) => latest[key] !== null || previous[key] !== null
  );

  if (rows.length === 0) {
    return null;
  }

  const panelContent = (
    <>
      <div style={{ fontSize: "13px", fontWeight: 700, color: T.textPrimary, marginBottom: "12px" }}>
        What Changed (latest vs previous session)
      </div>
      {rows.map(({ key, label }) => {
        const oldValue = (previous[key] as number | null) ?? 0;
        const newValue = (latest[key] as number | null) ?? 0;
        const delta = newValue - oldValue;
        return (
          <div
            key={key}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "8px 0",
            }}
          >
            <div style={{ fontSize: "13px", color: T.textSecondary }}>{label}</div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ fontSize: "13px", color: T.textPrimary, fontFamily: "'JetBrains Mono', monospace" }}>
                {oldValue} → {newValue}
              </div>
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: delta > 0 ? T.emerald : delta < 0 ? T.rose : T.textMuted,
                }}
              >
                {delta > 0 ? `+${delta}` : delta}
              </div>
            </div>
          </div>
        );
      })}
    </>
  );

  return (
    <div style={{ position: "relative" }}>
      <div
        style={{
          background: T.bgSubtle,
          borderRadius: "12px",
          padding: "20px",
          filter: isPro ? "none" : "blur(4px)",
          userSelect: isPro ? "auto" : "none",
        }}
      >
        {panelContent}
      </div>
      {!isPro && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(255,255,255,0.9)",
            backdropFilter: "blur(4px)",
            borderRadius: "12px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "14px", fontWeight: 700, color: T.textPrimary }}>
            🔒 Session diff is a Pro feature
          </div>
          <div style={{ fontSize: "13px", color: T.textSecondary }}>
            See exactly what changed between sessions — sub-score deltas, tier movement, and more.
          </div>
          <button
            type="button"
            onClick={onShowPaywall}
            style={{
              fontFamily: "inherit",
              background: T.primary,
              color: "#ffffff",
              borderRadius: "8px",
              padding: "10px 20px",
              border: "none",
              boxShadow: `0 4px 0 ${T.primaryFloor}`,
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: 700,
              marginTop: "4px",
            }}
          >
            Start 7-day free trial →
          </button>
        </div>
      )}
    </div>
  );
}
