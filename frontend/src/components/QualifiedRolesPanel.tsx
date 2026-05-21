import { useState } from "react";

interface QualifiedRolesPanelProps {
  recommendedRoles: string[];
  nextStepRoles: string[];
  onAnalyseRole: (role: string) => void;
}

function matchBadge(index: number): { text: string; color: string; bg: string } {
  if (index === 0) {
    return { text: "Strong match", color: "#16a34a", bg: "#dcfce7" };
  }
  return { text: "Moderate match", color: "#d97706", bg: "#fefce8" };
}

function AnalyseRoleButton({ onClick }: { onClick: () => void }) {
  const [pressed, setPressed] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
      onMouseLeave={() => setPressed(false)}
      style={{
        background: "#6366f1",
        color: "#ffffff",
        border: "none",
        borderRadius: "10px",
        padding: "10px 20px",
        fontSize: "13px",
        fontWeight: 700,
        cursor: "pointer",
        alignSelf: "flex-start",
        boxShadow: pressed
          ? "0 1px 0 #4338ca"
          : "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)",
        transform: pressed ? "translateY(3px)" : "translateY(0)",
        transition: "transform 0.1s, box-shadow 0.1s",
      }}
    >
      Analyse for this role →
    </button>
  );
}

export default function QualifiedRolesPanel({
  recommendedRoles,
  nextStepRoles,
  onAnalyseRole,
}: QualifiedRolesPanelProps) {
  return (
    <div
      style={{
        background: "#faf5ff",
        border: "1px solid #ede9fe",
        borderRadius: "24px",
        padding: "28px 24px",
        marginBottom: "20px",
        boxShadow: "0 4px 0 #ede9fe, 0 8px 24px rgba(124,58,237,0.06)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "14px",
          marginBottom: "18px",
        }}
      >
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            background: "#f5f0ff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            fontSize: "19px",
          }}
        >
          ◎
        </div>
        <div>
          <div
            style={{
              fontSize: "17px",
              fontWeight: 700,
              color: "#111827",
              letterSpacing: "-0.01em",
            }}
          >
            Roles you&apos;re qualified for today
          </div>
          <div
            style={{
              fontSize: "13px",
              fontWeight: 400,
              color: "#6b7280",
              marginTop: "2px",
              lineHeight: 1.55,
            }}
          >
            Next steps toward your goal: {nextStepRoles.join(" → ")}
          </div>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: "16px",
        }}
      >
        {recommendedRoles.map((role, index) => {
          const badge = matchBadge(index);
          return (
            <div
              key={role}
              style={{
                background: "#ffffff",
                border: "1.5px solid #e5e7eb",
                borderRadius: "18px",
                padding: "28px 24px",
                display: "flex",
                flexDirection: "column",
                boxShadow: "0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)",
              }}
            >
              <span
                style={{
                  alignSelf: "flex-start",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: badge.color,
                  background: badge.bg,
                  borderRadius: "999px",
                  padding: "4px 12px",
                  marginBottom: "12px",
                }}
              >
                {badge.text}
              </span>
              <div
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  color: "#111827",
                  letterSpacing: "-0.01em",
                  marginBottom: "16px",
                  flex: 1,
                }}
              >
                {role}
              </div>
              <AnalyseRoleButton onClick={() => onAnalyseRole(role)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
