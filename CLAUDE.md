# RIP V2 — CLAUDE.md

## Identity
**Resume Intelligence Platform V2** | Zenteiq Aitech | Bengaluru
Target: Indian SWEs 22–40, fresher–staff level
Production: `https://resumeevaluatortool-production.up.railway.app`

---

## Claude Code Workflow (READ THIS FIRST)

### Model Strategy — Plan with Sonnet, Code with Haiku

**Every non-trivial task must follow this two-phase protocol:**

| Phase | Model | Action |
|---|---|---|
| 1. Plan | `claude-sonnet-4-6` (default) | Understand the task, read relevant files, reason about the approach, write a plan |
| 2. Code | Switch to `claude-haiku-4-5` | Execute the plan — write/edit files, run commands, verify |

**How to apply:**
- Before writing a single line of code, Sonnet reads the relevant files and produces a written plan (files to touch, approach, edge cases, risks).
- Once the plan is clear, switch model to Haiku to execute. Haiku follows the plan exactly and does not re-derive architecture decisions.
- If Haiku hits a blocker that requires architectural reasoning, pause and re-engage Sonnet.
- This saves ~60–70% of token cost on implementation tasks.

**When Sonnet stays active (no switch):**
- Debugging a subtle runtime bug
- Reviewing a PR or analyzing a diff
- Writing the plan document itself
- Any task where the implementation IS the reasoning (e.g., designing a new schema)

### Session Start Protocol

At the start of every session, before doing any work:

```bash
# 1. Check current state
git status && git log --oneline -5

# 2. Check session timeline for recent context (if needed)
cat Handoff/SESSION_TIMELINE.md | head -50

# 3. Check what handoff files exist
ls Handoff/ | tail -5

# 4. Read the most recent handoff doc (if relevant)
cat Handoff/<most-recent>.md
```

Then re-read any files explicitly named in the handoff before proceeding.

### Task Execution Rules

- **Read before edit** — always read a file before editing it.
- **Plan before implement** — for any task touching >2 files, write the plan as a bullet list before touching code.
- **Verify after every change** — run the relevant test or build check immediately after each file change, not at the end.
- **Never assume file contents** — `grep` or `Read` to confirm, never guess function signatures or imports.
- **One concern per commit** — don't bundle unrelated changes.

---

## Dev Setup

### Prerequisites
- Python 3.11+ (`runtime.txt` pins `python-3.11.9`)
- Node.js 18+
- `.env` file at repo root (see schema below)

### Start Backend
```bash
# From repo root
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
Backend runs at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Start Frontend
```bash
cd frontend
npm install       # first time only
npm run dev
```
Frontend runs at `http://localhost:5173`.

### Environment Variables

**Repo-root `.env` (backend):**
```
OPENAI_API_KEY=...                    # Required: A1, A2, A3, A4
ANTHROPIC_API_KEY=...                 # Required: A5, A5b, A6, JDFetcher
SERPER_API_KEY=...                    # Required: JD fetcher (Serper search API)
SUPABASE_URL=https://your.supabase.co # Required: DB + auth
SUPABASE_JWT_SECRET=...               # Required: JWT verification (HS256 fallback)
SUPABASE_SERVICE_ROLE_KEY=...         # Required: server-side DB writes

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
FREE_TIER_MONTHLY_LIMIT=3             # Default: 3 analyses/user/month
STAGE_CACHE_TTL_SECONDS=3600          # 0 = disabled, 300 = fast dev cycle
```

**`frontend/.env.development` (Vite — never commit real keys):**
```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your.supabase.co
VITE_SUPABASE_ANON_KEY=...
VITE_USE_MOCK=true                    # MUST be true during dev; false in prod build
```

**`frontend/.env.production`:**
```
VITE_API_URL=https://resumeevaluatortool-production.up.railway.app
VITE_USE_MOCK=false                   # CRITICAL — never ship with mock=true
```

---

## Architecture Overview

