import type { CompanyReadinessResult } from '../../types'

interface CTCImplicationBlockProps {
  result: CompanyReadinessResult
}

export default function CTCImplicationBlock({ result }: CTCImplicationBlockProps) {
  if (result.current_ctc_min === null) {
    return null
  }

  const showDelta =
    result.ctc_delta_min !== null && result.ctc_delta_min !== 0

  return (
    <div
      style={{
        background: '#f0f0f8',
        borderRadius: '12px',
        padding: '20px 24px',
      }}
    >
      <div
        style={{
          fontSize: '12px',
          fontWeight: 700,
          color: '#8888aa',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          marginBottom: '16px',
        }}
      >
        CTC Implication
      </div>
      <div style={{ display: 'flex', flexDirection: 'row', gap: '32px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '12px', color: '#8888aa', marginBottom: '4px' }}>
            Current positioning
          </div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#0d0d1a' }}>
            {`₹${result.current_ctc_min}–${result.current_ctc_max} LPA`}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '12px', color: '#8888aa', marginBottom: '4px' }}>
            After targeted fixes
          </div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#0d0d1a' }}>
            {`₹${result.target_ctc_min}–${result.target_ctc_max} LPA`}
          </div>
        </div>
      </div>
      {showDelta && (
        <div
          style={{
            fontSize: '14px',
            fontWeight: 700,
            color: '#059669',
            marginTop: '16px',
          }}
        >
          {`Potential gain: ₹${result.ctc_delta_min}–${result.ctc_delta_max} LPA`}
        </div>
      )}
    </div>
  )
}
