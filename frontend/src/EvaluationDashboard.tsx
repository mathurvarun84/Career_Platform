import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";

import { downloadResumeReport, getDownloadVerification } from "./api/client";
import type { ATSDimensionDetail, DownloadVerification, PriorityFix } from "./types";
import DataSourceNotice from "./components/DataSourceNotice";
import { QuickReactionBanner } from "./components/feedback/QuickReactionBanner";
import { useWindowSize } from "./hooks/useWindowSize";
import { pageContainerStyle } from "./utils/pageLayout";
import { useResumeStore } from "./store/useResumeStore";
import { hasJobDescription } from "./utils/hasJobDescription";
import { T } from "./tokens";
import CompanyReadinessCard from "./components/CompanyReadiness/CompanyReadinessCard";
import CompanySelector from "./components/CompanyReadiness/CompanySelector";
import ReadinessBreakdown from "./components/CompanyReadiness/ReadinessBreakdown";

interface EvaluationDashboardProps {
  onTabChange?: (tab: string) => void;
}

interface ActionItem {
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  gainLabel: string;
  gainType: "ats" | "jd";
  linksToGap: boolean;
  targetTab: "fixes" | "gap";
}

const detailOrder = ["keyword_match", "formatting", "readability", "impact_metrics"] as const;

const detailFallbackMeta: Record<
  (typeof detailOrder)[number],
  { label: string; icon: string; benchmark: number }
> = {
  keyword_match: { label: "Keyword Match", icon: "🔑", benchmark: 20 },
  formatting: { label: "Formatting", icon: "📐", benchmark: 21 },
  readability: { label: "Readability", icon: "📖", benchmark: 19 },
  impact_metrics: { label: "Impact & Metrics", icon: "📊", benchmark: 18 },
};

function ShimmerBlock({ width, height }: { width: string | number; height: string | number }) {
  return (
    <div style={{
      width,
      height,
      borderRadius: 6,
      background: 'linear-gradient(90deg, #f0f0f8 25%, #e8e8f0 50%, #f0f0f8 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.4s infinite linear',
    }} />
  );
}

function getDimensionDetails(
  details: ATSDimensionDetail[] | undefined,
  breakdown: {
    keyword_match: number;
    formatting: number;
    readability: number;
    impact_metrics: number;
  }
): ATSDimensionDetail[] {
  if (details && details.length === 4) {
    return details;
  }

  return detailOrder.map((key) => {
    const score = breakdown[key];
    const benchmark = detailFallbackMeta[key].benchmark;
    const gap = Math.max(0, benchmark - score);
    return {
      score,
      benchmark,
      gap,
      gap_reason: gap === 0
        ? "At benchmark for this dimension."
        : "Below benchmark — apply targeted fixes in this dimension.",
      label: detailFallbackMeta[key].label,
      icon: detailFallbackMeta[key].icon,
    };
  });
}

