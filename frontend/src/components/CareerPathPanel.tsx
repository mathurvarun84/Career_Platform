import type { RoleFit } from "../types";

interface CareerPathPanelProps {
  roleFit: RoleFit;
  targetRoleTitle: string;
}

const STEP_BUILD: Record<string, string> = {
  "SDE 2": "Deepen ownership on features end-to-end; add 1–2 measurable impact metrics per quarter.",
  "Software Engineer II": "Own a service or module; document design decisions and on-call learnings.",
  "Senior Software Engineer": "Lead a project across teams; mentor juniors; show system design breadth.",
  "Tech Lead": "Balance delivery with technical direction; run design reviews; unblock the squad.",
  "Staff Engineer": "Drive cross-team architecture; write RFCs; influence without direct authority.",
  "Engineering Lead": "People leadership alongside IC work: hiring, 1:1s, and roadmap alignment.",
  "Engineering Manager": "Full people management: performance, org health, and stakeholder communication.",
  "Senior Staff Engineer": "Org-wide technical strategy; multi-quarter initiatives; executive partnership.",
  "Principal Engineer": "Company-level technical bets; mentorship at scale; external thought leadership.",
};

const currentTitleFromSeniority = (years: number): string => {
  if (years <= 2) return "Junior Software Engineer";
  if (years <= 5) return "Software Engineer";
  if (years <= 8) return "Senior Software Engineer";
  return "Staff Engineer";
};

export default function CareerPathPanel({ roleFit, targetRoleTitle }: CareerPathPanelProps) {
  const nowTitle = currentTitleFromSeniority(roleFit.candidate_years);
  const steps = roleFit.next_step_roles;

  return (
    <div
      style={{
        background: "#ffffff",
        border: "1.5px solid #e5e7eb",
        borderRadius: "24px",
        padding: "28px 24px",
        marginBottom: "20px",
        boxShadow: "0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)",
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
            background: "#eef2ff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            fontSize: "19px",
            color: "#6366f1",
          }}
        >
          ↗
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
            Path to {targetRoleTitle}
          </div>
          <div
            style={{
              fontSize: "13px",
              fontWeight: 400,
              color: "#6b7280",
              marginTop: "2px",
            }}
          >
            Build experience step by step — no keyword stuffing
          </div>
        </div>
      </div>

      <div style={{ position: "relative", paddingLeft: "28px" }}>
        <div
          style={{
            position: "absolute",
            left: "11px",
            top: "8px",
            bottom: "8px",
            width: "2px",
            background: "#e5e7eb",
          }}
        />
        <TimelineStep
          dotColor="#16a34a"
          title={`Now — ${nowTitle}`}
          body={`${roleFit.candidate_years} years experience · close ${roleFit.experience_gap} yr and ${roleFit.seniority_gap} level gap`}
          done
        />
        {steps.map((role, index) => (
          <TimelineStep
            key={role}
            dotColor="#6366f1"
            title={`Step ${index + 1} — ${role}`}
            body={STEP_BUILD[role] ?? "Build leadership signals, scope, and measurable org impact."}
          />
        ))}
        <TimelineStep
          dotColor="#fbbf24"
          title={`Goal — ${targetRoleTitle}`}
          body="Target role from your JD — apply when experience and seniority gaps are closed."
          isGoal
        />
      </div>
    </div>
  );
}

function TimelineStep({
  dotColor,
  title,
  body,
  done,
  isGoal,
}: {
  dotColor: string;
  title: string;
  body: string;
  done?: boolean;
  isGoal?: boolean;
}) {
  return (
    <div style={{ position: "relative", marginBottom: "20px" }}>
      <div
        style={{
          position: "absolute",
          left: "-22px",
          top: "4px",
          width: "12px",
          height: "12px",
          borderRadius: "50%",
          background: dotColor,
          border: done ? "2px solid #16a34a" : isGoal ? "2px solid #fbbf24" : "2px solid #ffffff",
          boxShadow: "0 0 0 2px #e5e7eb",
        }}
      />
      <div
        style={{
          fontSize: "15px",
          fontWeight: 700,
          color: "#111827",
          letterSpacing: "-0.01em",
          marginBottom: "4px",
        }}
      >
        {title}
        {done ? (
          <span
            style={{
              marginLeft: "8px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#16a34a",
              background: "#dcfce7",
              borderRadius: "999px",
              padding: "4px 12px",
            }}
          >
            Done
          </span>
        ) : null}
      </div>
      <p
        style={{
          fontSize: "13px",
          fontWeight: 400,
          color: "#6b7280",
          margin: 0,
          lineHeight: 1.55,
        }}
      >
        {body}
      </p>
    </div>
  );
}
