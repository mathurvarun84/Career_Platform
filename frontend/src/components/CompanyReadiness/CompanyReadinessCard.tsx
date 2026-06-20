import type { CompanyReadinessResult, DimensionResult } from '../../types'
import DimensionBadge from './DimensionBadge'
import ReadinessMeter from './ReadinessMeter'

interface CompanyReadinessCardProps {
  result: CompanyReadinessResult
  roleTitle: string
  onSeeBreakdown: () => void
  onFixTopGap: () => void
}

function dimensionIcon(dimension: DimensionResult): { icon: string; color: string } {
  if (dimension.passes || dimension.signal_strength === 'strong') {
    return { icon: '✓', color: '#059669' }
  }
  if (dimension.signal_strength === 'developing') {
    return { icon: '●', color: '#d97706' }
  }
  return { icon: '✗', color: '#dc2626' }
}

export default function CompanyReadinessCard({
  result,
  roleTitle,
  onSeeBreakdown,
  onFixTopGap,
}: CompanyReadinessCardProps) {
  return (
    <div
      style={{
        background: '#ffffff',
        border: '1.5px solid #e2e2ef',
        borderRadius: '24px',
        padding: '28px 32px',
        maxWidth: '1200px',
        margin: '28px auto 0',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            fontSize: '12px',
            fontWeight: 700,
            color: '#5b5fc7',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          ✦ Company Readiness
        </div>
        <div style={{ fontSize: '14px', fontWeight: 700, color: '#0d0d1a' }}>
          {`${result.company_display_name} · ${roleTitle}`}
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: '28px',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
        }}
      >
        <ReadinessMeter score={result.readiness_score} label={result.readiness_label} />

        <div style={{ flex: 1, minWidth: '220px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {result.dimensions.map((dimension) => {
              const { icon, color } = dimensionIcon(dimension)
              return (
                <div
                  key={dimension.dimension_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '13px',
                    color: '#4a4a6a',
                  }}
                >
                  <span style={{ color, fontWeight: 700, width: '14px', flexShrink: 0 }}>
                    {icon}
                  </span>
                  <span style={{ flex: 1 }}>{dimension.label}</span>
                  <DimensionBadge
                    strength={dimension.signal_strength}
                    label={dimension.display_label}
                  />
                </div>
              )
            })}
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'row',
              gap: '12px',
              marginTop: '20px',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              onClick={onSeeBreakdown}
              style={{
                fontFamily: 'inherit',
                border: '1.5px solid #5b5fc7',
                color: '#5b5fc7',
                background: 'transparent',
                borderRadius: '8px',
                padding: '9px 18px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              See full breakdown →
            </button>
            {result.top_fix && (
              <button
                type="button"
                onClick={onFixTopGap}
                style={{
                  fontFamily: 'inherit',
                  background: '#5b5fc7',
                  color: '#ffffff',
                  borderRadius: '8px',
                  padding: '9px 18px',
                  fontSize: '13px',
                  fontWeight: 700,
                  boxShadow: '0 4px 0 #3a3d9a',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Fix top gap →
              </button>
            )}
          </div>
        </div>
      </div>

      <div
        style={{
          fontSize: '11px',
          color: '#8888aa',
          marginTop: '20px',
          lineHeight: 1.5,
        }}
      >
        Based on language patterns in your resume — not a guarantee of interview outcome.
      </div>
    </div>
  )
}
