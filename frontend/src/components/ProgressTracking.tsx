import { useEffect, useMemo } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useResumeStore } from "../store/useResumeStore";

interface ProgressPoint {
  ats_score: number;
  jd_match: number | null;
  percentile: number | null;
  timestamp: string;
  label: string;
}

export default function ProgressTracking() {
  const analysisResult = useResumeStore((s) => s.analysisResult);
  const jobId = useResumeStore((s) => s.jobId);
  if (!analysisResult) return null;

  const sessionId = jobId ?? analysisResult.job_id ?? Date.now().toString();
  const key = `rip_progress_${sessionId}`;

  useEffect(() => {
    const raw = localStorage.getItem(key);
    if (raw) return;
    const baseline: ProgressPoint[] = [
      {
        ats_score: analysisResult.ats.score,
        jd_match: analysisResult.gap?.jd_match_score_before ?? null,
        percentile: analysisResult.percentile?.percentile ?? null,
        timestamp: new Date().toISOString(),
        label: "Initial Analysis",
      },
    ];
    localStorage.setItem(key, JSON.stringify(baseline));
  }, [analysisResult, key]);

  const points = useMemo(() => {
    try {
      const raw = localStorage.getItem(key);
      const parsed = raw ? (JSON.parse(raw) as ProgressPoint[]) : [];
      return parsed.map((p) => ({
        ...p,
        time: new Date(p.timestamp).toLocaleDateString(),
      }));
    } catch {
      return [];
    }
  }, [key]);

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <div style={{ maxWidth: "960px", margin: "0 auto", padding: "40px 32px 48px" }}>
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
            height: "360px",
          }}
        >
          <div aria-label="Score progress over time chart" style={{ width: "100%", height: "100%" }}>
            <ResponsiveContainer>
              <LineChart data={points}>
                <XAxis dataKey="time" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Line type="monotone" dataKey="ats_score" stroke="#6366f1" strokeWidth={2} />
                <Line type="monotone" dataKey="jd_match" stroke="#7c3aed" strokeWidth={2} />
                <Line type="monotone" dataKey="percentile" stroke="#16a34a" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
