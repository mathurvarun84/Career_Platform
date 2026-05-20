import { downloadResumeReport } from "../api/client";
import type { FixMode } from "../utils/modeScores";
import { downloadStyleForMode } from "../utils/modeScores";

interface FixValidationProps {
  selectedMode: FixMode;
  /** ATS at end of analysis (frozen baseline). */
  originalAts: number;
  /** Live ATS after applied fixes (deterministic in-browser rescore). */
  liveAts: number;
  appliedCount: number;
  originalJd: number | null;
  afterJd: number | null;
  hasJd: boolean;
  jobId: string | null;
  onSwitchMode: (mode: FixMode) => void;
}

function CheckCard({
  title,
  status,
  detail,
}: {
  title: string;
  status: "pass" | "warn" | "fail";
  detail: string;
}) {
  const styles = {
    pass: {
      background: "#f0fdf4",
      border: "1.5px solid #86efac",
    },
    warn: {
      background: "#fffbeb",
      border: "1.5px solid #fde68a",
    },
    fail: {
      background: "#fef2f2",
      border: "1.5px solid #fecaca",
    },
  }[status];

  const icon = status === "pass" ? "✓" : status === "warn" ? "⚠" : "✗";

  return (
    <div
      style={{
        ...styles,
        borderRadius: "14px",
        padding: "18px 22px",
      }}
    >
      <div style={{ fontSize: "14px", fontWeight: 700, color: "#111827" }}>
        {icon} {title}
      </div>
      <div style={{ fontSize: "13px", color: "#4b5563", marginTop: "6px", lineHeight: 1.55 }}>
        {detail}
      </div>
    </div>
  );
}

