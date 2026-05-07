# RIP V2 — Design System & Style Guide
# Source of truth for ALL pages. Never deviate from these tokens.
# Generated from: Upload page (pixel-perfect, production approved)

---

## 1. PAGE STRUCTURE (every page follows this)

```
<div style={{ minHeight: '100vh', background: '#ffffff' }}>
  <TopBar />                          ← sticky, always present
  <div style={{ maxWidth: '960px', margin: '0 auto', padding: '40px 32px 48px' }}>
    [page content]
  </div>
</div>
```

Rules:
- Page background: #ffffff (white) — set in both App.tsx wrapper AND index.css #root
- Content max-width: 960px, centered with margin: 0 auto
- Content padding: 40px 32px 48px (top / sides / bottom)
- NO Tailwind gap/padding/margin classes for layout — use inline style props only
- Tailwind allowed for: colors, font sizes, flex/grid shorthand, hover states

---

## 2. TOPBAR (locked — do not change)

```tsx
<header style={{
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '14px 32px', background: '#ffffff',
  borderBottom: '1.5px solid #e5e7eb',
  position: 'sticky', top: 0, zIndex: 50,
  backdropFilter: 'blur(12px)',
  boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
}}>
  Brand icon: 42×42, borderRadius 12px
    background: linear-gradient(135deg, #6366f1, #7c3aed)
    boxShadow: 0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.3)
    content: ✦ (sparkle), fontSize 19px, color #fff

  Brand name:  "AI Career Intelligence Platform"
    fontSize 16px, fontWeight 700, color #111827

  Brand sub:   "Powered by Advanced AI"
    fontSize 11px, fontWeight 400, color #6b7280

  Right button: Download Report
    background #6366f1, color #fff, borderRadius 10px
    padding 10px 20px, fontSize 13px, fontWeight 700
    3D shadow active:   0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)
    3D shadow disabled: 0 3px 0 #d1d5db
    disabled bg: #f3f4f6, disabled color: #9ca3af
    active:translateY(3px) on click
```

---

## 3. COLOR PALETTE

```
Primary:          #6366f1   (indigo)
Primary dark:     #4f46e5
Primary floor:    #4338ca   (3D shadow bottom)
Primary hover:    #5a38e8
Primary muted:    #f3f4f6   (disabled bg)
Primary text dis: #9ca3af   (disabled text)

Purple accent:    #7c3aed
Purple light:     #f5f0ff   (icon bg right col)
Purple border:    #e9d5ff
Purple hint bg:   #faf5ff
Purple hint brd:  #ede9fe

Blue light:       #eef2ff   (icon bg left col)
Blue border:      #c7d2fe
Blue bg:          #eef2ff   (privacy note)

Text primary:     #111827
Text secondary:   #374151
Text muted:       #6b7280
Text placeholder: #c4b5fd
Text hint:        #9ca3af
Text info:        #3730a3

Border default:   #e5e7eb
Border dashed:    #d1d5db
Border focus:     #6366f1

Background page:  #ffffff
Background card:  #ffffff
Background input: #fafafa
Background hover: #f5f3ff

Success green:    #16a34a
Success bg:       #dcfce7
Error red:        #ef4444
Warning amber:    #fbbf24
```

---

## 4. TYPOGRAPHY SCALE (ALL sizes use inline style — never Tailwind text-* for these)

```
Page section title:   fontSize 17px, fontWeight 700, color #111827, letterSpacing -0.01em
Page section sub:     fontSize 13px, fontWeight 400, color #6b7280
Card title (large):   fontSize 15px, fontWeight 700, color #111827, letterSpacing -0.01em
Card body:            fontSize 13px, fontWeight 400, color #6b7280, lineHeight 1.55
Pill label:           fontSize 13px, fontWeight 700, color #374151
Hint text:            fontSize 13px, fontWeight 600, fontStyle italic, color #7c3aed
Privacy/note text:    fontSize 12.5px, fontWeight 400, color #4b5563, lineHeight 1.55
Meta / counter:       fontSize 12px, fontWeight 400, color #9ca3af
Button primary:       fontSize 16px, fontWeight 700, color #ffffff
Button small:         fontSize 13px, fontWeight 700
Demo badge:           fontSize 12px, fontWeight 700, color #7c3aed
Input text:           fontSize 14px, fontWeight 400, color #374151, lineHeight 1.65
Analyze hint:         fontSize 12.5px, color #9ca3af
TopBar name:          fontSize 16px, fontWeight 700, color #111827
TopBar sub:           fontSize 11px, fontWeight 400, color #6b7280
```

