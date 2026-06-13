import { useEffect, useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { T } from "../../tokens";

interface PMFFollowUpCardProps {
  variant: "very_disappointed" | "not_disappointed";
  onDismiss: () => void;
}

const QUESTION: Record<string, string> = {
  very_disappointed: "What's the main thing RIP V2 does for you?",
  not_disappointed: "What's missing for you?",
};

export function PMFFollowUpCard({ variant, onDismiss }: PMFFollowUpCardProps) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [textareaFocused, setTextareaFocused] = useState(false);

  const { submit } = useFeedbackSubmit();

  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(() => onDismiss(), 2000);
    return () => clearTimeout(timer);
  }, [submitted, onDismiss]);

  const handleSend = () => {
    if (!text.trim()) return;
    void submit({
      moment_type: "pmf_followup",
      response_value: variant,
      open_text: text.trim(),
    });
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          zIndex: 180,
          width: "280px",
          background: T.bgCard,
          border: `1.5px solid ${T.border}`,
          borderRadius: "16px",
          padding: "16px",
          boxShadow: "0 4px 24px rgba(0,0,0,0.10)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "60px",
          }}
        >
          <span style={{ fontSize: "13px", color: T.emerald, fontWeight: 600 }}>
            ✓ Thanks!
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        zIndex: 180,
        width: "280px",
        background: T.bgCard,
        border: `1.5px solid ${T.border}`,
        borderRadius: "16px",
        padding: "16px",
        boxShadow: "0 4px 24px rgba(0,0,0,0.10)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "10px",
        }}
      >
        <div style={{ fontSize: "13px", fontWeight: 600, color: T.textPrimary }}>
          {QUESTION[variant]}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            color: T.textMuted,
            fontSize: "14px",
            fontFamily: "inherit",
          }}
        >
          ✕
        </button>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={() => setTextareaFocused(true)}
        onBlur={() => setTextareaFocused(false)}
        placeholder="Type your answer..."
        style={{
          width: "100%",
          minHeight: "64px",
          border: `1.5px solid ${textareaFocused ? T.primary : T.border}`,
          borderRadius: "10px",
          background: T.bgInput,
          padding: "8px 10px",
          fontSize: "13px",
          fontFamily: "inherit",
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />

      <button
        type="button"
        onClick={handleSend}
        disabled={!text.trim()}
        style={{
          marginTop: "8px",
          width: "100%",
          padding: "8px",
          borderRadius: "8px",
          border: "none",
          fontSize: "13px",
          fontWeight: 600,
          cursor: text.trim() ? "pointer" : "not-allowed",
          fontFamily: "inherit",
          background: text.trim() ? T.primary : T.textDisabled,
          color: text.trim() ? "#ffffff" : T.textMuted,
          boxShadow: text.trim() ? `0 2px 0 ${T.primaryFloor}` : "none",
        }}
      >
        Send
      </button>
    </div>
  );
}
