import { useEffect, useState } from "react";

import type { PriorityFix } from "./types";
import DataSourceNotice from "./components/DataSourceNotice";
import { useWindowSize } from "./hooks/useWindowSize";
import { useResumeStore } from "./store/useResumeStore";

interface EvaluationDashboardProps {
  onTabChange?: (tab: string) => void;
}

interface ActionItem {
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  gainLabel: string;
  gainType: "ats" | "jd";
  buttonLabel: string;
  targetTab: string;
}

function deriveButtonLabel(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("metric") || t.includes("quantif") || t.includes("number") || t.includes("achievement"))
    return "Add Metrics ↗";
  if (t.includes("keyword") || t.includes("summary") || t.includes("skill"))
    return "Fix Keywords ↗";
  if (t.includes("bullet") || t.includes("format") || t.includes("spacing") || t.includes("header"))
    return "Fix Format ↗";
  if (t.includes("experience") || t.includes("role") || t.includes("impact"))
    return "Fix Experience ↗";
  return "View Fix ↗";
}

export function EvaluationDashboard({ onTabChange }: EvaluationDashboardProps) {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const { isMobile, isTablet } = useWindowSize();
  const [barsAnimated, setBarsAnimated] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setBarsAnimated(true), 100);
    return () => window.clearTimeout(t);
  }, []);

  if (!analysisResult) {
    return <SkeletonLoader />;
  }

  const hasJD = Boolean(analysisResult.gap?.jd_match_score_before);
  const hasSim = Boolean(analysisResult.sim);
  const hasPositioning = Boolean(analysisResult.positioning);

  const bd = analysisResult.ats.breakdown;
  const atsScore = analysisResult.ats.score;
  const potentialGain =
    bd.impact_metrics < 12 ? 15 :
    bd.keyword_match  < 12 ? 12 :
    bd.formatting     < 12 ? 10 : 8;
  const potentialATS = Math.min(100, atsScore + potentialGain);

  const jdGain = hasJD && analysisResult.gap?.jd_match_score_after
    ? analysisResult.gap.jd_match_score_after - (analysisResult.gap.jd_match_score_before ?? 0)
    : 0;

  const missingCount = hasJD
    ? ((analysisResult.gap?.priority_fixes as PriorityFix[] | undefined) ?? [])
        .filter((p) => p.needs_change).length
    : 0;

  const pctScore = analysisResult.percentile?.percentile ?? null;
  const pctLabel = analysisResult.percentile?.label ?? "Calculating...";
  const pctGain = pctScore !== null ? Math.min(99 - pctScore, 23) : null;

  const shortlistPct = Math.round((analysisResult.sim?.shortlist_rate ?? 0) * 100);
  const atsCount = useCountUp(atsScore);
  const jdCount = useCountUp(analysisResult.gap?.jd_match_score_before ?? 0);
  const pctCount = useCountUp(pctScore ?? 0);
  const shortlistCount = useCountUp(shortlistPct);
  const shortlistColor = shortlistPct >= 50 ? "#16a34a" : shortlistPct >= 30 ? "#d97706" : "#dc2626";
  const shortlistLabel = shortlistPct >= 50 ? "Good" : shortlistPct >= 30 ? "Improve to High" : "Critical";
  const shortlistLabelColors: Record<string, { bg: string; color: string }> = {
    Good: { bg: "#dcfce7", color: "#16a34a" },
    "Improve to High": { bg: "#fefce8", color: "#d97706" },
    Critical: { bg: "#fef2f2", color: "#dc2626" },
  };

  // Action items construction
  const atsActions = (analysisResult.ats.ats_issues ?? []).slice(0, 2).map((issue, i) => {
    const gainAmount =
      bd.impact_metrics < 12 ? 15 :
      bd.keyword_match  < 12 ? 12 :
      bd.formatting     < 12 ? 10 : 8;
    return {
      priority: i === 0 ? ("high" as const) : ("medium" as const),
      title: issue.split(" — ")[0].split(" - ")[0],
      description: issue,
      gainLabel: `+${gainAmount} ATS`,
      gainType: "ats" as const,
      buttonLabel: deriveButtonLabel(issue),
      targetTab: "fixes",
    };
  });

  const jdGainPerFix = hasJD && analysisResult.gap?.jd_match_score_after
    ? Math.round(
        (analysisResult.gap.jd_match_score_after - (analysisResult.gap.jd_match_score_before ?? 0)) /
        Math.max(1, missingCount)
      )
    : 0;

  const gapActions = (hasJD
    ? ((analysisResult.gap?.priority_fixes as PriorityFix[] | undefined) ?? [])
        .filter((p) => p.needs_change)
        .slice(0, 2)
        .map((fix) => ({
          priority: "high" as const,
          title: fix.gap_reason,
          description: fix.rewrite_instruction,
          gainLabel: `+${jdGainPerFix} JD match`,
          gainType: "jd" as const,
          buttonLabel: deriveButtonLabel(fix.gap_reason),
          targetTab: "gap",
        }))
    : []) as ActionItem[];

  const actionItems = [...atsActions, ...gapActions].slice(0, 4);

  // ─── SECTION 3: Recruiter 6-sec scan ───
  const agencyRecruiter =
    analysisResult.sim?.personas.find(
      (p) =>
        p.persona.toLowerCase().includes("agency") ||
        p.persona.toLowerCase().includes("high-volume")
    ) ?? analysisResult.sim?.personas[0] ?? null;

  const shortlisted = agencyRecruiter?.shortlist_decision ?? false;

  const reasonItems = !shortlisted
    ? (agencyRecruiter?.rejection_reason ?? "")
        .split(/;\s*|\.\s+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 3)
    : (agencyRecruiter?.noticed ?? []).slice(0, 3);

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: "40px 32px 48px" }}>

        {/* ── SECTION 1: Page Header ── */}
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "6px",
            background: "#dcfce7", borderRadius: "999px",
            padding: "5px 14px", fontSize: "12px", fontWeight: 700, color: "#16a34a",
            marginBottom: "12px",
          }}>
            <span style={{ fontSize: "8px", lineHeight: 1 }}>●</span> Analysis Complete
          </div>
          <div style={{
            fontSize: "22px", fontWeight: 800, color: "#111827",
            letterSpacing: "-0.02em", marginBottom: "4px",
          }}>
            Your Resume Intelligence Report
          </div>
          <div style={{ fontSize: "14px", color: "#6b7280" }}>
            Resume analyzed successfully — here&apos;s what we found
          </div>
        </div>

        {/* ── SECTION 2: Score Cards Grid ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile
            ? "1fr"
            : isTablet
              ? "repeat(2, 1fr)"
              : hasJD && hasSim
                ? "repeat(4, 1fr)"
                : "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "28px",
        }}>
          {/* Card 1 — ATS Score */}
          <ScoreCard
            label="ATS Score"
            labelColor="#6366f1"
            score={atsCount}
            denomColor="#a5b4fc"
            hint={`You can reach ${potentialATS}`}
            deltaBadge={`↗ +${potentialATS - atsScore}`}
            infoText="ATS Score shows how well your resume passes applicant tracking systems based on keywords, formatting, readability, and impact."
          />

          {/* Card 2 — JD Match */}
          {hasJD && (
            <ScoreCard
              label="JD Match"
              labelColor="#7c3aed"
              score={jdCount}
              denomColor="#c4b5fd"
              hint={
                missingCount > 0
                  ? `Missing ${missingCount} key skill${missingCount !== 1 ? "s" : ""}`
                  : "Strong JD alignment"
              }
              deltaBadge={`↗ +${jdGain}`}
              infoText="JD Match shows how closely your resume aligns with the selected job description requirements."
            />
          )}

          {/* Card 3 — Market Percentile */}
          <ScoreCard
            label="Market Percentile"
            labelColor="#6366f1"
            score={pctCount}
            denomColor="#a5b4fc"
            hint={pctLabel}
            deltaBadge={pctGain !== null ? `↗ +${pctGain}` : undefined}
            infoText="Market Percentile compares your composite resume strength against similar candidates at your seniority level."
          />

          {/* Card 4 — Shortlist Probability */}
          {hasJD && hasSim && (
            <div style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "24px",
              boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
              position: "relative",
              display: "flex",
              flexDirection: "column",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "#6b7280" }}>
                  Shortlist Probability
                </span>
                <InfoTooltipButton infoText="Shortlist Probability estimates the chance that recruiters would move your profile to interview review." />
              </div>
              <div>
                <span style={{ fontSize: "42px", fontWeight: 800, color: shortlistColor, lineHeight: 1 }}>
                  {shortlistCount}%
                </span>
              </div>
              <div style={{
                display: "inline-flex", alignItems: "center",
                background: shortlistLabelColors[shortlistLabel].bg,
                color: shortlistLabelColors[shortlistLabel].color,
                borderRadius: "999px", padding: "3px 10px",
                fontSize: "11px", fontWeight: 700, marginTop: "6px",
              }}>
                {shortlistLabel}
              </div>
              <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                Based on {analysisResult.sim?.personas.length ?? 0} recruiter sim{(analysisResult.sim?.personas.length ?? 0) !== 1 ? "s" : ""}
              </div>
            </div>
          )}
        </div>

        {/* ── SECTION 3: Recruiter 6-Second Scan ── */}
        {hasSim && agencyRecruiter ? (
          <div style={{
            background: "#fff5f5",
            border: "1.5px solid #fecaca",
            borderRadius: "12px",
            padding: "20px 22px",
            marginBottom: "24px",
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", marginBottom: "12px" }}>
              <div style={{
                width: "22px", height: "22px", borderRadius: "50%", flexShrink: 0,
                background: "#fef2f2", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "12px", color: "#dc2626", fontWeight: 800, marginTop: "1px",
              }}>&#9888;</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: "#111827" }}>
                    Recruiter 6-Second Scan
                  </span>
                  <span style={{
                    background: "#fef2f2", color: "#dc2626",
                    borderRadius: "999px", padding: "3px 10px",
                    fontSize: "11px", fontWeight: 700,
                  }}>Critical Insight</span>
                </div>
                <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "2px" }}>
                  Based on 10,000+ hiring decisions
                </div>
              </div>
            </div>

            <div style={{
              background: shortlisted ? "#f0fdf4" : "#fef2f2",
              border: `1px solid ${shortlisted ? "#bbf7d0" : "#fecaca"}`,
              borderRadius: "10px", padding: "12px 16px",
              display: "flex", alignItems: "center", gap: "12px",
              marginBottom: "12px",
            }}>
              <div style={{
                width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0,
                background: shortlisted ? "#16a34a" : "#dc2626",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "14px", fontWeight: 800, color: "#ffffff",
              }}>
                {shortlisted ? "✓" : "✗"}
              </div>
              <div>
                <div style={{
                  fontSize: "14px", fontWeight: 700,
                  color: shortlisted ? "#16a34a" : "#dc2626",
                }}>
                  Decision: {shortlisted ? "Shortlisted" : "Not Shortlisted"}
                </div>
                <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "2px" }}>
                  {shortlisted
                    ? `${shortlistPct}% chance of recruiter review`
                    : `${shortlistPct}% chance of recruiter review — below 50% threshold`}
                </div>
              </div>
            </div>

            <div style={{ fontSize: "12px", fontWeight: 700, color: "#374151", marginBottom: "8px" }}>
              {shortlisted ? "What recruiters noticed:" : "Top reasons for rejection:"}
            </div>

            {(() => {
              const icons = ["\u{1F3AF}", "\u{1F50D}", "\u{1F4CA}"];
              return (
                <>
                  {reasonItems.map((text, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "6px",
                    }}>
                      <span style={{ fontSize: "13px", flexShrink: 0 }}>{icons[i % icons.length]}</span>
                      <span style={{ fontSize: "13px", color: "#374151", lineHeight: 1.5 }}>{text}</span>
                    </div>
                  ))}
                </>
              );
            })()}

            <div style={{
              background: "#f0f9ff", border: "1px solid #bae6fd",
              borderRadius: "8px", padding: "12px 14px", marginTop: "12px",
            }}>
              <div style={{ fontSize: "12px", fontWeight: 700, color: "#0369a1", marginBottom: "4px" }}>
                {shortlisted ? "✨ Keep this up:" : "✨ What would change this decision:"}
              </div>
              <div style={{ fontSize: "12px", color: "#374151", lineHeight: 1.6 }}>
                {agencyRecruiter.flip_condition || analysisResult.sim?.most_critical_fix}
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            background: "#fff5f5",
            border: "1.5px solid #fecaca",
            borderRadius: "12px",
            padding: "20px 22px",
            marginBottom: "24px",
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
              <div style={{
                width: "22px", height: "22px", borderRadius: "50%", flexShrink: 0,
                background: "#fef2f2", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "12px", color: "#dc2626", fontWeight: 800, marginTop: "1px",
              }}>&#9888;</div>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 700, color: "#111827" }}>
                  Recruiter Scan
                </div>
                <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "2px" }}>
                  Add quantified achievements and role-specific keywords to increase shortlist probability.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── SECTION 4: Career Positioning ── */}
        {hasPositioning && analysisResult.positioning && (() => {
          const pos = analysisResult.positioning;
          return (
            <div style={{
              background: "linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)",
              borderRadius: "16px", padding: "24px 28px", marginBottom: "24px",
              display: "grid", gridTemplateColumns: "1fr auto", gap: "24px", alignItems: "center",
            }}>
              <div>
                <div style={{
                  fontSize: "11px", fontWeight: 700, color: "rgba(255,255,255,0.65)",
                  letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: "8px",
                }}>
                  Career Positioning
                </div>
                <div style={{
                  fontSize: "15px", fontWeight: 700, color: "#ffffff",
                  lineHeight: 1.4, marginBottom: "6px",
                }}>
                  {pos.positioning_line}
                </div>
                <div style={{
                  fontSize: "13px", color: "rgba(255,255,255,0.85)",
                  lineHeight: 1.5, marginBottom: "10px",
                }}>
                  {pos.cta_line}
                </div>
                <div style={{
                  fontSize: "12px", color: "rgba(255,255,255,0.65)",
                  lineHeight: 1.5, fontStyle: "italic",
                }}>
                  {pos.rank_rationale}
                </div>
              </div>
              <div style={{
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.25)",
                borderRadius: "12px", padding: "16px 20px",
                backdropFilter: "blur(8px)",
                minWidth: "200px", flexShrink: 0,
              }}>
                <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.65)", fontWeight: 600 }}>
                  Current Range
                </div>
                <div style={{ fontSize: "18px", fontWeight: 800, color: "#ffffff", marginTop: "2px" }}>
                  ₹{pos.current_ctc_min}–{pos.current_ctc_max} LPA
                </div>
                <div style={{ borderTop: "1px solid rgba(255,255,255,0.2)", margin: "10px 0" }} />
                <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.65)", fontWeight: 600 }}>
                  After {pos.changes_needed} Fix{pos.changes_needed !== 1 ? "es" : ""}
                </div>
                <div style={{ fontSize: "18px", fontWeight: 800, color: "#86efac", marginTop: "2px" }}>
                  ₹{pos.potential_ctc_min}–{pos.potential_ctc_max} LPA
                </div>
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: "4px",
                  background: "rgba(134,239,172,0.2)", border: "1px solid rgba(134,239,172,0.35)",
                  borderRadius: "999px", padding: "4px 12px",
                  fontSize: "12px", fontWeight: 700, color: "#86efac",
                  marginTop: "8px",
                }}>
                  ↗ +₹{pos.ctc_delta_min}–{pos.ctc_delta_max} LPA/year
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── SECTION 5: Priority Actions ── */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px", marginBottom: "18px" }}>
          <div style={{
            width: "42px", height: "42px", borderRadius: "12px",
            background: "#fff7ed",
            display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
          }}>
            <span style={{ fontSize: "20px" }}>{"\u{1F3AF}"}</span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "17px", fontWeight: 700, color: "#111827", letterSpacing: "-0.01em" }}>
              Priority Actions
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "2px" }}>
              Fix these first to maximize your score
            </div>
          </div>
          <div style={{
            background: "#f3f4f6", borderRadius: "999px", padding: "4px 12px",
            fontSize: "12px", fontWeight: 600, color: "#374151",
          }}>
            {actionItems.length} opportunities found
          </div>
        </div>

        {actionItems.map((item, idx) => (
          <PriorityActionCard key={idx} item={item} onTabChange={onTabChange} />
        ))}

        <hr style={{ border: "none", borderTop: "1.5px solid #e5e7eb", margin: "20px 0" }} />

        {/* ── SECTION 6: ATS Score Breakdown ── */}
        <div style={{
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: "12px",
          padding: "20px 22px",
          marginBottom: "0",
        }}>
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827", marginBottom: "16px" }}>
            ATS Analysis Breakdown
          </div>

          {[
            { label: "Keyword Match", value: bd.keyword_match },
            { label: "Formatting & Structure", value: bd.formatting },
            { label: "Readability & Clarity", value: bd.readability },
            { label: "Impact & Achievements", value: bd.impact_metrics },
          ].map(({ label, value }) => {
            const getColor = (v: number) =>
              v >= 18 ? "#16a34a" : v >= 12 ? "#6366f1" : "#dc2626";
            const color = getColor(value);
            return (
              <div key={label} style={{
                display: "flex", alignItems: "center", gap: "12px", marginBottom: "10px",
              }}>
                <div style={{
                  flex: "0 0 170px", fontSize: "12px", fontWeight: 600, color: "#374151",
                }}>
                  {label}
                </div>
                <div style={{
                  flex: 1, height: "8px", background: "#f3f4f6",
                  borderRadius: "999px", overflow: "hidden",
                }}>
                  <div style={{
                    height: "100%",
                    width: barsAnimated ? `${Math.round((value / 25) * 100)}%` : "0%",
                    background: color,
                    borderRadius: "999px",
                    transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
                  }} />
                </div>
                <div style={{
                  flex: "0 0 36px", textAlign: "right",
                  fontSize: "12px", fontWeight: 700,
                  color,
                }}>
                  {value}/25
                </div>
              </div>
            );
          })}

          {analysisResult.ats.ats_issues.length > 0 && (
            <div style={{ marginTop: "16px" }}>
              <div style={{
                fontSize: "12px", fontWeight: 700, color: "#374151", marginBottom: "8px",
              }}>
                Issues Detected
              </div>
              {analysisResult.ats.ats_issues.map((issue, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "6px",
                }}>
                  <div style={{
                    width: "18px", height: "18px", borderRadius: "50%", flexShrink: 0,
                    background: "#fef3c7", color: "#d97706",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "10px", fontWeight: 800, marginTop: "1px",
                  }}>&#9888;</div>
                  <div style={{ fontSize: "12px", color: "#6b7280", lineHeight: 1.5 }}>
                    {issue}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <DataSourceNotice tab="overview" />
      </div>
    </div>
  );
}

/* ─── Sub-components (inline, same file) ─── */

interface ScoreCardProps {
  label: string;
  labelColor: string;
  score: number | null;
  denomColor: string;
  hint: string;
  deltaBadge?: string;
  infoText?: string;
}

function InfoTooltipButton({ infoText }: { infoText: string }) {
  const [tooltipOpen, setTooltipOpen] = useState(false);

  return (
    <div
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setTooltipOpen(true)}
      onMouseLeave={() => setTooltipOpen(false)}
    >
      <button
        type="button"
        onClick={(e) => e.preventDefault()}
        aria-label="Show score info"
        style={{
          width: "16px",
          height: "16px",
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          lineHeight: 1,
        }}
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <circle cx="7" cy="7" r="6.25" stroke="#9ca3af" strokeWidth="1.25" />
          <text
            x="7"
            y="11"
            textAnchor="middle"
            fontSize="8.5"
            fontWeight="700"
            fill="#9ca3af"
            fontFamily="inherit"
          >
            i
          </text>
        </svg>
      </button>
      {tooltipOpen && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: "50%",
            transform: "translateX(-50%)",
            background: "#111827",
            color: "#ffffff",
            fontSize: "12px",
            fontWeight: 400,
            lineHeight: 1.5,
            borderRadius: "8px",
            padding: "8px 12px",
            width: "180px",
            zIndex: 50,
            boxShadow: "0 4px 12px rgba(0,0,0,0.18)",
            pointerEvents: "none",
          }}
        >
          {infoText}
        </div>
      )}
    </div>
  );
}