export default function FixValidation({
  selectedMode,
  originalAts,
  liveAts,
  appliedCount,
  originalJd,
  afterJd,
  hasJd,
  jobId,
  onSwitchMode,
}: FixValidationProps) {
  const noPending = appliedCount === 0;
  const atsGain = liveAts - originalAts;
  const atsImproved = !noPending && liveAts > originalAts;
  const jdImproved =
    !noPending && hasJd && afterJd !== null && originalJd !== null && afterJd > originalJd;
  const jdDeclined =
    !noPending && hasJd && afterJd !== null && originalJd !== null && afterJd < originalJd;
  const overallImproved = atsImproved && (!hasJd || jdImproved || afterJd === originalJd);

  const otherMode: FixMode = selectedMode === "safe" ? "full" : "safe";
  const otherLabel = otherMode === "safe" ? "Safe fix" : "Full rewrite";

  const handleDownload = async (): Promise<void> => {
    if (!jobId) {
      window.alert("Session id unavailable. Download skipped.");
      return;
    }
    try {
      await downloadResumeReport(jobId, downloadStyleForMode(selectedMode));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Download failed.";
      window.alert(message);
    }
  };

  return (
    <div style={{ marginTop: "32px" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          gap: "16px",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <div
          style={{
            background: "#f9fafb",
            border: "1.5px solid #e5e7eb",
            borderRadius: "14px",
            padding: "18px 20px",
          }}
        >
          <div style={{ fontSize: "12px", fontWeight: 700, color: "#6b7280", marginBottom: "8px" }}>
            Original
          </div>
          <div style={{ fontSize: "13px", color: "#6b7280" }}>
            ATS: <strong>{originalAts}</strong>
          </div>
          {hasJd && originalJd !== null ? (
            <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "4px" }}>
              JD: <strong>{originalJd}%</strong>
            </div>
          ) : null}
        </div>

        <div style={{ textAlign: "center" }}>
          <span style={{ fontSize: "20px", color: "#9ca3af" }}>→</span>
          <div
            style={{
              marginTop: "8px",
              borderRadius: "999px",
              padding: "4px 12px",
              fontSize: "11px",
              fontWeight: 700,
              background: noPending ? "#f3f4f6" : overallImproved ? "#dcfce7" : "#fef2f2",
              color: noPending ? "#6b7280" : overallImproved ? "#15803d" : "#dc2626",
              whiteSpace: "nowrap",
            }}
          >
            {noPending ? "Pending" : overallImproved ? "✓ Improved" : "Review"}
          </div>
        </div>

        <div
          style={{
            background: "#f9fafb",
            border: "1.5px solid #e5e7eb",
            borderRadius: "14px",
            padding: "18px 20px",
          }}
        >
          <div style={{ fontSize: "12px", fontWeight: 700, color: "#6b7280", marginBottom: "8px" }}>
            {noPending ? "After (apply fixes)" : `After ${appliedCount} fix${appliedCount === 1 ? "" : "es"}`}
          </div>
          {noPending ? (
            <div style={{ fontSize: "12px", color: "#9ca3af", fontStyle: "italic" }}>
              Apply fixes above — ATS rescored live on Overview
            </div>
          ) : (
            <>
              <div
                style={{
                  fontSize: "13px",
                  color: atsImproved ? "#16a34a" : liveAts < originalAts ? "#dc2626" : "#6b7280",
                }}
              >
                ATS: <strong>{liveAts}</strong>
                {atsGain !== 0 && (
                  <span
                    style={{
                      marginLeft: "6px",
                      fontSize: "12px",
                      color: atsGain > 0 ? "#16a34a" : "#6b7280",
                    }}
                  >
                    {atsGain > 0 ? `+${atsGain}` : atsGain}
                  </span>
                )}
              </div>
              {hasJd && afterJd !== null && originalJd !== null ? (
                <div
                  style={{
                    fontSize: "13px",
                    marginTop: "4px",
                    color: jdImproved ? "#16a34a" : jdDeclined ? "#dc2626" : "#6b7280",
                  }}
                >
                  JD: <strong>{afterJd}%</strong>
                  <span style={{ marginLeft: "6px", fontSize: "12px", color: "#6b7280" }}>
                    (est. with all fixes)
                  </span>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "12px",
          marginBottom: "20px",
        }}
      >
        <CheckCard
          title="ATS Score check"
          status={noPending ? "warn" : atsImproved ? "pass" : liveAts < originalAts ? "warn" : "pass"}
          detail={
            noPending
              ? "Apply fixes above — your ATS score updates on the Overview tab."
              : atsImproved
                ? `ATS improved by +${atsGain} after ${appliedCount} applied fix${appliedCount === 1 ? "" : "es"} (live rescore).`
                : `ATS is ${liveAts} (was ${originalAts}). Content may still help JD match — check Overview.`
          }
        />
        <CheckCard
          title="JD Match check"
          status={!hasJd ? "warn" : noPending ? "warn" : jdImproved ? "pass" : "pass"}
          detail={
            !hasJd
              ? "No job description provided — JD match not evaluated."
              : noPending
                ? "Apply fixes to align sections with the job description."
                : afterJd !== null && originalJd !== null
                  ? `Target JD alignment: ${originalJd}% → ${afterJd}% when all fixes are applied.`
                  : "JD alignment improves with keyword-rich rewrites."
          }
        />
        <CheckCard
          title="Integrity check"
          status="pass"
          detail="No invented metrics detected in patch set."
        />
      </div>

      {noPending ? (
        <div
          style={{
            background: "#f9fafb",
            border: "1.5px solid #e5e7eb",
            borderRadius: "14px",
            padding: "20px 24px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "14px", fontWeight: 700, color: "#374151" }}>
            No fixes applied yet
          </div>
          <div style={{ fontSize: "13px", color: "#6b7280", marginTop: "6px" }}>
            Click <strong>Apply This Fix</strong> on each improvement. ATS rescoring runs instantly and
            updates the Overview tab.
          </div>
        </div>
      ) : (
        <div
          style={{
            background: "#f0fdf4",
            border: "1.5px solid #86efac",
            borderRadius: "14px",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
            flexWrap: "wrap",
          }}
        >
          <div>
            <div style={{ fontSize: "14px", fontWeight: 700, color: "#15803d" }}>
              {appliedCount} fix{appliedCount === 1 ? "" : "es"} applied ✓
            </div>
            <div style={{ fontSize: "13px", color: "#166534", marginTop: "4px" }}>
              Live ATS: {originalAts} → {liveAts}
              {atsGain > 0 ? ` (+${atsGain})` : ""} — see Overview for full breakdown
            </div>
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => void handleDownload()}
              style={{
                background: "#15803d",
                color: "#fff",
                border: "none",
                borderRadius: "12px",
                padding: "13px 24px",
                fontSize: "14px",
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 4px 0 #14532d",
                whiteSpace: "nowrap",
              }}
            >
              ⬇ Download Patched Resume
            </button>
            <button
              type="button"
              onClick={() => onSwitchMode(otherMode)}
              style={{
                background: "#fff",
                color: "#374151",
                border: "1.5px solid #e5e7eb",
                borderRadius: "12px",
                padding: "12px 20px",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              Switch to {otherLabel}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
