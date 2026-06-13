import { useEffect, useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { T } from "../../tokens";

interface QuickReactionBannerProps {
  onDismiss: () => void;
}

const REACTIONS = [
  { value: "surprised", emoji: "😮", label: "Surprised" },
  { value: "useful", emoji: "😊", label: "Useful" },
  { value: "confused", emoji: "😕", label: "Confused" },
  { value: "expected", emoji: "😐", label: "Expected" },
] as const;

const EXPAND_ON = new Set(["confused", "expected"]);

export function QuickReactionBanner({ onDismiss }: QuickReactionBannerProps) {
  const [reaction, setReaction] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [hoveredReaction, setHoveredReaction] = useState<string | null>(null);
  const [textareaFocused, setTextareaFocused] = useState(false);

  const { submit } = useFeedbackSubmit();

  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(() => onDismiss(), 2000);
    return () => clearTimeout(timer);
  }, [submitted, onDismiss]);

  const handleEmojiTap = (value: string) => {
    setReaction(value);
    void submit({ moment_type: "quick_reaction", response_value: value });
    if (EXPAND_ON.has(value)) {
      setExpanded(true);
    } else {
      setSubmitted(true);
    }
  };

  const handleTextSubmit = () => {
    if (!text.trim() || !reaction) return;
    void submit({
      moment_type: "quick_reaction",
      response_value: reaction,
      open_text: text.trim(),
    });
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div style={{ marginTop: "20px", marginBottom: "8px" }}>
        <div
          style={{
            background: T.emeraldLight,
            border: `1.5px solid ${T.emeraldBorder}`,
            borderRadius: "14px",
            padding: "12px 16px",
            display: "flex",
            alignItems: "center",
          }}
        >
          <span style={{ color: T.emerald, fontSize: "13px", fontWeight: 600 }}>
            ✓ Thanks
          </span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginTop: "20px", marginBottom: "8px" }}>
      <div
        style={{
          background: T.bgCard,
          border: `1.5px solid ${T.border}`,
          borderRadius: "14px",
          padding: "14px 16px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "12px",
          }}
        >
          <div style={{ fontSize: "13px", fontWeight: 600, color: T.textPrimary }}>
            How does this feel?
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

        <div style={{ display: "flex" }}>
          {REACTIONS.map((option, index) => {
            const isHovered = hoveredReaction === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => handleEmojiTap(option.value)}
                onMouseEnter={() => setHoveredReaction(option.value)}
                onMouseLeave={() => setHoveredReaction(null)}
                style={{
                  flex: 1,
                  marginRight: index < REACTIONS.length - 1 ? "8px" : 0,
                  padding: "8px 4px",
                  border: `1.5px solid ${isHovered ? T.primary : T.border}`,
                  borderRadius: "12px",
                  background: isHovered ? T.bgHover : "none",
                  cursor: "pointer",
                  fontSize: "13px",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  fontFamily: "inherit",
                }}
              >
                <span>{option.emoji}</span>
                <span style={{ fontSize: "10px", color: T.textSecondary, marginTop: "3px" }}>
                  {option.label}
                </span>
              </button>
            );
          })}
        </div>

        {expanded ? (
          <div style={{ marginTop: "10px" }}>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onFocus={() => setTextareaFocused(true)}
              onBlur={() => setTextareaFocused(false)}
              placeholder="What were you expecting?"
              style={{
                width: "100%",
                border: `1.5px solid ${textareaFocused ? T.primary : T.border}`,
                borderRadius: "10px",
                background: T.bgInput,
                padding: "8px 10px",
                fontSize: "13px",
                fontFamily: "inherit",
                resize: "vertical",
                minHeight: "60px",
                boxSizing: "border-box",
              }}
            />
            <button
              type="button"
              onClick={handleTextSubmit}
              disabled={!text.trim()}
              style={{
                marginTop: "6px",
                padding: "6px 14px",
                borderRadius: "8px",
                border: "none",
                cursor: text.trim() ? "pointer" : "not-allowed",
                fontSize: "12px",
                fontFamily: "inherit",
                background: text.trim() ? T.primary : T.textDisabled,
                color: text.trim() ? "#ffffff" : T.textMuted,
              }}
            >
              Send
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
