import { useEffect, useState } from "react";

import { useResumeStore } from "../store/useResumeStore";
import { getAuthToken } from "./useFeedbackSubmit";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function useFeedbackOrchestrator() {
  const isFullAnalysisReady = useResumeStore((s) => s.isFullAnalysisReady);
  const feedbackState = useResumeStore((s) => s.feedbackState);
  const setFeedbackState = useResumeStore((s) => s.setFeedbackState);
  const showFeedbackMoment = useResumeStore((s) => s.showFeedbackMoment);

  // ── Fetch feedback state from API on first mount (once per browser session) ──
  useEffect(() => {
    getAuthToken().then((token) => {
      if (!token) return;
      fetch(`${API_BASE_URL}/api/feedback/state`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((state) => setFeedbackState({ ...state, active_moment: null }))
        .catch(() => {/* non-fatal — feedback state stays null */});
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Moment 1 — Quick Reaction ─────────────────────────────────────────────
  // Fires when analysis results first become ready in this browser session.
  // Uses a local flag so it only fires once even if isFullAnalysisReady
  // briefly toggles during partial SSE merges.
  const [quickReactionFired, setQuickReactionFired] = useState(false);

  useEffect(() => {
    if (isFullAnalysisReady && !quickReactionFired) {
      setQuickReactionFired(true);
      showFeedbackMoment("quick_reaction");
    }
  }, [isFullAnalysisReady]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Moment 3 — PMF Signal ─────────────────────────────────────────────────
  // Fires when session_count reaches 3 and PMF has never been shown.
  useEffect(() => {
    if (!feedbackState) return;
    if (
      feedbackState.session_count >= 3 &&
      !feedbackState.pmf_shown &&
      !feedbackState.pmf_skipped
    ) {
      showFeedbackMoment("pmf_signal");
    }
  }, [feedbackState?.session_count]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Moment 4 — Re-engagement ──────────────────────────────────────────────
  // Fires when user returns after ≥7 days of inactivity.
  useEffect(() => {
    if (!feedbackState) return;
    const reference = feedbackState.last_reengagement_shown_at;
    if (!reference) return;
    const daysSince = (Date.now() - new Date(reference).getTime()) / 86_400_000;
    if (daysSince >= 7) {
      showFeedbackMoment("reengagement");
    }
  }, [feedbackState?.last_reengagement_shown_at]); // eslint-disable-line react-hooks/exhaustive-deps
}
