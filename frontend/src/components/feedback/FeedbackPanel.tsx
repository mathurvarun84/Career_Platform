import { useEffect, useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { T } from "../../tokens";

type Sentiment = "loving_it" | "okay" | "not_good";

interface FeedbackPanelProps {
  onClose: () => void;
  userFirstName: string;
}

const SENTIMENT_OPTIONS: { value: Sentiment; label: string }[] = [
  { value: "loving_it", label: "Loving it" },
  { value: "okay", label: "Okay" },
  { value: "not_good", label: "Not good" },
];

const SENTIMENT_COLORS: Record<Sentiment, { border: string; background: string; color: string }> = {
  loving_it: { border: T.emerald, background: T.emeraldLight, color: T.emerald },
  okay: { border: T.amber, background: T.amberLight, color: T.amber },
  not_good: { border: T.rose, background: T.roseLight, color: T.rose },
};

export function FeedbackPanel({ onClose, userFirstName }: FeedbackPanelProps) {
  const [sentiment, setSentiment] = useState<Sentiment | null>(null);
  const [hoveredSentiment, setHoveredSentiment] = useState<Sentiment | null>(null);
  const [text, setText] = useState("");
  const [includeEmail, setIncludeEmail] = useState(true);
  const [textareaFocused, setTextareaFocused] = useState(false);
  const [status, setStatus] = useState<"idle" | "submitting" | "success">("idle");

  const { submit } = useFeedbackSubmit();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    if (status === "success") {
      const timer = setTimeout(() => onClose(), 3000);
      return () => clearTimeout(timer);
    }
  }, [status, onClose]);

  const handleSubmit = async () => {
    if (!text.trim() || status === "submitting") return;
    setStatus("submitting");
    const ok = await submit({
      moment_type: "product_feedback",
      response_value: sentiment ?? undefined,
      open_text: text.trim(),
      include_email: includeEmail,
    });
    if (ok) {
      setStatus("success");
    } else {
      setStatus("idle");
    }
  };

  const canSend = text.trim().length > 0;

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 99,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: "68px",
          right: "40px",
          zIndex: 100,
          width: "300px",
          background: T.bgCard,
          border: `1.5px solid ${T.border}`,
          borderRadius: "18px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
          padding: "20px",
        }}
      >
        {status === "success" ? (
          <div style={{ textAlign: "center", padding: "24px 0" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "50%",
                background: T.emeraldLight,
                border: `2px solid ${T.emerald}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path
                  d="M3 8L6.5 11.5L13 4"
                  stroke={T.emerald}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div
              style={{
                fontSize: "15px",
                fontWeight: 600,
                color: T.emerald,
                marginTop: "12px",
              }}
            >
              Thanks, {userFirstName}!
            </div>
            <div style={{ fontSize: "13px", color: T.textSecondary, marginTop: "4px" }}>
              Got it.
            </div>
          </div>
        ) : (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: "16px",
              }}
            >
              <div style={{ fontSize: "14px", fontWeight: 600, color: T.textPrimary }}>
                Give feedback
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                style={{
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  color: T.textMuted,
                  fontSize: "16px",
                }}
              >
                {"✕"}
              </button>
            </div>

            <div style={{ display: "flex", marginBottom: "14px" }}>
              {SENTIMENT_OPTIONS.map((option, index) => {
                const isSelected = sentiment === option.value;
                const isHovered = hoveredSentiment === option.value;
                const selectedStyle = SENTIMENT_COLORS[option.value];
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSentiment(option.value)}
                    onMouseEnter={() => setHoveredSentiment(option.value)}
                    onMouseLeave={() => setHoveredSentiment(null)}
                    style={{
                      flex: 1,
                      marginRight: index < SENTIMENT_OPTIONS.length - 1 ? "8px" : 0,
                      padding: "8px 0",
                      border: `1.5px solid ${
                        isSelected
                          ? selectedStyle.border
                          : isHovered
                            ? T.primary
                            : T.border
                      }`,
                      borderRadius: "12px",
                      background: isSelected
                        ? selectedStyle.background
                        : isHovered
                          ? T.bgHover
                          : "none",
                      cursor: "pointer",
                      fontSize: "12px",
                      color: isSelected ? selectedStyle.color : T.textSecondary,
                      fontFamily: "inherit",
                    }}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>

            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onFocus={() => setTextareaFocused(true)}
              onBlur={() => setTextareaFocused(false)}
              placeholder="What's on your mind? (optional)"
              style={{
                width: "100%",
                minHeight: "80px",
                border: `1.5px solid ${textareaFocused ? T.primary : T.border}`,
                borderRadius: "10px",
                background: T.bgInput,
                padding: "10px 12px",
                fontSize: "13px",
                fontFamily: "inherit",
                resize: "vertical",
                boxSizing: "border-box",
              }}
            />

            <div
              style={{
                display: "flex",
                alignItems: "center",
                marginTop: "10px",
                marginBottom: "14px",
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  fontSize: "12px",
                  color: T.textSecondary,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={includeEmail}
                  onChange={(e) => setIncludeEmail(e.target.checked)}
                  style={{ marginRight: "6px" }}
                />
                Include my email for follow-up
              </label>
            </div>

            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={!canSend || status === "submitting"}
              style={{
                width: "100%",
                padding: "10px",
                borderRadius: "10px",
                border: "none",
                cursor: canSend && status !== "submitting" ? "pointer" : "not-allowed",
                fontSize: "13px",
                fontWeight: 600,
                fontFamily: "inherit",
                background: canSend ? T.primary : T.textDisabled,
                color: canSend ? "#ffffff" : T.textMuted,
                boxShadow: canSend ? T.shadowPrimarySm : "none",
              }}
            >
              {status === "submitting" ? "Sending..." : "Send"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