function ScoreCard({
  label,
  labelColor,
  score,
  denomColor,
  hint,
  deltaBadge,
  infoText,
}: ScoreCardProps) {
  return (
    <div style={{
      background: "#ffffff",
      border: "1.5px solid #e5e7eb",
      borderRadius: "16px",
      padding: "24px",
      boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
      position: "relative",
      display: "flex",
      flexDirection: "column",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
        <span style={{ fontSize: "13px", fontWeight: 600, color: "#6b7280" }}>
          {label}
        </span>
        {infoText && <InfoTooltipButton infoText={infoText} />}
      </div>
      <div>
        <span style={{ fontSize: "42px", fontWeight: 800, color: labelColor, lineHeight: 1 }}>
          {score ?? "--"}
        </span>
        <span style={{ fontSize: "16px", color: denomColor }}>
          /100
        </span>
      </div>
      <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "6px" }}>
        {hint}
      </div>
      {deltaBadge && (
        <div style={{
          position: "absolute", top: "16px", right: "16px",
          display: "inline-flex", alignItems: "center", gap: "3px",
          background: "#dcfce7", borderRadius: "999px",
          padding: "3px 8px", fontSize: "11px", fontWeight: 700, color: "#16a34a",
        }}>
          {deltaBadge}
        </div>
      )}
    </div>
  );
}

