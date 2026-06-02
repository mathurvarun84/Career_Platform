# RIP V2 — Premium Design System V2
# Single source of truth for ALL pages, components, and spacing.
# Generated from: career_intelligence_premium.html wireframe (May 2026 redesign)
# Replaces: DESIGN_SYSTEM.md (V1 — moderate UI)

---

## DESIGN PHILOSOPHY

### North Star: "Calm Intelligence"
This product does something powerful and complex — AI multi-agent resume analysis. The UI must feel like a focused, expert professional delivering results. Not flashy. Not playful. Authoritative, precise, and trustworthy.

**Reference products:** Stripe (editorial precision), Linear (information density), Vercel (typographic discipline)

### Three Aesthetic Decisions That Define The System

1. **Page background is `#f7f7fc`, not `#ffffff`**
   Pure white feels cheap in 2026. A barely-tinted off-white (`#f7f7fc`) gives the page material depth and makes white cards float above it. This single change raises the perceived quality more than any other.

2. **`DM Serif Display` italic for hero headlines, `DM Sans` for everything else**
   The serif/sans pairing creates editorial hierarchy. Every screen has ONE serif moment (the page title or score). Everything else is clean DM Sans. This creates visual rhythm and prevents sameness across screens.

3. **3D button shadow uses a floor color, not a blur**
   `box-shadow: 0 4px 0 #3a3d9a` (solid floor) + `0 8px 24px rgba(91,95,199,0.25)` (ambient glow). The solid floor is what gives buttons physical weight. Do not collapse these into a single blurred shadow.

---

## 1. PAGE STRUCTURE (every page follows this)

```tsx
<div style={{ minHeight: '100vh', background: '#f7f7fc' }}>
  <TopBar />                    {/* sticky, 64px tall */}
  <HeroSection />               {/* gradient bg, screen-specific */}
  <div style={{
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '40px 40px 80px'
  }}>
    [page content]
  </div>
</div>
```

### Changed from V1:
| Token | V1 | V2 |
|-------|----|----|
| Page background | `#ffffff` | `#f7f7fc` |
| Max content width | `960px` | `1200px` |
| Side padding | `32px` | `40px` |

### Rules (same as V1 — enforce strictly):
- NO Tailwind `gap-*` / `p-*` / `m-*` for layout — inline `style` props only
- Headings via `<div>` with inline styles — never `<h1>` / `<h2>`
- Disabled state: explicit `bg` + `color` — NEVER `opacity`

---

## 2. TOPBAR

```tsx
<header style={{
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '0 40px', height: '64px',
  background: 'rgba(255,255,255,0.96)',
  borderBottom: '1px solid #e2e2ef',
  position: 'sticky', top: 0, zIndex: 50,
  backdropFilter: 'blur(20px) saturate(180%)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
}}>
```

**Logo mark:**
```
width: 36px, height: 36px, borderRadius: 10px
background: linear-gradient(135deg, #5b5fc7, #7c3aed)
boxShadow: 0 3px 8px rgba(91,95,199,0.35)
content: ✦, fontSize: 16px, color: #ffffff, fontWeight: 700
```

**Logo text:**
```
Primary: "AI Career Intelligence"  — 14px, fontWeight 700, color #0d0d1a, letterSpacing -0.02em
Sub:     "Powered by Advanced AI" — 10px, fontWeight 400, color #8888aa
```

**Nav links (Landing page only):**
```
fontSize: 13px, fontWeight: 500, color: #4a4a6a
hover: color #5b5fc7
gap between links: 28px
```

**Primary action button (TopBar):**
```
padding: 9px 20px, borderRadius: 8px
fontSize: 13px, fontWeight: 700
background: #5b5fc7, color: #ffffff
boxShadow: 0 3px 0 #3a3d9a, 0 6px 16px rgba(91,95,199,0.25)
hover: background #4a4db8, translateY(-1px)
active: translateY(2px), boxShadow 0 1px 0 #3a3d9a
```

**Ghost button (TopBar):**
```
padding: 8px 16px, borderRadius: 8px
fontSize: 13px, fontWeight: 600
color: #4a4a6a, border: 1.5px solid #e2e2ef, background: transparent
hover: border-color #5b5fc7, color #5b5fc7
```

**Tab switcher (Results / Rewrites / Recruiter screens):**
```
Container: display flex, border: 1.5px solid #e2e2ef, borderRadius: 12px, overflow: hidden, background: #fff
Each tab:  padding 8px 18px, fontSize 13px, fontWeight 500, color #4a4a6a, border: none, background: #fff
Active:    background #5b5fc7, color #ffffff, fontWeight 700
Separator: borderLeft 1px solid #e2e2ef
```

---

## 3. COLOR PALETTE

