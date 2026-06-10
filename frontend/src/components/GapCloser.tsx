import { useWindowSize } from "../hooks/useWindowSize";
import { cardPadding, pageContainerStyle } from "../utils/pageLayout";
import { useResumeStore } from "../store/useResumeStore";
import type { PriorityFix, TabId } from "../types";
import DataSourceNotice from "./DataSourceNotice";

const toTitle = (value: string): string =>
  value
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");

const normalizeFixes = (priorityFixes: PriorityFix[] | string[]): PriorityFix[] =>
  priorityFixes.filter(
    (item): item is PriorityFix =>
      typeof item === "object" &&
      item !== null &&
      "section" in item &&
      "gap_reason" in item &&
      "rewrite_instruction" in item &&
      "missing_keywords" in item &&
      "needs_change" in item
  );

interface GapCloserProps {
  onTabChange: (tab: TabId, deepLink?: string) => void;
}

export default function GapCloser({ onTabChange }: GapCloserProps) {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const resetAnalysis = useResumeStore((s) => s.resetAnalysis);
  const { isMobile } = useWindowSize();

  if (!analysisResult) {
    return null;
  }

  if (!analysisResult.gap) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div style={pageContainerStyle(isMobile)}>
          <div
            style={{
              maxWidth: "620px",
              margin: "0 auto",
              border: "1.5px solid #e5e7eb",
              borderRadius: isMobile ? "16px" : "24px",
              padding: cardPadding(isMobile),
              textAlign: "center",
              background: "#ffffff",
              boxShadow: "0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)",
            }}
          >
            <div
              style={{
                width: "42px",
                height: "42px",
                borderRadius: "12px",
                background: "#eef2ff",
                color: "#4f46e5",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto",
                fontSize: "20px",
                fontWeight: 700,
              }}
            >
              ◎
            </div>
            <div
              style={{
                fontSize: "17px",
                fontWeight: 700,
                color: "#111827",
                marginTop: "14px",
              }}
            >
              Job Description Analysis Locked
            </div>
            <div
              style={{
                fontSize: "13px",
                color: "#6b7280",
                lineHeight: 1.6,
                marginTop: "8px",
              }}
            >
              Add a job description during upload to unlock deep JD match analysis,
              skill gap coverage, and section-by-section fix planning.
            </div>
            <button
              type="button"
              onClick={() => resetAnalysis()}
              style={{
                marginTop: "20px",
                background: "#5b5fc7",
                color: "#ffffff",
                border: "none",
                borderRadius: "10px",
                padding: "10px 20px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 3px 0 #3a3d9a, 0 5px 12px rgba(91,95,199,0.25)",
              }}
            >
              Re-analyze with JD
            </button>
          </div>
        </div>
      </div>
    );
  }

  const gap = analysisResult.gap;
  const fixes = normalizeFixes(gap.priority_fixes).filter((fix) => fix.needs_change);
  const beforeScore = gap.jd_match_score_before ?? analysisResult.ats.score;
  const afterScore = gap.jd_match_score_after ?? analysisResult.ats.score;
  const missingSkillSet = new Set(
    fixes.flatMap((fix) => fix.missing_keywords.map((k) => k.trim())).filter(Boolean)
  );
  const missingSkills = Array.from(missingSkillSet);
  const presentSkills = analysisResult.resume.tech_stack.filter(
    (skill) =>
      !missingSkillSet.has(skill) &&
      !missingSkillSet.has(skill.toLowerCase()) &&
      !missingSkillSet.has(skill.toUpperCase())
  );

  const allPriorityFixes = normalizeFixes(gap.priority_fixes);
  const mustHaveFixes = fixes.slice(0, 3);
  const niceToHaveFixes = allPriorityFixes.filter((f) => !f.needs_change);
  const progressWidth = Math.max(0, Math.min(100, beforeScore));

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={pageContainerStyle(isMobile)}>
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
            ◎ Job Description Analysis
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
            Close the Gap
          </div>
        </div>

        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: "24px",
            padding: "32px",
            boxShadow: "0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)",
            marginBottom: "20px",
            display: isMobile ? "flex" : "grid",
            flexDirection: isMobile ? "column" : undefined,
            gridTemplateColumns: isMobile ? undefined : "1fr 1fr",
            gap: isMobile ? "16px" : "40px",
          }}
        >
          <div>
            <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "8px" }}>
              Current JD Match
            </div>
            <div
              style={{
                fontSize: "48px",
                fontWeight: 800,
                color: "#5b5fc7",
                lineHeight: 1,
              }}
            >
              {beforeScore}%
            </div>
            <div
              style={{
                marginTop: "14px",
                height: "10px",
                background: "#f3f4f6",
                borderRadius: "999px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${progressWidth}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #5b5fc7, #7c3aed)",
                }}
              />
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "8px" }}>
              After Fixes:{" "}
              <span style={{ fontWeight: 700, color: "#16a34a" }}>{afterScore}%</span>
            </div>
          </div>

          <div>
            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "#374151",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "8px",
              }}
            >
              Must-Have Fixes
            </div>
            {mustHaveFixes.length > 0 ? (
              mustHaveFixes.map((fix) => (
                <div
                  key={`must-${fix.section}`}
                  style={{ fontSize: "13px", color: "#374151", lineHeight: 1.7 }}
                >
                  ✓ {toTitle(fix.section)} — {fix.gap_reason}
                </div>
              ))
            ) : (
              <div style={{ fontSize: "13px", color: "#6b7280" }}>No critical gaps.</div>
            )}

            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "#374151",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginTop: "12px",
                marginBottom: "8px",
              }}
            >
              Nice-to-Have Fixes
            </div>
            {niceToHaveFixes.length > 0 ? (
              niceToHaveFixes.map((fix) => (
                <div
                  key={`nice-${fix.section}`}
                  style={{ fontSize: "13px", color: "#6b7280", lineHeight: 1.7 }}
                >
                  • {toTitle(fix.section)}
                </div>
              ))
            ) : (
              <div style={{ fontSize: "13px", color: "#9ca3af" }}>
                Everything else already aligned.
              </div>
            )}
          </div>
        </div>

        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: "18px",
            padding: "28px 24px",
            boxShadow: "0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)",
            marginBottom: "20px",
          }}
        >
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
            Skills Coverage
          </div>
          <div
            style={{
              marginTop: "14px",
              display: isMobile ? "flex" : "grid",
              flexDirection: isMobile ? "column" : undefined,
              gridTemplateColumns: isMobile ? undefined : "1fr 1fr",
              gap: isMobile ? "16px" : "40px",
            }}
          >
            <div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "#16a34a", marginBottom: "8px" }}>
                Present Skills
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {presentSkills.map((skill) => (
                  <div
                    key={skill}
                    style={{
                      background: "#dcfce7",
                      border: "1px solid #bbf7d0",
                      color: "#16a34a",
                      borderRadius: "999px",
                      padding: "3px 10px",
                      fontSize: "11px",
                      fontWeight: 600,
                    }}
                  >
                    {skill}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "#dc2626", marginBottom: "8px" }}>
                Missing Skills
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {missingSkills.map((skill) => (
                  <div
                    key={skill}
                    style={{
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#dc2626",
                      borderRadius: "999px",
                      padding: "3px 10px",
                      fontSize: "11px",
                      fontWeight: 600,
                    }}
                  >
                    {skill}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>


        {fixes.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "#6b7280",
                textTransform: "uppercase" as const,
                letterSpacing: "0.07em",
                marginBottom: "14px",
              }}
            >
              {fixes.length} gap{fixes.length !== 1 ? "s" : ""} identified
            </div>
            {fixes.map((fix, index) => {
              const isHighPriority = index < 2;
              return (
                <div
                  key={`gap-${fix.section}-${index}`}
                  style={{
                    background: "#ffffff",
                    border: "1.5px solid #e5e7eb",
                    borderRadius: "16px",
                    padding: "16px 20px",
                    marginBottom: "10px",
                    boxShadow: "0 2px 0 #e5e7eb, 0 4px 8px rgba(0,0,0,0.03)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <div
                      style={{
                        background: "#eef2ff",
                        border: "1px solid #c7d2fe",
                        color: "#4f46e5",
                        borderRadius: "999px",
                        padding: "2px 9px",
                        fontSize: "11px",
                        fontWeight: 700,
                      }}
                    >
                      {toTitle(fix.section)}
                    </div>
                    {isHighPriority && (
                      <div
                        style={{
                          background: "#fff7ed",
                          border: "1px solid #fed7aa",
                          color: "#c2410c",
                          borderRadius: "999px",
                          padding: "2px 9px",
                          fontSize: "11px",
                          fontWeight: 700,
                        }}
                      >
                        High priority
                      </div>
                    )}
                  </div>
                  <div
                    style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: "#111827",
                      lineHeight: 1.5,
                      marginBottom: fix.missing_keywords?.length > 0 ? "10px" : 0,
                    }}
                  >
                    {fix.gap_reason}
                  </div>
                  {fix.missing_keywords?.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {fix.missing_keywords.map((kw) => (
                        <div
                          key={kw}
                          style={{
                            background: "#fef2f2",
                            border: "1px solid #fecaca",
                            color: "#dc2626",
                            borderRadius: "999px",
                            padding: "2px 9px",
                            fontSize: "11px",
                            fontWeight: 600,
                          }}
                        >
                          {kw}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div
          style={{
            background: "#dcfce7",
            border: "1.5px solid #bbf7d0",
            borderRadius: "16px",
            padding: "24px",
          }}
        >
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
            Action Plan
          </div>
          <div style={{ marginTop: "10px" }}>
            {fixes.slice(0, 3).map((fix, i) => (
              <div
                key={`plan-${fix.section}-${i}`}
                style={{ fontSize: "13px", color: "#374151", lineHeight: 1.7 }}
              >
                {i + 1}. {fix.gap_reason}
              </div>
            ))}
          </div>

          <div
            style={{
              background: "#f5f0ff",
              border: "1.5px solid #e9d5ff",
              borderRadius: "14px",
              padding: "20px 24px",
              marginTop: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "16px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <div
                style={{
                  fontSize: "14px",
                  fontWeight: 700,
                  color: "#5b21b6",
                  marginBottom: "3px",
                }}
              >
                Ready to apply these fixes?
              </div>
              <div style={{ fontSize: "13px", color: "#6d28d9" }}>
                Patches are waiting in the Fixes tab — estimated improvement shown there.
              </div>
            </div>
            <button
              type="button"
              onClick={() => onTabChange("fixes", undefined)}
              style={{
                background: "#5b5fc7",
                color: "#fff",
                border: "none",
                borderRadius: "12px",
                padding: "13px 24px",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 4px 0 #3a3d9a",
                whiteSpace: "nowrap",
              }}
            >
              Go to Fixes →
            </button>
          </div>
        </div>

        <DataSourceNotice tab="gap" />
      </div>
    </div>
  );
}
