# RIP V2 — CLAUDE.md (Compressed)

## Identity
Resume Intelligence Platform V2 | Zenteiq Aitech | Bengaluru
Target: Indian SWEs 22–40, fresher–staff level

## Backend Stack
Python 3.9+ | Pydantic v2 | Typer/Rich CLI | FastAPI (web) | python-docx | pdfplumber | python-dotenv

## Models
| Agent | Provider | Model | max_tokens |
|---|---|---|---|
| A1 Resume Understanding | OpenAI | gpt-4o-mini | 4000 |
| A2 JD Intelligence | OpenAI | gpt-4o-mini | 4000 |
| A3 Gap Analyzer | OpenAI | gpt-4o-mini | 4000 |
| A4 Rewriter | Anthropic | claude-haiku-4-5-20251001 | 6000 |
| A5 Recruiter Sim | Anthropic | claude-haiku-4-5-20251001 | 4000 |
| Orchestrator | OpenAI | gpt-4o-mini | 4000 |

Never hardcode model strings outside agent `__init__`. Never swap providers.
OPENAI_API_KEY → A1–A4 + Orchestrator. ANTHROPIC_API_KEY → A5 only. Both from .env only.

## Folder Structure
```
resume_platform/
├── main.py            # CLI (evaluate, close-gaps, simulate, history, agent)
├── orchestrator.py    # sequences agents, ThreadPoolExecutor parallelism
├── parser.py          # PDF/DOCX/TXT → clean text
├── gap_session.py     # interactive diff + .docx export
├── renderer.py        # rich terminal rendering
├── schemas/           # Pydantic models (agent1–5_schema.py, common.py)
├── agents/            # base_agent.py + A1–A5
├── engine/            # ats_scorer.py (NO LLM), percentile.py (NO LLM)
├── memory/            # session_store.py, style_extractor.py
└── data/benchmarks.json
```

## Schemas (critical shapes)

**common.py enums:** `Seniority` (junior/mid/senior/staff) | `CompanyType` (faang/product-unicorn/funded-startup/enterprise/service-based/unknown) | `RewriteStyle` (balanced/aggressive/top_1_percent)

**A1 out:** experience_years, seniority, tech_stack[], domains[], has_metrics, has_summary, sections_present[], resume_sections{}

**A2 out:** role_title, must_have_skills[], nice_to_have_skills[], hidden_signals[], semantic_skill_map{}, seniority_expected, company_type

**A3 out:** jd_match_score(0-100), gaps[]{section, missing_keywords[], rewrite_hint}, missing_keywords[], priority_fixes[]

**A4 out:** rewrites{section: {balanced, aggressive, top_1_percent}}

**A5 out:** personas[10]{persona, first_impression, noticed[], ignored[], rejection_reason, shortlist_decision}, shortlist_rate(0-1), consensus_strengths[], consensus_weaknesses[], most_critical_fix

## Agent contract
```python
class Agent(BaseAgent):
    def run(self, input_dict: dict) -> dict:
        inp = InputModel(**input_dict)       # validate input
        raw = self._call_llm(SYS, inp.x)
        out = OutputModel(**self._parse_json(raw))  # validate output
        return out.model_dump()
```
- Agents never import each other. Orchestrator is sole caller.
- Raw dicts only at LLM boundary. Use `.model_dump()` between agents.

## Orchestrator order
1. ATS score (deterministic)
2. A1 + A2 parallel (ThreadPoolExecutor, max_workers=2) — if JD provided
3. A3 sequential (needs 1+2)
4. Memory load + fingerprint
5. A4 + A5 parallel (if requested)
6. Percentile (deterministic)
7. Memory update
8. Return combined dict + career_positioning

**Graceful degradation:** A5/A4/memory fail → warn+continue. A1/A2 fail → raise.

## Key rules
- `response_format={"type":"json_object"}` on ALL OpenAI calls
- 1 auto-retry on JSON parse failure
- Style fingerprint: hard cap 200 tokens / 900 chars
- Max 50 runs per user in memory
- No `asyncio` — use ThreadPoolExecutor
- No `print()` in CLI — use `rich.console.Console`
- No LLM in engine/ats_scorer.py or engine/percentile.py
- Functions >40 lines need docstring. Google-style docstrings everywhere.