### Brand Colors
```
Primary (indigo):       #5b5fc7
Primary dark:           #4a4db8
Primary floor (3D):     #3a3d9a
Primary hover:          #4a4db8
Primary light bg:       #eef0ff
Primary mid border:     #dde0ff

Violet accent:          #7c3aed
Violet light bg:        #f5f3ff
Violet border:          #ddd6fe

Gradient primary:       linear-gradient(135deg, #5b5fc7, #7c3aed)
Gradient hero page:     linear-gradient(160deg, #f0f0ff 0%, #faf5ff 40%, #f7fff4 100%)
Gradient hero upload:   linear-gradient(160deg, #f0f0ff, #faf5ff 60%, #fff)
Gradient hero results:  linear-gradient(160deg, #f0f0ff, #fff 70%)
Gradient hero rewrites: linear-gradient(160deg, #f0fff4, #ecfdf5 40%, #fff)
Gradient hero recruiter: linear-gradient(160deg, #f5f3ff, #faf5ff 50%, #fff)
```

### Semantic Colors
```
Emerald (success):      #059669
Emerald light bg:       #ecfdf5
Emerald border:         #a7f3d0
Emerald text:           #059669

Amber (warning):        #d97706
Amber light bg:         #fffbeb
Amber border:           #fcd34d

Rose (error/critical):  #dc2626
Rose light bg:          #fef2f2
Rose border:            #fecaca

Indigo (scores/data):   #5b5fc7   ← same as primary; intentional
```

### Neutral / Text Colors
```
Text primary:           #0d0d1a   ← near-black with blue warmth (not pure #000)
Text secondary:         #4a4a6a   ← blue-grey mid
Text muted:             #8888aa   ← subdued labels, captions
Text disabled:          #c8c8e0   ← never opacity

Border default:         #e2e2ef   ← blue-tinted border (not grey #e5e7eb)
Border strong:          #c8c8e0

Background page:        #f7f7fc   ← off-white, NEVER pure #ffffff
Background card:        #ffffff   ← cards float above page
Background subtle:      #f0f0f8   ← inner sections, non-card areas
Background input:       #fafafd   ← textarea / input bg
Background hover:       #f8f8ff   ← interactive hover bg
```

### Changed from V1:
| Token | V1 value | V2 value | Why |
|-------|----------|----------|-----|
| Primary | `#6366f1` | `#5b5fc7` | Slightly cooler, more trustworthy |
| Primary floor | `#4338ca` | `#3a3d9a` | Matches new primary |
| Page bg | `#ffffff` | `#f7f7fc` | Adds material depth |
| Border | `#e5e7eb` | `#e2e2ef` | Warmer blue tint |
| Text primary | `#111827` | `#0d0d1a` | Richer, less grey |
| Text secondary | `#374151` | `#4a4a6a` | Blue-grey, not grey-grey |

---

## 4. TYPOGRAPHY SCALE

### Fonts
```
Display (hero):  'DM Serif Display', Georgia, serif — import from Google Fonts
Body / UI:       'DM Sans', -apple-system, sans-serif — import from Google Fonts
Mono (scores):   'JetBrains Mono', monospace — import from Google Fonts
```

### Add to `index.html`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400&family=DM+Serif+Display:ital@0;1&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
```

### Scale

| Role | Font | Size | Weight | Color | Notes |
|------|------|------|--------|-------|-------|
| Hero headline | DM Serif Display | 52px | 400 | `#0d0d1a` | Use `em` for italic accent |
| Hero headline mobile | DM Serif Display | 36px | 400 | `#0d0d1a` | |
| Page title (results) | DM Sans | 28px | 700 | `#0d0d1a` | letterSpacing -0.02em |
| Section heading | DM Sans | 36px | 700 | `#0d0d1a` | letterSpacing -0.025em |
| Card title large | DM Sans | 16px | 700 | `#0d0d1a` | letterSpacing -0.01em |
| Card title small | DM Sans | 14px | 700 | `#0d0d1a` | |
| Body text | DM Sans | 16px | 400 | `#4a4a6a` | lineHeight 1.65 |
| Body small | DM Sans | 14px | 400 | `#4a4a6a` | lineHeight 1.6 |
| Caption / label | DM Sans | 12px | 600 | `#8888aa` | textTransform uppercase, letterSpacing 0.05em |
| Score display | JetBrains Mono | 72px | 600 | `#5b5fc7` | fontVariantNumeric tabular-nums |
| Score medium | JetBrains Mono | 48px | 600 | [semantic color] | |
| Score small | JetBrains Mono | 36px | 600 | [semantic color] | |
| Metric strip number | DM Sans | 32px | 800 | `#0d0d1a` | letterSpacing -0.03em |
| Button primary lg | DM Sans | 15px | 700 | `#ffffff` | |
| Button primary sm | DM Sans | 13px | 700 | `#ffffff` | |
| Nav link | DM Sans | 13px | 500 | `#4a4a6a` | |
| Eyebrow / badge text | DM Sans | 12px | 700 | [contextual] | uppercase or not per context |