---

## 5. SPACING SYSTEM (ALL use inline style props — never Tailwind gap/margin/padding)

```
Page top padding:         40px
Page side padding:        32px
Page bottom padding:      48px
Section to section gap:   36px (pills → main card)
Between main card and feature cards: 20px (marginBottom on main card)
Between columns (2-col grid): 40px
Between header and content: 18px (section header → dropzone/textarea)
Card internal padding:    40px (main card), 28px 24px (feature cards)
Between pills:            12px
Between feature cards:    16px
Privacy note top margin:  14px
Demo badge top margin:    12px
Hint bar top margin:      12px
Character counter top:    8px
Divider margin:           28px top, 24px bottom
Section icon size:        42×42px
Section icon radius:      12px
```

---

## 6. CARD SYSTEM

### Main Container Card
```
background: #ffffff
border: 1.5px solid #e5e7eb
borderRadius: 24px
padding: 40px
boxShadow: 0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)
marginBottom: 20px
```

### Feature / Info Cards
```
background: #ffffff
border: 1.5px solid #e5e7eb
borderRadius: 18px
padding: 28px 24px
boxShadow: 0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)
display: flex, flexDirection: column
alignItems: center, textAlign: center
```

### Score / Stat Cards (Overview tab)
```
background: #ffffff
border: 1.5px solid #e5e7eb
borderRadius: 16px
padding: 24px
boxShadow: 0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)
```

### Alert / Warning Cards
```
Left border accent: 4px solid [color]
borderRadius: 12px (right side only via borderRadius: 0 12px 12px 0)
background: tinted version of accent color at 5% opacity
padding: 16px 20px
```

---

## 7. BUTTON SYSTEM (3D effect — apply everywhere)

### Primary Button (full width, e.g. Analyze Resume)
```
background: file ? '#6366f1' : '#f3f4f6'
color: file ? '#ffffff' : '#9ca3af'
border: none, borderRadius: 14px, padding: 17px
fontSize: 16px, fontWeight: 700
cursor: file ? 'pointer' : 'not-allowed'
boxShadow active:   0 4px 0 #4338ca, 0 6px 16px rgba(99,102,241,0.25)
boxShadow disabled: 0 4px 0 #d1d5db
transition: transform 0.1s
onClick press: translateY(3px)
NEVER use opacity for disabled state
```

### Secondary Button (e.g. TopBar Download Report)
```
background: #6366f1, color: #ffffff
borderRadius: 10px, padding: 10px 20px
fontSize: 13px, fontWeight: 700
boxShadow: 0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)
disabled: bg #f3f4f6, color #9ca3af, shadow: 0 3px 0 #d1d5db
```

### Tertiary / Ghost (e.g. Change file link)
```
fontSize: 13px, fontWeight: 700, color: #6366f1
background: transparent, border: none, cursor: pointer
hover: color #4f46e5
```

---

## 8. PILL / BADGE SYSTEM

### Feature Pills (top of page)
```
display: flex, alignItems: center, gap: 8px
background: #ffffff, border: 1.5px solid #e5e7eb
borderRadius: 999px, padding: 8px 18px
fontSize: 13px, fontWeight: 700, color: #374151
boxShadow: 0 2px 0 #d1d5db, 0 3px 8px rgba(0,0,0,0.08)
Icon circle: 22×22px, borderRadius 50%, colored bg per pill
```

### Demo Mode Badge
```
display: inline-flex, alignItems: center, gap: 7px
background: #f5f0ff, border: 1.5px solid #e9d5ff
borderRadius: 999px, padding: 6px 14px
fontSize: 12px, fontWeight: 700, color: #7c3aed
```

### Status Badge (success/error/warning)
```
borderRadius: 999px, padding: 4px 12px
fontSize: 12px, fontWeight: 600
success: bg #dcfce7, color #16a34a
error:   bg #fef2f2, color #dc2626
warning: bg #fefce8, color #d97706
```

---

## 9. FORM ELEMENTS

