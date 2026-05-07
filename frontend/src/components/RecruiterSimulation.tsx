import { useState } from "react";

import { useWindowSize } from "../hooks/useWindowSize";
import { useResumeStore } from "../store/useResumeStore";
import type { PersonaVerdict } from "../types";
import DataSourceNotice from "./DataSourceNotice";

const getBadgeStyle = (
  persona: string
): { bg: string; color: string; border: string } => {
  const p = persona.toLowerCase();
  if (p.includes("faang") || p.includes("maang")) {
    return { bg: "#eef2ff", color: "#4f46e5", border: "#c7d2fe" };
  }
  if (
    p.includes("startup") ||
    p.includes("cto") ||
    p.includes("series") ||
    p.includes("zepto") ||
    p.includes("blinkit") ||
    p.includes("d2c")
  ) {
    return { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" };
  }
  if (p.includes("agency") || p.includes("service") || p.includes("bench")) {
    return { bg: "#fff7ed", color: "#d97706", border: "#fed7aa" };
  }
  if (
    p.includes("fintech") ||
    p.includes("finance") ||
    p.includes("payment")
  ) {
    return { bg: "#fef2f2", color: "#dc2626", border: "#fecaca" };
  }
  if (
    p.includes("product") ||
    p.includes("edtech") ||
    p.includes("enterprise") ||
    p.includes("recruiter") ||
    p.includes("hr")
  ) {
    return { bg: "#f5f0ff", color: "#7c3aed", border: "#e9d5ff" };
  }
  return { bg: "#f3f4f6", color: "#374151", border: "#e5e7eb" };
};

const getShortlistColor = (
  rate: number
): { text: string; bg: string; border: string } => {
  if (rate >= 0.7) return { text: "#16a34a", bg: "#dcfce7", border: "#bbf7d0" };
  if (rate >= 0.4) return { text: "#d97706", bg: "#fff7ed", border: "#fed7aa" };
  return { text: "#dc2626", bg: "#fef2f2", border: "#fecaca" };
};

function PersonaCard({ persona }: { readonly persona: PersonaVerdict }) {
  const badge = getBadgeStyle(persona.persona);
  const isShortlisted = persona.shortlist_decision;

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: "16px",
        padding: "20px",
        boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "10px",
        }}
      >
        <div style={{ flex: 1 }}>
          <div
            style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}
          >
            {persona.persona}
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              background: badge.bg,
              border: `1px solid ${badge.border}`,
              color: badge.color,
              borderRadius: "999px",
              padding: "2px 10px",
              fontSize: "11px",
              fontWeight: 600,
              marginTop: "6px",
            }}
          >
            {persona.persona.split(" ").slice(-2).join(" ")}
          </div>
        </div>

        <div
          style={{
            background: isShortlisted ? "#dcfce7" : "#fef2f2",
            color: isShortlisted ? "#16a34a" : "#dc2626",
            borderRadius: "999px",
            padding: "4px 12px",
            fontSize: "12px",
            fontWeight: 700,
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {isShortlisted ? "✓ Shortlisted" : "✗ Not Shortlisted"}
        </div>
      </div>

      {/* Fit score */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{ fontSize: "12px", color: "#6b7280" }}>Fit Score</div>
        <div
          style={{
            fontSize: "13px",
            fontWeight: 700,
            color: persona.fit_score >= 70 ? "#16a34a" : persona.fit_score >= 50 ? "#d97706" : "#dc2626",
          }}
        >
          {persona.fit_score}/100
        </div>
        {/* Mini bar */}
        <div
          style={{
            flex: 1,
            height: "4px",
            background: "#f3f4f6",
            borderRadius: "999px",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${persona.fit_score}%`,
              height: "100%",
              background:
                persona.fit_score >= 70
                  ? "#16a34a"
                  : persona.fit_score >= 50
                    ? "#d97706"
                    : "#dc2626",
              borderRadius: "999px",
            }}
          />
        </div>
      </div>

      {/* First impression */}
      <div
        style={{
          fontSize: "13px",
          color: "#374151",
          fontStyle: "italic",
          lineHeight: 1.55,
        }}
      >
        "{persona.first_impression}"
      </div>

      {/* Noticed */}
      {persona.noticed.length > 0 && (
        <div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#374151",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "4px",
            }}
          >
            Noticed
          </div>
          {persona.noticed.map((item) => (
            <div
              key={item}
              style={{
                fontSize: "12px",
                color: "#16a34a",
                lineHeight: 1.6,
              }}
            >
              ✓ {item}
            </div>
          ))}
        </div>
      )}

      {/* Rejection reason */}
      {!isShortlisted && persona.rejection_reason && (
        <div
          style={{
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: "8px",
            padding: "10px 12px",
            fontSize: "12px",
            color: "#dc2626",
            lineHeight: 1.55,
          }}
        >
          <span style={{ fontWeight: 700 }}>Reason: </span>
          {persona.rejection_reason}
        </div>
      )}

      {/* Flip condition */}
      {persona.flip_condition && (
        <div
          style={{
            background: "#eef2ff",
            border: "1px solid #c7d2fe",
            borderRadius: "8px",
            padding: "10px 12px",
          }}
        >
          <div
            style={{
              fontSize: "11px",
              fontWeight: 700,
              color: "#4f46e5",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "4px",
            }}
          >
            What would change this
          </div>
          <div
            style={{ fontSize: "12px", color: "#374151", lineHeight: 1.55 }}
          >
            {persona.flip_condition}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RecruiterSimulation() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const setActiveTab = useResumeStore((s) => s.setActiveTab);
  const { isMobile } = useWindowSize();
  const [isViewFixPressed, setIsViewFixPressed] = useState(false);

  if (!analysisResult?.sim) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div style={{ maxWidth: "960px", margin: "0 auto", padding: "40px 32px 48px" }}>
          <div
            style={{
              textAlign: "center",
              padding: "64px 32px",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              background: "#ffffff",
            }}
          >
            <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚠️</div>
            <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827", marginBottom: "6px" }}>
              Data Unavailable
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280" }}>
              This analysis could not be completed. Try re-uploading your resume.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { sim, positioning } = analysisResult;
  const personas = sim.personas;
  const shortlistRate = Math.round(sim.shortlist_rate * 100);
  const avgFitScore = Math.round(
    personas.reduce((sum, p) => sum + p.fit_score, 0) / personas.length
  );
  const shortlistColors = getShortlistColor(sim.shortlist_rate);
  const nextTier = positioning?.next_tier_label ?? "the next tier";

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div
        style={{
          maxWidth: "960px",
          margin: "0 auto",
          padding: "40px 32px 48px",
        }}
      >
        {/* Hero Header */}
        <div style={{ marginBottom: "32px", textAlign: "center" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              borderRadius: "999px",
              background: "#f5f0ff",
              border: "1px solid #e9d5ff",
              color: "#7c3aed",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            👤 Recruiter Simulation
          </div>
          <div
            style={{
              fontSize: "28px",
              fontWeight: 800,
              color: "#111827",
              letterSpacing: "-0.02em",
              marginTop: "14px",
            }}
          >
            How Recruiters See Your Resume
          </div>
          <div style={{ fontSize: "15px", color: "#6b7280", marginTop: "8px" }}>
            {personas.length} recruiter archetypes evaluated your profile.
            Here's their verdict.
          </div>
        </div>

        {/* Summary Stats Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "repeat(4, 1fr)",
            gap: "16px",
            marginBottom: "32px",
          }}
        >
          {/* Shortlist Rate */}
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "8px" }}>
              Shortlist Rate
            </div>
            <div
              style={{
                fontSize: "36px",
                fontWeight: 800,
                color: shortlistColors.text,
                lineHeight: 1,
              }}
            >
              {shortlistRate}%
            </div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                background: shortlistColors.bg,
                border: `1px solid ${shortlistColors.border}`,
                color: shortlistColors.text,
                borderRadius: "999px",
                padding: "3px 10px",
                fontSize: "11px",
                fontWeight: 700,
                marginTop: "8px",
              }}
            >
              {shortlistRate >= 70
                ? "↗ Strong"
                : shortlistRate >= 40
                  ? "→ Moderate"
                  : "↘ Needs Work"}
            </div>
          </div>

          {/* Avg Fit Score */}
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "8px" }}>
              Avg Fit Score
            </div>
            <div
              style={{
                fontSize: "36px",
                fontWeight: 800,
                color: "#6366f1",
                lineHeight: 1,
              }}
            >
              {avgFitScore}
            </div>
            <div style={{ fontSize: "13px", color: "#9ca3af", marginTop: "4px" }}>
              /100
            </div>
          </div>

          {/* Top Strength */}
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "8px" }}>
              Top Strength
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "#16a34a",
                lineHeight: 1.4,
              }}
            >
              {sim.consensus_strengths[0] ?? "—"}
            </div>
          </div>

          {/* Top Weakness */}
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
            }}
          >
            <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "8px" }}>
              Top Weakness
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "#dc2626",
                lineHeight: 1.4,
              }}
            >
              {sim.consensus_weaknesses[0] ?? "—"}
            </div>
          </div>
        </div>

        {/* Persona Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "repeat(2, 1fr)",
            gap: "16px",
            marginBottom: "32px",
          }}
        >
          {personas.map((persona) => (
            <PersonaCard key={persona.persona} persona={persona} />
          ))}
        </div>

        {/* Strategic Insight Card */}
        <div
          style={{
            background: "linear-gradient(135deg, #6366f1, #7c3aed)",
            borderRadius: "20px",
            padding: "36px 40px",
            boxShadow: "0 4px 0 #4338ca, 0 8px 24px rgba(99,102,241,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "24px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "rgba(255,255,255,0.7)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "10px",
              }}
            >
              Strategic Insight
            </div>
            <div
              style={{
                fontSize: "17px",
                fontWeight: 700,
                color: "#ffffff",
                lineHeight: 1.4,
                marginBottom: "8px",
              }}
            >
              To break into {nextTier}, focus on:
            </div>
            <div
              style={{
                fontSize: "14px",
                color: "rgba(255,255,255,0.85)",
                lineHeight: 1.6,
              }}
            >
              {sim.most_critical_fix}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setActiveTab("fixes")}
            onMouseDown={() => setIsViewFixPressed(true)}
            onMouseUp={() => setIsViewFixPressed(false)}
            onMouseLeave={() => setIsViewFixPressed(false)}
            style={{
              background: "#ffffff",
              color: "#6366f1",
              borderRadius: "12px",
              padding: "12px 24px",
              fontSize: "13px",
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              whiteSpace: "nowrap",
              flexShrink: 0,
              boxShadow: isViewFixPressed
                ? "0 1px 0 rgba(0,0,0,0.15)"
                : "0 3px 0 rgba(0,0,0,0.15)",
              transform: isViewFixPressed ? "translateY(2px)" : "translateY(0)",
              transition: "transform 0.1s, box-shadow 0.1s",
            }}
          >
            View Recommended Fixes →
          </button>
        </div>

        <DataSourceNotice tab="recruiter" />
      </div>
    </div>
  );
}
