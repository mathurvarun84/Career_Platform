import type { PriorityFix } from "../../types";
import type { CardHandlers } from "./cardTypes";

function diffSentences(original: string, patched: string): { before: string; after: string } {
  const origSentences = original.match(/[^.!?]+[.!?]+/g) ?? [original];
  const patchSentences = patched.match(/[^.!?]+[.!?]+/g) ?? [patched];
  const changedIdx = origSentences.findIndex((sentence, index) => sentence !== patchSentences[index]);
  if (changedIdx === -1) {
    return { before: original.trim(), after: patched.trim() };
  }
  return {
    before: origSentences[changedIdx].trim(),
    after: (patchSentences[changedIdx] ?? "").trim(),
  };
}

interface StructuralPatchCardProps {
  fix: PriorityFix;
  fixKey: string;
  handlers: CardHandlers;
}

export default function StructuralPatchCard({
  fix,
  fixKey,
  handlers,
}: StructuralPatchCardProps) {
  const state = handlers.applyState[fixKey] ?? "idle";
  const before = handlers.getBeforeText(fix);
  const after = handlers.getAfterText(fix);
  const changedSentence = diffSentences(before, after);
  const pts = handlers.scoreDelta(fix);
  const loading = state === "loading";
  const isConfirmed = state === "applied";
  const failed = state === "failed";

  return (
    <div
      style={{
        border: "1.5px solid #e5e7eb",
        background: "#ffffff",
        borderRadius: "10px",
        padding: "16px 18px",
        marginBottom: "16px",
        boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          rowGap: "8px",
          marginBottom: "12px",
        }}
      >
        <div>
          <div style={{ fontSize: "15px", fontWeight: 700, color: "#111827" }}>
            {fix.section}
            {fix.sub_label ? ` · ${fix.sub_label}` : ""}
          </div>
          <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "4px" }}>
            {fix.gap_reason}
          </div>
        </div>
        <div
          style={{
            background: "#eef2ff",
            color: "#4f46e5",
            borderRadius: "999px",
            padding: "3px 10px",
            fontSize: "11px",
            fontWeight: 700,
          }}
        >
          +{pts} pts
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", rowGap: "6px" }}>
        <div
          style={{
            fontSize: "13px",
            color: "#dc2626",
            textDecoration: "line-through",
            lineHeight: 1.55,
          }}
        >
          {changedSentence.before}
        </div>
        <div
          style={{
            fontSize: "13px",
            color: "#16a34a",
            fontWeight: 600,
            lineHeight: 1.55,
          }}
        >
          {changedSentence.after}
        </div>
      </div>

      <div style={{ marginTop: "14px", display: "flex", alignItems: "center", gap: "10px" }}>
        {isConfirmed ? (
          <>
            <div
              style={{
                background: "#16a34a",
                color: "#ffffff",
                borderRadius: "999px",
                padding: "6px 14px",
                fontSize: "12px",
                fontWeight: 700,
              }}
            >
              ✓ Applied
            </div>
            <button
              type="button"
              onClick={() => handlers.onUndo(fix, fixKey)}
              style={{
                border: "none",
                background: "transparent",
                color: "#6366f1",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                padding: 0,
              }}
            >
              Undo
            </button>
          </>
        ) : failed ? (
          <div
            style={{
              background: "#fffbeb",
              border: "1.5px solid #fde68a",
              color: "#d97706",
              borderRadius: "8px",
              padding: "8px 12px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            ⚠ Could not apply — text may have changed
          </div>
        ) : (
          <button
            type="button"
            disabled={loading}
            onClick={() => handlers.onApply(fix, fixKey)}
            style={{
              border: "none",
              borderRadius: "10px",
              padding: "8px 18px",
              fontSize: "12px",
              fontWeight: 700,
              color: loading ? "#d1d5db" : "#ffffff",
              cursor: loading ? "wait" : "pointer",
              background: loading ? "#f3f4f6" : "#6366f1",
              boxShadow: loading ? "0 2px 0 #d1d5db" : "0 2px 0 #4338ca, 0 4px 10px rgba(99,102,241,0.25)",
            }}
          >
            {loading ? "Applying..." : "Apply Fix"}
          </button>
        )}
      </div>
    </div>
  );
}
