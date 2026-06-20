import { useEffect } from "react";

import { useResumeStore } from "../../store/useResumeStore";
import { T } from "../../tokens";
import MilestoneBanner from "./MilestoneBanner";
import ProgressSummary from "./ProgressSummary";
import SessionCard from "./SessionCard";
import TimelineChart from "./TimelineChart";
import WhatChangedPanel from "./WhatChangedPanel";

export default function ScoreJourneyTab() {
  const scoreJourney = useResumeStore((state) => state.scoreJourney);
  const scoreJourneyLoading = useResumeStore((state) => state.scoreJourneyLoading);
  const scoreJourneyError = useResumeStore((state) => state.scoreJourneyError);
  const activeMilestone = useResumeStore((state) => state.activeMilestone);
  const fetchScoreJourney = useResumeStore((state) => state.fetchScoreJourney);
  const dismissMilestone = useResumeStore((state) => state.dismissMilestone);

  useEffect(() => {
    if (scoreJourney === null && !scoreJourneyLoading && !scoreJourneyError) {
      void fetchScoreJourney();
    }
  }, [scoreJourney, scoreJourneyLoading, scoreJourneyError, fetchScoreJourney]);

  if (scoreJourneyLoading) {
    return (
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 32px 48px" }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              height: "60px",
              background: T.border,
              borderRadius: "12px",
              marginBottom: "16px",
            }}
          />
        ))}
      </div>
    );
  }

  if (scoreJourneyError) {
    const isNotFound = scoreJourneyError.includes("404");
    return (
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 32px 48px" }}>
        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e2e2ef",
            borderRadius: "16px",
            padding: "40px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "32px", marginBottom: "12px" }}>📈</div>
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#0d0d1a", marginBottom: "8px" }}>
            {isNotFound ? "Score Journey is coming soon" : "Could not load Score Journey"}
          </div>
          <div style={{ fontSize: "13px", color: "#8888aa", lineHeight: 1.6 }}>
            {isNotFound
              ? "This feature is being rolled out. Complete a few more analyses and check back soon."
              : "Something went wrong. Please refresh the page and try again."}
          </div>
        </div>
      </div>
    );
  }

  if (!scoreJourney || scoreJourney.total_sessions === 0) {
    return (
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "40px 32px 48px" }}>
        <div
          style={{
            background: T.bgCard,
            border: `1.5px solid ${T.border}`,
            borderRadius: "16px",
            padding: "40px",
            textAlign: "center",
            color: T.textMuted,
            fontSize: "14px",
          }}
        >
          Run your first analysis to start your Score Journey
        </div>
      </div>
    );
  }

  const { sessions, total_sessions } = scoreJourney;
  const latest = sessions[sessions.length - 1];
  const previous = sessions.length >= 2 ? sessions[sessions.length - 2] : null;

  return (
    <div
      style={{
        maxWidth: "1200px",
        margin: "0 auto",
        padding: "40px 32px 48px",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
      }}
    >
      {activeMilestone && (
        <MilestoneBanner milestone={activeMilestone} onDismiss={dismissMilestone} />
      )}

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: "20px", fontWeight: 700, color: T.textPrimary }}>
            Score Journey
          </div>
          <div style={{ fontSize: "13px", color: T.textMuted, marginTop: "4px" }}>
            {`Your resume's improvement arc across ${total_sessions} sessions`}
          </div>
        </div>
        <button
          type="button"
          disabled
          style={{
            fontFamily: "inherit",
            fontSize: "13px",
            fontWeight: 600,
            background: T.primary,
            color: "#ffffff",
            borderRadius: "8px",
            padding: "8px 16px",
            border: "none",
            opacity: 0.5,
            cursor: "default",
          }}
        >
          Export PDF
        </button>
      </div>

      <TimelineChart sessions={sessions} />

      <div style={{ display: "flex", gap: "16px", overflowX: "auto", paddingBottom: "8px" }}>
        {sessions.map((session, index) => {
          const isLatest = index === sessions.length - 1;
          return (
            <div key={session.run_id} style={{ flexShrink: 0 }}>
              <SessionCard session={session} isLatest={isLatest} />
            </div>
          );
        })}
      </div>

      {total_sessions >= 2 && <ProgressSummary journey={scoreJourney} />}

      {total_sessions >= 2 && previous && (
        <WhatChangedPanel
          latest={latest}
          previous={previous}
          isPro={true}
        />
      )}
    </div>
  );
}