### Changed from V1:
- Display font introduced (DM Serif Display) — hero headlines only
- JetBrains Mono introduced — scores and data numbers only
- All body text bumped from 13px → 14–16px
- Max-width content from 960px → 1200px allows larger type without crowding

---

## 5. SPACING SYSTEM (8pt grid — all inline style props)

```
4px   — micro: icon-to-label gap, badge internal padding
8px   — tight: between sibling labels/badges
12px  — small: list item gap, chip gap
16px  — base: between card-internal elements
20px  — medium: card internal section gap
24px  — standard: card padding (small cards), gap between score cards
28px  — section element gap
32px  — card padding (medium cards)
36px  — between cards in a column
40px  — side padding, between major sections
48px  — section padding top/bottom (compact sections)
52px  — hero section padding top (upload, results heroes)
64px  — large section padding top/bottom
80px  — major section padding (landing page features)
96px  — hero section top padding (landing page only)
```

### Card Internal Padding Rules:
```
Main feature card (large):    padding: 32px
Standard card:                padding: 24px
Compact card / stat card:     padding: 20px 24px
Badge / chip:                 padding: 5px 14px (medium), 3px 10px (small)
Button primary lg:            padding: 14px 32px
Button primary sm:            padding: 9px 20px
Button ghost:                 padding: 8px 16px
```

---

## 6. CARD SYSTEM

### Hero Product Card (Landing page — ATS score showcase)
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderRadius: 24px
padding: 32px
boxShadow: 0 20px 60px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.07)
maxWidth: 860px, margin: 0 auto
```

### Standard Content Card
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderRadius: 18px
padding: 24px
boxShadow: 0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)
```

### Elevated / Featured Card (hover state or featured testimonial)
```
background: #ffffff
border: 1.5px solid #5b5fc7   ← indigo border
borderRadius: 18px
padding: 24px
boxShadow: 0 0 0 3px rgba(91,95,199,0.10), 0 8px 24px rgba(0,0,0,0.10)
```

### Score Card (Results screen)
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderRadius: 18px
padding: 24px
boxShadow: 0 2px 6px rgba(0,0,0,0.06)
```

### Upload Card (outer container)
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderRadius: 24px
boxShadow: 0 20px 60px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.07)
overflow: hidden   ← clips interior panels
maxWidth: 900px, margin: 0 auto
```

### Upload Panel Interior (left/right inside upload card)
```
padding: 36px
```

### Action Card (priority actions list)
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderLeft: 4px solid [severity color]   ← overrides left border
borderRadius: 18px
padding: 20px 24px
boxShadow: 0 2px 6px rgba(0,0,0,0.06)
hover: boxShadow 0 4px 12px rgba(0,0,0,0.07)
```

Severity left-border colors:
```
High:   borderLeft 4px solid #ef4444
Medium: borderLeft 4px solid #f59e0b
Low:    borderLeft 4px solid #94a3b8
```

### Persona Card (Recruiter screen)
```
background: #ffffff
borderRadius: 24px
overflow: hidden
boxShadow: 0 4px 12px rgba(0,0,0,0.07)
shortlisted: border 2px solid #6ee7b7
rejected:    border 2px solid #fca5a5
```

### Rewrite Card (AI Rewrites screen)
```
background: #ffffff
border: 1.5px solid #e2e2ef
borderRadius: 24px
overflow: hidden
boxShadow: 0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)
hover: boxShadow 0 12px 32px rgba(0,0,0,0.10)
```

### Dark Insight Card (Strategic insight / landing CTA)
```
background: linear-gradient(135deg, #0d0d1a, #1a1240)
borderRadius: 24px
padding: 40px
boxShadow: 0 20px 60px rgba(0,0,0,0.12)
```

### Changed from V1:
| Card | V1 shadow | V2 shadow |
|------|-----------|-----------|
| Main container | `0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)` | `0 20px 60px rgba(0,0,0,0.12), 0 8px 16px rgba(0,0,0,0.07)` |
| Feature card | `0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)` | `0 4px 12px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.05)` |
| Border radius | `24px` main, `18px` feature | Same — keep |
| Border color | `#e5e7eb` | `#e2e2ef` (blue-tinted) |

---

## 7. BUTTON SYSTEM

