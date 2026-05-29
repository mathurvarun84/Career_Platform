import { useEffect, useRef, useState } from "react";

import { startSession, fetchSessionSummary } from "../api/interview";
import { IS_MOCK } from "../hooks/useMockData";
import { MOCK_INTERVIEW_QUESTIONS } from "../mocks/mockInterviewData";
import ModelAnswerCard from "./ModelAnswerCard";
import { useResumeStore } from "../store/useResumeStore";
import { composeResumeText } from "../utils/composeResumeText";
import { DIMENSIONS } from "../constants/interviewDimensions";
import type {
  AntiPatternFired,
  ExecutivePresenceLevel,
  InterviewQuestion,
  InterviewSession,
  InterviewProgressSnapshot,
  PastSessionSummary,
  PerQuestionFeedback,
  QuestionMode,
  SessionSummary,
  SignalStrength,
} from "../types";

const KEYFRAMES = `
@keyframes slideUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
`;

const COMPANIES = [
  "Amazon",
  "Google",
  "Meta",
  "Microsoft",
  "Stripe",
  "Razorpay",
  "Zepto",
  "PhonePe",
  "Flipkart",
  "Swiggy",
  "Zomato",
  "CRED",
  "Meesho",
  "Atlassian",
  "Salesforce",
  "Apple",
  "Netflix",
  "Uber",
  "Airbnb",
  "LinkedIn",
  "Shopify",
  "Coinbase",
  "Notion",
  "Figma",
  "Vercel",
  "DeepMind",
  "OpenAI",
  "Anthropic",
  "Databricks",
  "Other",
];

const COMPANY_HINTS: Record<string, string> = {
  Amazon: "We'll tune questions to Amazon's 16 Leadership Principles",
  Google: "We'll tune questions to Google's Googleyness + 4 Attributes framework",
  Meta: "We'll tune questions to Meta's core values and execution focus",
  Microsoft: "We'll tune questions to Microsoft's growth mindset framework",
  Stripe: "We'll tune questions to Stripe's operating principles",
};

const getHint = (c: string): string =>
  COMPANY_HINTS[c] ??
  (c && c !== "Other" ? `We'll tune questions to ${c}'s behavioral framework` : "");

const formatRelativeTime = (iso: string): string => {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
};

const formatCompanyLabel = (company: string): string =>
  company.charAt(0).toUpperCase() + company.slice(1).replace(/_/g, " ");

const SENIORITY_OPTIONS = ["junior", "mid", "senior", "staff", "em"] as const;

const SENIORITY_LABELS: Record<string, string> = {
  junior: "Junior",
  mid: "Mid",
  senior: "Senior",
  staff: "Staff",
  em: "EM",
};

const defaultMode = (s: string): QuestionMode =>
  s === "junior" ? "scenario" : "mixed";

const signalBadgeStyle = (strength: SignalStrength): React.CSSProperties => {
  switch (strength) {
    case "strong":
      return {
        background: "#dcfce7",
        color: "#166534",
        border: "1.5px solid #86efac",
      };
    case "developing":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        border: "1.5px solid #fde047",
      };
    case "weak":
      return {
        background: "#fee2e2",
        color: "#991b1b",
        border: "1.5px solid #fca5a5",
      };
  }
};

const executivePresenceBadgeStyle = (
  level: ExecutivePresenceLevel
): React.CSSProperties => {
  switch (level) {
    case "strong":
      return {
        background: "#dcfce7",
        color: "#166534",
        border: "1.5px solid #86efac",
      };
    case "developing":
      return {
        background: "#fef9c3",
        color: "#854d0e",
        border: "1.5px solid #fde047",
      };
    case "low":
      return {
        background: "#fee2e2",
        color: "#991b1b",
        border: "1.5px solid #fca5a5",
      };
    case "not_assessable":
      return {
        background: "#f3f4f6",
        color: "#6b7280",
        border: "1.5px solid #e5e7eb",
      };
  }
};

function ExecutivePresenceBadge({ level }: { level: ExecutivePresenceLevel }) {
  return (
    <span
      style={{
        borderRadius: 999,
        padding: "4px 12px",
        fontSize: 12,
        fontWeight: 600,
        display: "inline-block",
        ...executivePresenceBadgeStyle(level),
      }}
    >
      {level.replace(/_/g, " ")}
    </span>
  );
}

interface QuestionStyleCardProps {
  mode: QuestionMode;
  active: boolean;
  onSelect: () => void;
  style?: React.CSSProperties;
}

function QuestionStyleCard({
  mode,
  active,
  onSelect,
  style,
}: QuestionStyleCardProps) {
  const configs: Record<
    QuestionMode,
    { icon: React.ReactNode; title: string; desc: string; rec?: string }
  > = {
    behavioral: {
      icon: <span style={{ fontSize: 18 }}>🕐</span>,
      title: "Behavioral",
      desc: "Tell me about a time when... — draws from your past.",
      rec: "Best for mid / senior+",
    },
    scenario: {
      icon: <span style={{ fontSize: 18 }}>🧩</span>,
      title: "Scenario",
      desc: "Imagine you're leading a team... — tests judgment.",
      rec: "Best for junior / Staff+",
    },
    mixed: {
      icon: (
        <span style={{ fontSize: 18, color: active ? "#6366f1" : "#6b7280" }}>⚡</span>
      ),
      title: "Mixed (recommended)",
      desc: "2 behavioral + 1 scenario — mirrors real interview loops.",
    },
  };

  const cfg = configs[mode];

  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        position: "relative",
        borderRadius: 18,
        padding: 20,
        cursor: "pointer",
        textAlign: "left",
        transition: "border-color 0.15s, background 0.15s",
        border: active ? "1.5px solid #6366f1" : "1.5px solid #e5e7eb",
        background: active ? "#eef2ff" : "#ffffff",
        ...style,
      }}
    >
      {mode === "mixed" ? (
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            background: "#dcfce7",
            color: "#166534",
            borderRadius: 999,
            fontSize: 11,
            padding: "3px 10px",
            fontWeight: 600,
          }}
        >
          Recommended: mixed
        </div>
      ) : null}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        {cfg.icon}
        <span style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>{cfg.title}</span>
      </div>
      <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>{cfg.desc}</div>
      {cfg.rec ? (
        <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 6 }}>{cfg.rec}</div>
      ) : null}
    </button>
  );
}

interface AnswerAreaProps {
  minHeight?: number;
  submitLabel?: string;
  onSubmit: (text: string) => void;
  isEvaluating: boolean;
}