### Textarea / Input
```
border: 1.5px solid #e5e7eb
borderRadius: 14px, padding: 15px 18px
fontSize: 14px, fontFamily: inherit
color: #374151, lineHeight: 1.65
background: #ffffff, resize: none
outline: none, display: block
boxSizing: border-box
transition: border 0.15s
onFocus: borderColor #6366f1
onBlur: borderColor #e5e7eb
placeholder color: #c4b5fd
```

### Drop Zone
```
border: 2px dashed #d1d5db (default)
       2px dashed #6366f1 (hover/drag/file)
borderRadius: 16px
background: #fafafa (default), #f5f3ff (hover/drag), #f0fdf4 (file uploaded)
minHeight: 190px (match JD textarea height)
display: flex, flexDirection: column
alignItems: center, justifyContent: center
padding: 32px 24px, textAlign: center
cursor: pointer, transition: all 0.2s
```

### Privacy / Info Box
```
display: flex, alignItems: flex-start, gap: 10px
background: #eef2ff, borderRadius: 12px
padding: 13px 15px
i-badge: 18×18px circle, bg #c7d2fe, fontSize 10px, fontWeight 800, color #3730a3
text: fontSize 12.5px, color #4b5563, lineHeight 1.55
```

### Hint Bar
```
display: flex, alignItems: center, gap: 8px
background: #faf5ff, border: 1px solid #ede9fe
borderRadius: 10px, padding: 11px 15px
icon: ✦ fontSize 15px color #7c3aed
text: fontSize 13px, fontWeight 600, fontStyle italic, color #7c3aed
```

---

## 10. SECTION HEADER PATTERN (reuse on every tab)

```tsx
<div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '18px' }}>
  <div style={{
    width: '42px', height: '42px', borderRadius: '12px',
    background: '[tint color]',   // #eef2ff (blue) or #f5f0ff (purple) or #f0fdf4 (green)
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
  }}>
    [SVG icon in primary color]
  </div>
  <div>
    <div style={{ fontSize: '17px', fontWeight: 700, color: '#111827', letterSpacing: '-0.01em' }}>
      Section Title
    </div>
    <div style={{ fontSize: '13px', fontWeight: 400, color: '#6b7280', marginTop: '2px' }}>
      Section subtitle
    </div>
  </div>
</div>
```