function useCountUp(target: number, duration = 1200): number {
  const [current, setCurrent] = useState(0);
  useEffect(() => {
    if (target === 0) {
      setCurrent(0);
      return;
    }
    let start: number | null = null;
    let raf = 0;
    const step = (timestamp: number) => {
      if (!start) start = timestamp;
      const elapsed = timestamp - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(eased * target));
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);
  return current;
}

function PriorityActionCard({
  item,
  onTabChange,
}: {
  item: ActionItem;
  onTabChange?: (tab: string) => void;
}) {
  const styles = {
    high:   { cardBg: "#fff5f5", cardBorder: "#fecaca", pillBg: "#fef2f2", pillColor: "#dc2626", pillText: "● High Impact", btnBg: "#dc2626" },
    medium: { cardBg: "#fffbeb", cardBorder: "#fde68a", pillBg: "#fefce8", pillColor: "#d97706", pillText: "⚡ Medium",      btnBg: "#d97706" },
    low:    { cardBg: "#f8f8f8", cardBorder: "#e5e7eb", pillBg: "#f3f4f6", pillColor: "#6b7280", pillText: "○ Low",         btnBg: "#6b7280" },
  }[item.priority];

  const gainStyles = item.gainType === "ats"
    ? { bg: "#dcfce7", color: "#16a34a" }
    : { bg: "#eef2ff", color: "#6366f1" };

  const handleMouseDown = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.style.transform = "translateY(2px)";
  };
  const handleMouseUp = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.style.transform = "translateY(0)";
  };

  return (
    <div style={{
      background: styles.cardBg,
      border: `1.5px solid ${styles.cardBorder}`,
      borderRadius: "10px", padding: "16px 18px", marginBottom: "10px",
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px",
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "5px" }}>
          <span style={{
            background: styles.pillBg, color: styles.pillColor,
            borderRadius: "999px", padding: "3px 10px",
            fontSize: "11px", fontWeight: 700,
          }}>
            {styles.pillText}
          </span>
          <span style={{
            background: gainStyles.bg, color: gainStyles.color,
            borderRadius: "999px", padding: "3px 10px",
            fontSize: "11px", fontWeight: 700,
          }}>
            {item.gainLabel}
          </span>
        </div>
        <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827" }}>
          {item.title}
        </div>
        <div style={{ fontSize: "12px", color: "#6b7280", marginTop: "2px", lineHeight: 1.5 }}>
          {item.description}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onTabChange?.(item.targetTab)}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          background: styles.btnBg, color: "#ffffff",
          border: "none", borderRadius: "8px",
          padding: "8px 14px", fontSize: "12px", fontWeight: 700,
          cursor: "pointer", flexShrink: 0, whiteSpace: "nowrap",
          boxShadow: "0 2px 0 rgba(0,0,0,0.15)",
          transition: "transform 0.1s",
        }}
      >
        {item.buttonLabel}
      </button>
    </div>
  );
}

function SkeletonLoader() {
  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: "40px 32px 48px" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "16px",
          marginBottom: "28px",
        }}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} style={{
              borderRadius: "16px", height: "120px",
              background: "linear-gradient(90deg, #f3f4f6 25%, #e9ebf0 50%, #f3f4f6 75%)",
              backgroundSize: "200% 100%",
              animation: "shimmer 1.5s infinite",
            }} />
          ))}
        </div>
        {[0, 1].map((i) => (
          <div key={`bar-${i}`} style={{
            borderRadius: "16px", height: "60px", marginBottom: "12px",
            background: "linear-gradient(90deg, #f3f4f6 25%, #e9ebf0 50%, #f3f4f6 75%)",
            backgroundSize: "200% 100%",
            animation: "shimmer 1.5s infinite",
          }} />
        ))}
      </div>
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>
    </div>
  );
}

export default EvaluationDashboard;