function AnswerArea({
  minHeight = 160,
  submitLabel = "Submit answer",
  onSubmit,
  isEvaluating,
}: AnswerAreaProps) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [answerText, setAnswerText] = useState("");
  const [focused, setFocused] = useState(false);

  const handleInput = (): void => {
    const ta = taRef.current;
    if (!ta) {
      return;
    }
    ta.style.height = "auto";
    ta.style.height = `${ta.scrollHeight}px`;
  };

  const charCount = answerText.length;
  const charColor =
    charCount > 400 ? "#374151" : charCount > 100 ? "#6b7280" : "#9ca3af";
  const canSubmit = answerText.trim().length > 0 && !isEvaluating;

  return (
    <div
      style={{
        background: "#ffffff",
        border: `1.5px solid ${focused ? "#6366f1" : "#e5e7eb"}`,
        boxShadow: focused ? "0 0 0 3px rgba(99,102,241,0.1)" : "none",
        borderRadius: 12,
        overflow: "hidden",
        marginBottom: 12,
      }}
    >
      <textarea
        ref={taRef}
        value={answerText}
        onChange={(e) => {
          setAnswerText(e.target.value);
          handleInput();
        }}
        onInput={handleInput}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder="Share your experience..."
        style={{
          width: "100%",
          padding: 16,
          fontSize: 14,
          lineHeight: 1.65,
          color: "#374151",
          minHeight,
          resize: "none",
          fontFamily: "inherit",
          border: "none",
          outline: "none",
          background: "transparent",
          boxSizing: "border-box",
        }}
      />
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 16px",
          borderTop: "1.5px solid #e5e7eb",
        }}
      >
        <span style={{ fontSize: 12, color: charColor }}>{charCount} characters</span>
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => onSubmit(answerText.trim())}
          style={{
            padding: "9px 20px",
            fontSize: 13,
            fontWeight: 700,
            background: canSubmit ? "#6366f1" : "#f3f4f6",
            color: canSubmit ? "#ffffff" : "#9ca3af",
            border: "none",
            borderRadius: 10,
            cursor: canSubmit ? "pointer" : "not-allowed",
            boxShadow: canSubmit ? "0 3px 0 #4338ca" : "0 3px 0 #d1d5db",
          }}
        >
          {isEvaluating ? "⏳ Evaluating..." : submitLabel}
        </button>
      </div>
    </div>
  );
}

function QuestionCard({
  question,
  isCompleted,
}: {
  question: InterviewQuestion;
  isCompleted: boolean;
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: 16,
        padding: 24,
        marginBottom: 16,
        opacity: isCompleted ? 0.5 : 1,
        transition: "opacity 0.3s",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
        }}
      >
        <div
          style={{
            background: "#f9fafb",
            border: "1.5px solid #e5e7eb",
            borderRadius: 999,
            padding: "3px 10px",
            fontSize: 11,
            color: "#6b7280",
          }}
        >
          {question.company_value_ref}
        </div>
        <div
          style={{
            background: question.question_type === "scenario" ? "#fdf4ff" : "#f9fafb",
            border: `1.5px solid ${question.question_type === "scenario" ? "#e9d5ff" : "#e5e7eb"}`,
            borderRadius: 999,
            padding: "3px 10px",
            fontSize: 11,
            color: question.question_type === "scenario" ? "#7c3aed" : "#6b7280",
          }}
        >
          {question.question_type === "scenario" ? "Scenario" : "Behavioral"}
        </div>
      </div>

      {question.question_type === "scenario" && question.preamble ? (
        <div
          style={{
            background: "#fdf4ff",
            borderRadius: 8,
            padding: "10px 14px",
            marginBottom: 10,
            fontSize: 13,
            color: "#6b7280",
            fontStyle: "italic",
          }}
        >
          {question.preamble}
        </div>
      ) : null}

      <div
        style={{
          fontSize: 17,
          fontWeight: 500,
          color: "#111827",
          lineHeight: 1.6,
        }}
      >
        {question.text}
      </div>

      <div
        style={{
          fontSize: 12,
          color: "#9ca3af",
          fontStyle: "italic",
          marginTop: 10,
        }}
      >
        {question.question_type === "scenario"
          ? "Walk through your reasoning — there's no single right answer."
          : "Think of a specific instance from your past."}
      </div>
    </div>
  );
}

function EvaluatingState() {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: 16,
        padding: 24,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 20,
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          style={{ animation: "spin 1s linear infinite" }}
        >
          <circle cx="8" cy="8" r="6" fill="none" stroke="#e5e7eb" strokeWidth="2" />
          <path
            d="M8 2a6 6 0 0 1 6 6"
            fill="none"
            stroke="#6366f1"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        <span style={{ fontSize: 13, color: "#6b7280", fontStyle: "italic" }}>
          Evaluating your answer...
        </span>
      </div>
      {[60, 85, 40].map((w, i) => (
        <div
          key={w}
          style={{
            width: `${w}%`,
            height: 14,
            borderRadius: 6,
            background: "#f3f4f6",
            animation: "pulse 1.4s ease-in-out infinite",
            animationDelay: `${i * 0.15}s`,
            marginBottom: 12,
          }}
        />
      ))}
    </div>
  );
}

