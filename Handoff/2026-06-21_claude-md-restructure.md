# CLAUDE.md Full Restructure

**Date:** 2026-06-21
**Files changed:**
- `CLAUDE.md` — complete rewrite to reflect actual project state
- `Handoff/` — new directory created (this file is the first entry)

## What was built / changed
- Replaced outdated `resume_platform/` CLI-based folder map with the actual FastAPI + React structure
- Documented all 7 tabs (`overview`, `fixes`, `recruiter`, `gap`, `progress`, `mock_interview`, `score_journey`)
- Added full backend tree: `backend/api/`, `backend/engine/`, `backend/models/`, `backend/utils/`
- Verified and recorded actual model strings from agent source files (haiku, sonnet-4.6, gpt-4.1, gpt-4.1-mini, gpt-4o-mini)
- Listed all current API endpoints including interview, coaching, score-journey, company-readiness, and feedback routers
- Added Supabase auth references (`backend/auth.py`, `frontend/src/lib/supabase.ts`, `store/authStore.ts`)
- Added Handoff Log Protocol section so all future major work is documented

## Why
CLAUDE.md was describing a prototype CLI that no longer matches the app. Every session started with stale context — wrong folder names, missing tabs, wrong API endpoints.

## Key decisions
- Kept design rules (colours, CSS guards, self-verification steps) unchanged — they're still valid
- Noted `resume_platform/` exists at root but is legacy — not the main app
- Separated A5 (RecruiterSim) and A5b (CoachingAgent) since both use haiku but are distinct agents
- Documented that A6 (Interview) runs via its own session endpoints, not the main analyze flow

## How to test / verify
Open a new Claude Code session and ask "where is the company readiness API defined?" — it should point to `backend/api/company_readiness.py` without searching.

## Known gaps / follow-ups
- `backend/utils/question_ledger.py` internals not yet documented
- `frontend/src/engine/atsScorer.ts` (frontend rescoring) not described in detail
- Deployment config (`railway.toml`, `runtime.txt`) not captured
