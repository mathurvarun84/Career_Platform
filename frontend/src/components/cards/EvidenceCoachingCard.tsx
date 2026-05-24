import { useMemo, useRef, useState } from "react";

import { addBulletToResume, generateCoachingBullet } from "../../api/client";
import type { CareerMemoryEntry, PriorityFix } from "../../types";

type CardState = "question" | "generating" | "review" | "done";

interface EvidenceCoachingCardProps {
  fix: PriorityFix;
  fixKey: string;
  onDone?: (entry: CareerMemoryEntry) => void | Promise<void>;
  sessionId?: string;
}

const pulseKeyframes = `
  @keyframes pulse-coaching {
    0%, 100% {
      border-color: #6c47ff;
      box-shadow: 0 0 0 2px #6c47ff33;
    }
    50% {
      border-color: #c4b5fd;
      box-shadow: 0 0 0 2px #c4b5fd66;
    }
  }
`;

const normalizeSkillCategory = (
  section: string
): CareerMemoryEntry["skill_category"] => {
  const lower = section.toLowerCase();
  if (lower.includes("leader")) return "leadership";
  if (lower.includes("deliver")) return "delivery";
  if (lower.includes("commun")) return "communication";
  return "technical";
};

export default function EvidenceCoachingCard({
  fix,
  fixKey,
  onDone,
  sessionId,
}: EvidenceCoachingCardProps) {
  const [cardState, setCardState] = useState<CardState>("question");
  const [rawAnswer, setRawAnswer] = useState("");
  const [generatedBullet, setGeneratedBullet] = useState("");
  const [groundingCheck, setGroundingCheck] = useState(true);
  const [careerMemoryId, setCareerMemoryId] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const hints = fix.coaching_hint ?? [];
  const canGenerate = rawAnswer.trim().length > 15;
  const charCount = rawAnswer.length;
  const canAddToResume = generatedBullet.trim().length > 0 && !isAdding;

  const handleHintClick = (hint: string) => {
    setRawAnswer((prev) => (prev ? `${prev} ${hint}` : hint));
    textareaRef.current?.focus();
  };

  const handleGenerate = async () => {
    if (!canGenerate || !sessionId) return;
    setCardState("generating");
    setAddError(null);

    try {
      const response = await generateCoachingBullet({
        session_id: sessionId,
        gap_id: fixKey,
        section: fix.section,
        sub_label: fix.sub_label ?? null,
        raw_answer: rawAnswer,
        coaching_question: fix.coaching_question ?? fix.gap_reason,
        skill_category: fix.section,
      });

      if (response.error === "generation_timeout") {
        setAddError("Generation took too long — please try again.");
        setCardState("question");
        return;
      }

      setGeneratedBullet(response.generated_bullet);
      setGroundingCheck(response.grounding_check ?? true);
      setCareerMemoryId(response.career_memory_id ?? "");
      setCardState("review");
    } catch (error) {
      console.error("Coaching generation failed:", error);
      setAddError("Failed to generate bullet. Please try again.");
      setCardState("question");
    }
  };

  const handleRegenerate = async () => {
    if (!sessionId) return;
    setCardState("generating");
    setAddError(null);

    try {
      const response = await generateCoachingBullet({
        session_id: sessionId,
        gap_id: fixKey,
        section: fix.section,
        sub_label: fix.sub_label ?? null,
        raw_answer: rawAnswer,
        coaching_question: fix.coaching_question ?? fix.gap_reason,
        skill_category: fix.section,
      });

      if (response.error === "generation_timeout") {
        setAddError("Generation took too long — please try again.");
        setCardState("review");
        return;
      }

      setGeneratedBullet(response.generated_bullet);
      setGroundingCheck(response.grounding_check ?? true);
      setCareerMemoryId(response.career_memory_id ?? "");
      setCardState("review");
    } catch (error) {
      console.error("Coaching regeneration failed:", error);
      setAddError("Failed to regenerate bullet. Please try again.");
      setCardState("review");
    }
  };

  const handleEdit = () => {
    setCardState("question");
    setAddError(null);
  };

  const handleAddToResume = async () => {
    if (!sessionId || !generatedBullet.trim()) return;
    setAddError(null);
    setIsAdding(true);

    try {
      const response = await addBulletToResume({
        session_id: sessionId,
        gap_id: fixKey,
        section: fix.section,
        sub_label: fix.sub_label ?? null,
        bullet_text: generatedBullet,
        placement: "start",
        career_memory_id: careerMemoryId,
      });

      if (response.found_in_doc) {
        const approvedEntry: CareerMemoryEntry = {
          id: careerMemoryId,
          session_id: sessionId,
          gap_id: fixKey,
          section: fix.section,
          sub_label: fix.sub_label ?? null,
          raw_answer: rawAnswer,
          generated_bullet: generatedBullet,
          skill_category: normalizeSkillCategory(fix.section),
          company: null,
          timestamp: new Date().toISOString(),
          user_approved: true,
        };
        setCardState("done");
        await onDone?.(approvedEntry);
      } else {
        setAddError("Could not insert — text may have changed. Try again.");
      }
    } catch (error) {
      console.error("Add to resume failed:", error);
      setAddError("Request failed — please try again.");
    } finally {
      setIsAdding(false);
    }
  };

  const contextSentence = useMemo(() => {
    const reason = fix.gap_reason;
    if (reason.toLowerCase().includes("leadership")) {
      return "Demonstrating leadership impact strengthens your candidacy for senior roles.";
    }
    if (
      reason.toLowerCase().includes("metric") ||
      reason.toLowerCase().includes("outcome")
    ) {
      return "Quantified outcomes help recruiters assess your impact quickly.";
    }
    if (reason.toLowerCase().includes("technical")) {
      return "Specific technical examples validate your claimed expertise.";
    }
    return "Adding evidence for this skill improves your match score significantly.";
  }, [fix.gap_reason]);

  if (cardState === "question") {
    return (
      <div
        style={{
          border: "1.5px solid #e5e7eb",
          background: "#ffffff",
          borderRadius: "10px",
          padding: "20px",
          marginBottom: "16px",
          boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "16px",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-block",
                background: "#fef3c7",
                color: "#92400e",
                borderRadius: "4px",
                padding: "2px 8px",
                fontSize: "11px",
                fontWeight: 700,
                marginRight: "8px",
              }}
            >
              High
            </div>
            <span style={{ fontSize: "13px", color: "#6b7280" }}>
              {fix.gap_reason.substring(0, 60)}
              {fix.gap_reason.length > 60 ? "..." : ""}
            </span>
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "#6b7280",
              fontWeight: 500,
              whiteSpace: "nowrap",
              marginLeft: "12px",
            }}
          >
            Needs Your Input
          </div>
        </div>

        <div
          style={{
            fontSize: "14px",
            color: "#6b7280",
            marginBottom: "12px",
            lineHeight: 1.5,
          }}
        >
          {contextSentence}
        </div>

        <div
          style={{
            background: "#f5f3ff",
            borderLeft: "3px solid #6c47ff",
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "14px",
            fontSize: "14px",
            color: "#3730a3",
            fontWeight: 500,
          }}
        >
          {fix.coaching_question ?? "Can you share a specific example for this area?"}
        </div>

        {hints.length > 0 ? (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px",
              marginBottom: "14px",
            }}
          >
            {hints.map((hint) => (
              <button
                key={hint}
                type="button"
                onClick={() => handleHintClick(hint)}
                style={{
                  background: "#f3f4f6",
                  border: "1px solid #e5e7eb",
                  borderRadius: "20px",
                  padding: "4px 12px",
                  fontSize: "13px",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                {hint}
              </button>
            ))}
          </div>
        ) : null}

        <textarea
          ref={textareaRef}
          className="coaching-textarea"
          value={rawAnswer}
          onChange={(e) => setRawAnswer(e.target.value)}
          placeholder="Describe your experience in a few sentences..."
          style={{
            border: "1.5px solid #e5e7eb",
            borderRadius: "8px",
            padding: "10px 12px",
            width: "100%",
            minHeight: "80px",
            fontSize: "14px",
            lineHeight: 1.55,
            resize: "vertical",
            boxSizing: "border-box",
            outline: "none",
            fontFamily: "inherit",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "#6c47ff";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "#e5e7eb";
          }}
        />

        <style>{`
          .coaching-textarea {
            min-height: 80px;
          }
          @media (max-width: 768px) {
            .coaching-textarea {
              min-height: 120px;
            }
          }
        `}</style>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginTop: "10px",
          }}
        >
          <div
            style={{
              fontSize: "12px",
              color:
                charCount < 150 ? "#9ca3af" : charCount < 200 ? "#d97706" : "#dc2626",
            }}
          >
            {charCount}/200
          </div>
          <button
            type="button"
            disabled={!canGenerate}
            onClick={handleGenerate}
            style={{
              border: "none",
              borderRadius: "10px",
              padding: "10px 16px",
              fontSize: "13px",
              fontWeight: 700,
              cursor: canGenerate ? "pointer" : "not-allowed",
              background: canGenerate ? "#6c47ff" : "#f3f4f6",
              color: canGenerate ? "#ffffff" : "#9ca3af",
              boxShadow: canGenerate
                ? "0 2px 0 #5832d3, 0 4px 10px rgba(108,71,255,0.25)"
                : "0 2px 0 #d1d5db",
            }}
          >
            Generate Bullet →
          </button>
        </div>

        {addError ? (
          <div
            style={{
              color: "#dc2626",
              fontSize: "13px",
              marginTop: "8px",
            }}
          >
            {addError}
          </div>
        ) : null}
      </div>
    );
  }

  if (cardState === "generating") {
    return (
      <>
        <style>{pulseKeyframes}</style>
        <div
          style={{
            border: "1.5px solid #6c47ff",
            background: "#ffffff",
            borderRadius: "10px",
            padding: "32px 20px",
            marginBottom: "16px",
            textAlign: "center",
            animation: "pulse-coaching 1.4s infinite",
          }}
        >
          <div
            style={{
              fontSize: "15px",
              fontWeight: 500,
              color: "#6c47ff",
            }}
          >
            ✦ Crafting your bullet...
          </div>
        </div>
      </>
    );
  }

  if (cardState === "review") {
    return (
      <div
        style={{
          border: "1.5px solid #e5e7eb",
          background: "#ffffff",
          borderRadius: "10px",
          padding: "20px",
          marginBottom: "16px",
          boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
        }}
      >
        <div
          style={{
            fontSize: "13px",
            color: "#6b7280",
            marginBottom: "8px",
          }}
        >
          Here's your new bullet:
        </div>

        {generatedBullet && !groundingCheck ? (
          <div
            style={{
              background: "#fffbeb",
              border: "1.5px solid #fbbf24",
              borderRadius: "10px",
              padding: "8px 12px",
              fontSize: "12px",
              color: "#92400e",
              marginBottom: "8px",
            }}
          >
            ⚠ We added some language — please review before adding to your resume.
          </div>
        ) : null}

        <div
          style={{
            background: "#f0fdf4",
            border: "1.5px solid #bbf7d0",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "12px",
            color: "#166534",
            fontSize: "15px",
            lineHeight: 1.6,
          }}
        >
          {generatedBullet}
        </div>

        <div
          style={{
            display: "flex",
            gap: "8px",
            marginBottom: "12px",
            flexWrap: "wrap",
          }}
        >
          <button
            type="button"
            onClick={handleRegenerate}
            style={{
              border: "1px solid #d1d5db",
              background: "#ffffff",
              borderRadius: "8px",
              padding: "8px 14px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#374151",
              cursor: "pointer",
            }}
          >
            Regenerate
          </button>
          <button
            type="button"
            onClick={handleEdit}
            style={{
              border: "1px solid #d1d5db",
              background: "#ffffff",
              borderRadius: "8px",
              padding: "8px 14px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#374151",
              cursor: "pointer",
            }}
          >
            Edit
          </button>
          <button
            type="button"
            onClick={handleAddToResume}
            disabled={!canAddToResume}
            style={{
              border: "none",
              borderRadius: "8px",
              padding: "8px 14px",
              fontSize: "12px",
              fontWeight: 700,
              background: canAddToResume ? "#6c47ff" : "#f3f4f6",
              color: canAddToResume ? "#ffffff" : "#d1d5db",
              cursor: canAddToResume ? "pointer" : "not-allowed",
              boxShadow: canAddToResume ? "0 2px 0 #5832d3" : "0 2px 0 #d1d5db",
              marginLeft: "auto",
            }}
          >
            {isAdding ? "Adding..." : "Add to Resume ✓"}
          </button>
        </div>

        {addError ? (
          <div
            style={{
              color: "#dc2626",
              fontSize: "13px",
              marginTop: "8px",
            }}
          >
            {addError}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      style={{
        border: "1.5px solid #bbf7d0",
        background: "#f0fdf4",
        borderRadius: "10px",
        padding: "12px 16px",
        marginBottom: "16px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px",
        }}
      >
        <div
          style={{
            color: "#166534",
            fontWeight: 600,
            fontSize: "14px",
          }}
        >
          ✓ Added to your {fix.sub_label ?? fix.section} entry
        </div>
        <div
          style={{
            background: "#dcfce7",
            color: "#16a34a",
            borderRadius: "12px",
            padding: "2px 8px",
            fontSize: "12px",
            fontWeight: 600,
          }}
        >
          +3 pts
        </div>
      </div>

      <div
        style={{
          fontSize: "13px",
          color: "#4b5563",
          lineHeight: 1.5,
          paddingLeft: "16px",
        }}
      >
        {generatedBullet.length > 100 ? `${generatedBullet.substring(0, 100)}...` : generatedBullet}
      </div>
    </div>
  );
}