### Primary Button — Large (CTA, hero)
```tsx
style={{
  padding: '14px 32px',
  borderRadius: '12px',
  fontSize: '15px', fontWeight: 700,
  color: '#ffffff',
  background: '#5b5fc7',
  border: 'none', cursor: 'pointer',
  fontFamily: 'inherit',
  boxShadow: '0 4px 0 #3a3d9a, 0 8px 24px rgba(91,95,199,0.28)',
  display: 'inline-flex', alignItems: 'center', gap: '8px',
  transition: 'all 0.15s'
}}
onMouseEnter: transform translateY(-2px), boxShadow amplified
onMouseLeave: return to default
onClick:      transform translateY(3px), boxShadow 0 1px 0 #3a3d9a
```

### Primary Button — Small (topbar, inline actions)
```tsx
style={{
  padding: '9px 20px',
  borderRadius: '8px',
  fontSize: '13px', fontWeight: 700,
  color: '#ffffff',
  background: '#5b5fc7',
  border: 'none', cursor: 'pointer',
  fontFamily: 'inherit',
  boxShadow: '0 3px 0 #3a3d9a, 0 6px 16px rgba(91,95,199,0.25)',
  transition: 'all 0.15s'
}}
```

### Primary Button — Disabled
```tsx
style={{
  background: '#e2e2ef',
  color: '#c8c8e0',
  boxShadow: '0 3px 0 #d1d5db',
  cursor: 'not-allowed'
}}
```
**NEVER use opacity for disabled state.**

### Secondary Button — Large (demo, watch)
```tsx
style={{
  padding: '14px 28px',
  borderRadius: '12px',
  fontSize: '15px', fontWeight: 600,
  color: '#4a4a6a',
  background: '#ffffff',
  border: '1.5px solid #e2e2ef',
  cursor: 'pointer', fontFamily: 'inherit',
  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  display: 'inline-flex', alignItems: 'center', gap: '8px',
  transition: 'all 0.15s'
}}
hover: borderColor #5b5fc7, color #5b5fc7
```

### Ghost / Text Button
```tsx
style={{
  fontSize: '13px', fontWeight: 700,
  color: '#5b5fc7',
  background: 'transparent', border: 'none',
  cursor: 'pointer', fontFamily: 'inherit'
}}
hover: color #4a4db8
```

### Apply Fix Button (Rewrites screen — gradient)
```tsx
style={{
  padding: '9px 20px', borderRadius: '8px',
  fontSize: '13px', fontWeight: 700,
  color: '#ffffff', border: 'none',
  background: 'linear-gradient(135deg, #5b5fc7, #7c3aed)',
  cursor: 'pointer', fontFamily: 'inherit',
  boxShadow: '0 3px 8px rgba(91,95,199,0.25)'
}}
```

### Changed from V1:
| Element | V1 | V2 |
|---------|----|----|
| Primary bg | `#6366f1` | `#5b5fc7` |
| Primary floor | `#4338ca` | `#3a3d9a` |
| Primary border radius | `14px` | `12px` (large), `8px` (small) |
| Large button padding | `17px` (full width) | `14px 32px` (inline) |
| Disabled bg | `#f3f4f6` | `#e2e2ef` |
| Disabled color | `#9ca3af` | `#c8c8e0` |

---

## 8. BADGE / PILL / CHIP SYSTEM

### Section Badge (eyebrow above hero headline)
```tsx
style={{
  display: 'inline-flex', alignItems: 'center', gap: '6px',
  padding: '5px 14px', borderRadius: '20px',
  background: '#ffffff', border: '1.5px solid #dde0ff',
  fontSize: '12px', fontWeight: 700, color: '#5b5fc7',
  boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
}}
```

### Score Trend Pill
```tsx
// Indigo (ATS)
{ background: '#eef0ff', color: '#5b5fc7', borderRadius: '20px', padding: '3px 10px', fontSize: '11px', fontWeight: 700 }
// Violet (JD Match)
{ background: '#f5f3ff', color: '#7c3aed' }
// Emerald (Percentile)
{ background: '#ecfdf5', color: '#059669' }
```

### Action Priority Badge
```tsx
High:   { background: '#fef2f2', color: '#dc2626' }
Medium: { background: '#fffbeb', color: '#d97706' }
Low:    { background: '#f0f0f8', color: '#8888aa' }
All:    { padding: '3px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700 }
```

### Impact Badge (green "+X points")
```tsx
{ background: '#ecfdf5', color: '#059669', padding: '3px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 700 }
```

### Keyword Chip (ATS analysis)
```tsx
Found:   { background: '#ecfdf5', color: '#059669', border: '1px solid #a7f3d0' }
Missing: { background: '#fef2f2', color: '#dc2626', border: '1px solid #fecaca' }
All:     { padding: '5px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 600 }
```

