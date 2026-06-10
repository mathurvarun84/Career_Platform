# Resume Intelligence Platform V2

Resume Intelligence Platform V2 (RIP V2) is an AI-assisted resume evaluation and rewriting platform for software engineers in India (fresher through staff level). It parses uploaded resumes, scores ATS readiness, compares the resume against an optional job description, identifies gaps, generates rewrite suggestions and surgical patches, simulates recruiter reactions, and exports an improved Word document.

For a full system design walkthrough, see **[Architecture.md](Architecture.md)**.

## What It Does

- **Parse** PDF, DOCX, and TXT resumes into clean text and structured sections.
- **Score** resumes with a deterministic ATS engine (keyword match, formatting, readability, impact metrics).
- **Analyze** with a multi-agent LLM pipeline: resume understanding, JD intelligence, gap analysis, rewriting, and optional recruiter simulation.
- **Fix** via a deterministic **FixPlan** — one actionable item per gap, with pre-resolved patch IDs and before/after text for the Fixes tab.
- **Coach** evidence gaps through grounded bullet generation from user answers.
- **Benchmark** with percentile ranking and career-positioning engines (no LLM).
- **Interview** via a separate mock-interview flow (Agent 6) with evaluator-optimizer feedback.
- **Export** styled DOCX with accepted rewrites or surgically applied patches.

## Architecture at a Glance

```text
React frontend (Vite + Zustand)
        │
        ▼
FastAPI backend (auth, SSE, job cache, Supabase persistence)
        │
        ▼
Orchestrator ──► AI Agents A1–A5 (+ A6 for interviews)
        │
        ▼
Deterministic engine (ATS, percentile, role fit, patches, FixPlan, DOCX)
```

Analysis results use **`api_version: 2`**, which includes a `fix_plan[]` array. Each `FixPlanItem` has a `kind` (`coaching`, `surgical_patch`, `surface_keyword`, `rewrite_block`, or `info_only`) so the frontend can render the correct card without re-deriving patch matches client-side.

## Project Structure

```text
.
├── backend/
│   ├── agents/          # LLM agents A1–A6, JD fetcher, coaching, sectioner
│   ├── api/routes/      # Coaching and other route modules
│   ├── engine/          # ATS, patches, FixPlan builder, DOCX export
│   ├── schemas/         # Pydantic contracts (agents, FixKind, ResumePatch)
│   ├── main.py          # FastAPI app entry point
│   └── auth.py          # Supabase JWT verification
├── frontend/            # React/Vite dashboard (5 tabs + mock interview)
├── orchestrator.py      # Pipeline coordinator (parallel agents, caching, FixPlan)
├── parser.py            # Resume file parsing
├── gap_session.py       # CLI interactive gap-close workflow
├── engine/              # Legacy/shared deterministic modules (ATS, percentile)
├── memory/              # Per-user JSON session memory
├── validator/           # Rewriter and experience audit validators
├── data/                # Percentile benchmarks
├── tests/               # Pipeline, parser, FixPlan, and compliance tests
├── Architecture.md      # Full architecture reference
└── CLAUDE.md            # Agent model assignments and dev conventions
```

## AI Agents and Models (June 2026)

| Agent | Role | Provider | Model |
|-------|------|----------|-------|
| A1 | Resume Understanding | OpenAI | gpt-4o-mini |
| A2 | JD Intelligence | OpenAI | gpt-4.1-mini |
| A3 | Gap Analyzer | OpenAI | gpt-4.1 |
| A4 | Rewriter | OpenAI | gpt-4.1-mini |
| A5 | Recruiter Simulator | Anthropic | claude-haiku-4.5 |
| A6 | Mock Interview | Anthropic | claude-sonnet-4.6 |

Estimated cost per full analysis: ~$0.07. Mock interview sessions: ~$0.06 each.

## Requirements

- Python 3.11+
- Node.js and npm (frontend)
- OpenAI API key (A1–A4, orchestrator)
- Anthropic API key (A5, A6, coaching, JD fetcher rescue paths)
- Supabase project (auth, history, usage limits) for production web use
- Optional: Serper API key for automatic JD fetching from URLs

Some PDF/OCR flows may require Tesseract and Poppler locally.

## Environment Variables

Copy the example file and fill in secrets (never commit `.env`):

```bash
cp .env.example .env
```

Key variables:

```env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
CORS_ALLOWED_ORIGINS=http://localhost:5173
FREE_TIER_MONTHLY_LIMIT=3
STAGE_CACHE_TTL_SECONDS=3600
```

The frontend uses its own `.env.development` (see `frontend/.env.example`) with `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_USE_MOCK=true` during UI development.

## Python Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

## Run the FastAPI Backend

```bash
uvicorn backend.main:app --reload
```

Core endpoints: `POST /api/analyze`, `GET /api/stream/{job_id}`, `GET /api/result/{job_id}`, patch apply/rollback, coaching, DOCX download, and mock-interview routes under `/api/interview/*`.

## Run the React Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite dev server (default `http://localhost:5173`). With `VITE_USE_MOCK=true`, the UI renders against static mock data without a running backend.

## FixPlan (Single Action Contract)

After gap analysis and patch classification, `FixPlanBuilder` (`backend/engine/fix_plan_builder.py`) emits one `fix_plan` item per priority fix:

- **`fix_id`** — stable key from section + canonical `entry_id` or slugged sub-label
- **`kind`** — deterministic dispatch: coaching beats patch; surface gaps become keyword fixes; otherwise rewrite or info-only
- **`patch_id`** — pre-resolved on the backend (exact `entry_id` match only for canonical IDs)
- **`before_text` / `after_text`** — resolved from patch text or A1 verbatim sub-entries

The frontend adapter (`frontend/src/utils/fixPlanAdapter.ts`) maps `FixPlanItem` → `PriorityFix` for existing card components. Sessions with `api_version < 2` fall back to the legacy `buildActionableFixesList` pipeline.

## Testing

```bash
pytest
```

Notable test modules:

- `tests/test_fix_plan_builder.py` — FixPlan kind dispatch, patch_id contract, dedup
- `tests/test_compliance.py` — agent schema compliance
- `tests/test_patch_engine.py` — surgical patch apply/rollback

Frontend verification:

```bash
cd frontend && npx tsc --noEmit && npm run build
```

## Notes for Contributors

- Keep API keys in `.env` only; commit `.env.example` when adding new keys.
- Agents never call each other — only `orchestrator.py` sequences them.
- Scoring (ATS, percentile, role fit, FixPlan) is deterministic — no LLM in those paths.
- The graphify knowledge graph under `graphify-out/` helps navigate the codebase (`graphify query "..."`).
- API request/response shapes: `frontend/API_CONTRACT.md`. Agent conventions: `CLAUDE.md`.
