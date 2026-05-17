import { useState } from "react";

import { applyPatches, getResumeDownloadUrl, rollbackPatch } from "../api/client";
import { useWindowSize } from "../hooks/useWindowSize";
import { useResumeStore } from "../store/useResumeStore";
import type { PriorityFix, ResumePatch } from "../types";
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

export default function GapCloser() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const jobId = useResumeStore((s) => s.jobId);
  const selectedStyle = useResumeStore((s) => s.selectedStyle);
  const resetAnalysis = useResumeStore((s) => s.resetAnalysis);
  const [isGeneratePressed, setIsGeneratePressed] = useState(false);
  const [patches, setPatches] = useState<ResumePatch[]>(analysisResult?.patches || []);
  const [applying, setApplying] = useState<string | null>(null);
  const [patchScores, setPatchScores] = useState<Record<string, number | null>>({});
  const { isMobile } = useWindowSize();

  const handleApplyPatch = async (patch: ResumePatch) => {
    if (patch.risk === "needs_confirmation") {
      if (!confirm(`This patch may have been invented by AI.\n\n${patch.issue_detected}\n\nConfirm?`)) {
        return;
      }
    }
    setApplying(patch.patch_id);
    try {
      const result = await applyPatches(
        jobId || analysisResult?.job_id || "",
        [patch.patch_id],
        patch.risk === "needs_confirmation"
      );
      setPatches((prev) =>
        prev.map((p) =>
          p.patch_id === patch.patch_id
            ? { ...p, status: "applied" }
            : p
        )
      );
      if (result.score) {
        setPatchScores((prev) => ({
          ...prev,
          [patch.patch_id]: result.score.score,
        }));
      }
    } catch (error) {
      alert(`Error applying patch: ${error}`);
    } finally {
      setApplying(null);
    }
  };

  const handleRollback = async (patchId: string) => {
    try {
      await rollbackPatch(jobId || analysisResult?.job_id || "", patchId);
      setPatches((prev) =>
        prev.map((p) =>
          p.patch_id === patchId
            ? { ...p, status: "rolled_back" }
            : p
        )
      );
      setPatchScores((prev) => {
        const newScores = { ...prev };
        delete newScores[patchId];
        return newScores;
      });
    } catch (error) {
      alert(`Error rolling back patch: ${error}`);
    }
  };

  if (!analysisResult) {
    return null;
  }

  if (!analysisResult.gap) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div
          style={{
            maxWidth: "960px",
            margin: "0 auto",
            padding: "40px 32px 48px",
          }}
        >
          <div
            style={{
              maxWidth: "620px",
              margin: "0 auto",
              border: "1.5px solid #e5e7eb",
              borderRadius: "24px",
              padding: "40px",
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
                background: "#6366f1",
                color: "#ffffff",
                border: "none",
                borderRadius: "10px",
                padding: "10px 20px",
                fontSize: "13px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)",
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

  const handleGenerate = () => {
    if (!analysisResult.rewrites) {
      window.alert("Rewrites unavailable. Re-run analysis first.");
      return;
    }
    const id = jobId ?? analysisResult.job_id;
    if (!id) {
      window.alert("Session id unavailable. Download skipped.");
      return;
    }
    window.open(
      getResumeDownloadUrl(id, selectedStyle),
      "_blank",
      "noopener,noreferrer"
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div
        style={{
          maxWidth: "960px",
          margin: "0 auto",
          padding: isMobile ? "40px 16px 48px" : "40px 32px 48px",
        }}
      >
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
                color: "#6366f1",
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
                  background: "linear-gradient(90deg, #6366f1, #7c3aed)",
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

        {patches.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827", marginBottom: "16px" }}>
              Intelligent Patches
            </div>
            {patches.map((patch) => (
              <div
                key={patch.patch_id}
                style={{
                  background: "#ffffff",
                  border: "1.5px solid #e5e7eb",
                  borderRadius: "16px",
                  padding: "16px",
                  boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
                  marginBottom: "12px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    marginBottom: "12px",
                    gap: "12px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#374151", marginBottom: "4px" }}>
                      {patch.issue_detected}
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280" }}>
                      {patch.section} • {patch.op}
                    </div>
                  </div>
                  <div
                    style={{
                      background: patch.risk === "safe" ? "#dcfce7" : "#fef3c7",
                      border: `1px solid ${patch.risk === "safe" ? "#bbf7d0" : "#fcd34d"}`,
                      color: patch.risk === "safe" ? "#16a34a" : "#d97706",
                      borderRadius: "6px",
                      padding: "4px 8px",
                      fontSize: "11px",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {patch.risk === "safe" ? "Safe" : "Needs Review"}
                    {patch.hallucination_risk && " ⚠️"}
                  </div>
                </div>

                <div style={{ marginBottom: "12px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", marginBottom: "4px" }}>
                    Before (red)
                  </div>
                  <div
                    style={{
                      background: "#fef2f2",
                      border: "1px solid #fecaca",
                      color: "#991b1b",
                      borderRadius: "6px",
                      padding: "8px",
                      fontFamily: "monospace",
                      fontSize: "12px",
                      wordBreak: "break-word",
                      minHeight: "32px",
                    }}
                  >
                    {patch.original_text || "[Empty]"}
                  </div>
                </div>

                <div style={{ marginBottom: "12px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 600, color: "#6b7280", marginBottom: "4px" }}>
                    After (green)
                  </div>
                  <div
                    style={{
                      background: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      color: "#166534",
                      borderRadius: "6px",
                      padding: "8px",
                      fontFamily: "monospace",
                      fontSize: "12px",
                      wordBreak: "break-word",
                      minHeight: "32px",
                    }}
                  >
                    {patch.replacement_text}
                  </div>
                </div>

                <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "12px", fontStyle: "italic" }}>
                  Why: {patch.fix_rationale}
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "8px",
                    flexWrap: "wrap",
                  }}
                >
                  {patch.status === "pending" && (
                    <>
                      <button
                        onClick={() => handleApplyPatch(patch)}
                        disabled={applying === patch.patch_id}
                        style={{
                          background: "#6366f1",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: applying === patch.patch_id ? "not-allowed" : "pointer",
                          opacity: applying === patch.patch_id ? 0.6 : 1,
                          boxShadow: "0 2px 0 #4338ca",
                        }}
                      >
                        {applying === patch.patch_id ? "Applying..." : "Apply"}
                      </button>
                      <button
                        onClick={() => {
                          setPatches((prev) =>
                            prev.map((p) =>
                              p.patch_id === patch.patch_id
                                ? { ...p, status: "rejected" }
                                : p
                            )
                          );
                        }}
                        style={{
                          background: "#f3f4f6",
                          color: "#374151",
                          border: "1px solid #d1d5db",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Skip
                      </button>
                    </>
                  )}
                  {patch.status === "applied" && (
                    <>
                      <div
                        style={{
                          background: "#dcfce7",
                          border: "1px solid #bbf7d0",
                          color: "#16a34a",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          fontSize: "11px",
                          fontWeight: 600,
                        }}
                      >
                        ✓ Applied
                      </div>
                      {patchScores[patch.patch_id] && (
                        <div
                          style={{
                            background: "#eef2ff",
                            border: "1px solid #c7d2fe",
                            color: "#4f46e5",
                            borderRadius: "6px",
                            padding: "8px 12px",
                            fontSize: "11px",
                            fontWeight: 600,
                          }}
                        >
                          Score: {patchScores[patch.patch_id]}
                        </div>
                      )}
                      <button
                        onClick={() => handleRollback(patch.patch_id)}
                        style={{
                          background: "#fee2e2",
                          color: "#991b1b",
                          border: "1px solid #fecaca",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Undo
                      </button>
                    </>
                  )}
                  {patch.status === "rejected" && (
                    <div
                      style={{
                        background: "#f3f4f6",
                        border: "1px solid #d1d5db",
                        color: "#6b7280",
                        borderRadius: "6px",
                        padding: "8px 12px",
                        fontSize: "11px",
                        fontWeight: 600,
                      }}
                    >
                      Skipped
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginBottom: "20px" }}>
          {fixes.map((fix, index) => {
            const impact = index < 2 ? "High" : "Medium";
            const impactColor = impact === "High"
              ? { bg: "#fff7ed", border: "#fed7aa", color: "#d97706" }
              : { bg: "#fefce8", border: "#fde68a", color: "#d97706" };

            return (
              <div
                key={`${fix.section}-${index}`}
                style={{
                  background: "#ffffff",
                  border: "1.5px solid #e5e7eb",
                  borderRadius: "16px",
                  padding: "20px",
                  boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
                  marginBottom: "16px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "10px",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <div
                    style={{
                      background: "#eef2ff",
                      border: "1px solid #c7d2fe",
                      color: "#4f46e5",
                      borderRadius: "999px",
                      padding: "3px 10px",
                      fontSize: "11px",
                      fontWeight: 700,
                    }}
                  >
                    {toTitle(fix.section)}
                  </div>
                  <div
                    style={{
                      background: impactColor.bg,
                      border: `1px solid ${impactColor.border}`,
                      color: impactColor.color,
                      borderRadius: "999px",
                      padding: "3px 10px",
                      fontSize: "11px",
                      fontWeight: 700,
                    }}
                  >
                    {impact} Impact
                  </div>
                </div>
                <div
                  style={{
                    fontSize: "15px",
                    fontWeight: 700,
                    color: "#111827",
                    marginBottom: "8px",
                  }}
                >
                  {fix.gap_reason}
                </div>
                <div style={{ fontSize: "13px", color: "#4b5563", lineHeight: 1.6 }}>
                  {fix.rewrite_instruction}
                </div>
                {fix.missing_keywords.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "12px" }}>
                    {fix.missing_keywords.map((keyword) => (
                      <div
                        key={`${fix.section}-${keyword}`}
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
                        {keyword}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>

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

          <button
            type="button"
            onClick={handleGenerate}
            onMouseDown={() => setIsGeneratePressed(true)}
            onMouseUp={() => setIsGeneratePressed(false)}
            onMouseLeave={() => setIsGeneratePressed(false)}
            style={{
              marginTop: "16px",
              background: "#6366f1",
              color: "#ffffff",
              border: "none",
              borderRadius: "12px",
              padding: "12px 24px",
              fontSize: "14px",
              fontWeight: 700,
              cursor: "pointer",
              transform: isGeneratePressed ? "translateY(3px)" : "translateY(0)",
              boxShadow: isGeneratePressed
                ? "0 1px 0 #4338ca"
                : "0 4px 0 #4338ca, 0 6px 16px rgba(99,102,241,0.25)",
              transition: "transform 0.1s, box-shadow 0.1s",
            }}
          >
            Generate Optimized Resume
          </button>
        </div>

        <DataSourceNotice tab="gap" />
      </div>
    </div>
  );
}
