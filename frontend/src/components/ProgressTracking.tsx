import { useEffect, useMemo, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getCareerMemory } from "../api/client";
import { IS_MOCK } from "../hooks/useMockData";
import { useWindowSize } from "../hooks/useWindowSize";
import { mockCareerRecord, mockProgressSnapshots } from "../mocks/mockData";
import { useResumeStore } from "../store/useResumeStore";
import { pageContainerStyle } from "../utils/pageLayout";
import { isEvidenceGap } from "../utils/roleFitEvidence";
import type {
  CareerMemoryEntry,
  PriorityFix,
  ProgressSnapshot,
} from "../types";

interface ProgressTrackingProps {
  sessionId?: string | null;
  snapshots: ProgressSnapshot[];
  careerRecord: CareerMemoryEntry[];
  addCareerEntry: (entry: CareerMemoryEntry) => void;
}

interface MilestoneDotProps {
  cx?: number;
  cy?: number;
  payload?: {
    name?: string;
  };
}

const categoryOrder: CareerMemoryEntry["skill_category"][] = [
  "leadership",
  "technical",
  "delivery",
  "communication",
];

const categoryLabels: Record<CareerMemoryEntry["skill_category"], string> = {
  leadership: "Leadership",
  technical: "Technical",
  delivery: "Delivery",
  communication: "Communication",
};

const truncateBullet = (text: string): string =>
  text.length > 90 ? `${text.slice(0, 90)}...` : text;

function MilestoneDot({ cx, cy, payload }: MilestoneDotProps) {
  if (typeof cx !== "number" || typeof cy !== "number") {
    return null;
  }

  const isInitial = payload?.name === "Initial Analysis";
  const size = isInitial ? 5 : 8;
  const fill = isInitial ? "#6c47ff" : "#16a34a";

  return (
    <g>
      <circle cx={cx} cy={cy} r={size} fill={fill} stroke="#ffffff" strokeWidth={2} />
    </g>
  );
}