Full-stack web app:
- **Backend**: FastAPI (`backend/main.py`) — Python 3.11, Pydantic v2, port 8000
- **Frontend**: React 18 + TypeScript + Vite — port 5173
- **Auth**: Supabase JWT (ES256 + JWKS) — `backend/auth.py` + `frontend/src/lib/supabase.ts`
- **DB**: Supabase Postgres — `backend/db.py` (service role key, bypasses RLS)
- **Orchestration**: `orchestrator.py` (repo root) — `ThreadPoolExecutor`, no `asyncio`
- **Resume parsing**: `parser.py` (repo root) — PDF/DOCX/TXT → clean text
- **Deployment**: Railway (`railway.toml`) — `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

> `resume_platform/` at repo root is a **legacy CLI prototype** — not the main app. Do not modify it.

---

## Backend Folder Structure

```
backend/
├── main.py                   # FastAPI app; all route includes + inline endpoint defs
├── agents/
│   ├── base_agent.py         # BaseAgent._call_llm, _parse_json, 1 auto-retry
│   ├── resume_understanding.py  # A1 — gpt-4o-mini
│   ├── jd_intelligence.py    # A2 — gpt-4.1-mini
│   ├── gap_analyzer.py       # A3 — gpt-4.1
│   ├── rewriter.py           # A4 — gpt-4.1-mini (legacy; surgical patching now primary)
│   ├── recruiter_sim.py      # A5 — claude-haiku-4-5-20251001
│   ├── interview_agent.py    # A6 — claude-sonnet-4.6
│   ├── coaching_agent.py     # A5b — claude-haiku-4-5-20251001 (per-gap Q&A)
│   ├── jd_fetcher.py         # Serper search + Haiku extraction
│   ├── ats_classifier.py
│   └── sectioner_agent.py
├── api/
│   ├── company_readiness.py  # Router prefix: /api/company-readiness
│   ├── score_journey.py      # Router prefix: /api/score-journey
│   └── routes/
│       └── coaching.py       # Router prefix: /api/coaching
├── engine/
│   ├── company_readiness.py  # Deterministic readiness scoring (no LLM)
│   ├── fix_plan_builder.py   # Builds FixPlanItem[] from A3 output
│   ├── milestone_detector.py # Tier/percentile milestone detection
│   └── patch_engine.py       # Surgical patch apply/rollback
├── models/
│   ├── interview_session.py
│   ├── readiness.py
│   └── score_journey.py
├── schemas/
│   ├── agent1_schema.py … agent5_schema.py  # Pydantic I/O per agent
│   ├── common.py             # Seniority, CompanyType, RewriteStyle enums
│   ├── interview_schema.py
│   ├── career_memory.py
│   └── jd_fetch_schema.py
├── persistence.py            # save_analysis → Supabase (uploads table)
├── interview_persistence.py  # interview_sessions table
├── corpus_persistence.py     # corpus_runs, patch_decisions tables
├── coaching_persistence.py   # coaching_answers table
├── auth.py                   # get_current_user_id via Supabase JWKS
├── db.py                     # Supabase client (service role — bypasses RLS)
├── feedback.py               # Router: /api/feedback
├── limit_checker.py          # Monthly upload cap (FREE_TIER_MONTHLY_LIMIT)
├── role_fit.py               # RoleFit band: qualified/stretch/underqualified
├── email_service.py
├── few_shot_prompts.py
├── surgical_debug.py
├── seniority_from_titles.py
├── services/
│   └── serper_client.py      # Serper Google Search API wrapper
├── constants/
│   └── jd_fetch_data.py
└── utils/
    └── question_ledger.py    # Per-resume interview question deduplication

