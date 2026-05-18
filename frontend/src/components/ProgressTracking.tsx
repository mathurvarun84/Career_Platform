import { useMemo } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useWindowSize } from "../hooks/useWindowSize";
import { useUserHistory } from "../hooks/useUserHistory";
import { pageContainerStyle } from "../utils/pageLayout";
import type { HistoryEntry } from "../types";

interface ChartPoint {
  date: string;
  ats: number | null;
  jd_match: number | null;
  percentile: number | null;
}

function formatDate(isoStr: string): string {
  const d = new Date(isoStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function deriveChartData(entries: HistoryEntry[]): ChartPoint[] {
  return [...entries]
    .sort(
      (a, b) =>
        new Date(a.analyzed_at).getTime() - new Date(b.analyzed_at).getTime()
    )
    .map((e) => ({
    date: formatDate(e.analyzed_at),
    ats: e.ats_score,
    jd_match: e.jd_match_score,
    percentile: e.percentile,
  }));
}

export default function ProgressTracking() {
  const { isMobile } = useWindowSize();
  const { entries, loading, error } = useUserHistory();
  const containerStyle = pageContainerStyle(isMobile);

  const chartData = useMemo(() => deriveChartData(entries), [entries]);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div style={containerStyle}>
          <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", marginBottom: "16px" }}>
            Progress Tracking
          </div>
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "40px",
              textAlign: "center",
              color: "#6b7280",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: 500 }}>Loading your analysis history...</div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div style={containerStyle}>
          <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", marginBottom: "16px" }}>
            Progress Tracking
          </div>
          <div
            style={{
              border: "1px solid #fecaca",
              borderRadius: "16px",
              padding: "20px",
              background: "#fef2f2",
              color: "#dc2626",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: 500 }}>Error: {error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div style={{ minHeight: "100vh", background: "#ffffff" }}>
        <div style={containerStyle}>
          <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", marginBottom: "16px" }}>
            Progress Tracking
          </div>
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              padding: "48px 24px",
              textAlign: "center",
              background: "#f9fafb",
            }}
          >
            <div style={{ fontSize: "16px", fontWeight: 600, color: "#111827", marginBottom: "8px" }}>
              No analyses yet
            </div>
            <div style={{ fontSize: "14px", color: "#6b7280" }}>
              Run your first resume analysis to see progress tracking.
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={containerStyle}>
        <div style={{ fontSize: "22px", fontWeight: 800, color: "#111827", marginBottom: "16px" }}>
          Progress Tracking
        </div>

        <div
          style={{
            border: "1.5px solid #e5e7eb",
            borderRadius: "16px",
            padding: "20px",
            boxShadow: "0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)",
            background: "#ffffff",
            height: isMobile ? "260px" : "360px",
            marginBottom: "32px",
          }}
        >
          <div style={{ width: "100%", height: "100%" }}>
            <ResponsiveContainer>
              <LineChart data={chartData}>
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Line type="monotone" dataKey="ats" stroke="#6366f1" strokeWidth={2} name="ATS Score" />
                <Line type="monotone" dataKey="jd_match" stroke="#7c3aed" strokeWidth={2} name="JD Match" />
                <Line type="monotone" dataKey="percentile" stroke="#16a34a" strokeWidth={2} name="Percentile" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ marginTop: "32px" }}>
          <div style={{ fontSize: "16px", fontWeight: 700, color: "#111827", marginBottom: "16px" }}>
            Analysis History
          </div>
          <div
            style={{
              border: "1.5px solid #e5e7eb",
              borderRadius: "16px",
              overflow: "hidden",
              background: "#ffffff",
            }}
          >
            <div style={{ overflowX: "auto" }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "14px",
                }}
              >
                <thead>
                  <tr
                    style={{
                      background: "#f9fafb",
                      borderBottom: "1px solid #e5e7eb",
                    }}
                  >
                    <th style={{ padding: "12px 16px", textAlign: "left", fontWeight: 600, color: "#374151" }}>
                      File
                    </th>
                    <th style={{ padding: "12px 16px", textAlign: "left", fontWeight: 600, color: "#374151" }}>
                      Date
                    </th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontWeight: 600, color: "#374151" }}>
                      ATS Score
                    </th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontWeight: 600, color: "#374151" }}>
                      JD Match
                    </th>
                    <th style={{ padding: "12px 16px", textAlign: "center", fontWeight: 600, color: "#374151" }}>
                      Percentile
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry, idx) => (
                    <tr
                      key={entry.id}
                      style={{
                        borderBottom: idx < entries.length - 1 ? "1px solid #e5e7eb" : "none",
                        background: idx % 2 === 0 ? "#ffffff" : "#f9fafb",
                      }}
                    >
                      <td style={{ padding: "12px 16px", color: "#111827", fontWeight: 500 }}>
                        {entry.file_name}
                      </td>
                      <td style={{ padding: "12px 16px", color: "#6b7280" }}>
                        {formatDate(entry.analyzed_at)}
                      </td>
                      <td style={{ padding: "12px 16px", textAlign: "center", color: "#111827", fontWeight: 500 }}>
                        {entry.ats_score !== null ? Math.round(entry.ats_score) : "—"}
                      </td>
                      <td style={{ padding: "12px 16px", textAlign: "center", color: "#111827", fontWeight: 500 }}>
                        {entry.jd_match_score !== null ? Math.round(entry.jd_match_score) : "—"}
                      </td>
                      <td style={{ padding: "12px 16px", textAlign: "center", color: "#111827", fontWeight: 500 }}>
                        {entry.percentile !== null ? Math.round(entry.percentile) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