export default function ProgressTracking({
  sessionId,
  snapshots,
  careerRecord,
  addCareerEntry,
}: ProgressTrackingProps) {
  const { isMobile, width } = useWindowSize();
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const resetAnalysis = useResumeStore((state) => state.resetAnalysis);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});
  const [syncError, setSyncError] = useState<string | null>(null);
  const containerStyle = pageContainerStyle(isMobile);
  const isStacked = width < 768;

  const displayedSnapshots = useMemo(
    () => (snapshots.length > 0 ? snapshots : IS_MOCK ? mockProgressSnapshots : []),
    [snapshots]
  );
  const displayedCareerRecord = useMemo(
    () => (careerRecord.length > 0 ? careerRecord : IS_MOCK ? mockCareerRecord : []),
    [careerRecord]
  );

  useEffect(() => {
    if (!sessionId || IS_MOCK) {
      return;
    }

    let isCancelled = false;
    setSyncError(null);

    getCareerMemory(sessionId)
      .then((response) => {
        if (isCancelled) {
          return;
        }

        response.entries.forEach((entry) => addCareerEntry(entry));
      })
      .catch((error) => {
        console.error("Failed to sync career record:", error);
        if (!isCancelled) {
          setSyncError("Could not sync latest coaching answers.");
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [addCareerEntry, sessionId]);

  const chartData = useMemo(
    () =>
      displayedSnapshots.map((snap) => ({
        name: snap.label,
        score: snap.ats_score,
      })),
    [displayedSnapshots]
  );

  const groupedEntries = useMemo(() => {
    return categoryOrder.map((category) => ({
      category,
      title: categoryLabels[category],
      entries: displayedCareerRecord.filter(
        (entry) => entry.skill_category === category
      ),
    }));
  }, [displayedCareerRecord]);

  const initialScore = displayedSnapshots[0]?.ats_score ?? null;
  const currentScore =
    displayedSnapshots[displayedSnapshots.length - 1]?.ats_score ?? null;
  const scoreDelta =
    initialScore === null || currentScore === null
      ? null
      : currentScore - initialScore;
  const totalPatches =
    displayedSnapshots[displayedSnapshots.length - 1]?.patches_applied ?? 0;
  const totalCoaching =
    displayedSnapshots[displayedSnapshots.length - 1]?.coaching_answers ?? 0;
  const evidenceGapCount = (
    (analysisResult?.gap?.priority_fixes as Array<string | PriorityFix> | undefined) ?? []
  ).filter((fix) => typeof fix === "object" && fix !== null && isEvidenceGap(fix)).length;

  let milestoneMessage = "Upload your resume to start tracking progress.";
  if (displayedSnapshots.length === 1 && totalPatches === 0) {
    milestoneMessage = "Apply your first fix to see your score improve";
  } else if (totalPatches > 0 && totalCoaching === 0 && evidenceGapCount > 0) {
    milestoneMessage =
      "Answer a coaching question to add leadership signal to your resume";
  } else if (currentScore !== null && currentScore < 70) {
    milestoneMessage =
      "Reach ATS 70 to be in the top half of applicants for this role";
  } else if (currentScore !== null && currentScore < 80) {
    milestoneMessage =
      "Reach ATS 80 — most interviews go to candidates scoring 75+";
  } else if (currentScore !== null && currentScore >= 80) {
    milestoneMessage = "Strong score. Download your improved resume when you're ready.";
  }

  const handleToggleEntry = (entryId: string) => {
    setExpandedEntries((prev) => ({
      ...prev,
      [entryId]: !prev[entryId],
    }));
  };

  const handleStartNewAnalysis = () => {
    setActiveTab("overview");
    resetAnalysis();
  };

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={containerStyle}>
        <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", marginBottom: "16px" }}>
          Progress Tracking
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: isStacked ? "column" : "row",
            gap: 24,
            flexWrap: isStacked ? "nowrap" : "wrap",
          }}
        >
          <div
            style={{
              flex: "0 0 58%",
              minWidth: 280,
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: 18,
              padding: "24px 24px 20px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  background: "#eef2ff",
                  borderRadius: 8,
                  padding: "6px 8px",
                  fontSize: 16,
                }}
              >
                📈
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, color: "#111827" }}>
                  Score Journey
                </div>
                <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>
                  How your resume has improved
                </div>
              </div>
            </div>

            {scoreDelta !== null && scoreDelta > 0 ? (
              <div
                style={{
                  background: "#f0fdf4",
                  border: "1.5px solid #bbf7d0",
                  borderRadius: 12,
                  padding: "10px 16px",
                  marginBottom: 16,
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ color: "#16a34a", fontWeight: 700, fontSize: 18 }}>
                  +{scoreDelta} pts
                </div>
                <div style={{ color: "#4b5563", fontSize: 13 }}>
                  · ATS score improved from {initialScore} to {currentScore}
                </div>
              </div>
            ) : null}

            <div style={{ height: isMobile ? 240 : 300 }}>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 8, left: -20, bottom: 0 }}>
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: "#9ca3af" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 11, fill: "#9ca3af" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="#6c47ff"
                      strokeWidth={2}
                      dot={<MilestoneDot />}
                      activeDot={{ r: 6, fill: "#6c47ff" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    textAlign: "center",
                    color: "#9ca3af",
                    fontSize: 13,
                    lineHeight: 1.6,
                    background: "#fafafa",
                    borderRadius: 12,
                  }}
                >
                  Analyze a resume to start tracking.
                </div>
              )}
            </div>

            <div
              style={{
                background: "#f5f3ff",
                border: "1.5px solid #e0d9ff",
                borderRadius: 12,
                padding: "12px 16px",
                marginTop: 16,
                fontSize: 13,
                color: "#4c1d95",
              }}
            >
              → {milestoneMessage}
            </div>
          </div>

          <div
            style={{
              flex: "0 0 38%",
              minWidth: 240,
              background: "#fafafa",
              border: "1.5px solid #e5e7eb",
              borderRadius: 18,
              padding: "24px 24px 20px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: 12,
                marginBottom: 4,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    background: "#eef2ff",
                    borderRadius: 8,
                    padding: "6px 8px",
                    fontSize: 16,
                  }}
                >
                  📋
                </div>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15, color: "#111827" }}>
                    Your Career Record
                  </div>
                  <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>
                    Persists across sessions
                  </div>
                </div>
              </div>
              {displayedCareerRecord.length > 0 ? (
                <div
                  style={{
                    background: "#eef2ff",
                    color: "#6c47ff",
                    borderRadius: 12,
                    padding: "2px 10px",
                    fontSize: 12,
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                  }}
                >
                  {displayedCareerRecord.length} captured
                </div>
              ) : null}
            </div>

            {displayedCareerRecord.length === 0 ? (
              <div
                style={{
                  color: "#9ca3af",
                  fontSize: 13,
                  textAlign: "center",
                  padding: "24px 0",
                  lineHeight: 1.6,
                }}
              >
                <div>Your coaching answers will appear here.</div>
                <div>They carry over to your next resume upload.</div>
                {syncError ? <div style={{ marginTop: 8 }}>{syncError}</div> : null}
              </div>
            ) : (
              groupedEntries.map((group) => {
                if (group.entries.length === 0) {
                  return null;
                }

                return (
                  <div key={group.category}>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#9ca3af",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                        marginTop: 16,
                        marginBottom: 6,
                      }}
                    >
                      {group.title}
                    </div>

                    {group.entries.map((entry, index) => {
                      const expanded = expandedEntries[entry.id] ?? false;
                      const bulletText = expanded
                        ? entry.generated_bullet
                        : truncateBullet(entry.generated_bullet);

                      return (
                        <div
                          key={entry.id}
                          style={{
                            display: "flex",
                            alignItems: "flex-start",
                            gap: 10,
                            paddingBottom: 10,
                            marginBottom: 10,
                            borderBottom:
                              index < group.entries.length - 1
                                ? "1px solid #f3f4f6"
                                : "none",
                          }}
                        >
                          <div
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: "#6c47ff",
                              marginTop: 6,
                              flexShrink: 0,
                            }}
                          />
                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: 13,
                                color: "#374151",
                                lineHeight: 1.5,
                              }}
                            >
                              {bulletText}
                              {entry.generated_bullet.length > 90 ? (
                                <button
                                  type="button"
                                  onClick={() => handleToggleEntry(entry.id)}
                                  style={{
                                    background: "transparent",
                                    border: "none",
                                    color: "#6c47ff",
                                    cursor: "pointer",
                                    fontSize: 12,
                                    fontWeight: 600,
                                    padding: 0,
                                    marginLeft: 6,
                                  }}
                                >
                                  {expanded ? "less" : "more"}
                                </button>
                              ) : null}
                            </div>
                            <div
                              style={{
                                fontSize: 11,
                                color: "#9ca3af",
                                marginTop: 4,
                              }}
                            >
                              {(entry.company ?? "")}
                              {entry.company ? " · " : ""}
                              {new Date(entry.timestamp).getFullYear()}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div
          style={{
            background: "#f5f3ff",
            border: "1.5px solid #e0d9ff",
            borderRadius: 16,
            padding: "20px 24px",
            marginTop: 24,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, color: "#3730a3" }}>
              Applying for a different role?
            </div>
            <div
              style={{
                fontSize: 13,
                color: "#4c1d95",
                marginTop: 4,
                maxWidth: 520,
                lineHeight: 1.5,
              }}
            >
              Your Career Record carries over. Upload your resume against a new JD
              — we'll use your existing coaching answers where relevant.
            </div>
          </div>

          <button
            type="button"
            onClick={handleStartNewAnalysis}
            style={{
              background: "#6c47ff",
              color: "#ffffff",
              borderRadius: 10,
              padding: "10px 18px",
              fontSize: 13,
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
              boxShadow: "0 3px 0 #5b21b6, 0 5px 12px rgba(108, 71, 255, 0.25)",
            }}
          >
            Start New Analysis →
          </button>
        </div>
      </div>
    </div>
  );
}