# Root-level shared modules (imported by both backend and orchestrator)
engine/
├── ats_scorer.py             # Deterministic ATS — NO LLM
├── percentile.py             # Percentile lookup — NO LLM
├── career_positioning.py     # Tier/CTC bands — NO LLM
├── resume_builder.py         # build_final_docx (python-docx)
├── patch_engine.py           # Root-level patch engine (shared)
├── ats_semantic_booster.py
├── surgical_export.py
└── llm_trace.py
orchestrator.py               # Sequences A1–A5, fix_plan, percentile, persistence
parser.py                     # PDF/DOCX/TXT → clean text (pdfplumber, python-docx)
validator/
└── rewriter_validator.py
```

---

## API Endpoints

```
# Core
GET  /health
GET  /api/usage-limit
POST /api/analyze                              → {job_id}
GET  /api/stream/{job_id}                      → SSE: {step, label, pct, status, error?, partial_result?}
GET  /api/result/{job_id}                      → AnalysisResult
POST /api/gap-close                            → {docx_id}
GET  /api/download/{job_id}                    → binary .docx
POST /api/fetch-jd                             → FetchJDResponse
POST /api/reset-limit
GET  /api/session/{session_id}/rescore
GET  /api/session/{session_id}/download

# Patches
POST /api/patches/apply                        → PatchApplyResult[]
POST /api/patches/rollback

# Interview (A6)
POST /api/interview/questions                  → InterviewQuestionsResponse
POST /api/interview/session/start              → StartInterviewResponse
POST /api/interview/session/{id}/answer        → SubmitAnswerResponse
POST /api/interview/session/{id}/answer/stream → SSE feedback stream
POST /api/interview/session/{id}/summary       → SessionSummary
POST /api/interview/session/{id}/model-answer/{q_id} → ModelAnswer
GET  /api/interview/sessions                   → PastSessionSummary[]
POST /api/interview/evaluate
POST /api/interview/follow-up

# Coaching (backend/api/routes/coaching.py)
POST /api/coaching/answer                      → CoachingAnswer (generate bullet)
GET  /api/coaching/answers/{session_id}        → CoachingAnswer[]
POST /api/coaching/apply                       → apply bullet to docx

# Score Journey (backend/api/score_journey.py)
GET  /api/score-journey                        → ScoreJourneyResult

# Company Readiness (backend/api/company_readiness.py)
GET  /api/company-readiness                    → CompanyReadinessResult

