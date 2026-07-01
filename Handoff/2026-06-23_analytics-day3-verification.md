# RIP V2 Analytics — Day 3 Verification Report
**Date:** 2026-06-23  
**Deployed to:** Railway (https://resumeevaluatortool-production.up.railway.app)

---

## Code Audit (Phase 2)

**Audit script:** `scripts/analytics_audit.py`  
**Audit script exit code:** 0  
**Total checks:** 59  
**Passed:** 59  
**Failed:** 0 — none  
**Warnings:** 0 — none  

### Audit script adjustments (repo layout, not spec drift)

The Day 3 prompt assumed `backend/orchestrator.py`. In this repo, orchestrator lives at **`orchestrator.py`** (repo root). The audit script was updated to:

1. Read `backend/orchestrator.py` **or** `orchestrator.py`
2. Accept `analysis_failed` in **`backend/main.py`** (worker-thread except in `_analyze_event_stream`, not orchestrator)
3. Include `frontend/src/*.tsx` in event glob (covers `App.tsx` for `second_analysis_run` / `jd_uploaded`)
4. Force UTF-8 stdout on Windows (emoji status markers)

### Drift fixes applied during audit

| File | Fix | Reason |
|---|---|---|
| `backend/analytics.py` | Fall back to `SUPABASE_SERVICE_ROLE_KEY` when `SUPABASE_SERVICE_KEY` unset | Railway `.env` uses `SUPABASE_SERVICE_ROLE_KEY`; events were silently dropped |
| `orchestrator.py` | `role_fit_band` reads `fitness` (with `band` fallback) | Backend `RoleFit` uses `fitness`, not `band` — completed events had null `role_fit_band` |
| `scripts/analytics_audit.py` | Path + encoding fixes above | Audit runnable and accurate for this repo |

No changes to forbidden files (`fix_plan_builder.py`, `gap_analyzer.py`, `GapCloser.tsx`, `useResumeStore.ts` state shape).

### Implementation summary (verified by read + audit)

**Backend**
- `backend/analytics.py` — lazy singleton, bare `except Exception`, session_id defaults to `"unknown"`
- `orchestrator.py` — `analysis_started` after `has_jd`, before ATS; `analysis_completed` after `log_trace_summary()`, before `return final_result`
- `backend/main.py` — `POST /api/analytics` always returns `{"ok": True}`; `X-Session-ID` extracted; `analysis_failed` in stream worker except
- `backend/auth.py` — `get_current_user_optional` returns `AuthenticatedUser | None`

**Frontend**
- `analyticsSession.ts` — `sessionStorage` only
- `analytics.ts` — `useResumeStore.getState()`, fire-and-forget `fetch().catch()`
- `useTabEngagement.ts` — fires on cleanup with `dwell_seconds`, `scrolled_past_fold`, `interaction_count`
- `ActionableFixes.tsx` — `fix_card_opened` / `fix_applied` in `useEffect` + ref guards
- `App.tsx` — `session_start` once on mount; `second_analysis_run` + `jd_uploaded` in `handleBeginAnalysis` (before clearing result)
- `AnalysisProgress.tsx` — `X-Session-ID` header on analyze fetch
- Tab engagement wired: **overview**, **fixes**, **evaluate** (RecruiterSimulation), **progress** — **gap tab not instrumented** (`GapCloser.tsx` excluded per Day 2 DO NOT TOUCH)

---

## SQL Schema (Phase 4)

**Status:** SKIP — requires Supabase SQL editor access (not available in this audit session)

**Action for Varun:** Run in Supabase SQL editor:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'analytics_events'
ORDER BY ordinal_position;
```

**Expected columns:** `id`, `user_id`, `session_id`, `run_id`, `event_name`, `properties`, `ats_score`, `jd_match_score`, `role_fit_band`, `has_jd`, `seniority`, `created_at`

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'analytics_events';
```

**Expected indexes:** `idx_analytics_event_name`, `idx_analytics_user_id`, `idx_analytics_created_at`, `idx_analytics_run_id`

| Field | Result |
|---|---|
| analytics_events table | PENDING — Varun |
| Missing columns | PENDING — Varun |
| Missing indexes | PENDING — Varun |

---

## Build Gate (Phase 5)

| Check | Result |
|---|---|
| `python scripts/analytics_audit.py` | PASS (exit 0) |
| `npx tsc --noEmit` | PASS |
| `npm run build` | PASS |

---

## Manual QA (Phase 6)

**Status:** SKIP — Varun runs in browser + DevTools Network tab

| Step | Expected | Result |
|---|---|---|
| 1 — session_start (first visit) | `is_returning: false` | SKIP |
| 2 — jd_uploaded | `jd_length_chars` > 0 | SKIP |
| 3 — analysis_started + completed | run_id + ats_score | SKIP |
| 4 — tab_engagement (×5) | 5 tabs, dwell ≥ 5s | SKIP — **note: only 4 tabs wired; gap excluded** |
| 5 — fix_card_opened | kind + entry_id | SKIP |
| 6 — fix_applied | patch_id | SKIP |
| 7 — download_triggered | docx_id | SKIP |
| 8 — session_start (returning) | `is_returning: true` | SKIP |
| 9 — second_analysis_run | previous_ats_score | SKIP |
| 10 — POST /api/analytics | `{"ok": true}` | SKIP |

**Quick curl for Step 10:**
```bash
curl -s -X POST https://resumeevaluatortool-production.up.railway.app/api/analytics \
  -H "Content-Type: application/json" \
  -d '{"event_name":"test_event","session_id":"audit-test"}'
```

---

## SQL Queries (Phase 7)

**Status:** SKIP — requires Supabase data from manual QA

| Query | Result |
|---|---|
| Q1 Funnel bleed | SKIP |
| Q2 Tab attention | SKIP |
| Q3 Fix conversion | SKIP |
| Q4 JD attach rate | SKIP |
| Q5 Day-7 return rate | SKIP (expect `new_users_eligible = 0` until users age 7 days) |

---

## Sign-off

| Item | Status |
|---|---|
| Audit script exits 0 | ✅ |
| 12 columns in Supabase | ⏳ Varun |
| 4 indexes in Supabase | ⏳ Varun |
| tsc + build | ✅ |
| 10 manual QA steps | ⏳ Varun |
| 5 SQL queries | ⏳ Varun |

**Analytics feature:** **NEEDS FIXES** (pending Varun sign-off on Phases 4, 6, 7)

**Outstanding issues:**
1. Varun must confirm Supabase schema + indexes (Phase 4)
2. Varun must run manual QA script (Phase 6) — expect **4** `tab_engagement` tabs per session, not 5 (gap tab intentionally excluded)
3. After deploy, confirm Railway has `SUPABASE_SERVICE_ROLE_KEY` (analytics now accepts it as fallback)
4. Re-deploy after Day 3 drift fixes (`analytics.py` env fallback + orchestrator `role_fit_band`)

**Code-side Day 3:** Complete — audit passes, build passes, drift fixes applied.