### Requirement Chip (Recruiter card)
```tsx
{ padding: '5px 12px', borderRadius: '20px', background: '#f0f0f8', fontSize: '12px', fontWeight: 600, color: '#4a4a6a', border: '1px solid #e2e2ef' }
```

### Verdict Badge (Recruiter card)
```tsx
Shortlisted: { background: '#ecfdf5', color: '#059669', border: '1.5px solid #6ee7b7', padding: '9px 16px', borderRadius: '8px', fontSize: '13px', fontWeight: 700 }
Rejected:    { background: '#fef2f2', color: '#dc2626', border: '1.5px solid #fecaca' }
```

---

## 9. FORM ELEMENTS

### Textarea / Input
```tsx
style={{
  width: '100%',
  padding: '16px 18px',
  borderRadius: '12px',
  border: '1.5px solid #e2e2ef',
  fontSize: '14px', fontFamily: 'inherit',
  color: '#0d0d1a', lineHeight: 1.65,
  background: '#fafafd',
  resize: 'none', outline: 'none',
  transition: 'border-color 0.15s'
}}
onFocus: borderColor #5b5fc7, boxShadow 0 0 0 3px rgba(91,95,199,0.12)
onBlur:  borderColor #e2e2ef, boxShadow none
placeholder color: #c8c8e0
```

### Drop Zone
```tsx
// Default
{ border: '2px dashed #c8c8e4', borderRadius: '16px', padding: '40px 24px', background: '#fafafd', textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s' }
// Hover / Drag
{ borderColor: '#5b5fc7', background: '#eef0ff' }
// File uploaded
{ borderColor: '#6ee7b7', borderStyle: 'solid', background: '#ecfdf5' }
```

### Info Pill (Privacy / Hint bar)
```tsx
// Blue (privacy / security)
{ display: 'flex', alignItems: 'flex-start', gap: '8px', padding: '11px 14px', borderRadius: '8px', background: '#eef0ff', border: '1px solid #dde0ff', fontSize: '12px', color: '#3730a3', lineHeight: 1.5 }

// Violet (AI hint)
{ background: '#f5f3ff', border: '1px solid #ddd6fe', color: '#5b21b6' }
```

### Character counter
```tsx
{ fontSize: '12px', color: '#8888aa' }
valid (>50): color #059669
```

---

## 10. HERO SECTION PATTERN (per-screen gradient backgrounds)

Each screen has its own hero section with a distinct gradient that signals context.

```tsx
// Landing page hero
background: 'linear-gradient(160deg, #f0f0ff 0%, #faf5ff 40%, #f7fff4 100%)'
padding: '80px 40px 60px'   // generous — first impression

// Upload page hero
background: 'linear-gradient(160deg, #f0f0ff, #faf5ff 60%, #fff)'
padding: '56px 40px 48px'

// Results hero
background: 'linear-gradient(160deg, #f0f0ff, #fff 70%)'
padding: '40px 40px 32px'   // tighter — user has data to see

// Rewrites hero
background: 'linear-gradient(160deg, #f0fff4, #ecfdf5 40%, #fff)'
padding: '52px 40px 40px'

// Recruiter hero
background: 'linear-gradient(160deg, #f5f3ff, #faf5ff 50%, #fff)'
padding: '52px 40px 40px'
```

### Radial Glow Decorations (Landing page only)
```tsx
// Top-right glow
position: absolute, top: -100px, right: -100px
width: 600px, height: 600px, borderRadius: '50%'
background: 'radial-gradient(circle, rgba(91,95,199,0.08) 0%, transparent 70%)'
pointerEvents: 'none'

// Bottom-left glow
position: absolute, bottom: -80px, left: -80px
width: 400px, height: 400px, borderRadius: '50%'
background: 'radial-gradient(circle, rgba(124,58,237,0.06) 0%, transparent 70%)'
```

---

## 11. SECTION HEADER PATTERN

Used for every major section within a page (not hero headlines):

```tsx
<div style={{ textAlign: 'center', marginBottom: '48px' }}>
  <div style={{
    fontSize: '12px', fontWeight: 700, color: '#5b5fc7',
    textTransform: 'uppercase', letterSpacing: '0.06em',
    marginBottom: '10px'
  }}>
    Eyebrow Label
  </div>
  <div style={{
    fontSize: '36px', fontWeight: 700, letterSpacing: '-0.025em',
    color: '#0d0d1a', lineHeight: 1.2
  }}>
    Section Heading
  </div>
  <div style={{
    fontSize: '17px', color: '#4a4a6a', lineHeight: 1.65,
    maxWidth: '600px', margin: '14px auto 0'
  }}>
    Section subheadline
  </div>
</div>
```