function AntiPatternCard({ ap }: { ap: AntiPatternFired }) {
  return (
    <div
      style={{
        border: "1.5px solid #fca5a5",
        borderRadius: 12,
        padding: 14,
        marginTop: 10,
        animation: "slideUp 0.2s ease-out",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
        }}
      >
        <span
          style={{
            background: "#fee2e2",
            color: "#991b1b",
            borderRadius: 999,
            padding: "3px 10px",
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          {ap.label}
        </span>
        <span style={{ fontSize: 12, color: "#6b7280" }}>Found in your answer</span>
      </div>
      <div
        style={{
          background: "#fef2f2",
          borderLeft: "3px solid #fca5a5",
          borderRadius: "0 8px 8px 0",
          padding: "10px 14px",
          fontSize: 13,
          color: "#991b1b",
          fontStyle: "italic",
        }}
      >
        {ap.triggered_excerpt}
      </div>
      {ap.interviewer_reads_as ? (
        <div
          style={{
            fontSize: 12,
            color: "#6b7280",
            fontStyle: "italic",
            marginBottom: 8,
            marginTop: 8,
            padding: "8px 12px",
            background: "#f9fafb",
            borderRadius: 8,
            lineHeight: 1.5,
          }}
        >
          💬 Interviewer reads this as: &quot;{ap.interviewer_reads_as}&quot;
        </div>
      ) : null}
      <div
        style={{
          fontSize: 11,
          color: "#166534",
          fontWeight: 500,
          marginTop: 10,
        }}
      >
        Fix →
      </div>
      <div
        style={{
          background: "#f0fdf4",
          borderLeft: "3px solid #86efac",
          borderRadius: "0 8px 8px 0",
          padding: "10px 14px",
          fontSize: 13,
          color: "#166534",
        }}
      >
        {ap.rewrite_suggestion}
      </div>
    </div>
  );
}

function FeedbackCard({
  feedback,
  questionIndex,
  totalQuestions,
  onNext,
  showFooter,
}: {
  feedback: Partial<PerQuestionFeedback>;
  questionIndex: number;
  totalQuestions: number;
  onNext: () => void;
  showFooter: boolean;
}) {
  const dimScore = feedback.dimension_score;
  const isLast = questionIndex >= totalQuestions - 1;

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: 16,
        overflow: "hidden",
        marginBottom: 16,
      }}
    >
      {dimScore ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px",
            borderBottom: "1.5px solid #e5e7eb",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: "#111827" }}>
              {DIMENSIONS[dimScore.dimension]?.label ??
                dimScore.dimension.replace(/_/g, " ")}
            </span>
            <span
              style={{
                borderRadius: 999,
                padding: "4px 12px",
                fontSize: 12,
                fontWeight: 600,
                ...signalBadgeStyle(dimScore.signal_strength),
              }}
            >
              {dimScore.signal_strength}
            </span>
          </div>
          <span style={{ fontSize: 12, color: "#6b7280" }}>{dimScore.score_delta}</span>
        </div>
      ) : null}

      <div style={{ padding: "16px 20px" }}>
        {feedback.best_line ? (
          <div style={{ animation: "slideUp 0.2s ease-out", marginBottom: 14 }}>
            <div
              style={{
                fontSize: 11,
                color: "#166534",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
              }}
            >
              ✓ Strongest line
            </div>
            <div
              style={{
                background: "#f0fdf4",
                borderLeft: "3px solid #86efac",
                borderRadius: "0 8px 8px 0",
                padding: "10px 14px",
                fontSize: 13,
                color: "#166534",
                fontStyle: "italic",
              }}
            >
              {feedback.best_line}
            </div>
          </div>
        ) : null}

        {feedback.level_signal && !feedback.level_signal.match ? (
          <div
            style={{
              background: "#fffbeb",
              border: "1.5px solid #fde68a",
              borderRadius: 12,
              padding: "14px 16px",
              marginTop: 12,
              animation: "slideUp 0.2s ease-out",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#854d0e",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
              }}
            >
              ⚠ Level Signal Mismatch
            </div>
            <div style={{ fontSize: 13, color: "#92400e", lineHeight: 1.6 }}>
              This answer signals{" "}
              <strong>{feedback.level_signal.signaled_level}</strong> — you&apos;re
              interviewing for{" "}
              <strong>{feedback.level_signal.declared_level}</strong>.
            </div>
            <div
              style={{
                fontSize: 13,
                color: "#92400e",
                marginTop: 6,
                lineHeight: 1.6,
              }}
            >
              {feedback.level_signal.note}
            </div>
          </div>
        ) : null}

        {feedback.executive_presence || feedback.authenticity_note ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 10,
              marginTop: 12,
              animation: "slideUp 0.2s ease-out",
            }}
          >
            <div
              style={{
                background: "#f9fafb",
                border: "1.5px solid #e5e7eb",
                borderRadius: 10,
                padding: "10px 14px",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: "#6b7280",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 4,
                }}
              >
                Executive Presence
              </div>
              {feedback.executive_presence ? (
                <ExecutivePresenceBadge level={feedback.executive_presence} />
              ) : null}
            </div>
            <div
              style={{
                background: "#f9fafb",
                border: "1.5px solid #e5e7eb",
                borderRadius: 10,
                padding: "10px 14px",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: "#6b7280",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 4,
                }}
              >
                Authenticity
              </div>
              <div style={{ fontSize: 12, color: "#374151", lineHeight: 1.5 }}>
                {feedback.authenticity_note}
              </div>
            </div>
          </div>
        ) : null}

        {dimScore &&
        dimScore.signal_strength !== "strong" &&
        dimScore.what_was_missing ? (
          <div style={{ animation: "slideUp 0.2s ease-out", marginBottom: 14, marginTop: 12 }}>
            <div
              style={{
                fontSize: 11,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
              }}
            >
              Why interviewers care
            </div>
            <div
              style={{
                background: "#f9fafb",
                borderLeft: "3px solid #e5e7eb",
                borderRadius: "0 8px 8px 0",
                padding: "10px 14px",
                fontSize: 13,
                color: "#6b7280",
                lineHeight: 1.6,
              }}
            >
              {dimScore.what_was_missing}
            </div>
          </div>
        ) : null}

        {feedback.anti_patterns_fired?.map((ap) => (
          <AntiPatternCard key={ap.key} ap={ap} />
        ))}

        {feedback.overall_verdict ? (
          <div
            style={{
              background: "#f9fafb",
              borderRadius: 10,
              padding: "12px 16px",
              marginTop: 14,
              fontSize: 13,
              color: "#374151",
              lineHeight: 1.6,
              animation: "slideUp 0.2s ease-out",
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: "#6b7280",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
              }}
            >
              Interviewer impression
            </div>
            {feedback.overall_verdict}
          </div>
        ) : null}

        {feedback.coaching_close ? (
          <div
            style={{
              background: "#eef2ff",
              border: "1.5px solid #c7d2fe",
              borderRadius: 12,
              padding: "14px 16px",
              marginTop: 16,
              animation: "slideUp 0.2s ease-out",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#4f46e5",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 6,
              }}
            >
              ✦ Coaching Note
            </div>
            <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.65 }}>
              {feedback.coaching_close}
            </div>
          </div>
        ) : null}
      </div>

      {showFooter ? (
        <div style={{ padding: "16px 20px", borderTop: "1.5px solid #e5e7eb" }}>
          <button
            type="button"
            onClick={onNext}
            style={{
              width: "100%",
              padding: "14px 0",
              fontSize: 15,
              fontWeight: 700,
              background: "#6366f1",
              color: "#ffffff",
              border: "none",
              borderRadius: 12,
              cursor: "pointer",
              boxShadow: "0 4px 0 #4338ca",
            }}
          >
            {isLast ? "See session summary →" : "Next question →"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ProgressBar({ session }: { session: InterviewSession }) {
  const currentIndex = session.current_question_index;
  const currentQuestion = session.questions[currentIndex];

  if (!currentQuestion) {
    return null;
  }

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "#ffffff",
        borderBottom: "1.5px solid #e5e7eb",
        padding: "12px 0",
        marginBottom: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ display: "flex", gap: 6 }}>
          {session.questions.map((_, i) => (
            <div
              key={i}
              style={{
                width: 24,
                height: 5,
                borderRadius: 3,
                background:
                  i < currentIndex
                    ? "#6366f1"
                    : i === currentIndex
                      ? "#818cf8"
                      : "#e5e7eb",
              }}
            />
          ))}
        </div>
        <span style={{ fontSize: 13, color: "#6b7280" }}>
          Question {currentIndex + 1} of {session.questions.length}
        </span>
        <div
          style={{
            background: "#eef2ff",
            border: "1.5px solid #c7d2fe",
            color: "#4f46e5",
            borderRadius: 999,
            padding: "4px 12px",
            fontSize: 12,
          }}
        >
          {currentQuestion.dimension.replace(/_/g, " ")}
        </div>
        {currentQuestion.question_type === "scenario" ? (
          <div
            style={{
              background: "#fdf4ff",
              border: "1.5px solid #e9d5ff",
              color: "#7c3aed",
              borderRadius: 999,
              padding: "4px 12px",
              fontSize: 12,
            }}
          >
            Scenario
          </div>
        ) : null}
      </div>
    </div>
  );
}

