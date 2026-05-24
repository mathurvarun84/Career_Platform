import { useEffect, useState } from "react";
import { getCareerMemory } from "../api/client";
import type { CareerMemoryEntry } from "../types";

interface CareerRecordPanelProps {
  sessionId: string;
  version: number;
}

const skillChipColors: Record<string, { bg: string; color: string }> = {
  leadership: { bg: "#eef2ff", color: "#6c47ff" },
  technical: { bg: "#eff6ff", color: "#3b82f6" },
  delivery: { bg: "#f0fdf4", color: "#16a34a" },
  communication: { bg: "#fffbeb", color: "#d97706" },
};

export default function CareerRecordPanel({
  sessionId,
  version,
}: CareerRecordPanelProps) {
  const [entries, setEntries] = useState<CareerMemoryEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [expandedBulletIdx, setExpandedBulletIdx] = useState<Set<number>>(
    new Set()
  );

  useEffect(() => {
    setLoading(true);
    setError(null);

    getCareerMemory(sessionId)
      .then((res) => {
        setEntries(res.entries);
        setTotal(res.total);
        if (res.total === 0) {
          setExpanded(false);
        } else {
          setExpanded(true);
        }
      })
      .catch((err) => {
        console.error("Failed to fetch career memory:", err);
        setError("Could not load career record");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [sessionId, version]);

  const handleCopy = (idx: number, bullet: string) => {
    navigator.clipboard
      .writeText(bullet)
      .then(() => {
        setCopiedIdx(idx);
        setTimeout(() => setCopiedIdx(null), 2000);
      })
      .catch(() => {
        console.error("Copy failed");
      });
  };

  const toggleBullet = (idx: number) => {
    const newSet = new Set(expandedBulletIdx);
    if (newSet.has(idx)) {
      newSet.delete(idx);
    } else {
      newSet.add(idx);
    }
    setExpandedBulletIdx(newSet);
  };

  return (
    <div
      style={{
        background: "#fafafa",
        border: "1.5px solid #e5e7eb",
        borderRadius: "16px",
        padding: "20px",
        marginTop: "32px",
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "transparent",
          border: "none",
          padding: "0",
          cursor: "pointer",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "12px",
          }}
        >
          <div
            style={{
              background: "#eef2ff",
              borderRadius: "8px",
              padding: "6px 8px",
              fontSize: "16px",
            }}
          >
            📋
          </div>
          <div>
            <div
              style={{
                fontWeight: 700,
                fontSize: "15px",
                color: "#111827",
                textAlign: "left",
              }}
            >
              Your Career Record
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "#9ca3af",
                marginTop: "4px",
                textAlign: "left",
              }}
            >
              Experiences you've shared — reusable for future JDs
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <div
            style={{
              background: "#eef2ff",
              color: "#6c47ff",
              borderRadius: "12px",
              padding: "2px 10px",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            {total} captured
          </div>
          <div
            style={{
              color: "#6b7280",
              fontSize: "18px",
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
            }}
          >
            ▼
          </div>
        </div>
      </button>

      {expanded && loading && (
        <div
          style={{
            marginTop: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                height: "56px",
                background: "#e5e7eb",
                borderRadius: "8px",
                animation: "pulse 2s infinite",
              }}
            />
          ))}
        </div>
      )}

      {expanded && error && (
        <div
          style={{
            marginTop: "16px",
            fontSize: "13px",
            color: "#6b7280",
            textAlign: "center",
          }}
        >
          {error}
        </div>
      )}

      {expanded && !loading && total === 0 && (
        <div
          style={{
            marginTop: "20px",
            color: "#9ca3af",
            fontSize: "14px",
            textAlign: "center",
            padding: "20px 0",
          }}
        >
          Answer coaching questions to build your career record.
        </div>
      )}

      {expanded && !loading && entries.length > 0 && (
        <div style={{ marginTop: "16px" }}>
          {entries.map((entry, idx) => {
            const colors = skillChipColors[entry.skill_category] || {
              bg: "#f3f4f6",
              color: "#6b7280",
            };
            const isExpanded = expandedBulletIdx.has(idx);
            const isCopied = copiedIdx === idx;
            const bulletDisplay = isExpanded
              ? entry.generated_bullet
              : entry.generated_bullet.length > 100
              ? entry.generated_bullet.substring(0, 100) + "…"
              : entry.generated_bullet;

            return (
              <div
                key={entry.id}
                style={{
                  borderTop: "1px solid #f3f4f6",
                  padding: "14px 0",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "6px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <div
                      style={{
                        background: colors.bg,
                        color: colors.color,
                        borderRadius: "12px",
                        padding: "2px 8px",
                        fontSize: "11px",
                        fontWeight: 600,
                        textTransform: "capitalize",
                      }}
                    >
                      {entry.skill_category}
                    </div>
                    <div
                      style={{
                        fontSize: "13px",
                        color: "#6b7280",
                      }}
                    >
                      {entry.company ? entry.company + " • " : ""}
                      {new Date(entry.timestamp).getFullYear()}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopy(idx, entry.generated_bullet)}
                    style={{
                      border: "none",
                      background: "transparent",
                      color: "#6b7280",
                      fontSize: "12px",
                      cursor: "pointer",
                      fontWeight: 500,
                      padding: 0,
                    }}
                  >
                    {isCopied ? "Copied!" : "Copy"}
                  </button>
                </div>

                <div
                  style={{
                    fontSize: "13px",
                    color: "#374151",
                    lineHeight: 1.5,
                    marginTop: "6px",
                  }}
                >
                  {bulletDisplay}
                  {entry.generated_bullet.length > 100 && (
                    <button
                      type="button"
                      onClick={() => toggleBullet(idx)}
                      style={{
                        background: "transparent",
                        border: "none",
                        color: "#6c47ff",
                        cursor: "pointer",
                        fontSize: "12px",
                        fontWeight: 600,
                        padding: 0,
                        marginLeft: "4px",
                      }}
                    >
                      {isExpanded ? "show less" : "show more"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