export function EvaluationDashboard({ onTabChange }: EvaluationDashboardProps) {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const baselineAts = useResumeStore((s) => s.baselineAts);
  const jobId = useResumeStore((s) => s.jobId);
  const selectedStyle = useResumeStore((s) => s.selectedStyle);
  const isLoading = useResumeStore((s) => s.isLoading);
  const resetAnalysis = useResumeStore((s) => s.resetAnalysis);
  const feedbackState = useResumeStore((s) => s.feedbackState);
  const clearActiveMoment = useResumeStore((s) => s.clearActiveMoment);
  const companyReadiness = useResumeStore((s) => s.companyReadiness);
  const companyReadinessSeniority = useResumeStore((s) => s.companyReadinessSeniority);
  const showReadinessBreakdown = useResumeStore((s) => s.showReadinessBreakdown);
  const setShowReadinessBreakdown = useResumeStore((s) => s.setShowReadinessBreakdown);
  const setActiveTab = useResumeStore((s) => s.setActiveTab);
  const { isMobile, isTablet } = useWindowSize();
  const [barsAnimated, setBarsAnimated] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadPressed, setIsDownloadPressed] = useState(false);
  const [verificationResult, setVerificationResult] = useState<DownloadVerification | null>(null);

  const atsScoreForCount = analysisResult?.ats.score ?? 0;
  const jdScoreForCount = analysisResult?.gap?.jd_match_score_before ?? 0;
  const pctScoreForCount = analysisResult?.percentile?.percentile ?? 0;

  const atsCount = useCountUp(atsScoreForCount);
  const jdCount = useCountUp(jdScoreForCount);
  const pctCount = useCountUp(pctScoreForCount);

  useEffect(() => {
    const t = window.setTimeout(() => setBarsAnimated(true), 100);
    return () => window.clearTimeout(t);
  }, []);


  if (!analysisResult) {
    return <SkeletonLoader />;
  }

  const hasJD = hasJobDescription(analysisResult.gap);
  const hasSim = Boolean(analysisResult.sim);
  const hasPositioning = Boolean(analysisResult.positioning);
  const targetRoleTitle =
    analysisResult.jd_intelligence?.role_title ?? "Target role";

  const SENIORITY_DISPLAY: Record<string, string> = {
    junior: "Junior",
    mid: "Mid-level",
    senior: "Senior",
    staff: "Staff / Lead",
    em: "Engineering Manager",
    senior_em: "Senior Engineering Manager",
    director: "Director",
  };
  const companyRoleTitle = companyReadinessSeniority
    ? (SENIORITY_DISPLAY[companyReadinessSeniority] ?? companyReadinessSeniority)
    : (analysisResult.jd_intelligence?.role_title ?? "Target Role");

  const bd = analysisResult.ats.breakdown;
  const atsDetails = getDimensionDetails(analysisResult.ats.details, bd);
  const atsScore = analysisResult.ats.score;
  const atsDeltaFromBaseline =
    baselineAts !== null && atsScore > baselineAts ? atsScore - baselineAts : 0;
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


  // Action items construction
  const atsActions = (analysisResult.ats.ats_issues ?? []).slice(0, 3).map((issue, i) => {
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
      linksToGap: false,
      targetTab: "fixes" as const,
    };
  });

  const jdGainPerFix = hasJD && analysisResult.gap?.jd_match_score_after
    ? Math.round(
        (analysisResult.gap.jd_match_score_after - (analysisResult.gap.jd_match_score_before ?? 0)) /
        Math.max(1, missingCount)
      )
    : 0;

  // Overview reads resume.weaknesses (A1 health assessment) — always available with or without JD.
  // Without JD, improvement_areas acts as fallback. Fixes tab owns gap.priority_fixes.
  const weaknessSources: string[] = [
    ...(analysisResult.resume?.weaknesses ?? []),
    ...(analysisResult.resume?.improvement_areas ?? []),
  ].filter(Boolean);
  const uniqueWeaknesses = Array.from(new Set(weaknessSources)).slice(0, 3);

  const gapActions = uniqueWeaknesses.map((weakness, i) => ({
    priority: i === 0 ? ("high" as const) : ("medium" as const),
    title: weakness.split("→")[0].trim(),
    description: weakness,
    gainLabel: hasJD ? `+${jdGainPerFix} JD match` : "Resume fix",
    gainType: hasJD ? ("jd" as const) : ("ats" as const),
    linksToGap: hasJD,
    targetTab: (hasJD ? "gap" : "fixes") as "gap" | "fixes",
  })) as ActionItem[];

  const actionItems = [...atsActions, ...gapActions].slice(0, 6);

  // ─── SECTION 3: Recruiter 6-sec scan ───
  const agencyRecruiter =
    analysisResult.sim?.personas.find(
      (p) =>
        p.persona.toLowerCase().includes("agency") ||
        p.persona.toLowerCase().includes("high-volume")
    ) ?? analysisResult.sim?.personas[0] ?? null;

  const shortlisted = agencyRecruiter?.shortlist_decision ?? false;
  const shortlistPct = Math.round((analysisResult?.sim?.shortlist_rate ?? 0) * 100);

  const reasonItems = !shortlisted
    ? (agencyRecruiter?.rejection_reason ?? "")
        .split(/;\s*|\.\s+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 3)
    : (agencyRecruiter?.noticed ?? []).slice(0, 3);
  const downloadJobId = jobId ?? analysisResult.job_id;
  const canDownload = Boolean(downloadJobId) && !isLoading && !isDownloading;

  const handleDownload = async (): Promise<void> => {
    if (!downloadJobId) {
      return;
    }

    setIsDownloading(true);
    try {
      const verification = await getDownloadVerification(downloadJobId);
      setVerificationResult(verification);
      await downloadResumeReport(downloadJobId, selectedStyle);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Download failed.";
      window.alert(message);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: T.bgPage }}>
      {/* ── SECTION 1: Results Hero ── */}
      <div style={{
        background: T.gradientHeroResults,
        borderBottom: `1.5px solid ${T.border}`,
        padding: "40px 40px 32px",
      }}>
        <div style={{
          maxWidth: T.maxWidth,
          margin: "0 auto",
          display: "flex",
          flexDirection: isTablet ? "column" : "row",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: isTablet ? "16px" : "32px",
        }}>
          {/* Left: Title + Context */}
          <div style={{ flex: 1 }}>
            <div style={{
              fontSize: "12px",
              fontWeight: 700,
              color: T.primary,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: "6px",
            }}>
              ● Analysis Complete
            </div>
            <div style={{
              fontSize: "28px",
              fontWeight: 700,
              color: T.textPrimary,
              marginBottom: "6px",
            }}>
              Resume Analysis Results
            </div>
            {targetRoleTitle && (
              <div style={{
                fontSize: "14px",
                color: T.textMuted,
              }}>
                Analyzed against: {targetRoleTitle}
              </div>
            )}
          </div>

          {/* Right: Re-analyze Button */}
          <button
            type="button"
            onClick={() => resetAnalysis()}
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: T.textPrimary,
              background: T.bgCard,
              border: `1.5px solid ${T.border}`,
              borderRadius: T.radiusSm,
              padding: "10px 18px",
              cursor: "pointer",
              whiteSpace: "nowrap",
              flexShrink: 0,
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = T.bgHover;
              (e.currentTarget as HTMLButtonElement).style.boxShadow = T.shadowSm;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = T.bgCard;
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
            }}
          >
            ← Re-analyze
          </button>
        </div>
      </div>

      <div style={pageContainerStyle(isMobile)}>

        {/* ── Download & Verification Banner ── */}
        <div style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: "12px",
          marginTop: "20px",
          marginBottom: "28px",
        }}>
          {verificationResult && !verificationResult.clean ? (
            <div style={{
              background: T.amberLight,
              border: `1.5px solid ${T.amberBorder}`,
              borderRadius: T.radiusSm,
              padding: "10px 14px",
              fontSize: "13px",
              color: "#92400e",
            }}>
              ⚠ {verificationResult.total_verified} of {verificationResult.total_applied} changes confirmed in document.
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => void handleDownload()}
            disabled={!canDownload}
            onMouseDown={() => {
              if (canDownload) {
                setIsDownloadPressed(true);
              }
            }}
            onMouseUp={() => setIsDownloadPressed(false)}
            onMouseLeave={() => setIsDownloadPressed(false)}
            style={{
              background: canDownload ? T.primary : T.bgSubtle,
              color: canDownload ? "#ffffff" : T.textDisabled,
              borderRadius: T.radiusSm,
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 700,
              border: "none",
              cursor: canDownload ? "pointer" : "not-allowed",
              transform: canDownload && isDownloadPressed ? "translateY(3px)" : "translateY(0px)",
              transition: "transform 0.1s, box-shadow 0.1s",
              boxShadow: canDownload
                ? isDownloadPressed
                  ? `0 1px 0 ${T.primaryDark}`
                  : `0 3px 0 ${T.primaryDark}, 0 5px 12px rgba(91,95,199,0.25)`
                : "0 3px 0 #d1d5db",
            }}
          >
            {isDownloading ? "Downloading..." : "Download Report"}
          </button>
        </div>

        {/* ── SECTION 2: Score Cards Grid (always 3 columns) ── */}
        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : isTablet ? "repeat(2, 1fr)" : "repeat(3, 1fr)",
          gap: "16px",
          marginBottom: "28px",
          maxWidth: T.maxWidth,
          margin: "28px auto 0",
          padding: "0 40px",
        }}>
          {/* Card 1 — ATS Score */}
          <ScoreCardV2
            label="ATS Score"
            labelColor={T.primary}
            score={atsCount}
            actualScore={atsScoreForCount}
            trendLabel={
              atsDeltaFromBaseline > 0
                ? `↑ +${atsDeltaFromBaseline} pts live`
                : `↑ +${potentialATS - atsScore} pts possible`
            }
            trendColor={T.primary}
            progressPercent={Math.min(100, (atsScoreForCount / 100) * 100)}
            progressGradient="linear-gradient(90deg, #5b5fc7, #7c3aed)"
            footnote="ATS keyword + formatting analysis"
            infoText="ATS Score shows how well your resume passes applicant tracking systems based on keywords, formatting, readability, and impact."
            isLoading={isLoading}
          />

          {/* Card 2 — JD Match (only if hasJD) */}
          {hasJD && (
            <ScoreCardV2
              label="JD Match"
              labelColor={T.violet}
              score={jdCount}
              actualScore={jdScoreForCount}
              trendLabel={`↑ +${jdGain}% possible`}
              trendColor={T.violet}
              progressPercent={Math.min(100, (jdScoreForCount / 100) * 100)}
              progressGradient="linear-gradient(90deg, #7c3aed, #a855f7)"
              footnote="Match against provided job description"
              infoText="JD Match shows how closely your resume aligns with the selected job description requirements."
              isLoading={isLoading}
            />
          )}

          {/* Card 3 — Percentile */}
          <ScoreCardV2
            label="Percentile"
            labelColor={T.emerald}
            score={pctCount}
            actualScore={pctScoreForCount}
            trendLabel={`Top ${pctCount}%`}
            trendColor={T.emerald}
            progressPercent={Math.min(100, pctScoreForCount)}
            progressGradient="linear-gradient(90deg, #059669, #10b981)"
            footnote="vs. similar profiles on RIP V2"
            infoText="Percentile compares your resume strength against similar candidates at your seniority level."
            isLoading={isLoading}
          />

        </div>

        {/* ── SECTION 3: Recruiter Alert Card (redesigned — only if hasSim) ── */}
        {hasSim && agencyRecruiter && (
          <div style={{
            background: `linear-gradient(135deg, ${T.roseLight}, #ffffff)`,
            border: `2px solid ${T.roseBorder}`,
            borderRadius: T.radiusXl,
            padding: "32px",
            marginBottom: "28px",
            maxWidth: T.maxWidth,
            margin: "28px auto",
            display: "flex",
            gap: "20px",
          }}>
            {/* Left: Icon */}
            <div style={{
              width: "52px",
              height: "52px",
              flexShrink: 0,
              background: T.roseLight,
              borderRadius: T.radiusSm,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "26px",
            }}>
              👀
            </div>

            {/* Right: Content */}
            <div style={{ flex: 1 }}>
              {/* Heading */}
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: "16px",
              }}>
                <div>
                  <div style={{
                    fontSize: "20px",
                    fontWeight: 700,
                    color: T.textPrimary,
                  }}>
                    Recruiter 6-Second Scan
                  </div>
                  <div style={{
                    fontSize: "13px",
                    color: T.textMuted,
                    marginTop: "4px",
                  }}>
                    Based on 10,000+ hiring decisions
                  </div>
                </div>
                <div style={{
                  background: T.roseLight,
                  color: T.rose,
                  border: `1px solid ${T.roseBorder}`,
                  borderRadius: T.radiusPill,
                  padding: "4px 12px",
                  fontSize: "11px",
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  Critical Insight
                </div>
              </div>

              {/* Verdict Box */}
              <div style={{
                background: T.bgCard,
                border: `2px solid ${T.roseBorder}`,
                borderRadius: T.radiusSm,
                padding: "14px 18px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginBottom: "16px",
              }}>
                <div style={{
                  width: "36px",
                  height: "36px",
                  background: T.roseLight,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "16px",
                  color: T.rose,
                  flexShrink: 0,
                }}>
                  ✗
                </div>
                <div>
                  <div style={{
                    fontSize: "16px",
                    fontWeight: 700,
                    color: T.rose,
                  }}>
                    Decision: {shortlisted ? "Shortlisted" : "Not Shortlisted"}
                  </div>
                  <div style={{
                    fontSize: "12px",
                    color: T.textMuted,
                    marginTop: "2px",
                  }}>
                    {shortlistPct}% chance of recruiter review
                  </div>
                </div>
              </div>

              {/* Rejection Reasons */}
              {reasonItems.map((text, i) => {
                const isPriority = i === 0;
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      padding: "10px 14px",
                      borderRadius: T.radiusSm,
                      marginBottom: i < reasonItems.length - 1 ? "8px" : "16px",
                      background: isPriority ? "#fff5f5" : T.amberLight,
                      borderLeft: `3px solid ${isPriority ? T.rose : T.amber}`,
                    }}
                  >
                    <span style={{
                      fontSize: "13px",
                      color: T.textSecondary,
                      lineHeight: 1.6,
                    }}>
                      {text}
                    </span>
                  </div>
                );
              })}

              {/* Fix Preview */}
              <div style={{
                background: `linear-gradient(135deg, ${T.emeraldLight}, #d1fae5)`,
                border: `1px solid ${T.emeraldBorder}`,
                borderRadius: T.radiusSm,
                padding: "14px 18px",
                fontSize: "13px",
                lineHeight: 1.6,
                color: T.textSecondary,
              }}>
                <strong style={{ color: T.emerald }}>
                  💡 What would change this decision:
                </strong>
                <div style={{ marginTop: "8px" }}>
                  {agencyRecruiter.flip_condition || analysisResult.sim?.most_critical_fix}
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
              background: T.gradientBrand,
              borderRadius: T.radiusXl,
              padding: "24px 28px",
              marginBottom: "28px",
              maxWidth: T.maxWidth,
              margin: "28px auto",
              display: isMobile ? "flex" : "grid",
              flexDirection: isMobile ? "column" : undefined,
              gridTemplateColumns: isMobile ? undefined : "1fr auto",
              gap: "24px",
              alignItems: isMobile ? "stretch" : "center",
            }}>
              <div>
                <div style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "rgba(255,255,255,0.65)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  marginBottom: "8px",
                }}>
                  Career Positioning
                </div>
                <div style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#ffffff",
                  lineHeight: 1.4,
                  marginBottom: "6px",
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {pos.positioning_line}
                </div>
                <div style={{
                  fontSize: "13px",
                  color: "rgba(255,255,255,0.85)",
                  lineHeight: 1.5,
                  marginBottom: "10px",
                }}>
                  {pos.cta_line}
                </div>
                <div style={{
                  fontSize: "12px",
                  color: "rgba(255,255,255,0.65)",
                  lineHeight: 1.5,
                  fontStyle: "italic",
                }}>
                  {pos.rank_rationale}
                </div>
              </div>
              <div style={{
                background: "rgba(255,255,255,0.15)",
                border: "1px solid rgba(255,255,255,0.25)",
                borderRadius: T.radiusSm,
                padding: "16px 20px",
                backdropFilter: "blur(8px)",
                minWidth: isMobile ? undefined : "200px",
                flexShrink: 0,
                width: isMobile ? "100%" : undefined,
              }}>
                <div style={{
                  fontSize: "11px",
                  color: "rgba(255,255,255,0.65)",
                  fontWeight: 600,
                }}>
                  Current Range
                </div>
                <div style={{
                  fontSize: "18px",
                  fontWeight: 800,
                  color: "#ffffff",
                  marginTop: "2px",
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ₹{pos.current_ctc_min}–{pos.current_ctc_max} LPA
                </div>
                <div style={{
                  borderTop: "1px solid rgba(255,255,255,0.2)",
                  margin: "10px 0",
                }}/>
                <div style={{
                  fontSize: "11px",
                  color: "rgba(255,255,255,0.65)",
                  fontWeight: 600,
                }}>
                  After {pos.changes_needed} Fix{pos.changes_needed !== 1 ? "es" : ""}
                </div>
                <div style={{
                  fontSize: "18px",
                  fontWeight: 800,
                  color: "#86efac",
                  marginTop: "2px",
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ₹{pos.potential_ctc_min}–{pos.potential_ctc_max} LPA
                </div>
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  background: "rgba(134,239,172,0.2)",
                  border: "1px solid rgba(134,239,172,0.35)",
                  borderRadius: T.radiusPill,
                  padding: "4px 12px",
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "#86efac",
                  marginTop: "8px",
                }}>
                  ↗ +₹{pos.ctc_delta_min}–{pos.ctc_delta_max} LPA/year
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── Company Readiness Card ── */}
        {companyReadiness && (
          <CompanyReadinessCard
            result={companyReadiness}
            roleTitle={companyRoleTitle}
            onSeeBreakdown={() => setShowReadinessBreakdown(true)}
            onFixTopGap={() => {
              if (onTabChange) onTabChange("fixes");
              else setActiveTab("fixes");
            }}
          />
        )}

        {/* ── Company Selector (always shown when analysis exists, no JD path) ── */}
        <CompanySelector
          runId={analysisResult.run_id ?? null}
        />

        {/* ── Readiness Breakdown modal ── */}
        {showReadinessBreakdown && companyReadiness && (
          <ReadinessBreakdown
            result={companyReadiness}
            roleTitle={companyRoleTitle}
            onClose={() => setShowReadinessBreakdown(false)}
            onFixGap={() => {
              setShowReadinessBreakdown(false);
              if (onTabChange) onTabChange("fixes");
              else setActiveTab("fixes");
            }}
          />
        )}

        {/* ── SECTION 5: Priority Actions ── */}
        <div style={{
          maxWidth: T.maxWidth,
          margin: "28px auto 0",
          padding: isMobile ? "0 20px" : "0 40px",
        }}>
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
          }}>
            <div>
              <div style={{
                fontSize: "18px",
                fontWeight: 700,
                color: T.textPrimary,
              }}>
                🎯 Priority Actions
              </div>
            </div>
            <div style={{
              fontSize: "13px",
              color: T.textMuted,
            }}>
              {actionItems.length} opportunities found
            </div>
          </div>

          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}>
            {actionItems.map((item, idx) => (
              <PriorityActionCardV2 key={idx} item={item} onTabChange={onTabChange} isMobile={isMobile} />
            ))}
          </div>
        </div>

        {/* ── SECTION 6: ATS Score Breakdown ── */}
        <div
          style={{
            background: T.bgCard,
            border: `1.5px solid ${T.border}`,
            borderRadius: T.radiusXl,
            padding: isMobile ? "24px 20px" : "32px",
            maxWidth: T.maxWidth,
            margin: "28px auto 0",
            marginBottom: "48px",
            transition: "box-shadow 0.2s ease",
            cursor: "default",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowLg;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
          }}
        >
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "24px",
          }}>
            <div style={{
              width: "40px",
              height: "40px",
              background: T.primaryLight,
              borderRadius: T.radiusSm,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}>
              <BarChart3 size={18} color={T.primary}/>
            </div>
            <div>
              <div style={{
                fontSize: "18px",
                fontWeight: 700,
                color: T.textPrimary,
              }}>
                ATS Score Breakdown
              </div>
              <div style={{
                fontSize: "13px",
                color: T.textMuted,
              }}>
                Deterministic — zero LLM calls
              </div>
            </div>
          </div>

          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "18px",
          }}>
            {atsDetails.map((detail) => {
              const scorePercent = Math.round((detail.score / 25) * 100);
              const gradientMap: Record<string, string> = {
                "Keyword Match": "linear-gradient(90deg, #5b5fc7, #7c3aed)",
                "Formatting": "linear-gradient(90deg, #059669, #10b981)",
                "Readability": "linear-gradient(90deg, #7c3aed, #a855f7)",
                "Impact & Metrics": "linear-gradient(90deg, #dc2626, #f97316)",
              };

              return (
                <div key={detail.label}>
                  <div style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "8px",
                  }}>
                    <div style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: T.textSecondary,
                    }}>
                      {detail.label}
                    </div>
                    <div style={{
                      fontSize: "14px",
                      fontWeight: 600,
                      color: T.textPrimary,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>
                      {detail.score}/25
                    </div>
                  </div>
                  <div style={{
                    height: "8px",
                    background: T.bgSubtle,
                    borderRadius: "4px",
                    overflow: "hidden",
                  }}>
                    <div
                      style={{
                        width: barsAnimated ? `${scorePercent}%` : "0%",
                        height: "100%",
                        background: gradientMap[detail.label] || "linear-gradient(90deg, #5b5fc7, #7c3aed)",
                        borderRadius: "4px",
                        transition: "width 0.8s ease",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <DataSourceNotice tab="overview" />

        {feedbackState?.active_moment === "quick_reaction" ? (
          <QuickReactionBanner onDismiss={clearActiveMoment} />
        ) : null}
      </div>
    </div>
  );
}

/* ─── Sub-components (inline, same file) ─── */

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
            background: T.textPrimary,
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

interface ScoreCardV2Props {
  label: string;
  labelColor: string;
  score: number | null;
  actualScore: number;
  trendLabel: string;
  trendColor: string;
  progressPercent: number;
  progressGradient: string;
  footnote: string;
  infoText?: string;
  isLoading?: boolean;
}

function ScoreCardV2({
  label,
  labelColor,
  score,
  trendLabel,
  trendColor,
  progressPercent,
  progressGradient,
  footnote,
  infoText,
  isLoading = false,
}: ScoreCardV2Props) {
  return (
    <div
      style={{
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: T.radiusLg,
        padding: "24px",
        boxShadow: T.shadowSm,
        display: "flex",
        flexDirection: "column",
        transition: "box-shadow 0.2s ease, transform 0.2s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowMd;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowSm;
      }}
    >
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "6px",
        marginBottom: "8px",
      }}>
        <span style={{
          fontSize: "11px",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: labelColor,
        }}>
          {label}
        </span>
        {infoText && <InfoTooltipButton infoText={infoText} />}
      </div>

      {/* Score Display */}
      <div style={{ marginBottom: "10px" }}>
        {isLoading ? (
          <ShimmerBlock width={80} height={52} />
        ) : (
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: "48px",
            fontWeight: 700,
            lineHeight: 1,
            color: labelColor,
            display: "inline",
          }}>
            {score ?? "--"}
          </span>
        )}
      </div>

      {/* Trend Pill */}
      {isLoading ? (
        <div style={{ marginBottom: "10px" }}>
          <ShimmerBlock width={100} height={22} />
        </div>
      ) : (
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          borderRadius: T.radiusPill,
          padding: "4px 10px",
          fontSize: "11px",
          fontWeight: 700,
          background: trendColor === T.primary ? "#eef0ff" : trendColor === T.violet ? "#f5f3ff" : "#ecfdf5",
          color: trendColor,
          marginBottom: "10px",
          width: "fit-content",
        }}>
          {trendLabel}
        </div>
      )}

      {/* Progress Bar */}
      <div style={{
        height: "5px",
        borderRadius: "3px",
        background: T.bgSubtle,
        marginBottom: "8px",
        overflow: "hidden",
      }}>
        {isLoading ? (
          <ShimmerBlock width="100%" height={5} />
        ) : (
          <div style={{
            width: `${Math.min(100, progressPercent)}%`,
            height: "100%",
            background: progressGradient,
            borderRadius: "3px",
          }}/>
        )}
      </div>

      {/* Footnote */}
      <div style={{
        fontSize: "12px",
        color: T.textMuted,
      }}>
        {footnote}
      </div>
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

