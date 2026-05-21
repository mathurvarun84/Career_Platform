import { useState } from "react";

import type { RoleFit } from "../types";

interface RoleFitBannerProps {
  roleFit: RoleFit;
  onShowQualifiedRoles: () => void;
  onShowCareerPath: () => void;
  onApplyAnyway: () => void;
}

/** Alert / stat chip — DESIGN_SYSTEM §6 Score card, compact */
function StatChip({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: "16px",
        padding: "16px 18px",
        minWidth: "120px",
        flex: "1 1 140px",
        boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          fontWeight: 400,
          color: "#9ca3af",
          marginBottom: "6px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "15px",
          fontWeight: 700,
          color: "#111827",
          letterSpacing: "-0.01em",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function OptionRow({
  number,
  title,
  onClick,
  accentColor,
}: {
  number: string;
  title: string;
  onClick: () => void;
  accentColor: string;
}) {
  const [pressed, setPressed] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      onMouseLeave={() => setPressed(false)}
      style={{
        display: "flex",
        alignItems: "center",
        width: "100%",
        textAlign: "left",
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: "18px",
        padding: "16px 20px",
        cursor: "pointer",
        marginBottom: "12px",
        boxShadow: pressed
          ? "0 1px 0 #e5e7eb"
          : "0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)",
        transform: pressed ? "translateY(2px)" : "translateY(0)",
        transition: "transform 0.1s, box-shadow 0.1s",
      }}
    >
      <span
        style={{
          fontSize: "17px",
          fontWeight: 700,
          color: accentColor,
          marginRight: "14px",
          flexShrink: 0,
          lineHeight: 1,
        }}
      >
        {number}
      </span>
      <span
        style={{
          fontSize: "15px",
          fontWeight: 700,
          color: "#111827",
          letterSpacing: "-0.01em",
        }}
      >
        {title}
      </span>
    </button>
  );
}

export default function RoleFitBanner({
  roleFit,
  onShowQualifiedRoles,
  onShowCareerPath,
  onApplyAnyway,
}: RoleFitBannerProps) {
  const [stretchExpanded, setStretchExpanded] = useState(false);

  if (roleFit.fitness === "qualified") {
    return null;
  }

  if (roleFit.fitness === "stretch") {
    return (
      <div
        style={{
          borderLeft: "4px solid #fbbf24",
          borderRadius: "0 12px 12px 0",
          background: "#fff7ed",
          marginBottom: "20px",
          overflow: "hidden",
        }}
      >
        <button
          type="button"
          onClick={() => setStretchExpanded((v) => !v)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "transparent",
            border: "none",
            padding: "16px 20px",
            cursor: "pointer",
            textAlign: "left",
          }}
        >
          <span
            style={{
              fontSize: "15px",
              fontWeight: 700,
              color: "#111827",
              letterSpacing: "-0.01em",
            }}
          >
            Stretch role — {roleFit.score}/100 fit · {roleFit.experience_gap} yr gap · parallel-track
            recommended
          </span>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#d97706" }}>
            {stretchExpanded ? "▲" : "▼"}
          </span>
        </button>
        {stretchExpanded ? (
          <div style={{ padding: "0 20px 18px 20px" }}>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "12px",
                marginBottom: "14px",
              }}
            >
              <StatChip label="Your experience" value={`${roleFit.candidate_years} yrs`} />
              <StatChip label="Role requires" value={`${roleFit.jd_min_years}+ yrs`} />
              <StatChip label="Gap (years)" value={roleFit.experience_gap} />
              <StatChip label="Seniority gap" value={roleFit.seniority_gap} />
              <StatChip label="Evidence gaps" value={roleFit.unanswerable_evidence_gaps} />
            </div>
            <p
              style={{
                fontSize: "13px",
                fontWeight: 400,
                color: "#6b7280",
                margin: 0,
                lineHeight: 1.55,
              }}
            >
              This role is achievable with targeted growth. We recommend applying in parallel to roles
              you match today while closing the gaps below.
            </p>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      style={{
        borderLeft: "4px solid #ef4444",
        borderRadius: "0 12px 12px 0",
        background: "#fef2f2",
        padding: "16px 20px",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          fontSize: "17px",
          fontWeight: 700,
          color: "#111827",
          letterSpacing: "-0.01em",
          marginBottom: "14px",
        }}
      >
        Honest Assessment: This Role Is a Significant Reach
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "12px",
          marginBottom: "18px",
        }}
      >
        <StatChip label="Your experience" value={`${roleFit.candidate_years} yrs`} />
        <StatChip label="Role requires" value={`${roleFit.jd_min_years}+ yrs`} />
        <StatChip label="Gap (years)" value={roleFit.experience_gap} />
        <StatChip label="Seniority gap" value={roleFit.seniority_gap} />
        <StatChip label="Evidence gaps unanswerable" value={roleFit.unanswerable_evidence_gaps} />
      </div>
      <OptionRow
        number="①"
        title="Show me roles I'm qualified for"
        onClick={onShowQualifiedRoles}
        accentColor="#6366f1"
      />
      <OptionRow
        number="②"
        title="Show my path to this role"
        onClick={onShowCareerPath}
        accentColor="#7c3aed"
      />
      <OptionRow
        number="③"
        title="Apply anyway — optimise what we can"
        onClick={onApplyAnyway}
        accentColor="#ef4444"
      />
    </div>
  );
}