## Anti-hallucination (A4 rewriter — enforced in prompt)
Never invent: companies, degrees, institutions, years of experience, specific metrics, project names.
Missing metrics → use placeholders: [X%] [N users] [Xms] [₹X Cr ARR]

## ATS scoring (deterministic, 0-100)
keyword_match(25) + formatting(25) + readability(25) + impact_metrics(25)
Composite = ats×0.4 + jd_match×0.6

## Benchmarks (data/benchmarks.json)
junior: avg48 | mid: avg55 | senior: avg63 | staff: avg70

## docx export styling
Name: H1 16pt bold centered | Contact: Normal centered | Section: H2 teal(0,128,128) 13pt bold ALLCAPS | Bullets: ListBullet | Other: Normal

## Memory schema
```json
{"user_id":"","created_at":"","runs":[{"timestamp":"","ats_score":0,"match_score":0,"accepted_sections":[],"rejected_sections":[]}],"style_decisions":{"accepted":[],"rejected":[]}}
```

## Testing gates
```bash
python -c "from engine.ats_scorer import score_resume; from engine.percentile import get_percentile; from agents.base_agent import BaseAgent; from parser import parse_resume; print('OK')"
python -c "from orchestrator import Orchestrator; print('OK')"
python -c "from gap_session import run_gap_session; print('OK')"
# Schema gate:
python -c "from schemas.common import *; from schemas.agent1_schema import *; print('All schemas OK')"
```

## Session fixes applied (Merged Fix Set)
- parser.py: 6-pass _clean_text()
- rewriter.py: COMPANY_HEADER markers, _ensure_experience_markers(), _resolve_sub_text() 4-level fallback
- resume_builder.py: structure-aware build_final_docx(), _write_experience() with markers+heuristic
- orchestrator.py: sectioner removed, resume_sections from A1, progress_cb(6 points), career_positioning in return
- career_positioning.py: get_positioning_statement() — no LLM
- LLM calls per run: 4 (was 5). Latency: ~14-18s (was 18-22s)

**Key invariant:** ALL original resume sections preserved in output docx. Experience: company BOLD, role italic, bullets ListBullet. Unchanged sections: verbatim, never placeholder. Placeholder guard: [.*] pattern never written.

---

# Frontend — Claude Code Agreement

## Stack
React 18 + TypeScript + Vite | Tailwind CSS | Zustand | React Query | Axios | Recharts
Backend: FastAPI http://localhost:8000 (CORS configured)

## Source of truth
frontend/API_CONTRACT.md | frontend/src/types/index.ts | frontend/src/mocks/mockData.ts | frontend/src/store/useResumeStore.ts

## Non-negotiable rules
1. **Mock-first**: every component renders with mockData before touching real API
2. Only `useMockData.ts` hook switches mock/real — never direct Axios in components
3. All data reads from Zustand store — no prop drilling
4. `VITE_USE_MOCK=true` in .env.development during all dev
5. No `any` TypeScript types. No TODO comments. No inline styles (except dynamic %).
6. All 5 tabs rendered in DOM simultaneously, toggled via CSS `display:none`
7. **No global h1/h2 font-size rules in index.css** (breaks Tailwind arbitrary values)
8. `<h1>` tags → use `<div>` to avoid global CSS overrides

## Self-verification (run IN ORDER before declaring done)
```
V1: cd frontend && npx tsc --noEmit          → 0 errors required
V2: cd frontend && npm run build             → "built in Xs" required
V3: Mock render — no console errors, all props typed, optional chaining
V4: Wireframe pixel-check — colors, layout, data fields
V5: Store wiring — reads store only, loading/error states handled
V6: Tab isolation — renders with null other-tab state
```

## Colours
```
Primary:     #6c47ff   Card bg:  #f7f5ff
Success:     #16a34a   Border:   #c4b5fd
Error:       #dc2626   Dark bg:  #1a1a2e
Warning:     #d97706   Score num: #6c47ff 42px 800w
Tab active:  border-b-2 border-[#6c47ff]
```

## API endpoints
```
POST /api/analyze     → {job_id}
GET  /api/stream/{id} → SSE {step,label,pct,status,error?}
GET  /api/result/{id} → AnalysisResult
POST /api/gap-close   → {docx_id, updated_result}
GET  /api/download/{id} → binary docx
GET  /api/history     → {runs:[]}
```

