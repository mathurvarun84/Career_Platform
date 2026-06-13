import { useEffect, useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { T } from "../../tokens";

interface ReengagementBannerProps {
  onDismiss: () => void;
}

const Q1 = {
  label: "What brought you back today?",
  options: [
    "Applying for a new role",
    "Improving my resume",
    "Interview practice",
    "Just exploring",
  ],
};

const Q2 = {
  label: "What stopped you from coming back sooner?",
  options: [
    "Busy / no reason",
    "Not sure what to do next",
    "Wasn't helpful enough",
    "Got the job!",
  ],
};

export function ReengagementBanner({ onDismiss }: ReengagementBannerProps) {
  const [q1Answer, setQ1Answer] = useState<string | null>(null);
  const [q2Answer, setQ2Answer] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [textareaFocused, setTextareaFocused] = useState(false);

  const { submit } = useFeedbackSubmit();

  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(() => onDismiss(), 1500);
    return () => clearTimeout(timer);
  }, [submitted, onDismiss]);

  const handleDone = () => {
    if (q1Answer) {
      void submit({
        moment_type: "reengagement",
        feature_name: "reason",
        response_value: q1Answer,
        open_text: text.trim() || undefined,
      });
    }
    if (q2Answer) {
      void submit({
        moment_type: "reengagement",
        feature_name: "blocker",
        response_value: q2Answer,
      });
    }
    setSubmitted(true);
  };

  const canSubmit = Boolean(q1Answer || q2Answer);

  if (submitted) {
    return (
      <div
        style={{
          background: T.bgCard,
          border: `1.5px solid ${T.border}`,
          borderRadius: "14px",
          padding: "16px 18px",
          marginBottom: "16px",
        }}
      >
        <div style={{ fontSize: "13px", color: T.emerald, fontWeight: 600 }}>
          ✓ Got it, thanks!
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: "14px",
        padding: "16px 18px",
        marginBottom: "16px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "14px",
        }}
      >
        <div style={{ fontSize: "13px", fontWeight: 600, color: T.textPrimary }}>
          Welcome back — quick check-in
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: "12px",
            color: T.textMuted,
            fontFamily: "inherit",
          }}
        >
          skip
        </button>
      </div>

      <div style={{ fontSize: "12px", fontWeight: 600, color: T.textSecondary, marginBottom: "8px" }}>
        {Q1.label}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", marginBottom: "12px" }}>
        {Q1.options.map((option, index) => {
          const isSelected = q1Answer === option;
          return (
            <button
              key={option}
              type="button"
              onClick={() => setQ1Answer(option)}
              style={{
                padding: "5px 12px",
                border: `1.5px solid ${isSelected ? T.primary : T.border}`,
                borderRadius: "100px",
                fontSize: "12px",
                color: isSelected ? T.primary : T.textSecondary,
                background: isSelected ? T.primaryLight : "none",
                cursor: "pointer",
                marginRight: index < Q1.options.length - 1 ? "6px" : 0,
                marginBottom: "6px",
                fontFamily: "inherit",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = T.primary;
                  (e.currentTarget as HTMLButtonElement).style.background = T.bgHover;
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = T.border;
                  (e.currentTarget as HTMLButtonElement).style.background = "none";
                }
              }}
            >
              {option}
            </button>
          );
        })}
      </div>

      <div style={{ fontSize: "12px", fontWeight: 600, color: T.textSecondary, marginBottom: "8px" }}>
        {Q2.label}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", marginBottom: "12px" }}>
        {Q2.options.map((option, index) => {
          const isSelected = q2Answer === option;
          return (
            <button
              key={option}
              type="button"
              onClick={() => setQ2Answer(option)}
              style={{
                padding: "5px 12px",
                border: `1.5px solid ${isSelected ? T.primary : T.border}`,
                borderRadius: "100px",
                fontSize: "12px",
                color: isSelected ? T.primary : T.textSecondary,
                background: isSelected ? T.primaryLight : "none",
                cursor: "pointer",
                marginRight: index < Q2.options.length - 1 ? "6px" : 0,
                marginBottom: "6px",
                fontFamily: "inherit",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = T.primary;
                  (e.currentTarget as HTMLButtonElement).style.background = T.bgHover;
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = T.border;
                  (e.currentTarget as HTMLButtonElement).style.background = "none";
                }
              }}
            >
              {option}
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: "4px", marginBottom: "12px" }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, 280))}
          onFocus={() => setTextareaFocused(true)}
          onBlur={() => setTextareaFocused(false)}
          placeholder="Anything else on your mind? (optional)"
          style={{
            width: "100%",
            border: `1.5px solid ${textareaFocused ? T.primary : T.border}`,
            borderRadius: "8px",
            background: T.bgInput,
            padding: "7px 10px",
            fontSize: "12px",
            fontFamily: "inherit",
            resize: "vertical",
            minHeight: "48px",
            boxSizing: "border-box",
          }}
        />
      </div>

      <button
        type="button"
        onClick={handleDone}
        disabled={!canSubmit}
        style={{
          padding: "8px 20px",
          borderRadius: "8px",
          border: "none",
          fontSize: "13px",
          fontWeight: 600,
          cursor: canSubmit ? "pointer" : "not-allowed",
          fontFamily: "inherit",
          background: canSubmit ? T.primary : T.textDisabled,
          color: canSubmit ? "#ffffff" : T.textMuted,
          boxShadow: canSubmit ? `0 2px 0 ${T.primaryFloor}` : "none",
        }}
      >
        Done
      </button>
    </div>
  );
}
