import type { ReadinessSignalStrength } from '../../types'

interface DimensionBadgeProps {
  strength: ReadinessSignalStrength
  label?: string
}

const BADGE_STYLE: Record<
  ReadinessSignalStrength,
  { background: string; color: string; border: string; text: string }
> = {
  strong: {
    background: '#d1fae5',
    color: '#065f46',
    border: '1px solid #a7f3d0',
    text: 'Signal Found',
  },
  developing: {
    background: '#fef3c7',
    color: '#92400e',
    border: '1px solid #fde68a',
    text: 'Partial Signal',
  },
  weak: {
    background: '#fee2e2',
    color: '#991b1b',
    border: '1px solid #fecaca',
    text: 'Signal Not Found',
  },
}

export default function DimensionBadge({ strength, label }: DimensionBadgeProps) {
  const config = BADGE_STYLE[strength]
  const text = label ?? config.text

  return (
    <span
      style={{
        background: config.background,
        color: config.color,
        border: config.border,
        fontSize: '11px',
        fontWeight: 700,
        borderRadius: '6px',
        padding: '2px 8px',
        textTransform: 'uppercase',
        display: 'inline-block',
        flexShrink: 0,
      }}
    >
      {text}
    </span>
  )
}
