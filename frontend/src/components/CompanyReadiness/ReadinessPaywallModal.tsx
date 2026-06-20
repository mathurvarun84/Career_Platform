interface ReadinessPaywallModalProps {
  onClose: () => void
}

const FEATURES = [
  'Full Score Journey — unlimited history + PDF export',
  'Company Readiness breakdown — for 15 companies',
  'AI Career Coach — Evidence loop + bullet rewriting',
  'Career Pivot Mode — when changing tracks',
  'Mock Interview — grounded in your JD',
]

export default function ReadinessPaywallModal({ onClose }: ReadinessPaywallModalProps) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
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
          borderRadius: '20px',
          padding: '36px',
          maxWidth: '440px',
          width: '100%',
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
        <div style={{ textAlign: 'center', fontSize: '32px', marginBottom: '12px' }}>🔒</div>
        <div
          style={{
            fontSize: '18px',
            fontWeight: 700,
            color: '#0d0d1a',
            textAlign: 'center',
          }}
        >
          This is a Pro feature
        </div>
        <div
          style={{
            fontSize: '14px',
            color: '#4a4a6a',
            textAlign: 'center',
            marginTop: '8px',
            lineHeight: 1.5,
          }}
        >
          Score Journey full history and Company Readiness breakdown are part of RIP V2 Pro.
        </div>
        <div style={{ marginTop: '20px', marginBottom: '24px' }}>
          {FEATURES.map((feature) => (
            <div
              key={feature}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                fontSize: '13px',
                color: '#4a4a6a',
                marginBottom: '8px',
              }}
            >
              <span style={{ color: '#059669', fontWeight: 700 }}>✓</span>
              <span>{feature}</span>
            </div>
          ))}
        </div>
        <div
          style={{
            fontSize: '13px',
            color: '#8888aa',
            textAlign: 'center',
            marginBottom: '16px',
          }}
        >
          ₹499/month · Cancel anytime
        </div>
        <button
          type="button"
          style={{
            fontFamily: 'inherit',
            width: '100%',
            background: '#5b5fc7',
            color: '#ffffff',
            borderRadius: '10px',
            padding: '14px',
            fontSize: '15px',
            fontWeight: 700,
            boxShadow: '0 4px 0 #3a3d9a',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Start 7-day free trial →
        </button>
      </div>
    </div>
  )
}
