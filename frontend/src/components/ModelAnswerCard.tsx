import { useState } from "react";

import { useResumeStore } from "../store/useResumeStore";
import type { ModelAnswerCardState } from "../types";

const KEYFRAMES = `
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}
`;

interface ModelAnswerCardProps {
  question_id: string;
  session_id: string;
  answer_text: string;
}

function SkeletonLines() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
      {[100, 72, 88, 45].map((w) => (
        <div
          key={w}
          style={{
            width: `${w}%`,
            height: 14,
            borderRadius: 4,
            background: "#e5e7eb",
            animation: "pulse 1.4s ease-in-out infinite",
          }}
        />
      ))}
    </div>
  );
}

export default function ModelAnswerCard({
  question_id,
  session_id,
  answer_text,
}: ModelAnswerCardProps) {
  const cardState = useResumeStore(
    (s) => s.model_answer_cards[question_id] as ModelAnswerCardState | undefined
  );
  const fetchModelAnswer = useResumeStore((s) => s.fetchModelAnswer);
  const [isOpen, setIsOpen] = useState(false);

  if (answer_text.trim().split(/\s+/).filter(Boolean).length < 50) {
    return null;
  }

  if (cardState?.status === "skipped") {
    return null;
  }

  const handleExpand = (): void => {
    const nextOpen = !isOpen;
    setIsOpen(nextOpen);
    if (!nextOpen) {
      return;
    }
    if (
      cardState?.status === "loaded" ||
      cardState?.status === "loading" ||
      cardState?.status === "skipped"
    ) {
      return;
    }
    void fetchModelAnswer(session_id, question_id);
  };

  const status = cardState?.status ?? "idle";

  return (
    <>
      <style>{KEYFRAMES}</style>
      <div style={{ marginBottom: 16 }}>
        <button
          type="button"
          onClick={handleExpand}
          style={{
            width: "100%",
            textAlign: "left",
            background: "#f9fafb",
            border: "1.5px solid #e5e7eb",
            borderRadius: isOpen ? "12px 12px 0 0" : 12,
            padding: "12px 16px",
            cursor: "pointer",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                display: "inline-block",
                transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform 200ms",
                color: "#6b7280",
                fontSize: 12,
              }}
            >
              ▶
            </span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>
                How this could have sounded
              </div>
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                A stronger version using what you shared
              </div>
            </div>
          </div>
        </button>

        {isOpen ? (
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderTop: "none",
              borderLeft: "4px solid #6366f1",
              background: "#f5f3ff",
              padding: 16,
              borderRadius: "0 0 12px 0",
            }}
          >
            {status === "loading" ? <SkeletonLines /> : null}

            {status === "error" ? (
              <div style={{ fontSize: 13, color: "#991b1b" }}>
                Couldn&apos;t load this — try expanding again.
              </div>
            ) : null}

            {status === "loaded" && cardState?.data ? (
              <>
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.7,
                    color: "#374151",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {cardState.data.text}
                </div>
                {cardState.data.what_changed ? (
                  <div
                    style={{
                      background: "#fffbeb",
                      border: "1.5px solid #fcd34d",
                      borderRadius: 8,
                      fontSize: 13,
                      padding: "10px 14px",
                      marginTop: 14,
                      color: "#92400e",
                      lineHeight: 1.55,
                    }}
                  >
                    ✦ What changed: {cardState.data.what_changed}
                  </div>
                ) : null}
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