### Inline Section Header (inside content area, left-aligned)
```tsx
<div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
  <div style={{ fontSize: '18px', fontWeight: 700, color: '#0d0d1a', letterSpacing: '-0.01em' }}>
    Section Title
  </div>
  <div style={{ fontSize: '13px', color: '#8888aa' }}>
    Count or metadata
  </div>
</div>
```

---

## 12. SCORE DISPLAY PATTERNS

### Large Score (Landing / Results hero)
```tsx
<span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '72px', fontWeight: 600, color: '#0d0d1a', lineHeight: 1, letterSpacing: '-0.03em' }}>
  91
</span>
<span style={{ fontSize: '22px', color: '#8888aa', fontWeight: 400, fontFamily: 'inherit' }}>/100</span>
```

### Score Card (Results dashboard — 3-up grid)
```tsx
// Number
{ fontFamily: "'JetBrains Mono', monospace", fontSize: '48px', fontWeight: 600, lineHeight: 1, letterSpacing: '-0.03em' }
// Colors per metric
ATS:        color #5b5fc7
JD Match:   color #7c3aed
Percentile: color #059669
```

### Score Ring (SVG — landing hero card)
```
outer circle:  stroke #e2e2ef, strokeWidth 9
fill circle:   stroke url(#gradient), strokeWidth 9, strokeLinecap round
gradient:      #5b5fc7 → #7c3aed
size:          120×120px viewBox
```

### Progress Bar (inside score cards)
```tsx
// Track
{ height: '5px', background: '#f0f0f8', borderRadius: '3px', overflow: 'hidden' }
// Fill
ATS:        { background: 'linear-gradient(90deg, #5b5fc7, #818cf8)' }
JD Match:   { background: 'linear-gradient(90deg, #7c3aed, #a78bfa)' }
Percentile: { background: 'linear-gradient(90deg, #059669, #34d399)' }
```

---

## 13. TAB NAVIGATION (Results / Rewrites / Recruiter screens)

Tab switcher lives in the TopBar for results screens (not below topbar):

```tsx
<div style={{ display: 'flex', border: '1.5px solid #e2e2ef', borderRadius: '12px', overflow: 'hidden', background: '#fff' }}>
  {tabs.map(tab => (
    <button key={tab.id} style={{
      padding: '8px 18px',
      fontSize: '13px',
      fontWeight: activeTab === tab.id ? 700 : 500,
      background: activeTab === tab.id ? '#5b5fc7' : '#ffffff',
      color: activeTab === tab.id ? '#ffffff' : '#4a4a6a',
      border: 'none',
      borderLeft: tab.id !== tabs[0].id ? '1px solid #e2e2ef' : 'none',
      cursor: 'pointer',
      fontFamily: 'inherit',
      transition: 'all 0.15s'
    }}>
      {tab.label}
    </button>
  ))}
</div>
```

**Changed from V1:**
- Tabs moved from below topbar → inside topbar (saves vertical real estate)
- Active style: indigo filled pill segment, not just an underline
- No underline indicator — filled background is the signal

---

## 14. BEFORE / AFTER DIFF PATTERN (Rewrites screen)

```tsx
// Container
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }

// Before pane
{ background: '#fff5f5', border: '1.5px solid #fecaca', borderRadius: '12px', padding: '18px 20px' }

// After pane
{ background: '#f0fdf4', border: '1.5px solid #a7f3d0', borderRadius: '12px', padding: '18px 20px' }

// Label row
{ fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '5px' }
Before label color: #ef4444
After label color:  #059669

// Text
Before: fontSize 13px, color #4a4a6a, lineHeight 1.65
After:  fontSize 13px, color #0d0d1a, fontWeight 500, lineHeight 1.65
```

### "Why This Matters" box
```tsx
{ background: 'linear-gradient(135deg, #eef0ff, #f5f3ff)', border: '1px solid #dde0ff', borderRadius: '12px', padding: '18px 20px' }
title: fontSize 12px, fontWeight 700, color #5b5fc7, marginBottom 8px
text:  fontSize 13px, color #4a4a6a, lineHeight 1.6
```

---

## 15. FEATURE SECTION PATTERNS (Landing page)

### Alternating Layout (image left / text right, then reversed)
```tsx
// Row container
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '64px', alignItems: 'center', marginBottom: '80px' }

// Feature tag (eyebrow above feature title)
{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '5px 14px', borderRadius: '20px', fontSize: '12px', fontWeight: 700, marginBottom: '16px' }
Indigo tag: background #eef0ff, color #5b5fc7
Violet tag: background #f5f3ff, color #7c3aed
Green tag:  background #ecfdf5, color #059669

// Feature title
{ fontSize: '30px', fontWeight: 700, letterSpacing: '-0.025em', color: '#0d0d1a', marginBottom: '14px', lineHeight: 1.25 }

// Feature body
{ fontSize: '16px', color: '#4a4a6a', lineHeight: 1.7, marginBottom: '20px' }

// Feature list item
display: flex, alignItems: flex-start, gap: 10px, fontSize: 14px, color: #4a4a6a
checkmark circle: width 18px, height 18px, borderRadius 50%, background #eef0ff, color #5b5fc7, fontSize 10px, fontWeight 800
```