function FollowUpCard({
  session,
  submittedAnswerText,
  isEvaluating,
  onSubmitFollowUp,
}: {
  session: InterviewSession;
  submittedAnswerText: string;
  isEvaluating: boolean;
  onSubmitFollowUp: (text: string) => void;
}) {
  if (!session.active_follow_up) {
    return null;
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div
        style={{
          background: "#f9fafb",
          borderRadius: 10,
          padding: "10px 14px",
          marginBottom: 0,
        }}
      >
        <div style={{ fontSize: 11, color: "#9ca3af", marginBottom: 4 }}>Your answer</div>
        <div
          style={{
            fontSize: 13,
            color: "#6b7280",
            fontStyle: "italic",
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {submittedAnswerText}
        </div>
      </div>
      <div
        style={{
          marginLeft: 20,
          width: 2,
          height: 20,
          background: "#fde68a",
        }}
      />
      <div
        style={{
          border: "1.5px solid #fde68a",
          borderLeft: "4px solid #f59e0b",
          borderRadius: "0 12px 12px 0",
          background: "#fffbeb",
          padding: "16px 20px",
          animation: "slideUp 0.2s ease-out",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 8,
          }}
        >
          <span style={{ color: "#d97706", fontSize: 14 }}>↳</span>
          <span style={{ fontSize: 12, color: "#92400e", fontWeight: 500 }}>
            The interviewer wants to know more...
          </span>
        </div>
        <div
          style={{
            fontSize: 15,
            color: "#111827",
            lineHeight: 1.6,
            marginBottom: 14,
          }}
        >
          {session.active_follow_up.text}
        </div>
        <AnswerArea
          minHeight={120}
          submitLabel="Submit follow-up"
          onSubmit={onSubmitFollowUp}
          isEvaluating={isEvaluating}
        />
      </div>
    </div>
  );
}

function InSessionView({ session }: { session: InterviewSession }) {
  const interviewLoading = useResumeStore((s) => s.interviewLoading);
  const interviewError = useResumeStore((s) => s.interviewError);
  const setInterviewError = useResumeStore((s) => s.setInterviewError);
  const submitAnswerWithStream = useResumeStore((s) => s.submitAnswerWithStream);
  const submitFollowUpAnswer = useResumeStore((s) => s.submitFollowUpAnswer);
  const advanceQuestion = useResumeStore((s) => s.advanceQuestion);
  const setSessionState = useResumeStore((s) => s.setSessionState);
  const [lastSubmittedAnswer, setLastSubmittedAnswer] = useState<string>("");

  const currentIndex = session.current_question_index;

  const currentQuestionId = session.questions[currentIndex]?.id;
  const currentTurn = session.answers.find(
    (turn) => turn.question_id === currentQuestionId
  );
  const submittedAnswerText = currentTurn?.answer_text ?? "";

  const handleSubmitAnswer = (answerText: string): void => {
    const q = session.questions[currentIndex];
    if (!q) {
      return;
    }
    setLastSubmittedAnswer(answerText);
    setInterviewError(null);
    submitAnswerWithStream(q.id, answerText, false);
  };

  const handleRetrySubmit = (): void => {
    if (lastSubmittedAnswer) {
      handleSubmitAnswer(lastSubmittedAnswer);
    }
  };

  const handleSubmitFollowUp = (answerText: string): void => {
    const q = session.questions[currentIndex];
    const followUp = session.active_follow_up;
    if (!q || !followUp) {
      return;
    }
    submitFollowUpAnswer(q.id, followUp.id, answerText);
    submitAnswerWithStream(q.id, answerText, true, followUp.id);
  };

  const handleNext = (): void => {
    if (currentIndex >= session.questions.length - 1) {
      setSessionState("summary");
    } else {
      advanceQuestion();
    }
  };

  const isFeedbackComplete = (fb: Partial<PerQuestionFeedback>): boolean =>
    Boolean(
      fb.overall_verdict &&
        fb.best_line &&
        fb.dimension_score &&
        fb.level_signal &&
        fb.executive_presence &&
        "coaching_close" in fb &&
        fb.anti_patterns_fired !== undefined
    );

  return (
    <div>
      <ProgressBar session={session} />
      {session.questions.map((question, i) => {
        if (i > currentIndex) {
          return null;
        }

        const isCompleted = i < currentIndex;
        const isCurrent = i === currentIndex;
        const completedFeedback = session.feedback[i];
        const showPartial =
          isCurrent &&
          session.state === "evaluating" &&
          session.partialFeedback &&
          Object.keys(session.partialFeedback).length > 0;
        const showEvaluating =
          isCurrent &&
          session.state === "evaluating" &&
          !showPartial;
        const showFollowUp =
          isCurrent &&
          session.state === "awaiting_follow_up" &&
          session.active_follow_up !== null;
        const showAnswerArea =
          isCurrent && session.state === "in_progress";
        const showFeedback =
          (isCurrent && session.state === "feedback_shown" && completedFeedback) ||
          showPartial ||
          (isCompleted && completedFeedback);

        const feedbackData: Partial<PerQuestionFeedback> | undefined = showPartial
          ? session.partialFeedback ?? undefined
          : completedFeedback;

        const showFooter =
          isCurrent &&
          session.state === "feedback_shown" &&
          feedbackData &&
          isFeedbackComplete(feedbackData);

        const turnForQuestion = session.answers.find(
          (turn) => turn.question_id === question.id
        );
        const answerTextForQuestion = turnForQuestion?.answer_text ?? "";

        return (
          <div key={question.id}>
            <QuestionCard question={question} isCompleted={isCompleted} />
            {showAnswerArea ? (
              <AnswerArea
                onSubmit={handleSubmitAnswer}
                isEvaluating={interviewLoading}
              />
            ) : null}
            {showFollowUp ? (
              <FollowUpCard
                session={session}
                submittedAnswerText={submittedAnswerText}
                isEvaluating={interviewLoading}
                onSubmitFollowUp={handleSubmitFollowUp}
              />
            ) : null}
            {showEvaluating && interviewError ? (
              <div
                style={{
                  background: "#fef2f2",
                  border: "1.5px solid #fca5a5",
                  borderRadius: 16,
                  padding: 24,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "#991b1b",
                    marginBottom: 8,
                  }}
                >
                  Something went wrong
                </div>
                <div
                  style={{
                    fontSize: 13,
                    color: "#991b1b",
                    marginBottom: 16,
                  }}
                >
                  {interviewError}
                </div>
                <button
                  onClick={handleRetrySubmit}
                  style={{
                    padding: "9px 20px",
                    fontSize: 13,
                    fontWeight: 700,
                    background: "#6366f1",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: 10,
                    cursor: "pointer",
                    boxShadow: "0 3px 0 #4338ca",
                  }}
                >
                  Try submitting again
                </button>
              </div>
            ) : showEvaluating ? (
              <EvaluatingState />
            ) : null}
            {showFeedback && feedbackData ? (
              <>
                <FeedbackCard
                  feedback={feedbackData}
                  questionIndex={i}
                  totalQuestions={session.questions.length}
                  onNext={handleNext}
                  showFooter={Boolean(showFooter)}
                />
                {isFeedbackComplete(feedbackData) ? (
                  <ModelAnswerCard
                    question_id={question.id}
                    session_id={session.session_id}
                    answer_text={answerTextForQuestion}
                  />
                ) : null}
              </>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

const SIGNAL_STYLE: Record<string, React.CSSProperties> = {
  strong: { background: "#dcfce7", color: "#166534", borderColor: "#86efac" },
  developing: { background: "#fef9c3", color: "#854d0e", borderColor: "#fde047" },
  weak: { background: "#fee2e2", color: "#991b1b", borderColor: "#fca5a5" },
};

const SignalBadge = ({ strength }: { strength: string }) => (
  <div
    style={{
      display: "inline-block",
      border: "1.5px solid",
      borderRadius: 999,
      padding: "2px 10px",
      fontSize: 11,
      fontWeight: 600,
      ...(SIGNAL_STYLE[strength] ?? SIGNAL_STYLE.weak),
    }}
  >
    {strength.charAt(0).toUpperCase() + strength.slice(1)}
  </div>
);

const MiniSparkline = ({ snapshots }: { snapshots: InterviewProgressSnapshot[] }) => {
  if (!snapshots.length) return null;
  const values = snapshots.map((s) => s.average_signal_strength);
  const W = 80,
    H = 28,
    pad = 4;

  if (values.length === 1) {
    return (
      <svg width={W} height={H}>
        <circle cx={W / 2} cy={H / 2} r={3} fill="#6366f1" />
      </svg>
    );
  }

  const xs = values.map((_, i) => pad + (i / (values.length - 1)) * (W - pad * 2));
  const ys = values.map((v) => H - pad - (v / 2) * (H - pad * 2));
  const path = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");

  return (
    <svg width={W} height={H}>
      <path
        d={path}
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r={3} fill="#6366f1" />
    </svg>
  );
};

interface SummaryScreenProps {
  session: InterviewSession;
  summary: SessionSummary;
  setActiveTab: (tab: any) => void;
}

function SummaryScreen({ session, summary, setActiveTab }: SummaryScreenProps) {
  const retryFromQuestion = useResumeStore((s) => s.retryFromQuestion);
  const startInterviewSession = useResumeStore((s) => s.startInterviewSession);
  const pastSessions = useResumeStore((s) => s.interview_history.past_sessions);

  const progressSnapshots: InterviewProgressSnapshot[] = pastSessions.map((s) => {
    const SIGNAL_RANK: Record<string, number> = { weak: 0, developing: 1, strong: 2 };
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

  const handleRetry = (questionIndex: number) => {
    retryFromQuestion(questionIndex);
  };

  const handleNewSession = () => {
    useResumeStore.setState({ interviewSession: null, interviewError: null });
    startInterviewSession(session.company, session.seniority, "mixed");
    useResumeStore.setState((s) => ({
      interviewSession: s.interviewSession
        ? { ...s.interviewSession, state: "configuring" as const }
        : null,
    }));
  };

  const handleViewProgress = () => {
    setActiveTab("progress");
  };

  const SIGNAL_RANK = { weak: 0, developing: 1, strong: 2 };
  const weakestIndex = summary.dimension_scorecard.reduce(
    (minIdx, row, i) =>
      (SIGNAL_RANK[row.signal_strength as keyof typeof SIGNAL_RANK] ?? 0) <
      (SIGNAL_RANK[summary.dimension_scorecard[minIdx].signal_strength as keyof typeof SIGNAL_RANK] ?? 0)
        ? i
        : minIdx,
    0
  );
  const weakestDimension = summary.dimension_scorecard[weakestIndex].dimension.replace(/_/g, " ");

  if (!summary) {
    return (
      <div style={{ padding: "40px 0", display: "flex", flexDirection: "column", gap: 20 }}>
        {[100, 70, 85, 50].map((w, i) => (
          <div
            key={i}
            style={{
              width: `${w}%`,
              height: 18,
              borderRadius: 8,
              background: "#f3f4f6",
              animation: "pulse 1.4s ease-in-out infinite",
              animationDelay: `${i * 0.12}s`,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 40 }}>
      {/* Section 1 — Header */}
      <div style={{ marginBottom: 32 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "#f0fdf4",
            border: "1.5px solid #86efac",
            borderRadius: 999,
            padding: "5px 14px",
            fontSize: 12,
            fontWeight: 600,
            color: "#166534",
            marginBottom: 16,
          }}
        >
          ✦ Session Complete
        </div>

        <div style={{ fontSize: 28, fontWeight: 700, color: "#111827", marginBottom: 8 }}>
          Here's how you did
        </div>

        <div style={{ fontSize: 15, color: "#6b7280" }}>
          {session.company} Behavioral Interview · {SENIORITY_LABELS[session.seniority]} Level
        </div>
      </div>

      {/* Section 2 — Top Strength + Gap */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        <div style={{ background: "#f0fdf4", border: "1.5px solid #86efac", borderRadius: 16, padding: 20 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#166534",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 10,
            }}
          >
            ✓ Your Strongest Signal
          </div>
          <div style={{ fontSize: 14, color: "#166534", lineHeight: 1.6 }}>
            {summary.top_strength}
          </div>
        </div>

        <div style={{ background: "#fffbeb", border: "1.5px solid #fde68a", borderRadius: 16, padding: 20 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#854d0e",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 10,
            }}
          >
            → Biggest Opportunity
          </div>
          <div style={{ fontSize: 14, color: "#92400e", lineHeight: 1.6 }}>
            {summary.top_gap}
          </div>
        </div>
      </div>

      {/* Section 3 — Dimension Scorecard */}
      <div
        style={{
          background: "#ffffff",
          border: "1.5px solid #e5e7eb",
          borderRadius: 18,
          overflow: "hidden",
          marginBottom: 24,
        }}
      >
        <div style={{ padding: "16px 24px", borderBottom: "1.5px solid #e5e7eb" }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#111827" }}>
            Dimension Scorecard
          </div>
        </div>

        {summary.dimension_scorecard.map((row, i) => {
          const isRed = row.signal_strength === "weak" || row.gap;
          const isAmber = !isRed && row.signal_strength === "developing";

          const rowBg = isRed ? "#fef2f2" : isAmber ? "#fffbeb" : "#f0fdf4";
          const leftBorder = isRed ? "#fca5a5" : isAmber ? "#fde68a" : "#86efac";

          return (
            <div
              key={row.dimension}
              style={{
                display: "flex",
                flexDirection: "column",
                padding: "14px 24px",
                background: rowBg,
                borderLeft: `4px solid ${leftBorder}`,
                borderBottom: i < summary.dimension_scorecard.length - 1 ? "1.5px solid #e5e7eb" : "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: "#111827", minWidth: 180 }}>
                  {row.dimension.replace(/_/g, " ")}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <SignalBadge strength={row.signal_strength} />
                  <div
                    style={{
                      fontSize: 11,
                      color: "#6b7280",
                      background: "#f9fafb",
                      border: "1.5px solid #e5e7eb",
                      borderRadius: 999,
                      padding: "2px 10px",
                    }}
                  >
                    Expected: {row.expected_for_seniority}
                  </div>
                </div>

                {row.gap ? (
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#991b1b",
                      background: "#fee2e2",
                      border: "1.5px solid #fca5a5",
                      borderRadius: 999,
                      padding: "3px 10px",
                    }}
                  >
                    ↓ Gap
                  </div>
                ) : (
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#166534",
                      background: "#dcfce7",
                      border: "1.5px solid #86efac",
                      borderRadius: 999,
                      padding: "3px 10px",
                    }}
                  >
                    ✓ Meets bar
                  </div>
                )}
              </div>

              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 4 }}>
                {row.note}
              </div>
            </div>
          );
        })}
      </div>

      {/* Section 4 — Anti-Pattern Report */}
      {summary.anti_pattern_report.length > 0 && (
        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: 18,
            overflow: "hidden",
            marginBottom: 24,
          }}
        >
          <div style={{ padding: "16px 24px", borderBottom: "1.5px solid #e5e7eb" }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#111827" }}>
              Patterns to Fix
            </div>
            <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
              These patterns appeared across your answers and are worth addressing before your real interview.
            </div>
          </div>

          <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
            {summary.anti_pattern_report.map((ap) => (
              <div key={ap.key} style={{ border: "1.5px solid #fca5a5", borderRadius: 12, padding: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <div
                    style={{
                      background: "#fee2e2",
                      color: "#991b1b",
                      borderRadius: 999,
                      padding: "3px 12px",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {ap.label}
                  </div>
                  <div
                    style={{
                      background: "#f9fafb",
                      border: "1.5px solid #e5e7eb",
                      borderRadius: 999,
                      padding: "2px 10px",
                      fontSize: 11,
                      color: "#6b7280",
                    }}
                  >
                    ×{ap.count}
                  </div>
                </div>

                <div
                  style={{
                    background: "#fef2f2",
                    borderLeft: "3px solid #fca5a5",
                    borderRadius: "0 8px 8px 0",
                    padding: "10px 14px",
                    fontSize: 13,
                    color: "#991b1b",
                    fontStyle: "italic",
                    marginBottom: 12,
                  }}
                >
                  "{ap.worst_excerpt}"
                </div>

                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: "#166534",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    marginBottom: 6,
                  }}
                >
                  Fix →
                </div>
                <div
                  style={{
                    background: "#f0fdf4",
                    borderLeft: "3px solid #86efac",
                    borderRadius: "0 8px 8px 0",
                    padding: "10px 14px",
                    fontSize: 13,
                    color: "#166534",
                  }}
                >
                  {ap.fix}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Section 5 — What to Do Next */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 24 }}>
        {/* RetryCard */}
        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: 16,
            padding: 20,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              Retry Weakest Answer
            </div>
            <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.5 }}>
              Your <strong>{weakestDimension}</strong> answer had the lowest signal. Try it again with the
              rubric in mind.
            </div>
          </div>
          <button
            onClick={() => handleRetry(weakestIndex)}
            style={{
              padding: "10px 0",
              width: "100%",
              background: "#6366f1",
              color: "#ffffff",
              fontSize: 13,
              fontWeight: 700,
              border: "none",
              borderRadius: 10,
              cursor: "pointer",
              boxShadow: "0 3px 0 #4338ca",
            }}
          >
            Retry This Answer
          </button>
        </div>

        {/* NewSessionCard */}
        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: 16,
            padding: 20,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              Next Practice Session
            </div>
            <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.5 }}>
              The AI recommends practicing:
            </div>
            <div
              style={{
                display: "inline-block",
                background: "#eef2ff",
                border: "1.5px solid #c7d2fe",
                borderRadius: 999,
                padding: "4px 12px",
                fontSize: 12,
                color: "#4f46e5",
                fontWeight: 500,
                marginTop: 6,
              }}
            >
              {summary.recommended_next_dimension.replace(/_/g, " ")}
            </div>
          </div>
          <button
            onClick={handleNewSession}
            style={{
              padding: "10px 0",
              width: "100%",
              background: "#6366f1",
              color: "#ffffff",
              fontSize: 13,
              fontWeight: 700,
              border: "none",
              borderRadius: 10,
              cursor: "pointer",
              boxShadow: "0 3px 0 #4338ca",
            }}
          >
            Practice {summary.recommended_next_dimension.replace(/_/g, " ")}
          </button>
        </div>

        {/* ProgressCard */}
        <div
          style={{
            background: "#ffffff",
            border: "1.5px solid #e5e7eb",
            borderRadius: 16,
            padding: 20,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            gap: 14,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 8,
              }}
            >
              Track Your Growth
            </div>
            <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.5 }}>
              Your session has been saved. View your improvement across sessions over time.
            </div>
          </div>
          <button
            onClick={handleViewProgress}
            style={{
              padding: "10px 0",
              width: "100%",
              background: "#f9fafb",
              color: "#374151",
              fontSize: 13,
              fontWeight: 600,
              border: "1.5px solid #e5e7eb",
              borderRadius: 10,
              cursor: "pointer",
              boxShadow: "0 3px 0 #e5e7eb",
            }}
          >
            View Progress Tab
          </button>
        </div>
      </div>

      {/* Section 6 — Score Trend Update */}
      <div
        style={{
          background: "#f9fafb",
          border: "1.5px solid #e5e7eb",
          borderRadius: 14,
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 13, color: "#6b7280", flex: 1 }}>
          This session has been added to your Progress tab.
        </div>
        <MiniSparkline snapshots={progressSnapshots} />
      </div>
    </div>
  );
}

function ContinuityCard({
  session,
  onPracticeGap,
  onToggleHistory,
  showHistory,
}: {
  session: PastSessionSummary;
  onPracticeGap: () => void;
  onToggleHistory: () => void;
  showHistory: boolean;
}) {
  const topAp = session.anti_pattern_report[0];
  const gapDetail = topAp ? `${session.top_gap} (${topAp.key} ×${topAp.count})` : session.top_gap;

  return (
    <div
      style={{
        background: "#f5f3ff",
        border: "1.5px solid #6366f1",
        borderRadius: 18,
        padding: "20px 24px",
        marginBottom: 24,
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 700, color: "#4338ca", marginBottom: 12 }}>
        ↩ Pick up where you left off
      </div>
      <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 14 }}>
        Last session: {formatCompanyLabel(session.company)} ·{" "}
        {SENIORITY_LABELS[session.seniority] ?? session.seniority} ·{" "}
        {formatRelativeTime(session.created_at)}
      </div>
      <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6, marginBottom: 6 }}>
        ✓ Strongest: {session.top_strength.split(".")[0]}
      </div>
      <div style={{ fontSize: 13, color: "#374151", lineHeight: 1.6, marginBottom: 18 }}>
        → To fix: {gapDetail}
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={onPracticeGap}
          style={{
            padding: "10px 18px",
            fontSize: 13,
            fontWeight: 700,
            background: "#6366f1",
            color: "#ffffff",
            border: "none",
            borderRadius: 10,
            cursor: "pointer",
            boxShadow: "0 3px 0 #4338ca",
          }}
        >
          Practice this gap →
        </button>
        <button
          type="button"
          onClick={onToggleHistory}
          style={{
            padding: "10px 18px",
            fontSize: 13,
            fontWeight: 600,
            background: "transparent",
            color: "#4338ca",
            border: "1.5px solid #c7d2fe",
            borderRadius: 10,
            cursor: "pointer",
          }}
        >
          {showHistory ? "Hide history" : "View full history"}
        </button>
      </div>
    </div>
  );
}

function PreSessionScreen() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const sectionOverrides = useResumeStore((s) => s.sectionOverrides);
  const setInterviewSession = useResumeStore((s) => s.setInterviewSession);
  const setInterviewError = useResumeStore((s) => s.setInterviewError);
  const startInterviewSession = useResumeStore((s) => s.startInterviewSession);
  const pastSessions = useResumeStore((s) => s.interview_history.past_sessions);
  const interviewPrefill = useResumeStore((s) => s.interviewPrefill);
  const setInterviewPrefill = useResumeStore((s) => s.setInterviewPrefill);
  const fetchInterviewHistory = useResumeStore((s) => s.fetchInterviewHistory);
  const activeTab = useResumeStore((s) => s.activeTab);

  const inferredSeniority =
    analysisResult?.resume?.seniority ?? "senior";

  const lastSession = pastSessions[0] ?? null;

  const [company, setCompany] = useState("");
  const [customCompany, setCustomCompany] = useState("");
  const [seniority, setSeniority] = useState<string>(inferredSeniority);
  const [questionMode, setQuestionMode] = useState<QuestionMode>(
    defaultMode(inferredSeniority)
  );
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (activeTab === "mock_interview") {
      void fetchInterviewHistory();
    }
  }, [activeTab, fetchInterviewHistory]);

  useEffect(() => {
    if (!interviewPrefill) {
      return;
    }
    const match = COMPANIES.find(
      (c) => c.toLowerCase() === interviewPrefill.company.toLowerCase()
    );
    if (match) {
      setCompany(match);
      setCustomCompany("");
    } else {
      setCompany("Other");
      setCustomCompany(formatCompanyLabel(interviewPrefill.company));
    }
    setSeniority(interviewPrefill.seniority);
    setQuestionMode(defaultMode(interviewPrefill.seniority));
    setInterviewPrefill(null);
  }, [interviewPrefill, setInterviewPrefill]);

  useEffect(() => {
    setQuestionMode(defaultMode(seniority));
  }, [seniority]);

  const resolvedCompany = company === "Other" ? customCompany : company;
  const canStart = resolvedCompany.trim().length > 0;

  const handlePracticeGap = (): void => {
    if (!lastSession) {
      return;
    }
    setInterviewPrefill({
      company: lastSession.company,
      seniority: lastSession.seniority,
      recommended_dimension: lastSession.recommended_next_dimension,
    });
  };

  const handleStartSession = async (): Promise<void> => {
    setLoading(true);
    startInterviewSession(resolvedCompany, seniority, questionMode);

    try {
      if (IS_MOCK) {
        await new Promise((r) => setTimeout(r, 600));
        setInterviewSession({
          session_id: "mock-interview-session-001",
          company: resolvedCompany,
          seniority,
          question_mode: questionMode,
          questions: MOCK_INTERVIEW_QUESTIONS,
          answers: [],
          feedback: [],
          current_question_index: 0,
          current_follow_up_count: 0,
          active_follow_up: null,
          summary: null,
          state: "in_progress",
          partialFeedback: null,
        });
        return;
      }

      const resumeText = analysisResult
        ? composeResumeText(analysisResult.resume, sectionOverrides)
        : "";

      const res = await startSession(
        resolvedCompany,
        seniority,
        questionMode,
        resumeText
      );
      if (!res.ok) {
        throw new Error("Failed to start session");
      }
      const data = (await res.json()) as {
        session_id: string;
        questions: InterviewQuestion[];
      };
      setInterviewSession({
        session_id: data.session_id,
        company: resolvedCompany,
        seniority,
        question_mode: questionMode,
        questions: data.questions,
        answers: [],
        feedback: [],
        current_question_index: 0,
        current_follow_up_count: 0,
        active_follow_up: null,
        summary: null,
        state: "in_progress",
        partialFeedback: null,
      });
    } catch {
      setInterviewError("Failed to start session");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          background: "#f5f0ff",
          border: "1.5px solid #e9d5ff",
          borderRadius: 999,
          padding: "5px 14px",
          fontSize: 12,
          fontWeight: 600,
          color: "#7c3aed",
          marginBottom: 16,
        }}
      >
        ✦ AI-Powered Interview Practice
      </div>

      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: "#111827",
          marginBottom: 8,
        }}
      >
        Practice like it&apos;s real
      </div>

      <div style={{ fontSize: 15, color: "#6b7280", marginBottom: 28 }}>
        3 questions. Immediate feedback. Dimension-aware scoring.
      </div>

      {lastSession ? (
        <>
          <ContinuityCard
            session={lastSession}
            onPracticeGap={handlePracticeGap}
            onToggleHistory={() => setShowHistory((v) => !v)}
            showHistory={showHistory}
          />
          {showHistory && pastSessions.length > 1 ? (
            <div
              style={{
                background: "#ffffff",
                border: "1.5px solid #e5e7eb",
                borderRadius: 14,
                padding: "12px 16px",
                marginBottom: 24,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {pastSessions.slice(1).map((s) => (
                <div
                  key={s.session_id}
                  style={{
                    fontSize: 13,
                    color: "#374151",
                    padding: "8px 0",
                    borderBottom: "1px solid #f3f4f6",
                  }}
                >
                  {formatCompanyLabel(s.company)} · {SENIORITY_LABELS[s.seniority]} ·{" "}
                  {formatRelativeTime(s.created_at)}
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 10,
          marginBottom: 28,
        }}
      >
        {["3 questions", "7 dimensions", "7 anti-patterns detected"].map((label) => (
          <div
            key={label}
            style={{
              background: "#f9fafb",
              border: "1.5px solid #e5e7eb",
              borderRadius: 10,
              padding: "10px 16px",
              fontSize: 13,
              fontWeight: 500,
              color: "#374151",
              textAlign: "center",
            }}
          >
            {label}
          </div>
        ))}
      </div>

      <div
        style={{
          background: "#ffffff",
          border: "1.5px solid #e5e7eb",
          borderRadius: 18,
          padding: 28,
        }}
      >
        <div
          style={{
            fontSize: 12,
            color: "#6b7280",
            marginBottom: 18,
            lineHeight: 1.5,
          }}
        >
          Your answers are stored to help track your improvement over time.
        </div>

        <div style={{ marginBottom: 22 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "#374151",
              marginBottom: 8,
            }}
          >
            Target company
          </div>
          <select
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 14px",
              fontSize: 14,
              color: "#111827",
              border: "1.5px solid #e5e7eb",
              borderRadius: 10,
              background: "#ffffff",
              outline: "none",
              appearance: "none",
              cursor: "pointer",
            }}
          >
            <option value="">Select a company...</option>
            {COMPANIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {company && company !== "Other" ? (
            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 6 }}>
              {getHint(company)}
            </div>
          ) : null}
          {company === "Other" ? (
            <input
              type="text"
              placeholder="Type company name..."
              value={customCompany}
              onChange={(e) => setCustomCompany(e.target.value)}
              style={{
                width: "100%",
                marginTop: 10,
                padding: "10px 14px",
                fontSize: 14,
                color: "#111827",
                border: "1.5px solid #e5e7eb",
                borderRadius: 10,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          ) : null}
        </div>

        <div style={{ marginBottom: 22 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: "#374151",
              marginBottom: 8,
            }}
          >
            Seniority level
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {SENIORITY_OPTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSeniority(s)}
                style={{
                  padding: "8px 18px",
                  borderRadius: 999,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: "pointer",
                  border: "1.5px solid",
                  borderColor: seniority === s ? "#6366f1" : "#e5e7eb",
                  background: seniority === s ? "#eef2ff" : "#ffffff",
                  color: seniority === s ? "#4f46e5" : "#374151",
                }}
              >
                {SENIORITY_LABELS[s]}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "#6b7280", marginTop: 6 }}>
            Inferred from your resume · rubric adapts to this level
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: "auto auto",
            gap: 12,
          }}
        >
          <QuestionStyleCard
            mode="behavioral"
            active={questionMode === "behavioral"}
            onSelect={() => setQuestionMode("behavioral")}
          />
          <QuestionStyleCard
            mode="scenario"
            active={questionMode === "scenario"}
            onSelect={() => setQuestionMode("scenario")}
          />
          <QuestionStyleCard
            mode="mixed"
            active={questionMode === "mixed"}
            onSelect={() => setQuestionMode("mixed")}
            style={{ gridColumn: "1 / -1" }}
          />
        </div>

        <div style={{ marginTop: 24 }}>
          <button
            type="button"
            disabled={!canStart || loading}
            onClick={() => void handleStartSession()}
            style={{
              width: "100%",
              padding: "14px 0",
              fontSize: 15,
              fontWeight: 700,
              background: canStart && !loading ? "#6366f1" : "#f3f4f6",
              color: canStart && !loading ? "#ffffff" : "#9ca3af",
              border: "none",
              borderRadius: 12,
              cursor: canStart && !loading ? "pointer" : "not-allowed",
              boxShadow:
                canStart && !loading ? "0 4px 0 #4338ca" : "0 4px 0 #e5e7eb",
              transform: "translateY(0)",
              transition: "transform 0.1s",
            }}
            onMouseDown={(e) => {
              if (canStart && !loading) {
                (e.currentTarget as HTMLElement).style.transform = "translateY(3px)";
              }
            }}
            onMouseUp={(e) => {
              if (canStart && !loading) {
                (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
              }
            }}
          >
            {loading ? "Generating your questions..." : "Start session"}
          </button>
          <div
            style={{
              fontSize: 12,
              color: "#9ca3af",
              textAlign: "center",
              marginTop: 8,
            }}
          >
            {canStart
              ? "3 questions · immediate feedback · ~12 minutes"
              : "Select a company to begin"}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MockInterview() {
  const session = useResumeStore((s) => s.interviewSession);
  const activeTab = useResumeStore((s) => s.activeTab);
  const setActiveTab = useResumeStore((s) => s.setActiveTab);
  const clearInterviewSession = useResumeStore((s) => s.clearInterviewSession);
  const setInterviewSummary = useResumeStore((s) => s.setInterviewSummary);
  const setInterviewError = useResumeStore((s) => s.setInterviewError);
  const fetchInterviewHistory = useResumeStore((s) => s.fetchInterviewHistory);
  const sessionState = session?.state ?? "idle" as const;

  useEffect(() => {
    if (activeTab !== "mock_interview") {
      const cancel = useResumeStore.getState()._cancelStream;
      if (cancel) {
        cancel();
        useResumeStore.setState({ _cancelStream: null, interviewLoading: false });
      }
    }
  }, [activeTab]);

  useEffect(() => {
    return () => {
      clearInterviewSession();
    };
  }, [clearInterviewSession]);

  useEffect(() => {
    if (sessionState !== "summary") return;
    if (!session?.session_id) return;
    if (session.summary) return;

    const fetchSummary = async () => {
      try {
        const res = await fetchSessionSummary(session.session_id);
        if (!res.ok) {
          throw new Error("Failed to load summary");
        }
        const data: SessionSummary = await res.json();
        setInterviewSummary(data);
        void fetchInterviewHistory();
      } catch {
        setInterviewError("Failed to load summary");
      }
    };

    fetchSummary();
  }, [
    sessionState,
    session?.session_id,
    setInterviewSummary,
    setInterviewError,
    fetchInterviewHistory,
  ]);

  if (sessionState === "idle" || sessionState === "configuring") {
    return (
      <>
        <style>{KEYFRAMES}</style>
        <PreSessionScreen />
      </>
    );
  }

  if (sessionState === "summary") {
    if (!session || !session.summary) {
      return (
        <div style={{ padding: "40px 0", display: "flex", flexDirection: "column", gap: 20 }}>
          {[100, 70, 85, 50].map((w, i) => (
            <div
              key={i}
              style={{
                width: `${w}%`,
                height: 18,
                borderRadius: 8,
                background: "#f3f4f6",
                animation: "pulse 1.4s ease-in-out infinite",
                animationDelay: `${i * 0.12}s`,
              }}
            />
          ))}
        </div>
      );
    }
    return (
      <>
        <style>{KEYFRAMES}</style>
        <SummaryScreen session={session} summary={session.summary} setActiveTab={setActiveTab} />
      </>
    );
  }

  if (!session) {
    return null;
  }

  return (
    <>
      <style>{KEYFRAMES}</style>
      <InSessionView session={session} />
    </>
  );
}
