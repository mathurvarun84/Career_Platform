import type { CSSProperties } from "react";

import type { FixModeBaseline } from "../utils/modeScores";

export interface ModeSelectorProps {
  baseline: FixModeBaseline;
  selected: "safe" | "full";
  onChange: (mode: "safe" | "full") => void;
}

function RadioIndicator({ selected }: { selected: boolean }) {
  if (selected) {
    return (
      <div
        style={{
          width: "18px",
          height: "18px",
          borderRadius: "50%",
          background: "#6366f1",
          border: "2px solid #6366f1",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: "7px",
            height: "7px",
            borderRadius: "50%",
            background: "#fff",
          }}
        />
      </div>
    );
  }

  return (
    <div
      style={{
        width: "18px",
        height: "18px",
        borderRadius: "50%",
        border: "2px solid #d1d5db",
        flexShrink: 0,
      }}
    />
  );
}

function ScoreBlock({
  label,
  value,
  suffix,
}: {
  label: string;
  value: number;
  suffix?: string;
}) {
  return (
    <div>
      <div style={{ fontSize: "11px", color: "#6b7280" }}>{label}</div>
      <div
        style={{
          fontSize: "22px",
          fontWeight: 800,
          color: "#6366f1",
          lineHeight: 1.1,
        }}
      >
        {value}
        {suffix ?? ""}
      </div>
    </div>
  );
}

function BaselineScores({ baseline }: { baseline: FixModeBaseline }) {
  return (
    <div
      style={{
        display: "flex",
        gap: "24px",
        flexWrap: "wrap",
        marginBottom: "12px",
        padding: "14px 16px",
        background: "#f9fafb",
        border: "1.5px solid #e5e7eb",
        borderRadius: "12px",
      }}
    >
      <ScoreBlock label="Your ATS Score" value={baseline.baselineAts} />
      {baseline.hasJd && baseline.baselineJd !== null ? (
        <ScoreBlock label="JD Match" value={baseline.baselineJd} suffix="%" />
      ) : null}
    </div>
  );
}

function JdGainBanner({ baseline }: { baseline: FixModeBaseline }) {
  if (!baseline.hasJd || baseline.jdGain <= 0 || baseline.targetJd === null) {
    return null;
  }

  return (
    <div
      style={{
        background: "#f5f0ff",
        border: "1px solid #e9d5ff",
        borderRadius: "12px",
        padding: "12px 16px",
        marginBottom: "16px",
        fontSize: "13px",
        color: "#5b21b6",
        lineHeight: 1.55,
      }}
    >
      <strong>Primary value:</strong> Applying fixes can improve JD alignment from{" "}
      <strong>{baseline.baselineJd}%</strong> → <strong>{baseline.targetJd}%</strong>
      {baseline.jdGain > 0 ? ` (+${baseline.jdGain}%)` : ""}. Review content changes below —
      ATS updates on the Overview tab after you apply each fix.
    </div>
  );
}

export default function ModeSelector({
  baseline,
  selected,
  onChange,
}: ModeSelectorProps) {
  const renderCard = (
    mode: "safe" | "full",
    title: string,
    tag: { label: string; bg: string; color: string },
    description: string,
    trustText: string,
    trustDotColor: string
  ) => {
    const isSelected = selected === mode;

    let cardStyle: CSSProperties = {
      border: "2px solid #e5e7eb",
      borderRadius: "14px",
      padding: "18px 20px",
      background: "#fff",
      cursor: "pointer",
      textAlign: "left",
      width: "100%",
    };

    if (isSelected) {
      cardStyle = {
        ...cardStyle,
        border: "2px solid #6366f1",
        background: "#fafafe",
        boxShadow: "0 0 0 3px rgba(99,102,241,0.12)",
      };
    }

    return (
      <button
        key={mode}
        type="button"
        onClick={() => onChange(mode)}
        style={cardStyle}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
            marginBottom: "10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <RadioIndicator selected={isSelected} />
            <span style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
              {title}
            </span>
          </div>
          <span
            style={{
              background: tag.bg,
              color: tag.color,
              borderRadius: "999px",
              padding: "3px 10px",
              fontSize: "11px",
              fontWeight: 700,
              whiteSpace: "nowrap",
            }}
          >
            {tag.label}
          </span>
        </div>

        <p
          style={{
            fontSize: "13px",
            color: "#6b7280",
            lineHeight: 1.5,
            margin: "0 0 12px",
          }}
        >
          {description}
        </p>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "12px",
            color: "#4b5563",
            lineHeight: 1.5,
          }}
        >
          <span
            style={{
              width: "7px",
              height: "7px",
              borderRadius: "50%",
              background: trustDotColor,
              flexShrink: 0,
            }}
          />
          {trustText}
        </div>
      </button>
    );
  };

  return (
    <div>
      <BaselineScores baseline={baseline} />
      <JdGainBanner baseline={baseline} />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "12px",
          marginBottom: "12px",
        }}
      >
        {renderCard(
          "safe",
          "Safe fix",
          { label: "Recommended", bg: "#dcfce7", color: "#15803d" },
          "Surgical edits — only flagged phrases change; everything else stays verbatim.",
          "Best when you want minimal risk and maximum fidelity to your original resume.",
          "#16a34a"
        )}
        {renderCard(
          "full",
          "Full rewrite",
          { label: "Higher impact", bg: "#eef2ff", color: "#4f46e5" },
          "AI rewrites entire weak sections — review every diff before downloading.",
          "Use when a section needs a full refresh, not just a phrase swap.",
          "#d97706"
        )}
      </div>
    </div>
  );
}
