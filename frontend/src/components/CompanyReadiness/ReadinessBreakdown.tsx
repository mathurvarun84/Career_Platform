import { useEffect, useState } from 'react'

import type { CompanyReadinessResult } from '../../types'
import CTCImplicationBlock from './CTCImplicationBlock'
import DimensionCard from './DimensionCard'

interface ReadinessBreakdownProps {
  result: CompanyReadinessResult
  roleTitle: string
  onClose: () => void
  onFixGap: (dimensionId: string) => void
}

function getFillColor(score: number): string {
  if (score >= 80) return '#059669'
  if (score >= 40) return '#f59e0b'
  return '#dc2626'
}

function MiniBar({ value }: { value: number }) {
  return (
    <div
      style={{
        flex: 1,
        height: '6px',
        borderRadius: '3px',
        background: '#e2e2ef',
        overflow: 'hidden',
        marginLeft: '16px',
        marginRight: '16px',
      }}
    >
      <div
        style={{
          width: `${Math.max(0, Math.min(100, value))}%`,
          height: '100%',
          background: getFillColor(value),
          borderRadius: '3px',
        }}
      />
    </div>
  )
}

export default function ReadinessBreakdown({
  result,
  roleTitle,
  onClose,
  onFixGap,
}: ReadinessBreakdownProps) {
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== 'undefined' ? window.innerWidth >= 768 : true
  )

  useEffect(() => {
    const onResize = () => setIsDesktop(window.innerWidth >= 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const STRENGTH_ORDER: Record<string, number> = { weak: 0, developing: 1, strong: 2 }
  const sortedDimensions = [...result.dimensions].sort(
    (a, b) => STRENGTH_ORDER[a.signal_strength] - STRENGTH_ORDER[b.signal_strength]
  )

  const compositionRows = [
    { label: 'ATS Match', value: result.ats_component, muted: false },
    {
      label: 'JD Alignment',
      value: result.jd_component,
      muted: result.jd_component === null,
    },
    { label: 'Seniority Match', value: result.seniority_component, muted: false },
    { label: 'Company Signal Fit', value: result.company_signal_component, muted: false },
  ]

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.4)',
        zIndex: 100,
        display: 'flex',
        alignItems: isDesktop ? 'center' : 'flex-end',
        justifyContent: isDesktop ? 'center' : 'stretch',
        padding: isDesktop ? '20px' : 0,
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        style={{
          position: 'relative',
          background: '#ffffff',
          borderRadius: isDesktop ? '24px' : '24px 24px 0 0',
          padding: '32px',
          maxWidth: '720px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          style={{
            position: 'absolute',
            top: '16px',
            right: '20px',
            fontSize: '20px',
            color: '#8888aa',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            fontFamily: 'inherit',
            lineHeight: 1,
          }}
        >
          ×
        </button>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '20px',
            paddingRight: '32px',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              fontFamily: 'inherit',
              color: '#5b5fc7',
              fontSize: '14px',
              fontWeight: 600,
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            ← Back
          </button>
          <div style={{ fontSize: '14px', fontWeight: 700, color: '#0d0d1a' }}>
            {`${result.company_display_name} · ${roleTitle}`}
          </div>
        </div>

        <div
          style={{
            fontFamily: "'DM Serif Display', serif",
            fontStyle: 'italic',
            fontSize: '28px',
            color: '#0d0d1a',
            marginBottom: '28px',
            lineHeight: 1.3,
          }}
        >
          {`${result.readiness_score}% Ready for ${result.company_display_name}`}
        </div>

        <div
          style={{
            fontSize: '12px',
            color: '#8888aa',
            fontStyle: 'italic',
            marginBottom: '28px',
            lineHeight: 1.5,
          }}
        >
          {result.disclaimer}
        </div>

        {result.jd_component === null && (
          <div
            style={{
              background: '#fef9ec',
              border: '1px solid #fde68a',
              borderRadius: '10px',
              padding: '10px 14px',
              fontSize: '13px',
              color: '#92400e',
              marginBottom: '20px',
              lineHeight: 1.5,
            }}
          >
            <strong>No JD provided</strong> — score is based on resume signals only. Add a job description during analysis for a full readiness picture.
          </div>
        )}
        <div style={{ marginBottom: '28px' }}>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 700,
              color: '#8888aa',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '12px',
            }}
          >
            Score Composition
          </div>
          {compositionRows.map((row) => (
            <div
              key={row.label}
              style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: '10px',
              }}
            >
              <div
                style={{
                  fontSize: '13px',
                  color: row.muted ? '#8888aa' : '#4a4a6a',
                  width: '140px',
                  flexShrink: 0,
                }}
              >
                {row.label}
              </div>
              {!row.muted && row.value !== null && <MiniBar value={row.value} />}
              <div
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: row.muted ? '#8888aa' : '#0d0d1a',
                  width: '80px',
                  textAlign: 'right',
                  flexShrink: 0,
                }}
              >
                {row.muted ? 'No JD provided' : row.value}
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: '24px' }}>
          <div
            style={{
              fontSize: '12px',
              fontWeight: 700,
              color: '#8888aa',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '12px',
            }}
          >
            {`Dimension Breakdown (${result.company_display_name}-specific)`}
          </div>
          {sortedDimensions.map((dimension) => (
            <DimensionCard
              key={dimension.dimension_id}
              dimension={dimension}
              onFixGap={onFixGap}
            />
          ))}
        </div>

        <CTCImplicationBlock result={result} />
      </div>
    </div>
  )
}