Icon bg colors by context:
- Blue  (#eef2ff): documents, resume, data
- Purple (#f5f0ff): AI, analysis, description
- Green (#f0fdf4): success, progress, fixes
- Amber (#fff7ed): warnings, actions
- Red   (#fef2f2): errors, critical issues

---

## 11. TAB NAVIGATION (TabNav.tsx — locked)

```
Container: bg #ffffff, borderBottom 1.5px #e5e7eb
Tab item: padding 14px 20px, fontSize 13px, fontWeight 500, color #6b7280
Active:   color #6366f1, borderBottom 2px solid #6366f1, fontWeight 700
Hover:    color #374151, bg #f9fafb
Disabled: opacity unset — use color #d1d5db, cursor not-allowed
Icons:    w-4 h-4 per tab, gap 6px between icon and label
```

---

## 12. TWO-COLUMN GRID PATTERN

```tsx
<div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px' }}>
  <div>[left content]</div>
  <div>[right content]</div>
</div>
```

Three-column (feature cards):
```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
```

Four-column (score cards):
```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px' }}>
```

---

## 13. SCORE / METRIC CARD PATTERN (Overview tab)

```tsx
<div style={{
  background: '#ffffff', border: '1.5px solid #e5e7eb',
  borderRadius: '16px', padding: '24px',
  boxShadow: '0 2px 0 #e5e7eb, 0 4px 12px rgba(0,0,0,0.04)'
}}>
  <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '8px' }}>
    Label
  </div>
  <div style={{ fontSize: '42px', fontWeight: 800, color: '#6366f1', lineHeight: 1 }}>
    68
  </div>
  <div style={{ fontSize: '13px', color: '#9ca3af' }}>/100</div>
  {/* Delta pill */}
  <div style={{
    display: 'inline-flex', alignItems: 'center', gap: '4px',
    background: '#dcfce7', borderRadius: '999px',
    padding: '3px 10px', fontSize: '12px', fontWeight: 700, color: '#16a34a',
    marginTop: '8px'
  }}>
    ↗ +14
  </div>
</div>
```

---

## 14. BEFORE/AFTER DIFF CARD PATTERN (Fixes tab)

```
Container: border 1.5px #e5e7eb, borderRadius 16px, overflow hidden
Left panel (before):  bg #fafafa, padding 20px, fontSize 13px, color #6b7280
Right panel (after):  bg #f0fdf4, padding 20px, fontSize 13px, color #374151
Divider: 1.5px solid #e5e7eb vertical
Header row: bg #f9fafb, padding 10px 20px
  "Before" label: fontSize 11px, fontWeight 700, color #9ca3af, textTransform uppercase
  "After" label:  fontSize 11px, fontWeight 700, color #16a34a, textTransform uppercase
```

---

## 15. RECRUITER PERSONA CARD PATTERN (Recruiter tab)

```
Grid: repeat(2, 1fr), gap 16px
Card: bg #fff, border 1.5px #e5e7eb, borderRadius 16px, padding 20px
Header: persona name (15px 700 #111827) + company type badge
Decision badge: 
  Shortlisted: bg #dcfce7, color #16a34a, text "✓ Shortlisted"
  Rejected:    bg #fef2f2, color #dc2626, text "✗ Not shortlisted"
  borderRadius 999px, padding 4px 12px, fontSize 12px, fontWeight 700
First impression: fontSize 13px, color #374151, fontStyle italic, marginTop 8px
Rejection reason: fontSize 13px, color #dc2626, marginTop 6px
```

---

## 16. PROGRESS CHART PATTERN (Progress tab)

```
Chart container: bg #fff, border 1.5px #e5e7eb, borderRadius 16px, padding 24px
Recharts LineChart:
  ATS line:      stroke #6366f1, strokeWidth 2.5
  JD Match line: stroke #16a34a, strokeWidth 2.5
  Grid:          stroke #f3f4f6
  Tooltip:       bg #fff, border 1.5px #e5e7eb, borderRadius 8px
```

---

## 17. CRITICAL RULES (enforce on every page)

```
SPACING:   ALWAYS use inline style props for gap/margin/padding
           NEVER rely on Tailwind gap-*, p-*, m-* for layout spacing
           Tailwind gap classes do not survive CSS purge in this project

DISABLED:  ALWAYS use explicit bg/color for disabled state
           NEVER use opacity-40 or opacity-50 on buttons

HEADINGS:  ALWAYS use <div> not <h1>/<h2> for page titles
           Global h1/h2 CSS rules override Tailwind arbitrary values

INDEX.CSS: NEVER add h1, h2, :root font rules, or text-align:center
           Only @tailwind directives + html/body/#root allowed

FONTS:     ALWAYS add fontFamily: 'inherit' or font-sans to textarea/input
           Browser default monospace applies to form elements otherwise

IMAGES:    NEVER use opacity-based disabled. Card shadows use 3-layer system:
           floor shadow (#4338ca) + diffuse shadow (rgba) + disabled floor (#d1d5db)
```

---

## 18. ADDING A NEW PAGE — CHECKLIST

Before writing any component for a new tab:

[ ] Import useResumeStore — read analysisResult, selectedStyle, activeTab
[ ] Import useMockData hook — never call API directly in component
[ ] Page wrapper: maxWidth 960px, margin auto, padding 40px 32px 48px (inline style)
[ ] Section headers: 42px icon + 17px bold title + 13px subtitle
[ ] Cards: white bg + 1.5px #e5e7eb border + appropriate borderRadius + box shadow
[ ] Spacing: ALL gaps via inline style props
[ ] Buttons: 3D shadow system, no opacity disabled
[ ] Typography: match the scale in section 4
[ ] tsc --noEmit → 0 errors before reporting done
[ ] npm run build → success before reporting done



---

## 19. HOW TO USE THIS FILE IN CLAUDE CODE

Add this to the start of every Day prompt:

  [Read CLAUDE.md]
  [Read frontend/DESIGN_SYSTEM.md]   ← READ THIS FIRST
  [Read frontend/src/types/index.ts]
  [Read frontend/src/mocks/mockData.ts]

The DESIGN_SYSTEM.md is the single source of truth for:
  - Every color value
  - Every spacing value  
  - Every shadow value
  - Every card pattern
  - Every typography size

Claude Code must not invent new values. If a component needs a style
not listed here, it must ask before creating a new pattern.