# Feedback (backend/feedback.py)
GET  /api/feedback/state                       → FeedbackState
POST /api/feedback/submit                      → 204
```

Source of truth for request/response shapes: `frontend/src/types/index.ts` + `frontend/API_CONTRACT.md`.

---

## Frontend Folder Structure

```
frontend/src/
├── App.tsx                          # Root shell: Supabase auth, view switching (Landing/Upload/Progress/Dashboard)
├── EvaluationDashboard.tsx          # Overview tab
├── tokens.ts                        # Design tokens (T.primary, T.success, etc.)
├── main.tsx
├── index.css                        # Minimal global CSS — see guard rules below
├── types/index.ts                   # ← SOURCE OF TRUTH for all TS interfaces
├── store/
│   ├── useResumeStore.ts            # Main Zustand store
│   └── authStore.ts                 # Supabase session + UserProfile
├── lib/
│   └── supabase.ts                  # Supabase browser client
├── api/
│   ├── client.ts                    # Axios instance (VITE_API_URL base)
│   ├── analyze.ts
│   ├── interview.ts
│   ├── companyReadiness.ts
│   └── scoreJourney.ts
├── hooks/
│   ├── useMockData.ts               # IS_MOCK flag; useAnalysisResult wraps mock/real
│   ├── useSSE.ts                    # EventSource lifecycle + mock simulation
│   ├── useFeedbackOrchestrator.ts
│   ├── useFeedbackSubmit.ts
│   ├── useProgressStore.ts
│   ├── useRescore.ts
│   ├── useUsageLimits.ts
│   ├── useUserHistory.ts
│   └── useWindowSize.ts
├── mocks/
│   ├── mockData.ts                  # MOCK_ANALYSIS_RESULT
│   ├── mockInterviewData.ts
│   ├── mockReadinessData.ts
│   └── mockScoreJourneyData.ts
├── components/
│   ├── layout/TopBar.tsx, TabNav.tsx
│   ├── upload/
│   │   ├── UploadZone.tsx           # Use <div> not <h1>
│   │   ├── AnalysisProgress.tsx
│   │   ├── VerdictBanner.tsx
│   │   └── CareerPositioning.tsx
│   ├── auth/
│   │   ├── AuthGateScreen.tsx, AuthModal.tsx, RequireAuth.tsx, UpgradeModal.tsx
│   ├── cards/
│   │   ├── EvidenceCoachingCard.tsx
│   │   ├── StructuralPatchCard.tsx
│   │   ├── SurfacePatchCard.tsx
│   │   └── cardTypes.ts
│   ├── CompanyReadiness/            # CompanyReadinessCard, CompanySelector, CTCImplicationBlock,
│   │                                #   DimensionBadge, DimensionCard, ReadinessBreakdown,
│   │                                #   ReadinessMeter, ReadinessPaywallModal
│   ├── ScoreJourney/               # ScoreJourneyTab, TimelineChart, SessionCard,
│   │                                #   MilestoneBanner, ProgressSummary, WhatChangedPanel
│   ├── feedback/                   # FeedbackPanel, FeaturePulseCard, PMFModal,
│   │                                #   PMFFollowUpCard, ReengagementBanner
│   ├── ActionableFixes.tsx          # Tab: fixes
│   ├── GapCloser.tsx                # Tab: gap
│   ├── MockInterview.tsx            # Tab: mock_interview
│   ├── RecruiterSimulation.tsx      # Tab: recruiter
│   ├── ProgressTracking.tsx         # Tab: progress
│   ├── LandingPage.tsx, ResumeUpload.tsx, ModeSelector.tsx
│   ├── CareerPathPanel.tsx, CareerRecordPanel.tsx, QualifiedRolesPanel.tsx
│   ├── RoleFitBanner.tsx, ModelAnswerCard.tsx, FixValidation.tsx
│   ├── DataSourceNotice.tsx, UploadReturnBanner.tsx, ErrorBoundary.tsx, Footer.tsx
├── engine/
│   └── atsScorer.ts                 # Client-side live ATS rescoring after patches
├── utils/
│   ├── actionableFixes.ts, analysisFallback.ts, coachingQuestions.ts
│   ├── coachingSession.ts, composeResumeText.ts, fixesCardLogic.ts
│   ├── fixesPipeline.ts, fixPlanAdapter.ts, hasJobDescription.ts
│   ├── modeScores.ts, overviewFixes.ts, pageLayout.ts
│   ├── progressStorage.ts, roleFitEvidence.ts
├── constants/
│   ├── interviewDimensions.ts
│   └── jdFetchData.ts
└── pages/
    └── PipelineInspectorPage.tsx    # Dev-only at /debug/pipeline
```

---

## Tab System (7 tabs)

```typescript
type TabId = 'overview' | 'fixes' | 'recruiter' | 'gap' | 'progress' | 'mock_interview' | 'score_journey'
```

| TabId | Component | What it shows |
|---|---|---|
| overview | EvaluationDashboard.tsx | ATS scores, recruiter scan, positioning, company readiness |
| fixes | ActionableFixes.tsx | Surgical/surface/evidence patch cards |
| recruiter | RecruiterSimulation.tsx | 10 persona verdicts (A5) |
| gap | GapCloser.tsx | Gap close + coaching Q&A (A5b) |
| progress | ProgressTracking.tsx | Score history + career record |
| mock_interview | MockInterview.tsx | A6 interview session |
| score_journey | ScoreJourney/ScoreJourneyTab.tsx | Multi-run timeline + milestones |

All 7 tabs rendered in DOM simultaneously. Toggled via CSS `display:none`. Never unmount tabs.

---

## Key Types (frontend/src/types/index.ts)

```typescript
// Top-level result
AnalysisResult {
  job_id, session_id, run_id, resume_id, jd_id, api_version,
  ats: ATSResult, resume: ResumeUnderstanding, gap: GapResult|null,
  rewrites: Record<string,SectionRewrite>|null, sim: SimResult|null,
  percentile: PercentileResult|null, positioning: PositioningResult|null,
  patches: ResumePatch[], validation: ValidationSummary|null,
  jd_intelligence: JDIntelligence|null, role_fit: RoleFit|null,
  fix_plan: FixPlanItem[], company_readiness: CompanyReadinessResult|null
}

