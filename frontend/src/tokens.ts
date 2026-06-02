// RIP V2 — Design Token Constants
// Source of truth: DESIGN_SYSTEM_V2.md §3
// Use T.* instead of raw hex values in all components going forward.

export const T = {
  // Brand
  primary:           '#5b5fc7',
  primaryDark:       '#4a4db8',
  primaryFloor:      '#3a3d9a',
  primaryLight:      '#eef0ff',
  primaryMid:        '#dde0ff',
  violet:            '#7c3aed',
  violetLight:       '#f5f3ff',
  violetBorder:      '#ddd6fe',

  // Gradients (as strings — use in background style prop)
  gradientBrand:     'linear-gradient(135deg, #5b5fc7, #7c3aed)',
  gradientHeroPage:  'linear-gradient(160deg, #f0f0ff 0%, #faf5ff 40%, #f7fff4 100%)',
  gradientHeroUpload:'linear-gradient(160deg, #f0f0ff, #faf5ff 60%, #fff)',
  gradientHeroResults:'linear-gradient(160deg, #f0f0ff, #fff 70%)',
  gradientHeroRewrites:'linear-gradient(160deg, #f0fff4, #ecfdf5 40%, #fff)',
  gradientHeroRecruiter:'linear-gradient(160deg, #f5f3ff, #faf5ff 50%, #fff)',

  // Semantic — Success
  emerald:           '#059669',
  emeraldLight:      '#ecfdf5',
  emeraldBorder:     '#a7f3d0',

  // Semantic — Warning
  amber:             '#d97706',
  amberLight:        '#fffbeb',
  amberBorder:       '#fcd34d',

  // Semantic — Error / Critical
  rose:              '#dc2626',
  roseLight:         '#fef2f2',
  roseBorder:        '#fecaca',

  // Neutrals — Text
  textPrimary:       '#0d0d1a',
  textSecondary:     '#4a4a6a',
  textMuted:         '#8888aa',
  textDisabled:      '#c8c8e0',

  // Neutrals — Surfaces
  border:            '#e2e2ef',
  borderStrong:      '#c8c8e0',
  bgPage:            '#f7f7fc',
  bgCard:            '#ffffff',
  bgSubtle:          '#f0f0f8',
  bgInput:           '#fafafd',
  bgHover:           '#f8f8ff',

  // Shadows
  shadowSm:          '0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.04)',
  shadowMd:          '0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)',
  shadowLg:          '0 12px 32px rgba(0,0,0,0.10), 0 4px 8px rgba(0,0,0,0.06)',
  shadowXl:          '0 20px 60px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.07)',
  shadowPrimary:     '0 4px 0 #3a3d9a, 0 8px 24px rgba(91,95,199,0.28)',
  shadowPrimarySm:   '0 3px 0 #3a3d9a, 0 6px 16px rgba(91,95,199,0.25)',
  shadowTopBar:      '0 1px 3px rgba(0,0,0,0.04)',

  // Layout
  maxWidth:          '1200px',
  topBarHeight:      '64px',

  // Radius
  radiusXl:          '24px',
  radiusLg:          '18px',
  radiusMd:          '16px',
  radiusSm:          '12px',
  radiusXs:          '8px',
  radiusPill:        '999px',
} as const;

export type TToken = typeof T;
