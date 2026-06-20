import { T } from "../../tokens";
import type { SessionSnapshot } from "../../types";

interface TimelineChartProps {
  sessions: SessionSnapshot[];
}

const CHART_WIDTH = 600;
const CHART_HEIGHT = 180;
const PADDING_X = 40;
const PADDING_Y = 20;

const formatDate = (iso: string): string => {
  const date = new Date(iso);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

export default function TimelineChart({ sessions }: TimelineChartProps) {
  if (sessions.length === 0) {
    return null;
  }

  const plotWidth = CHART_WIDTH - PADDING_X * 2;
  const plotHeight = CHART_HEIGHT - PADDING_Y * 2;

  const yForScore = (score: number): number =>
    PADDING_Y + plotHeight - (score / 100) * plotHeight;

  const xForIndex = (index: number): number =>
    sessions.length === 1
      ? PADDING_X + plotWidth / 2
      : PADDING_X + (index / (sessions.length - 1)) * plotWidth;

  const points = sessions.map((session, index) => ({
    x: xForIndex(index),
    y: yForScore(session.composite_score),
    session,
  }));

  const linePath = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`)
    .join(" ");

  const gridLines = [0, 25, 50, 75, 100];

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      width="100%"
      height={CHART_HEIGHT}
      preserveAspectRatio="xMidYMid meet"
    >
      {gridLines.map((value) => (
        <line
          key={value}
          x1={PADDING_X}
          x2={CHART_WIDTH - PADDING_X}
          y1={yForScore(value)}
          y2={yForScore(value)}
          stroke={T.border}
          strokeOpacity={0.5}
          strokeWidth={1}
        />
      ))}

      {[0, 50, 100].map((value) => (
        <text
          key={value}
          x={PADDING_X - 10}
          y={yForScore(value)}
          fontSize={11}
          fill={T.textMuted}
          textAnchor="end"
          dominantBaseline="middle"
        >
          {value}
        </text>
      ))}

      {points.length > 1 && (
        <path d={linePath} stroke={T.primary} strokeWidth={2.5} fill="none" />
      )}

      {points.map((p, i) => {
        const isLatest = i === points.length - 1;
        return (
          <g key={p.session.run_id}>
            <circle
              cx={p.x}
              cy={p.y}
              r={isLatest ? 6 : 5}
              fill={isLatest ? "#ffffff" : T.primary}
              stroke={isLatest ? T.primary : "none"}
              strokeWidth={isLatest ? 2.5 : 0}
            >
              <title>
                {`${p.session.composite_score} · ${p.session.percentile_label ?? "—"}`}
              </title>
            </circle>
            <text
              x={p.x}
              y={CHART_HEIGHT - 4}
              fontSize={11}
              fill={T.textMuted}
              textAnchor="middle"
            >
              {formatDate(p.session.created_at)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