### Full-Width Feature Card (AI Rewrites preview)
```tsx
{ background: 'linear-gradient(135deg, #eef0ff, #f5f3ff)', borderRadius: '24px', padding: '52px', border: '1.5px solid #dde0ff' }
```

---

## 16. TESTIMONIAL CARD PATTERN

```tsx
// Container
{ background: '#ffffff', border: '1.5px solid #e2e2ef', borderRadius: '18px', padding: '28px', boxShadow: '0 2px 6px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column', gap: '16px' }

// Featured variant (center card)
border: '1.5px solid #5b5fc7'
boxShadow: '0 0 0 3px rgba(91,95,199,0.10), 0 4px 12px rgba(0,0,0,0.07)'

// Stars
{ color: '#f59e0b', fontSize: '14px', letterSpacing: '2px' }

// Quote
{ fontSize: '14px', color: '#0d0d1a', lineHeight: 1.65, fontStyle: 'italic' }

// Author row
{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: 'auto' }

// Avatar
{ width: 40px, height: 40px, borderRadius: '50%', objectFit: 'cover', border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }

// Avatar fallback (no image)
gradient background per person, fontWeight 700, color #fff

// Outcome line
{ fontSize: '11px', fontWeight: 700, color: '#059669', marginTop: '2px' }
```

---

## 17. SUCCESS STORY CARD PATTERN (Landing page)

```tsx
// Emerald card
{ borderRadius: '24px', padding: '36px', background: 'linear-gradient(135deg, #ecfdf5, #d1fae5)', border: '1.5px solid #6ee7b7', position: 'relative', overflow: 'hidden' }

// Indigo card
{ background: 'linear-gradient(135deg, #eef0ff, #ede9fe)', border: '1.5px solid #dde0ff' }

// Score comparison grid
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }

// Score box
{ background: '#ffffff', borderRadius: '12px', padding: '16px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }
before score: fontSize 36px, fontWeight 800, color #dc2626
after score:  fontSize 36px, fontWeight 800, color #059669 or #5b5fc7

// Completion badge (top-right of after box)
{ position: 'absolute', top: -10, right: -10, width: 22, height: 22, background: [color], borderRadius: '50%', color: '#fff', fontSize: 11, fontWeight: 800 }
```

---

## 18. HOW IT WORKS — STEP PATTERN

```tsx
// Step icon
{ width: 64, height: 64, borderRadius: 18, background: 'linear-gradient(135deg, #5b5fc7, #7c3aed)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', fontSize: 26, color: '#fff', boxShadow: '0 6px 20px rgba(91,95,199,0.3)' }

// Step number (display font)
{ fontFamily: "'DM Serif Display', serif", fontSize: '56px', background: 'linear-gradient(135deg, #5b5fc7, #7c3aed)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', marginBottom: 4 }

// Step title
{ fontSize: '18px', fontWeight: 700, color: '#0d0d1a', marginBottom: 8 }

// Step body
{ fontSize: '14px', color: '#4a4a6a', lineHeight: 1.65 }
```

---

## 19. METRICS STRIP (Landing page — social proof numbers)

```tsx
// Container
{ background: '#ffffff', borderTop: '1px solid #e2e2ef', borderBottom: '1px solid #e2e2ef', padding: '32px 40px' }

// Grid
{ maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }

// Item
{ padding: '0 32px', textAlign: 'center' }
// Not first: borderLeft '1px solid #e2e2ef'

// Value
{ fontSize: '32px', fontWeight: 800, color: '#0d0d1a', letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums' }

// Label
{ fontSize: '12px', color: '#8888aa', marginTop: '3px', fontWeight: 500 }
```

---

## 20. GRID TEMPLATES

```tsx
// 2-column equal (feature alternating, before/after)
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }         // tight
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }         // standard
{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '64px' }         // feature section

// 3-column equal (score cards, preview features, testimonials)
{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }  // testimonials
{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }  // preview feat

// 4-column equal (metrics strip, recruiter stats)
{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }

// 4-column footer
{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: '48px' }
```

---

## 21. FOOTER PATTERN

