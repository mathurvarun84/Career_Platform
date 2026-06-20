import { useEffect, useMemo, useState } from "react";

import ScoreJourneyTab from "./ScoreJourney/ScoreJourneyTab";

import { getCareerMemory } from "../api/client";
import { IS_MOCK } from "../hooks/useMockData";
import { useWindowSize } from "../hooks/useWindowSize";
import { mockCareerRecord } from "../mocks/mockData";
import { useResumeStore } from "../store/useResumeStore";
import { pageContainerStyle } from "../utils/pageLayout";
import type {
  CareerMemoryEntry,
  InterviewProgressSnapshot,
  ProgressSnapshot,
} from "../types";

interface ProgressTrackingProps {
  sessionId?: string | null;
  snapshots: ProgressSnapshot[];
  careerRecord: CareerMemoryEntry[];
  addCareerEntry: (entry: CareerMemoryEntry) => void;
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

export default function ProgressTracking({
  sessionId,
  snapshots: _snapshots,
  careerRecord,
  addCareerEntry,
}: ProgressTrackingProps) {
  const { isMobile } = useWindowSize();
  const resetAnalysis = useResumeStore((state) => state.resetAnalysis);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const pastSessions = useResumeStore((state) => state.interview_history.past_sessions);
  const fetchInterviewHistory = useResumeStore((state) => state.fetchInterviewHistory);
  const interviewHistoryLoading = useResumeStore(
    (state) => state.interview_history.is_loading
  );
  const [expandedEntries, setExpandedEntries] = useState<Record<string, boolean>>({});
  const [syncError, setSyncError] = useState<string | null>(null);
  const containerStyle = pageContainerStyle(isMobile);

  const displayedCareerRecord = useMemo(
    () => (careerRecord.length > 0 ? careerRecord : IS_MOCK ? mockCareerRecord : []),
    [careerRecord]
  );

  useEffect(() => {
    void fetchInterviewHistory();
  }, [fetchInterviewHistory]);

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

  const groupedEntries = useMemo(() => {
    return categoryOrder.map((category) => ({
      category,
      title: categoryLabels[category],
      entries: displayedCareerRecord.filter(
        (entry) => entry.skill_category === category
      ),
    }));
  }, [displayedCareerRecord]);

  const interviewSnapshots: InterviewProgressSnapshot[] = useMemo(() => {
    const SIGNAL_RANK: Record<string, number> = { weak: 0, developing: 1, strong: 2 };
    return pastSessions.map((s) => {
      const scores = s.dimension_scorecard.map(
        (d) => SIGNAL_RANK[d.signal_strength] ?? 0
      );
      const average_signal_strength =
        scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
      return {
        timestamp: s.created_at,
        company: s.company,
        seniority: s.seniority,
        dimensions_covered: s.dimension_scorecard.map((d) => d.dimension),
        average_signal_strength,
        anti_patterns_count: s.anti_pattern_report.reduce((sum, ap) => sum + ap.count, 0),
      };
    });
  }, [pastSessions]);

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

        <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827", marginBottom: 4 }}>
          Career flywheel
        </div>
        <div style={{ fontSize: "13px", color: "#9ca3af", marginBottom: 16 }}>
          What carries over into your next analysis
        </div>
        <div
          style={{
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

        {/* Interview Practice History */}
        {interviewHistoryLoading ? (
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: 18,
              padding: "20px 24px",
              marginTop: 24,
              fontSize: 13,
              color: "#9ca3af",
            }}
          >
            Loading interview history...
          </div>
        ) : interviewSnapshots.length > 0 ? (
          <div
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: 18,
              overflow: "hidden",
              marginTop: 24,
            }}
          >
            <div style={{ padding: "16px 24px", borderBottom: "1.5px solid #e5e7eb" }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#111827" }}>
                Interview Practice History
              </div>
              <div style={{ fontSize: 13, color: "#6b7280", marginTop: 2 }}>
                {interviewSnapshots.length} session
                {interviewSnapshots.length !== 1 ? "s" : ""} completed
              </div>
            </div>

            <div
              style={{
                padding: "16px 24px",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              {interviewSnapshots.map((snap, i) => {
                const SENIORITY_LABELS: Record<string, string> = {
                  junior: "Junior",
                  mid: "Mid",
                  senior: "Senior",
                  staff: "Staff",
                  em: "EM",
                };
                const SIGNAL_STYLE: Record<string, React.CSSProperties> = {
                  strong: { background: "#dcfce7", color: "#166534", borderColor: "#86efac" },
                  developing: {
                    background: "#fef9c3",
                    color: "#854d0e",
                    borderColor: "#fde047",
                  },
                  weak: { background: "#fee2e2", color: "#991b1b", borderColor: "#fca5a5" },
                };
                const signalStrength =
                  snap.average_signal_strength >= 1.5
                    ? "strong"
                    : snap.average_signal_strength >= 0.75
                      ? "developing"
                      : "weak";

                return (
                  <div
                    key={`${snap.timestamp}-${i}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "12px 16px",
                      background: "#f9fafb",
                      border: "1.5px solid #e5e7eb",
                      borderRadius: 12,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, color: "#111827" }}>
                        {snap.company.charAt(0).toUpperCase() + snap.company.slice(1)} ·{" "}
                        {SENIORITY_LABELS[snap.seniority]}
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                        {snap.dimensions_covered.map((d) => d.replace(/_/g, " ")).join(", ")}
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div
                        style={{
                          display: "inline-block",
                          border: "1.5px solid",
                          borderRadius: 999,
                          padding: "2px 10px",
                          fontSize: 11,
                          fontWeight: 600,
                          ...(SIGNAL_STYLE[signalStrength] ?? SIGNAL_STYLE.weak),
                        }}
                      >
                        {signalStrength.charAt(0).toUpperCase() + signalStrength.slice(1)}
                      </div>
                      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 4 }}>
                        {new Date(snap.timestamp).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}

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

      <div style={{ marginTop: "40px", borderTop: "1px solid #e2e2ef", paddingTop: "40px" }}>
        <ScoreJourneyTab />
      </div>
    </div>
  );
}
