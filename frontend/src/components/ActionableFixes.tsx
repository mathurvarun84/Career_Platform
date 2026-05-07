import { useState } from "react";

import { getResumeDownloadUrl } from "../api/client";
import { useWindowSize } from "../hooks/useWindowSize";
import { useResumeStore } from "../store/useResumeStore";
import type { ATSResult, GapResult, PriorityFix, RewriteStyle } from "../types";
import DataSourceNotice from "./DataSourceNotice";

type PriorityLevel = "critical" | "high" | "medium" | "low";
type FilterValue = "all" | "critical" | "high" | "medium";
type SortValue = "impact" | "section" | "score_gain";

interface FixItem {
  id: string;
  sectionKey: string;
  sectionName: string;
  gapReason: string;
  rewriteInstruction: string;
  missingKeywords: string[];
  priority: PriorityLevel;
  source: "gap" | "ats";
  needsChange: boolean;
  originalContent?: string;
}

const priorityOrder: Record<PriorityLevel, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const scoreGainByPriority: Record<PriorityLevel, number> = {
  critical: 18,
  high: 12,
  medium: 7,
  low: 2,
};

const atsSectionMap: Record<string, { reason: string; instruction: string }> = {
  impact_metrics: {
    reason: "Missing quantified impact in bullets",
    instruction: "Add numbers, percentages, and scale to show measurable results.",
  },
  keyword_match: {
    reason: "Low keyword density",
    instruction:
      "Add more domain-specific keywords and action verbs from the job description.",
  },
  formatting: {
    reason: "Formatting inconsistencies detected",
    instruction:
      "Align bullet styles, date formats, and section headers consistently.",
  },
  readability: {
    reason: "Sentence clarity could be improved",
    instruction: "Shorten sentences, use active voice, and avoid filler phrases.",
  },
};

const stylePillConfig: Record<
  RewriteStyle,
  {
    label: string;
    sublabel: string;
    activeColor: string;
    activeBg: string;
    activeBorder: string;
    icon: string;
  }
> = {
  balanced: {
    label: "Balanced",
    sublabel: "Safe & Professional",
    activeColor: "#6366f1",
    activeBg: "#eef2ff",
    activeBorder: "#c7d2fe",
    icon: "⚖",
  },
  aggressive: {
    label: "Aggressive",
    sublabel: "Punchy & Bold",
    activeColor: "#d97706",
    activeBg: "#fffbeb",
    activeBorder: "#fde68a",
    icon: "⚡",
  },
  top_1_percent: {
    label: "Top 1%",
    sublabel: "Maximum Impact",
    activeColor: "#7c3aed",
    activeBg: "#f5f0ff",
    activeBorder: "#e9d5ff",
    icon: "✦",
  },
};

const styleDescriptions: Record<RewriteStyle, string> = {
  balanced:
    "Conservative rewrites — safe for any company, ATS-friendly, no risk.",
  aggressive:
    "Strong verbs, quantified claims, direct language — works for product startups.",
  top_1_percent:
    "Executive-level phrasing with maximum keyword density — for senior/leadership roles.",
};

const toTitleCase = (value: string): string =>
  value
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

const canonicalSections = new Set([
  "summary",
  "skills",
  "experience",
  "education",
  "certifications",
  "awards",
  "projects",
]);

const inferSectionKey = (value: string): string => {
  const lower = value.toLowerCase();
  if (canonicalSections.has(lower)) return lower;
  if (lower.includes("summary")) return "summary";
  if (lower.includes("skill") || lower.includes("keyword")) return "skills";
  if (lower.includes("experience") || lower.includes("bullet")) return "experience";
  if (lower.includes("education") || lower.includes("degree")) return "education";
  if (lower.includes("certification") || lower.includes("certificate")) return "certifications";
  if (lower.includes("award")) return "awards";
  if (lower.includes("project")) return "projects";
  return "summary";
};

