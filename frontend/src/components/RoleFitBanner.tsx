import { useState } from "react";

import type { RoleFit } from "../types";

interface RoleFitBannerProps {
  roleFit: RoleFit;
  atsScore?: number;
  roleTitle?: string;
  onShowQualifiedRoles: () => void;
  onShowCareerPath: () => void;
}

/** Alert / stat chip — compact supporting evidence */
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
        boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0, 0, 0, 0.04)",
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

function UnderqualifiedStatChip({
  label,
  value,
  emphasizeGap,
}: {
  label: string;
  value: string | number;
  emphasizeGap?: boolean;
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #fde68a",
        borderRadius: "12px",
        padding: "12px 16px",
        minWidth: "110px",
      }}
    >
      <div
        style={{
          fontSize: "12px",
          fontWeight: 400,
          color: "#92400e",
          marginBottom: "6px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "15px",
          fontWeight: emphasizeGap ? 800 : 700,
          color: emphasizeGap ? "#d97706" : "#111827",
          letterSpacing: "-0.01em",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function UnderqualifiedOptionRow({
  number,
  title,
  onClick,
  variant,
}: {
  number: string;
  title: string;
  onClick: () => void;
  variant: "primary" | "secondary";
}) {
  const isPrimary = variant === "primary";

  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        width: "100%",
        textAlign: "left",
        gap: "14px",
        padding: "14px 18px",
        borderRadius: "12px",
        marginBottom: isPrimary ? "10px" : "0",
        border: isPrimary ? "1.5px solid #6366f1" : "1.5px solid #e5e7eb",
        background: isPrimary ? "#eef2ff" : "#ffffff",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          fontSize: "17px",
          fontWeight: 700,
          color: isPrimary ? "#6366f1" : "#7c3aed",
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

function buildUnderqualifiedParagraph(roleFit: RoleFit, roleTitle: string): string {
  const roleClause = roleTitle.trim() ? ` for “${roleTitle.trim()}”` : "";
  const parts: string[] = [];

  if (roleFit.jd_min_years > 0 || roleFit.candidate_years > 0) {
    const gapPhrase =
      roleFit.experience_gap > 0
        ? ` — about ${roleFit.experience_gap} year${roleFit.experience_gap === 1 ? "" : "s"} short`
        : "";
    parts.push(
      `You have ${roleFit.candidate_years} year${roleFit.candidate_years === 1 ? "" : "s"} of experience. This role requires ${roleFit.jd_min_years}+ years${gapPhrase}.`
    );
  }

  if (roleFit.seniority_gap > 0) {
    parts.push(
      `The responsibilities read ${roleFit.seniority_gap} seniority level${roleFit.seniority_gap === 1 ? "" : "s"} above where your resume is positioned today.`
    );
  }

  if (parts.length === 0) {
    return `This role${roleClause} is a significant reach compared to your profile (${roleFit.score}/100 fit).`;
  }

  return parts.join(" ");
}

function buildStretchParagraph(roleFit: RoleFit, roleTitle: string): string {
  const roleClause = roleTitle.trim() ? ` for “${roleTitle.trim()}”` : "";
  return `This role${roleClause} is achievable with targeted growth (${roleFit.score}/100 fit). You are ${roleFit.experience_gap} year${roleFit.experience_gap === 1 ? "" : "s"} and ${roleFit.seniority_gap} level${roleFit.seniority_gap === 1 ? "" : "s"} away — apply in parallel to roles you match today while closing the gaps below.`;
}

export default function RoleFitBanner({
  roleFit,
  atsScore = 0,
  roleTitle = "",
  onShowQualifiedRoles,
  onShowCareerPath,
}: RoleFitBannerProps) {
  const [stretchExpanded, setStretchExpanded] = useState(false);

  if (roleFit.fitness === "qualified") {
    return null;
  }

  if (roleFit.fitness === "stretch") {
    return (
      <div
        style={{
          border: "1.5px solid #fde68a",
          borderRadius: "16px",
          background: "#fffbeb",
          marginBottom: "20px",
          overflow: "hidden",
          borderLeft: "5px solid #d97706",
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
            Stretch role — {roleFit.score}/100 fit
          </span>
          <span style={{ fontSize: "12px", fontWeight: 600, color: "#d97706" }}>
            {stretchExpanded ? "▲" : "▼"}
          </span>
        </button>
        <div
          style={{
            fontSize: "13px",
            color: "#92400e",
            marginTop: "6px",
            fontWeight: 400,
            lineHeight: 1.5,
            padding: "0 20px 12px 20px",
          }}
        >
          You meet most requirements but have some gaps in seniority or skills. Still worth
          applying — address the gaps in your cover letter.
        </div>
        {stretchExpanded ? (
          <div style={{ padding: "0 20px 18px 20px" }}>
            <p
              style={{
                fontSize: "14px",
                fontWeight: 400,
                color: "#374151",
                margin: "0 0 14px 0",
                lineHeight: 1.6,
              }}
            >
              {buildStretchParagraph(roleFit, roleTitle)}
            </p>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                marginBottom: "14px",
              }}
            >
              <div style={{ marginRight: "12px", marginBottom: "12px" }}>
                <StatChip label="Your experience" value={`${roleFit.candidate_years} yrs`} />
              </div>
              <div style={{ marginRight: "12px", marginBottom: "12px" }}>
                <StatChip label="Role requires" value={`${roleFit.jd_min_years}+ yrs`} />
              </div>
              <div style={{ marginRight: "12px", marginBottom: "12px" }}>
                <StatChip label="Gap (years)" value={roleFit.experience_gap} />
              </div>
              <div style={{ marginBottom: "12px" }}>
                <StatChip label="Seniority gap" value={roleFit.seniority_gap} />
              </div>
            </div>
            {atsScore > 0 ? (
              <p
                style={{
                  fontSize: "12px",
                  fontWeight: 400,
                  color: "#6b7280",
                  margin: 0,
                  lineHeight: 1.55,
                }}
              >
                ATS score today: {atsScore}/100 — fixes can still lift visibility while you grow toward this role.
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  const experienceGap = roleFit.experience_gap;

  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        background: "#fffbeb",
        border: "2px solid #f59e0b",
        borderRadius: "16px",
        padding: "28px 32px",
        boxShadow: "0 4px 0 #fde68a, 0 8px 24px rgba(245,158,11,0.12)",
        marginBottom: "20px",
      }}
    >
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: "6px",
          background: "linear-gradient(180deg, #f59e0b, #d97706)",
          borderRadius: "16px 0 0 16px",
        }}
      />
      <div style={{ display: "flex", alignItems: "flex-start", marginBottom: "14px" }}>
        <div
          style={{
            width: "48px",
            height: "48px",
            borderRadius: "12px",
            background: "#fef3c7",
            border: "1.5px solid #fde68a",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "22px",
            flexShrink: 0,
            marginRight: "14px",
          }}
          aria-hidden
        >
          ⚠
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: "20px",
              fontWeight: 800,
              color: "#92400e",
              letterSpacing: "-0.02em",
              marginBottom: "6px",
            }}
          >
            This role is a significant reach
          </div>
          <p
            style={{
              fontSize: "14px",
              fontWeight: 400,
              color: "#374151",
              margin: 0,
              lineHeight: 1.6,
            }}
          >
            {buildUnderqualifiedParagraph(roleFit, roleTitle)}
          </p>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
        }}
      >
        <div style={{ marginRight: "12px", marginBottom: "12px" }}>
          <UnderqualifiedStatChip
            label="Your experience"
            value={`${roleFit.candidate_years} yrs`}
          />
        </div>
        <div style={{ marginRight: "12px", marginBottom: "12px" }}>
          <UnderqualifiedStatChip
            label="Role requires"
            value={`${roleFit.jd_min_years}+ yrs`}
          />
        </div>
        <div style={{ marginRight: "12px", marginBottom: "12px" }}>
          <UnderqualifiedStatChip
            label="Gap (years)"
            value={roleFit.experience_gap}
            emphasizeGap
          />
        </div>
        <div style={{ marginBottom: "12px" }}>
          <UnderqualifiedStatChip
            label="Seniority gap"
            value={roleFit.seniority_gap}
            emphasizeGap
          />
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "10px",
          background: "#fff7ed",
          border: "1px solid #fed7aa",
          borderRadius: "10px",
          padding: "12px 14px",
          marginTop: "16px",
        }}
      >
        <div
          style={{
            width: "20px",
            height: "20px",
            borderRadius: "50%",
            background: "#fed7aa",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "11px",
            fontWeight: 800,
            color: "#92400e",
            flexShrink: 0,
            marginTop: "1px",
          }}
        >
          i
        </div>
        <div style={{ fontSize: "13px", color: "#92400e", lineHeight: 1.6 }}>
          <strong>Gap analysis and fixes are not shown for this role.</strong>{" "}
          With a {experienceGap}-year experience gap, optimising keywords would not move you
          past the recruiter screen. We&apos;ve skipped those steps to save your time and show
          you what actually helps instead.
        </div>
      </div>

      <div style={{ height: "1.5px", background: "#fde68a", margin: "20px 0" }} />

      <div>
        <UnderqualifiedOptionRow
          number="①"
          title="See the roles you're competitive for right now"
          onClick={onShowQualifiedRoles}
          variant="primary"
        />
        <UnderqualifiedOptionRow
          number="②"
          title="See your step-by-step path to this level"
          onClick={onShowCareerPath}
          variant="secondary"
        />
      </div>
    </div>
  );
}
