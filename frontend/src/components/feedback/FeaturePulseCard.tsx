import { useEffect, useRef, useState } from "react";

import { useFeedbackSubmit } from "../../hooks/useFeedbackSubmit";
import { T } from "../../tokens";

interface FeaturePulseCardProps {
  featureName: "coach" | "interview" | "rewriter" | "gap_analysis" | "jd_fetch";
  featureLabel: string;
  question: string;
  onDismiss: () => void;
}

const FAILURE_OPTIONS: Record<string, string[]> = {
  coach: [
    "Suggestions were too generic",
    "Changed my meaning",
    "Wasn't sure what to do next",
  ],
  interview: [
    "Questions weren't relevant",
    "Feedback too harsh / too soft",
    "Didn't understand scoring",
  ],
  rewriter: [
    "Rewrites changed my meaning",
    "Too aggressive / too safe",
    "Didn't fix the actual problem",
  ],
  gap_analysis: [
    "Gaps didn't match the JD",
    "Too many gaps flagged",
    "Missing gaps I know exist",
  ],
  jd_fetch: [
    "Wrong role was fetched",
    "JD was incomplete",
    "Wrong company",
  ],
};

export function FeaturePulseCard({
  featureName,
  featureLabel,
  question,
  onDismiss,
}: FeaturePulseCardProps) {
  const [verdict, setVerdict] = useState<"up" | "down" | null>(null);
  const [failureCategory, setFailureCategory] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [hoveredOption, setHoveredOption] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { submit } = useFeedbackSubmit();

  const options = FAILURE_OPTIONS[featureName] ?? [];

  useEffect(() => {
    if (!submitted) return;
    const timer = setTimeout(() => onDismiss(), 1500);
    return () => clearTimeout(timer);
  }, [submitted, onDismiss]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleThumbsUp = () => {
    setVerdict("up");
    void submit({
      moment_type: "feature_pulse",
      feature_name: featureName,
      response_value: "thumbs_up",
    });
    setSubmitted(true);
  };

  const handleThumbsDown = () => {
    setVerdict("down");
  };

  const handleCategoryTap = (option: string) => {
    setFailureCategory(option);
    if (option === "other") {
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void submit({
        moment_type: "feature_pulse",
        feature_name: featureName,
        response_value: "thumbs_down",
        failure_category: option,
      });
      setSubmitted(true);
    }, 400);
  };

  const submitOther = () => {
    if (!otherText.trim()) return;
    void submit({
      moment_type: "feature_pulse",
      feature_name: featureName,
      response_value: "thumbs_down",
      failure_category: "other",
      open_text: otherText.trim(),
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
          zIndex: 80,
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
        zIndex: 80,
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
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "10px",
        }}
      >
        <div
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: T.primary,
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          {featureLabel}
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

      <div style={{ fontSize: "13px", fontWeight: 600, color: T.textPrimary, marginBottom: "12px" }}>
        {question}
      </div>

      <div style={{ display: "flex" }}>
        <button
          type="button"
          onClick={handleThumbsUp}
          style={{
            flex: 1,
            marginRight: "8px",
            padding: "8px",
            border: `1.5px solid ${verdict === "up" ? T.primary : T.border}`,
            borderRadius: "10px",
            background: verdict === "up" ? T.primaryLight : "none",
            cursor: "pointer",
            fontSize: "20px",
            display: "flex",
            justifyContent: "center",
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => {
            if (verdict !== "up") {
              (e.currentTarget as HTMLButtonElement).style.borderColor = T.primary;
              (e.currentTarget as HTMLButtonElement).style.background = T.bgHover;
            }
          }}
          onMouseLeave={(e) => {
            if (verdict !== "up") {
              (e.currentTarget as HTMLButtonElement).style.borderColor = T.border;
              (e.currentTarget as HTMLButtonElement).style.background = "none";
            }
          }}
        >
          👍
        </button>
        <button
          type="button"
          onClick={handleThumbsDown}
          style={{
            flex: 1,
            padding: "8px",
            border: `1.5px solid ${verdict === "down" ? T.primary : T.border}`,
            borderRadius: "10px",
            background: verdict === "down" ? T.primaryLight : "none",
            cursor: "pointer",
            fontSize: "20px",
            display: "flex",
            justifyContent: "center",
            fontFamily: "inherit",
          }}
          onMouseEnter={(e) => {
            if (verdict !== "down") {
              (e.currentTarget as HTMLButtonElement).style.borderColor = T.primary;
              (e.currentTarget as HTMLButtonElement).style.background = T.bgHover;
            }
          }}
          onMouseLeave={(e) => {
            if (verdict !== "down") {
              (e.currentTarget as HTMLButtonElement).style.borderColor = T.border;
              (e.currentTarget as HTMLButtonElement).style.background = "none";
            }
          }}
        >
          👎
        </button>
      </div>

      {verdict === "down" ? (
        <div style={{ marginTop: "10px" }}>
          {options.map((option) => {
            const isSelected = failureCategory === option;
            const isHovered = hoveredOption === option;
            return (
              <button
                key={option}
                type="button"
                onClick={() => handleCategoryTap(option)}
                onMouseEnter={() => setHoveredOption(option)}
                onMouseLeave={() => setHoveredOption(null)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "7px 10px",
                  border: `1.5px solid ${isSelected || isHovered ? T.primary : T.border}`,
                  borderRadius: "8px",
                  background: isSelected ? T.primaryLight : isHovered ? T.bgHover : "none",
                  cursor: "pointer",
                  fontSize: "12px",
                  color: isSelected ? T.primary : T.textSecondary,
                  marginBottom: "6px",
                  fontFamily: "inherit",
                }}
              >
                {option}
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => handleCategoryTap("other")}
            onMouseEnter={() => setHoveredOption("other")}
            onMouseLeave={() => setHoveredOption(null)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "7px 10px",
              border: `1.5px solid ${failureCategory === "other" || hoveredOption === "other" ? T.primary : T.border}`,
              borderRadius: "8px",
              background:
                failureCategory === "other"
                  ? T.primaryLight
                  : hoveredOption === "other"
                    ? T.bgHover
                    : "none",
              cursor: "pointer",
              fontSize: "12px",
              color: failureCategory === "other" ? T.primary : T.textSecondary,
              fontFamily: "inherit",
            }}
          >
            Other
          </button>
          {failureCategory === "other" ? (
            <input
              type="text"
              value={otherText}
              onChange={(e) => setOtherText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitOther();
              }}
              onBlur={submitOther}
              placeholder="Tell us more..."
              style={{
                width: "100%",
                marginTop: "6px",
                padding: "6px 8px",
                border: `1.5px solid ${T.border}`,
                borderRadius: "8px",
                fontSize: "12px",
                fontFamily: "inherit",
                boxSizing: "border-box",
              }}
              onFocus={(e) => {
                (e.currentTarget as HTMLInputElement).style.borderColor = T.primary;
              }}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