const normalizePriorityFixes = (gap: GapResult | null): PriorityFix[] => {
  if (!gap?.priority_fixes) {
    return [];
  }

  return gap.priority_fixes.filter(
    (item): item is PriorityFix =>
      typeof item === "object" &&
      item !== null &&
      "section" in item &&
      "gap_reason" in item &&
      "rewrite_instruction" in item &&
      "missing_keywords" in item &&
      "needs_change" in item
  );
};

const derivePriority = (
  sectionName: string,
  ats: ATSResult,
  gap: GapResult | null,
  fixIndex: number
): PriorityLevel => {
  const normalizedFixes = normalizePriorityFixes(gap);

  if (sectionName === "experience" && ats.breakdown.impact_metrics < 12) {
    return "critical";
  }
  if (sectionName === "summary" && ats.breakdown.impact_metrics < 12) {
    return "critical";
  }
  if (normalizedFixes[fixIndex]?.needs_change && fixIndex === 0) {
    return "critical";
  }
  if (ats.breakdown.keyword_match < 12) {
    return "high";
  }
  if (normalizedFixes[fixIndex]?.needs_change && fixIndex === 1) {
    return "high";
  }
  if (ats.breakdown.formatting < 16) {
    return "medium";
  }
  if (normalizedFixes[fixIndex]?.needs_change) {
    return "medium";
  }
  return "low";
};

const extractImprovementBullets = (instruction: string): string[] => {
  const parts = instruction
    .split(/[.;]/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3);

  if (parts.length === 0 || instruction.length < 30) {
    return [
      "Add measurable outcomes",
      "Use stronger action verbs",
      "Include scale indicators",
    ];
  }

  while (parts.length < 3) {
    parts.push("Add measurable outcomes");
  }

  return parts.slice(0, 3);
};