```tsx
// Site footer
{ background: '#0d0d1a', padding: '60px 40px 40px' }

// Grid
{ maxWidth: 1200, margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 48, marginBottom: 48 }

// Brand column
name: fontSize 14px, fontWeight 700, color #f0f0ff, marginBottom 10px
body: fontSize 13px, color #52526a, lineHeight 1.6

// Column title
{ fontSize: '12px', fontWeight: 700, color: '#f0f0ff', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '14px' }

// Link
{ display: 'block', fontSize: '13px', color: '#52526a', marginBottom: '8px' }
hover: color #a1a1c0

// Bottom bar
{ borderTop: '1px solid #1e1e3a', marginTop: 0, paddingTop: 24, fontSize: 12, color: '#333358', textAlign: 'center' }
```

---

## 22. FINAL CTA SECTION (Landing page)

```tsx
{ background: 'linear-gradient(135deg, #5b5fc7, #7c3aed)', padding: '80px 40px', textAlign: 'center' }

headline: fontFamily DM Serif Display, fontSize 44px, color #fff, letterSpacing -0.02em, marginBottom 16px
sub:      fontSize 17px, color rgba(255,255,255,0.75), maxWidth 520px, margin 0 auto 32px, lineHeight 1.65

// CTA button (inverted — white on indigo background)
{ padding: '14px 32px', borderRadius: '12px', background: '#ffffff', color: '#5b5fc7', fontSize: '15px', fontWeight: 700, border: 'none', cursor: 'pointer', fontFamily: 'inherit', boxShadow: '0 4px 0 rgba(0,0,0,0.15), 0 8px 24px rgba(0,0,0,0.2)' }
```

---

## 23. CRITICAL RULES (enforce on every page — same as V1 plus additions)

```
SPACING:     ALWAYS use inline style props for gap/margin/padding
             NEVER rely on Tailwind gap-*, p-*, m-* for layout

DISABLED:    ALWAYS use explicit bg + color
             NEVER use opacity-* on buttons or interactive elements

HEADINGS:    ALWAYS use <div> not <h1>/<h2> for page titles (CSS override risk)

INDEX.CSS:   NEVER add h1, h2, :root font rules, text-align:center
             Only @tailwind directives + html/body/#root

FONTS:       ALWAYS add fontFamily: 'inherit' to textarea/input/button
             Import all three fonts (DM Sans, DM Serif Display, JetBrains Mono)

PAGE BG:     ALWAYS #f7f7fc — NEVER pure #ffffff as page background
             #ffffff is reserved for card surfaces only

BORDERS:     ALWAYS #e2e2ef (blue-tinted) — NEVER #e5e7eb (grey) in new components
             1.5px solid on all cards — NOT 1px

SHADOWS:     3-layer system required on primary buttons:
             floor shadow (solid #3a3d9a) + diffuse shadow (rgba) + hover amplification

SCORE FONT:  ALWAYS JetBrains Mono for score numbers
             NEVER use DM Sans for large numeric displays

DISPLAY:     ALWAYS DM Serif Display italic for hero headlines (ONE per screen)
             NEVER use it for body text, labels, or secondary content

COLORS:      Use tokens from §3 only — no invented hex values
             Primary is #5b5fc7 not #6366f1 (V1 value — do not regress)
```

---

## 24. ADDING A NEW PAGE — CHECKLIST (updated)

Before writing any component:

- [ ] Read CLAUDE.md → DESIGN_SYSTEM_V2.md → types/index.ts → mockData.ts
- [ ] Page background: `#f7f7fc` (not `#ffffff`)
- [ ] Max-width: `1200px` (not `960px`)
- [ ] Fonts imported: DM Sans, DM Serif Display, JetBrains Mono
- [ ] Hero section: correct gradient from §10 for this screen
- [ ] One serif display headline per screen maximum
- [ ] Score/number displays: JetBrains Mono
- [ ] All borders: `1.5px solid #e2e2ef`
- [ ] All spacing: inline `style` props — zero Tailwind layout classes
- [ ] Primary buttons: 3D shadow floor + ambient glow
- [ ] Disabled state: explicit bg/color — never opacity
- [ ] `tsc --noEmit` → 0 errors before marking done
- [ ] `npm run build` → success before marking done

---

## 25. HOW TO USE THIS FILE IN CLAUDE CODE

Add this to the start of every Day prompt:

```
Read CLAUDE.md
Read frontend/DESIGN_SYSTEM_V2.md   ← this file, replaces V1
Read frontend/src/types/index.ts
Read frontend/src/mocks/mockData.ts
```

This file is the single source of truth for:
- Every color token and when to use it
- Every font choice and pairing rule
- Every spacing value on the 8pt grid
- Every shadow layer (floor + ambient + hover)
- Every card variant and when to use which
- Every pattern with production-ready TSX snippets

Claude Code must not invent new values. If a component needs a style
not listed here, add it here first, then implement.