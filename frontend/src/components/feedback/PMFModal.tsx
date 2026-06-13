import { useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { useResumeStore } from "../../store/useResumeStore";
import { T } from "../../tokens";

type PMFResponse = "very_disappointed" | "somewhat_disappointed" | "not_disappointed";

interface PMFModalProps {
  onClose: (variant?: "very_disappointed" | "not_disappointed") => void;
}

const OPTIONS: { value: PMFResponse; emoji: string; label: string }[] = [
  { value: "very_disappointed", emoji: "😔", label: "Very disappointed" },
  { value: "somewhat_disappointed", emoji: "😐", label: "Somewhat disappointed" },
  { value: "not_disappointed", emoji: "🤷", label: "Not disappointed" },
];

export function PMFModal({ onClose }: PMFModalProps) {
  const [selected, setSelected] = useState<PMFResponse | null>(null);
  const [hoveredOption, setHoveredOption] = useState<PMFResponse | null>(null);

  const { submit } = useFeedbackSubmit();
  const markPMFSkipped = useResumeStore((s) => s.markPMFSkipped);

  const handleSelect = (option: PMFResponse) => {
    setSelected(option);
    void submit({ moment_type: "pmf_signal", response_value: option });
    if (option === "very_disappointed" || option === "not_disappointed") {
      onClose(option);
    } else {
      onClose();
    }
  };

  const handleSkip = () => {
    void submit({ moment_type: "pmf_signal", response_value: "skipped" });
    markPMFSkipped();
    onClose();
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(13,13,26,0.4)",
        zIndex: 200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: T.bgCard,
          borderRadius: "20px",
          padding: "28px 32px",
          maxWidth: "440px",
          width: "90%",
          position: "relative",
        }}
      >
        <button
          type="button"
          onClick={handleSkip}
          style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: "16px",
            color: T.textMuted,
            fontFamily: "inherit",
          }}
        >
          ✕
        </button>

        <div
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: T.primary,
            textTransform: "uppercase",
            letterSpacing: "0.5px",
            marginBottom: "8px",
          }}
        >
          Quick question (8 seconds)
        </div>

        <div style={{ fontSize: "16px", fontWeight: 600, color: T.textPrimary, marginBottom: "20px" }}>
          How would you feel if you could no longer use RIP V2?
        </div>

        {OPTIONS.map((opt) => {
          const isSelected = selected === opt.value;
          const isHovered = hoveredOption === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleSelect(opt.value)}
              onMouseEnter={() => setHoveredOption(opt.value)}
              onMouseLeave={() => setHoveredOption(null)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "14px 18px",
                marginBottom: "8px",
                border: `1.5px solid ${isSelected || isHovered ? T.primary : T.border}`,
                borderRadius: "10px",
                background: isSelected ? T.primaryLight : isHovered ? T.bgInput : "none",
                cursor: "pointer",
                fontSize: "14px",
                color: T.textPrimary,
                fontFamily: "inherit",
              }}
            >
              {opt.emoji}  {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
