interface ReadinessMeterProps {
  score: number
  label: string
}

const RADIUS = 50
const CENTER = 60
const STROKE_WIDTH = 10
const ARC_DEGREES = 240
const ROTATION = 150

function getFillColor(score: number): string {
  if (score >= 80) return '#059669'
  if (score >= 40) return '#f59e0b'
  return '#dc2626'
}

export default function ReadinessMeter({ score, label }: ReadinessMeterProps) {
  const clampedScore = Math.max(0, Math.min(100, score))
  const circumference = 2 * Math.PI * RADIUS
  const arcLength = circumference * (ARC_DEGREES / 360)
  const fillLength = arcLength * (clampedScore / 100)
  const fillColor = getFillColor(clampedScore)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke="#e2e2ef"
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          transform={`rotate(${ROTATION} ${CENTER} ${CENTER})`}
        />
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke={fillColor}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          strokeDasharray={`${fillLength} ${circumference}`}
          transform={`rotate(${ROTATION} ${CENTER} ${CENTER})`}
        />
        <text
          x={CENTER}
          y={CENTER - 4}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '28px',
            fontWeight: 600,
            fill: fillColor,
          }}
        >
          {clampedScore}
        </text>
        <text
          x={CENTER}
          y={CENTER + 18}
          textAnchor="middle"
          dominantBaseline="middle"
          style={{
            fontFamily: "'DM Sans', sans-serif",
            fontSize: '11px',
            fill: '#8888aa',
          }}
        >
          {label}
        </text>
      </svg>
    </div>
  )
}
