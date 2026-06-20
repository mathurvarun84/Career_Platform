import type { DimensionResult } from '../../types'
import DimensionBadge from './DimensionBadge'

interface DimensionCardProps {
  dimension: DimensionResult
  onFixGap: (dimensionId: string) => void
}

function leftBorderColor(strength: DimensionResult['signal_strength']): string {
  if (strength === 'strong') return '#059669'
  if (strength === 'developing') return '#f59e0b'
  return '#dc2626'
}

export default function DimensionCard({ dimension, onFixGap }: DimensionCardProps) {
  return (
    <div
      style={{
        background: '#ffffff',
        border: '1.5px solid #e2e2ef',
        borderLeft: `3px solid ${leftBorderColor(dimension.signal_strength)}`,
        borderRadius: '16px',
        padding: '20px 24px',
        marginBottom: '12px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ fontSize: '14px', fontWeight: 700, color: '#0d0d1a' }}>
          {dimension.label}
        </div>
        <DimensionBadge strength={dimension.signal_strength} label={dimension.display_label} />
      </div>
      <div
        style={{
          fontSize: '13px',
          color: '#8888aa',
          fontStyle: 'italic',
          marginTop: '8px',
        }}
      >
        {dimension.company_expectation}
      </div>
      <div style={{ fontSize: '13px', color: '#4a4a6a', marginTop: '6px' }}>
        {dimension.resume_evidence}
      </div>
      {dimension.fix_hint && (
        <>
          <div
            style={{
              background: '#fafafd',
              borderLeft: '3px solid #5b5fc7',
              padding: '10px 14px',
              borderRadius: '0 8px 8px 0',
              marginTop: '12px',
              fontSize: '13px',
              color: '#5b5fc7',
            }}
          >
            {`→ ${dimension.fix_hint}`}
          </div>
          <button
            type="button"
            onClick={() => onFixGap(dimension.dimension_id)}
            style={{
              fontFamily: 'inherit',
              background: '#5b5fc7',
              color: '#ffffff',
              borderRadius: '8px',
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: 700,
              boxShadow: '0 4px 0 #3a3d9a',
              marginTop: '12px',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Fix this gap →
          </button>
        </>
      )}
    </div>
  )
}