function PriorityActionCardV2({
  item,
  onTabChange,
  isMobile,
}: {
  item: ActionItem;
  onTabChange?: (tab: string) => void;
  isMobile: boolean;
}) {
  const severityMap = {
    high:   { borderColor: T.rose, bgColor: T.roseLight, textColor: T.rose },
    medium: { borderColor: T.amber, bgColor: T.amberLight, textColor: T.amber },
    low:    { borderColor: "#94a3b8", bgColor: "#f1f5f9", textColor: "#64748b" },
  };

  const severity = severityMap[item.priority];

  const badgeMap = {
    high: { bg: T.roseLight, color: T.rose, label: "Critical" },
    medium: { bg: T.amberLight, color: T.amber, label: "Medium" },
    low: { bg: "#f1f5f9", color: "#64748b", label: "Low" },
  };

  const badge = badgeMap[item.priority];

  const gainStyles = item.gainType === "ats"
    ? { bg: T.emeraldLight, color: T.emerald }
    : { bg: T.primaryLight, color: T.primary };

  return (
    <div style={{
      background: T.bgCard,
      border: `1.5px solid ${T.border}`,
      borderLeft: `4px solid ${severity.borderColor}`,
      borderRadius: T.radiusLg,
      padding: "20px 24px",
      display: "flex",
      flexDirection: isMobile ? "column" : "row",
      alignItems: isMobile ? "flex-start" : "center",
      justifyContent: "space-between",
      gap: "12px",
      transition: "all 0.2s ease",
      boxShadow: T.shadowSm,
    }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowMd;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = T.shadowSm;
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "8px",
        }}>
          <span style={{
            background: badge.bg,
            color: badge.color,
            borderRadius: T.radiusPill,
            padding: "3px 10px",
            fontSize: "11px",
            fontWeight: 700,
          }}>
            {badge.label}
          </span>
          <span style={{
            background: gainStyles.bg,
            color: gainStyles.color,
            borderRadius: T.radiusPill,
            padding: "3px 10px",
            fontSize: "11px",
            fontWeight: 700,
          }}>
            {item.gainLabel}
          </span>
        </div>
        <div style={{
          fontSize: "14px",
          fontWeight: 700,
          color: T.textPrimary,
          marginBottom: "4px",
        }}>
          {item.title}
        </div>
        <div style={{
          fontSize: "13px",
          color: T.textSecondary,
          lineHeight: 1.5,
        }}>
          {item.description}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onTabChange?.(item.targetTab)}
        style={{
          fontSize: "12px",
          fontWeight: 700,
          color: severity.textColor,
          background: "none",
          border: "none",
          cursor: "pointer",
          whiteSpace: "nowrap",
          flexShrink: 0,
          padding: "8px 12px",
          borderRadius: T.radiusSm,
          transition: "all 0.2s ease",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = severity.bgColor;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "none";
        }}
      >
        {item.linksToGap ? "Go to Gap Analysis →" : "Go to Fixes →"}
      </button>
    </div>
  );
}

function SkeletonLoader() {
  const { isMobile } = useWindowSize();
  return (
    <div style={{ minHeight: "100vh", background: T.bgPage }}>
      <div style={pageContainerStyle(isMobile)}>
        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(4, 1fr)",
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
    </div>
  );
}

export default EvaluationDashboard;