export default function ActionableFixes() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const selectedStyle = useResumeStore((s) => s.selectedStyle);
  const setSelectedStyle = useResumeStore((s) => s.setSelectedStyle);
  const jobId = useResumeStore((s) => s.jobId);

  const [activeFilter, setActiveFilter] = useState<FilterValue>("all");
  const [sortBy, setSortBy] = useState<SortValue>("impact");
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());
  const [appliedFixes, setAppliedFixes] = useState<Set<string>>(new Set());
  const [pressedFixButton, setPressedFixButton] = useState<string | null>(null);
  const [isAcceptPressed, setIsAcceptPressed] = useState(false);
  const { isMobile } = useWindowSize();

  if (!analysisResult) {
    return null;
  }

  const normalizedGapFixes = normalizePriorityFixes(analysisResult.gap);

  const gapFixes: FixItem[] = normalizedGapFixes
    .filter((f) => f.needs_change)
    .map((f, i) => {
      const sectionKey = inferSectionKey(f.section);
      return ({
        id: `gap-${sectionKey}-${i}`,
        sectionKey,
        sectionName: sectionKey,
      gapReason: f.gap_reason,
      rewriteInstruction: f.rewrite_instruction,
      missingKeywords: f.missing_keywords,
      priority: derivePriority(f.section, analysisResult.ats, analysisResult.gap, i),
      source: "gap",
      needsChange: f.needs_change,
      originalContent:
        (f as PriorityFix & { original_content?: string }).original_content ?? undefined,
      });
    });

  const gapSections = new Set(gapFixes.map((f) => f.sectionName));

  const atsFixes: FixItem[] = (analysisResult.ats.ats_issues ?? [])
    .filter((issue) => !gapSections.has(issue))
    .slice(0, 3)
    .map((issue, i) => {
      const sectionKey = inferSectionKey(issue);
      const info = atsSectionMap[issue] ?? { reason: issue, instruction: issue };
      return {
        id: `ats-${sectionKey}-${i}`,
        sectionKey,
        sectionName: sectionKey,
        gapReason: info.reason,
        rewriteInstruction: info.instruction,
        missingKeywords: [],
        priority: derivePriority(
          issue,
          analysisResult.ats,
          null,
          i + gapFixes.length
        ),
        source: "ats",
        needsChange: false,
      };
    });

  const allFixes = [...gapFixes, ...atsFixes];
  const totalGain = allFixes.reduce(
    (sum, fix) => sum + scoreGainByPriority[fix.priority],
    0
  );
  const allApplied = allFixes.length > 0 && appliedFixes.size === allFixes.length;

  const counts = {
    all: allFixes.length,
    critical: allFixes.filter((f) => f.priority === "critical").length,
    high: allFixes.filter((f) => f.priority === "high").length,
    medium: allFixes.filter((f) => f.priority === "medium").length,
  };

  const filtered = allFixes.filter((f) =>
    activeFilter === "all" ? true : f.priority === activeFilter
  );

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === "impact") {
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    }
    if (sortBy === "section") {
      return a.sectionName.localeCompare(b.sectionName);
    }
    if (sortBy === "score_gain") {
      return scoreGainByPriority[b.priority] - scoreGainByPriority[a.priority];
    }
    return 0;
  });

  const getBeforeText = (fix: FixItem): string => {
    if (fix.needsChange) {
      return (
        fix.originalContent?.trim() ||
        analysisResult.resume.resume_sections?.[fix.sectionKey]?.full_text ||
        "[Original text from your resume]"
      );
    }

    return (
      analysisResult.resume.resume_sections?.[fix.sectionKey]?.full_text ??
      "[Original text from your resume]"
    );
  };

  const rewriteMap =
    analysisResult.rewrites &&
    typeof analysisResult.rewrites === "object" &&
    "rewrites" in (analysisResult.rewrites as Record<string, unknown>)
      ? ((analysisResult.rewrites as { rewrites?: Record<string, Record<RewriteStyle, string>> }).rewrites ?? {})
      : ((analysisResult.rewrites as Record<string, Record<RewriteStyle, string>> | null) ?? {});

  const getAfterText = (sectionKey: string, style: RewriteStyle): string => {
    const sectionRewrite = rewriteMap[sectionKey];
    if (!sectionRewrite) {
      return "[Rewrite not available for this section]";
    }
    return sectionRewrite[style] ?? `[${stylePillConfig[style].label} rewrite unavailable]`;
  };

  const toggleCard = (key: string) => {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const applyFix = (key: string) => {
    setAppliedFixes((prev) => new Set([...prev, key]));
  };

  const applyAll = () => {
    setAppliedFixes(new Set(allFixes.map((fix) => fix.sectionName)));

    const sessionId = jobId ?? analysisResult.job_id;
    if (!sessionId) {
      window.alert("Session id unavailable. Download skipped.");
      return;
    }

    window.open(
      getResumeDownloadUrl(sessionId, selectedStyle),
      "_blank",
      "noopener,noreferrer"
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: isMobile ? "40px 16px 120px" : "40px 32px 120px" }}>
        <div style={{ marginBottom: "32px", textAlign: "center" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              borderRadius: "999px",
              background: "#eef2ff",
              border: "1px solid #c7d2fe",
              color: "#4f46e5",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            ✦ AI-Powered Transformations
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
            Before → After Fixes
          </div>
          <div style={{ fontSize: "15px", color: "#6b7280", marginTop: "8px" }}>
            See exactly how your resume transforms. {allFixes.length} improvements
            ready.
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              borderRadius: "999px",
              background: "#dcfce7",
              border: "1px solid #bbf7d0",
              color: "#16a34a",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 700,
              marginTop: "10px",
            }}
          >
            ↗ Total potential gain: +{totalGain} pts
          </div>
        </div>

        <div style={{ marginBottom: "24px", textAlign: "center" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "stretch",
              background: "#f9fafb",
              border: "1.5px solid #e5e7eb",
              borderRadius: "12px",
              padding: "4px",
              gap: "4px",
            }}
          >
            {(Object.entries(stylePillConfig) as Array<[RewriteStyle, (typeof stylePillConfig)[RewriteStyle]]>).map(([styleKey, cfg]) => {
              const isActive = selectedStyle === styleKey;
              return (
                <button
                  key={styleKey}
                  type="button"
                  onClick={() => setSelectedStyle(styleKey)}
                  style={{
                    border: "none",
                    borderRadius: "8px",
                    padding: "10px 20px",
                    fontSize: "13px",
                    fontWeight: isActive ? 700 : 500,
                    cursor: "pointer",
                    transition: "all 0.15s",
                    background: isActive ? cfg.activeBg : "transparent",
                    color: isActive ? cfg.activeColor : "#6b7280",
                    boxShadow: isActive ? "0 2px 0 rgba(0,0,0,0.08)" : "none",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px" }}>
                    <span style={{ fontSize: "14px" }}>{cfg.icon}</span>
                    <span>{cfg.label}</span>
                  </div>
                  <div style={{ fontSize: "11px", fontWeight: 400, color: "inherit", opacity: 0.8 }}>
                    {cfg.sublabel}
                  </div>
                </button>
              );
            })}
          </div>
          <div
            style={{
              marginTop: "12px",
              padding: "10px 16px",
              background: "#f9fafb",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#6b7280",
              textAlign: "center",
              border: "1px solid #e5e7eb",
            }}
          >
            {styleDescriptions[selectedStyle]}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "20px",
            flexWrap: "wrap",
            rowGap: "10px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            {([
              ["all", `All (${counts.all})`],
              ["critical", `Critical (${counts.critical})`],
              ["high", `High (${counts.high})`],
              ["medium", `Medium (${counts.medium})`],
            ] as const).map(([key, label]) => {
              const isActive = activeFilter === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveFilter(key)}
                  style={{
                    border: "none",
                    borderRadius: "999px",
                    padding: "6px 16px",
                    fontSize: "12px",
                    fontWeight: 700,
                    cursor: "pointer",
                    background: isActive ? "#6366f1" : "#f3f4f6",
                    color: isActive ? "#ffffff" : "#6b7280",
                    transition: "background 0.15s, color 0.15s",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div style={{ fontSize: "12px", color: "#6b7280" }}>Sort by:</div>
            <select
              value={sortBy}
              onChange={(event) => setSortBy(event.target.value as SortValue)}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: "8px",
                padding: "6px 12px",
                fontSize: "12px",
                color: "#374151",
                background: "#ffffff",
                cursor: "pointer",
              }}
            >
              <option value="impact">Impact</option>
              <option value="section">Section</option>
              <option value="score_gain">Score Gain</option>
            </select>
          </div>
        </div>

        {sorted.length === 0 ? (
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "48px 32px",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "32px", color: "#d1d5db" }}>✦</div>
            <div
              style={{
                fontSize: "17px",
                fontWeight: 700,
                color: "#111827",
                marginTop: "12px",
              }}
            >
              No fixes in this category
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "4px" }}>
              Try &apos;All&apos; to see every improvement
            </div>
          </div>
        ) : (
          sorted.map((fix) => {
            const key = fix.id;
            const isExpanded = expandedCards.has(key);
            const isApplied = appliedFixes.has(key);
            const scoreGain = scoreGainByPriority[fix.priority];
            const improvements = extractImprovementBullets(fix.rewriteInstruction);
            const afterAccentColor = {
              balanced: "#6366f1",
              aggressive: "#d97706",
              top_1_percent: "#7c3aed",
            }[selectedStyle];

            const priorityColors: Record<
              PriorityLevel,
              { bg: string; text: string; border: string }
            > = {
              critical: { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" },
              high: { bg: "#fff7ed", text: "#d97706", border: "#fed7aa" },
              medium: { bg: "#fefce8", text: "#ca8a04", border: "#fde68a" },
              low: { bg: "#f0fdf4", text: "#16a34a", border: "#bbf7d0" },
            };

            return (
              <div
                key={key}
                style={{
                  border: "1.5px solid #e5e7eb",
                  borderRadius: "16px",
                  overflow: "hidden",
                  marginBottom: "16px",
                  background: "#ffffff",
                  boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
                }}
              >
                <div
                  role="button"
                  aria-expanded={isExpanded}
                  onClick={() => toggleCard(key)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "18px 20px",
                    cursor: "pointer",
                    background: isExpanded ? "#f9fafb" : "#ffffff",
                    borderBottom: isExpanded ? "1.5px solid #e5e7eb" : "none",
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1 }}
                  >
                    <div
                      style={{
                        borderRadius: "999px",
                        padding: "3px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                        background: priorityColors[fix.priority].bg,
                        color: priorityColors[fix.priority].text,
                        border: `1px solid ${priorityColors[fix.priority].border}`,
                        textTransform: "capitalize",
                      }}
                    >
                      {fix.priority}
                    </div>
                    <div
                      style={{
                        fontSize: "15px",
                        fontWeight: 700,
                        color: "#111827",
                      }}
                    >
                      {toTitleCase(fix.sectionName)}
                      {fix.gapReason ? ` — ${fix.gapReason}` : ""}
                    </div>
                    <div
                      style={{
                        background: "#dcfce7",
                        color: "#16a34a",
                        borderRadius: "999px",
                        padding: "3px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                      }}
                    >
                      +{scoreGain} pts ATS
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div
                      style={{
                        fontSize: "12px",
                        color: "#9ca3af",
                        transition: "transform 0.2s",
                        transform: isExpanded ? "rotate(0deg)" : "rotate(0deg)",
                      }}
                    >
                      {isExpanded ? "▼" : "▶"}
                    </div>
                    {isExpanded && (
                      <button
                        type="button"
                        aria-label={`Apply fix for ${fix.sectionName}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          applyFix(key);
                        }}
                        onMouseDown={() => setPressedFixButton(key)}
                        onMouseUp={() => setPressedFixButton(null)}
                        onMouseLeave={() => setPressedFixButton(null)}
                        style={{
                          border: "none",
                          borderRadius: "10px",
                          padding: "8px 18px",
                          fontSize: "12px",
                          fontWeight: 700,
                          color: "#ffffff",
                          cursor: "pointer",
                          background: isApplied ? "#16a34a" : "#6366f1",
                          boxShadow: isApplied
                            ? "0 2px 0 #15803d"
                            : "0 2px 0 #4338ca, 0 4px 10px rgba(99,102,241,0.25)",
                          transform:
                            pressedFixButton === key ? "translateY(2px)" : "translateY(0)",
                        }}
                      >
                        {isApplied ? "✓ Applied" : "Apply This Fix"}
                      </button>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    maxHeight: isExpanded ? "2000px" : "0px",
                    opacity: isExpanded ? 1 : 0,
                    overflow: "hidden",
                    transition: "max-height 0.25s ease, opacity 0.2s",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: isMobile ? "column" : "row",
                    }}
                  >
                    <div
                      style={{
                        background: "#f9fafb",
                        padding: "10px 20px",
                        display: "flex",
                        flexDirection: isMobile ? "column" : "row",
                        gap: isMobile ? "8px" : "0",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#9ca3af",
                          textTransform: "uppercase",
                        }}
                      >
                        Before
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#16a34a",
                          textTransform: "uppercase",
                        }}
                      >
                        ● {stylePillConfig[selectedStyle].label} Version
                      </div>
                    </div>
                    <div
                      style={{
                        background: "#fafafa",
                        padding: "20px",
                        borderRight: isMobile ? "none" : "1.5px solid #e5e7eb",
                        borderBottom: isMobile ? "1.5px solid #e5e7eb" : "none",
                        fontSize: "13px",
                        color: "#6b7280",
                        lineHeight: 1.65,
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {getBeforeText(fix)}
                    </div>
                    <div
                      style={{
                        background: "#f0fdf4",
                        padding: "20px",
                        fontSize: "13px",
                        color: "#374151",
                        lineHeight: 1.65,
                        whiteSpace: "pre-wrap",
                        borderLeft: `3px solid ${afterAccentColor}`,
                      }}
                    >
                      <div
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: afterAccentColor,
                          marginBottom: "8px",
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {styleDescriptions[selectedStyle]}
                      </div>
                      {getAfterText(fix.sectionKey, selectedStyle)}
                    </div>
                  </div>

                  <div
                    style={{
                      background: "#f9fafb",
                      border: "1px solid #e5e7eb",
                      borderTop: "none",
                      padding: "16px 20px",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827" }}>
                      💡 Why this matters
                    </div>
                    <div
                      style={{
                        fontSize: "13px",
                        color: "#4b5563",
                        lineHeight: 1.65,
                        marginTop: "6px",
                      }}
                    >
                      {fix.rewriteInstruction}
                    </div>

                    {(fix.missingKeywords.length > 0 ||
                      fix.priority === "critical" ||
                      fix.priority === "high") && (
                      <>
                        <div
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "#374151",
                            letterSpacing: "0.06em",
                            textTransform: "uppercase",
                            marginTop: "12px",
                          }}
                        >
                          Key Improvements
                        </div>
                        <div
                          style={{
                            fontSize: "12px",
                            color: "#374151",
                            lineHeight: 1.7,
                            marginTop: "4px",
                          }}
                        >
                          {improvements.map((item) => (
                            <div key={`${key}-${item}`}>✓ {item}</div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>

                  {fix.missingKeywords.length > 0 && (
                    <div
                      style={{
                        background: "#ffffff",
                        borderTop: "1px solid #e5e7eb",
                        padding: "12px 20px",
                        display: "flex",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: "8px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "12px",
                          fontWeight: 600,
                          color: "#6b7280",
                          marginRight: "4px",
                        }}
                      >
                        Keywords added:
                      </div>
                      {fix.missingKeywords.map((keyword) => (
                        <div
                          key={`${key}-${keyword}`}
                          style={{
                            background: "#eef2ff",
                            border: "1px solid #c7d2fe",
                            color: "#4f46e5",
                            borderRadius: "999px",
                            padding: "3px 10px",
                            fontSize: "11px",
                            fontWeight: 600,
                          }}
                        >
                          {keyword}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        <DataSourceNotice tab="fixes" />
      </div>

      <div
        style={{
          position: "sticky",
          bottom: 0,
          background: "rgba(255,255,255,0.95)",
          backdropFilter: "blur(12px)",
          borderTop: "1.5px solid #e5e7eb",
          padding: "16px 32px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 40,
        }}
      >
        <div style={{ fontSize: "13px", color: "#6b7280" }}>
          {appliedFixes.size} of {allFixes.length} fixes applied
        </div>
        <button
          type="button"
          onClick={applyAll}
          onMouseDown={() => setIsAcceptPressed(true)}
          onMouseUp={() => setIsAcceptPressed(false)}
          onMouseLeave={() => setIsAcceptPressed(false)}
          style={{
            border: "none",
            borderRadius: "12px",
            padding: "12px 28px",
            fontSize: "14px",
            fontWeight: 700,
            color: "#ffffff",
            cursor: "pointer",
            background: allApplied ? "#16a34a" : "#6366f1",
            boxShadow: allApplied
              ? "0 4px 0 #15803d"
              : isAcceptPressed
                ? "0 1px 0 #4338ca"
                : "0 4px 0 #4338ca, 0 6px 16px rgba(99,102,241,0.25)",
            transform: isAcceptPressed ? "translateY(3px)" : "translateY(0)",
            transition: "transform 0.1s, box-shadow 0.1s",
          }}
        >
          {allApplied ? "✓ All Changes Applied" : "Accept All Changes"}
        </button>
      </div>
    </div>
  );
}