// Critical discriminated unions
GapType = "surface" | "structural" | "evidence"
PatchOp = "replace_text" | "insert_keyword" | "shorten_bullet" | "reorder_bullets" | "add_metric" | "add_bullet"
PatchStatus = "pending" | "applied" | "rejected" | "rolled_back"
PatchRisk = "safe" | "needs_confirmation"
FitnessBand = "qualified" | "stretch" | "underqualified"
TabId = 'overview'|'fixes'|'recruiter'|'gap'|'progress'|'mock_interview'|'score_journey'
RewriteStyle = "balanced" | "aggressive" | "top_1_percent"
QuestionMode = "behavioral" | "scenario" | "mixed"
SignalStrength = "weak" | "developing" | "strong"

// Key shapes
FixPlanItem { fix_id, kind, section, entry_id, patch_id, before_text, after_text,
              requires_user_input, gap_type, risk, auto_apply, status }
ResumePatch  { patch_id, op, original_text, replacement_text, risk, status, score_delta }
SectionGap   { section, gap_type, sub_changes[], coaching_question, auto_apply }
RoleFit      { fitness: FitnessBand, score, experience_gap, recommended_roles[] }
```

---

## Zustand Store (useResumeStore.ts)

Manages: `analysisResult`, `interviewSession`, `feedbackState`, `companyReadiness` (via `fetchCompanyReadiness`), `scoreJourney` (via `fetchScoreJourney`), `activeTab`, `isAnalyzing`, `isFullAnalysisReady`, `userId`, `sectionOverrides`, `acceptedSections`, `baselineAts`, `docxId`, `analysisJdText`, `applyAnywayAccepted`.

Auth state lives in `authStore.ts` (Supabase session + UserProfile). Never merge auth into the resume store.

---

## Frontend Rules (Non-Negotiable)

1. **Mock-first** — every component renders with mockData before real API. Add to the relevant `mocks/*.ts` first.
2. Only `useMockData.ts` switches mock/real — never raw Axios in components.
3. All data reads from Zustand store — no prop drilling, no local fetch in components.
4. `VITE_USE_MOCK=true` in `.env.development`. `VITE_USE_MOCK=false` in prod.
5. No `any` TypeScript types. No TODO comments. No inline styles (except dynamic `%` values).
6. `<h1>` tags → use `<div>` to avoid global CSS overrides.
7. All 7 tabs rendered simultaneously, toggled by `display:none` — never conditionally mount/unmount.

### Self-Verification (run IN ORDER before declaring done)
```bash
V1: cd frontend && npx tsc --noEmit          # 0 errors required
V2: cd frontend && npm run build             # "built in Xs" required
V3: Mock render check — no console errors, all props typed
V4: Layout check — colours, spacing, data fields match design
V5: Store wiring — reads from store only, loading/error states handled
V6: Tab isolation — renders correctly with null sibling-tab state
```

---

## Colours

```
Primary:      #6c47ff    Card bg:    #f7f5ff
Success:      #16a34a    Border:     #c4b5fd
Error:        #dc2626    Dark bg:    #1a1a2e
Warning:      #d97706    Score num:  #6c47ff, 42px, font-weight 800
Tab active:   border-b-2 border-[#6c47ff]
```

---

## What NOT To Do (Consolidated)

### Backend
- No `asyncio` anywhere — use `ThreadPoolExecutor` for concurrency.
- No `print()` — use `logging.getLogger(__name__)`.
- No LLM calls in `engine/ats_scorer.py`, `engine/percentile.py`, `engine/career_positioning.py`.
- Agents never import each other — Orchestrator is the sole caller.
- Never hardcode model strings outside `__init__` / `super().__init__`.
- Never hardcode API keys — `.env` only.
- A4 rewriter must never invent: companies, degrees, institutions, years, metrics, project names. Missing metrics → placeholders: `[X%]` `[N users]` `[Xms]` `[₹X Cr ARR]`.

### Frontend
- No `any` types, no TODO comments, no prop drilling.
- No direct Axios calls in components — always via hooks/store actions.
- No `display:none` removal or tab unmounting.
- No `h1`/`h2` font-size rules in `index.css`.
- Never ship with `VITE_USE_MOCK=true`.

---

## ATS Scoring (Deterministic, No LLM)

```
keyword_match(25) + formatting(25) + readability(25) + impact_metrics(25) = 100
Composite = ats_score × 0.4 + jd_match_score × 0.6
```

Benchmarks: junior avg 48 | mid avg 55 | senior avg 63 | staff avg 70

---

## Testing

### Backend
```bash
# Unit tests (from repo root)
pytest backend/tests/ -v

# Single test file
pytest backend/tests/test_company_readiness.py -v

# Integration tests (requires real API keys)
pytest backend/tests/integration/ -v
```

### Frontend
```bash
cd frontend
npx vitest run                         # unit tests (fixesCardLogic, fixesPipeline)
npx tsc --noEmit                       # type check
npm run build                          # production build check
```

### Smoke test
```bash
python smoke_test.py                   # end-to-end: upload → analyze → result
```

---

## Deployment

- **Platform**: Railway
- **Start command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Runtime**: Python 3.11.9 (`runtime.txt`)
- **Restart policy**: ON_FAILURE, max 5 retries (`railway.toml`)
- **Prod URL**: `https://resumeevaluatortool-production.up.railway.app`
- All env vars injected via Railway environment (same names as `.env` schema above)
- Frontend is a separate static deploy (not Railway) — `VITE_API_URL` points to Railway URL

---

## Commit & Branch Conventions

```
Branch naming:
  feat/<slug>       # new feature
  fix/<slug>        # bug fix
  refactor/<slug>   # no behaviour change
  chore/<slug>      # tooling, deps, config

Commit format (imperative, 50 char subject):
  feat: add score journey timeline chart
  fix: coaching agent retry on empty response
  refactor: extract fix_plan_builder from orchestrator

Rules:
- One concern per commit — no bundling unrelated changes
- Never commit directly to main without review
- Run V1+V2 (tsc + build) before every frontend commit
- Run pytest before every backend commit
```

---

## Handoff Log Protocol

After completing any **major piece of work**, create a markdown file in `Handoff/`:

### Naming
```
Handoff/YYYY-MM-DD_<short-slug>.md
```

### Template
```markdown
# <Title>
**Date:** YYYY-MM-DD
**Files changed:** path — one-line reason (repeat per file)

## What was built / changed
2–5 bullet summary of what was delivered.

## Why
The problem this solved.

## Key decisions
Non-obvious choices, trade-offs, constraints.

## How to verify
Commands or steps to confirm it works.

## Known gaps / follow-ups
Deferred work specific to this deliverable.
```

> **Scope rule:** Handoff docs describe what was **completed** — not current state or what the next session should do. Those live in `Handoff/SESSION_TIMELINE.md`.

### When to write
- New API endpoint or router
- New agent or model change
- New tab or major component
- Schema/type changes across multiple files
- Bug fix requiring non-obvious root-cause work
- Any session where >5 files were modified

### When NOT to write
- Typo / copy fixes
- Single-file style tweaks
- CLAUDE.md-only updates

---

## index.css Guard

Must NOT contain: `h1/h2 font-size` | `#root text-align:center` | `:root font:18px` | width constraints on `#root`

```bash
grep -E "h1|h2|text-align.*center|56px|1126px" frontend/src/index.css
# Expected: no output
```