## Key types (frontend/src/types/index.ts)
```typescript
AnalysisResult { ats, resume, gap, rewrites, sim, percentile, positioning }
ATSResult { score, breakdown:{keyword_match,formatting,readability,impact_metrics}, ats_issues[] }
SimResult { personas[10], shortlist_rate, consensus_strengths[], consensus_weaknesses[], most_critical_fix }
PersonaVerdict { persona, first_impression, noticed[], ignored[], rejection_reason, shortlist_decision }
RewriteStyle = 'balanced'|'aggressive'|'top_1_percent'
TabId = 'overview'|'fixes'|'recruiter'|'gap'|'progress'
```

## File structure (current state)
```
frontend/src/
  App.tsx                         # 3 views: Upload/Progress/Dashboard
  types/index.ts                  # all interfaces
  mocks/mockData.ts               # MOCK_ANALYSIS_RESULT (ats=68,jd=73,10 personas,shortlist=0.6)
  store/useResumeStore.ts         # jobId,analysisResult,selectedStyle,activeTab,isAnalyzing
  hooks/useMockData.ts            # IS_MOCK + useAnalysisResult + useHistory
  hooks/useSSE.ts                 # EventSource lifecycle + mock simulation
  api/client.ts                   # Axios instance + typed functions
  components/layout/TopBar.tsx    ✅
  components/layout/TabNav.tsx    ✅
  components/upload/UploadZone.tsx       ✅ (h1→div fix applied)
  components/upload/AnalysisProgress.tsx ✅
  components/upload/VerdictBanner.tsx    ✅
  components/upload/CareerPositioning.tsx ✅
  # Days 2-7 tabs: placeholder text only
```

## Day build order
- ✅ Day 0: Foundation files
- ✅ Day 1: Upload shell + App shell + SSE + TopBar + TabNav (index.css bug fixed)
- ⬜ Day 2: Overview (ScoreCards, RecruiterScan, PriorityActions, ATSBars, VerdictBanner, CareerPositioning)
- ⬜ Day 3: Actionable Fixes (BeforeAfterCard, 3-style toggle, accept/keep)
- ⬜ Day 4: Recruiter View (10 CompanyCards, StatCards, StrategicInsight)
- ⬜ Day 5: Gap Closer (HeroScore, SkillsGrid, ExpRequirements, ActionPlan)
- ⬜ Day 6: Progress (ScoreChart/Recharts, MetricCards, Timeline, download wiring)

## Day prompt wrapper
```
[Read CLAUDE.md] [Read frontend/src/types/index.ts] [Read frontend/src/mocks/mockData.ts]
Day N: [task]
Deliver: 1)files read 2)write files 3)run V1-V6 4)fix errors immediately 5)final report
```

## index.css must NOT contain
h1/h2 font-size rules | #root text-align:center | :root font:18px | width constraints on #root
Audit: `cat frontend/src/index.css | grep -E "h1|h2|text-align.*center|56px|1126px"` → no matches

## Wireframe UI Validation Checklist

After writing or modifying ANY component, Claude Code must run this
self-check before reporting done:

### Upload Screen (UploadZone + TopBar)
- [ ] TopBar: horizontal flex row, brand LEFT, button RIGHT, NOT stacked
- [ ] Brand icon: 38×38 purple (#6c47ff) square, not invisible
- [ ] Hero title: 28px (use div not h1 to avoid global CSS override)
- [ ] Upload box: dashed border (#c4b5fd), NOT raw browser file input
- [ ] file input has className="hidden"
- [ ] Browse Files button: inside upload box, purple
- [ ] Demo mode badge: pill shape, below upload box, only if IS_MOCK
- [ ] JD textarea + Analyze button: flex row (not stacked)

### Global CSS rules that MUST NOT exist in index.css
- NO h1 { font-size: ... } (overrides Tailwind text-[Xpx] classes)
- NO h2 { font-size: ... }
- NO #root { text-align: center } (breaks TopBar flex alignment)
- NO :root { font: 18px ... } (overrides body font)
- NO width constraint on #root (breaks full-width layout)

### Before every Day prompt, verify
  cat frontend/src/index.css | grep -E "h1|h2|text-align.*center|56px|1126px"
  Expected: no matches