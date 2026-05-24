import type { PriorityFix } from "../../types";
import type { CardHandlers } from "./cardTypes";

interface SurfacePatchCardProps {
  fix: PriorityFix;
  fixKey: string;
  handlers: CardHandlers;
}

export default function SurfacePatchCard({
  fix,
  fixKey,
  handlers,
}: SurfacePatchCardProps) {
  const diff = handlers.getPatchDiff(fix);
  const state = handlers.applyState[fixKey] ?? "idle";
  const pts = handlers.scoreDelta(fix);
  const isConfirmed = state === "applied";
  const isLoading = state === "loading";
  const isFailed = state === "failed";

  return (
    <div
      style={{
        border: "1.5px solid #bbf7d0",
        background: "#f0fdf4",
        borderRadius: "10px",
        padding: "14px 16px",
        marginBottom: "12px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          flexWrap: "wrap",
          rowGap: "8px",
        }}
      >
        <div style={{ flex: 1, minWidth: "200px" }}>
          <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827" }}>
            {fix.section}
            {fix.sub_label ? ` · ${fix.sub_label}` : ""}
          </div>
          <div
            style={{
              fontSize: "12px",
              color: "#4b5563",
              marginTop: "6px",
              lineHeight: 1.5,
            }}
          >
            {diff ? (
              <>
                <span style={{ textDecoration: "line-through", color: "#9ca3af" }}>
                  {diff.original}
                </span>
                <span style={{ margin: "0 6px", color: "#6b7280" }}>→</span>
                <span style={{ color: "#166534", fontWeight: 600 }}>
                  {diff.replacement}
                </span>
              </>
            ) : (
              fix.gap_reason
            )}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div
            style={{
              background: "#dcfce7",
              color: "#16a34a",
              borderRadius: "999px",
              padding: "3px 10px",
              fontSize: "11px",
              fontWeight: 700,
            }}
          >
            +{pts} pts
          </div>
          {isConfirmed ? (
            <div
              style={{
                background: "#16a34a",
                color: "#ffffff",
                borderRadius: "999px",
                padding: "4px 12px",
                fontSize: "11px",
                fontWeight: 700,
              }}
            >
              ✓ Applied
            </div>
          ) : isLoading ? (
            <div
              style={{
                background: "#eef2ff",
                color: "#6366f1",
                borderRadius: "999px",
                padding: "4px 12px",
                fontSize: "11px",
                fontWeight: 700,
              }}
            >
              Applying...
            </div>
          ) : (
            <button
              type="button"
              onClick={() => handlers.onApply(fix, fixKey)}
              style={{
                border: "none",
                borderRadius: "999px",
                background: "#6366f1",
                color: "#ffffff",
                padding: "4px 12px",
                fontSize: "11px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Apply Fix
            </button>
          )}
        </div>
      </div>
      {isFailed ? (
        <div
          style={{
            marginTop: "10px",
            fontSize: "12px",
            color: "#d97706",
          }}
        >
          Could not confirm this fix in document. Try again.
        </div>
      ) : null}
      {isConfirmed ? (
        <button
          type="button"
          onClick={() => handlers.onUndo(fix, fixKey)}
          style={{
            marginTop: "10px",
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
      ) : null}
    </div>
  );
}
