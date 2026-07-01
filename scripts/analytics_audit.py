#!/usr/bin/env python3
"""
Analytics implementation audit for RIP V2.
Checks all Day 1 and Day 2 implementations against the spec.
Reports pass/fail for each check. Exit code 1 if any check fails.
"""

import ast
import re
import sys
from pathlib import Path

# Windows consoles may default to cp1252; emoji status markers require UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"
results: list[tuple[str, str, str]] = []  # (check_name, status, detail)


def check(name: str, condition: bool, detail: str = "", warn_only: bool = False):
    status = PASS if condition else (WARN if warn_only else FAIL)
    results.append((name, status, detail))


def read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# ─── BACKEND CHECKS ────────────────────────────────────────────────────────────

analytics_py = read("backend/analytics.py")
orchestrator_py = read("backend/orchestrator.py") or read("orchestrator.py")
main_py = read("backend/main.py")

# analytics.py — structure
check("analytics.py exists", bool(analytics_py), "backend/analytics.py not found")
check("analytics.py: lazy singleton _supabase",
      "_supabase: Client | None = None" in analytics_py or
      "_supabase = None" in analytics_py)
check("analytics.py: _get_client() uses SUPABASE_SERVICE_KEY",
      "SUPABASE_SERVICE_KEY" in analytics_py)
check("analytics.py: track() has bare except",
      "except Exception" in analytics_py)
check("analytics.py: track() never re-raises",
      "raise" not in analytics_py.split("except Exception")[1][:200]
      if "except Exception" in analytics_py else False,
      "Found 're-raise' after except in analytics.py")
check("analytics.py: session_id defaults to 'unknown'",
      '"unknown"' in analytics_py or "'unknown'" in analytics_py)

# orchestrator.py — import and events
check("orchestrator.py: imports analytics.track",
      "from backend.analytics import track" in orchestrator_py)
check("orchestrator.py: analysis_started event",
      '"analysis_started"' in orchestrator_py or "'analysis_started'" in orchestrator_py)
check("orchestrator.py: analysis_completed event",
      '"analysis_completed"' in orchestrator_py or "'analysis_completed'" in orchestrator_py)
check("orchestrator.py: analysis_failed event",
      '"analysis_failed"' in orchestrator_py or "'analysis_failed'" in orchestrator_py or
      '"analysis_failed"' in main_py or "'analysis_failed'" in main_py)
check("orchestrator.py: browser_session_id parameter",
      "browser_session_id" in orchestrator_py)
check("orchestrator.py: analysis_completed before return final_result",
      orchestrator_py.index("analysis_completed") < orchestrator_py.index("return final_result")
      if "analysis_completed" in orchestrator_py and "return final_result" in orchestrator_py else False)

# main.py — endpoint and model
check("main.py: AnalyticsEventRequest model",
      "AnalyticsEventRequest" in main_py)
check("main.py: POST /api/analytics endpoint",
      '"/api/analytics"' in main_py or "'/api/analytics'" in main_py)
check("main.py: analytics endpoint returns ok:true",
      '"ok": True' in main_py or '"ok":True' in main_py)
check("main.py: X-Session-ID header extraction",
      "X-Session-ID" in main_py)
check("main.py: browser_session_id passed to orchestrator",
      "browser_session_id=browser_session_id" in main_py)
check("main.py: get_current_user_optional exists",
      "get_current_user_optional" in main_py or
      "get_current_user_optional" in read("backend/auth.py"))

# ─── FRONTEND CHECKS ───────────────────────────────────────────────────────────

session_ts = read("frontend/src/utils/analyticsSession.ts")
analytics_ts = read("frontend/src/utils/analytics.ts")
tab_hook_ts = read("frontend/src/hooks/useTabEngagement.ts")
fixes_tsx = read("frontend/src/components/ActionableFixes.tsx")
app_tsx = read("frontend/src/App.tsx")

# analyticsSession.ts
check("analyticsSession.ts exists", bool(session_ts))
check("analyticsSession.ts: uses sessionStorage (not localStorage)",
      "sessionStorage" in session_ts and
      session_ts.count("localStorage") == 0,
      "Found localStorage in analyticsSession.ts — must use sessionStorage")
check("analyticsSession.ts: exports getOrCreateSessionId",
      "getOrCreateSessionId" in session_ts)

# analytics.ts
check("analytics.ts exists", bool(analytics_ts))
check("analytics.ts: uses useResumeStore.getState()",
      "useResumeStore.getState()" in analytics_ts)
check("analytics.ts: fire-and-forget fetch (no top-level await on fetch)",
      "await fetch" not in analytics_ts,
      "Found 'await fetch' in analytics.ts — fetch must be fire-and-forget")
check("analytics.ts: .catch() on fetch",
      ".catch(" in analytics_ts)
check("analytics.ts: sends session_id",
      "session_id" in analytics_ts)
check("analytics.ts: sends event_name",
      "event_name" in analytics_ts)
check("analytics.ts: outer try/catch",
      analytics_ts.count("} catch") >= 1 or analytics_ts.count("catch {") >= 1)
check("analytics.ts: function is NOT a hook (no use prefix exported)",
      "export function track" in analytics_ts or "export async function track" in analytics_ts,
      "Function should be named 'track', not 'useTrack'")

# useTabEngagement.ts
check("useTabEngagement.ts exists", bool(tab_hook_ts))
check("useTabEngagement.ts: fires on cleanup (return () =>)",
      "return () =>" in tab_hook_ts)
check("useTabEngagement.ts: tracks dwell_seconds",
      "dwell_seconds" in tab_hook_ts)
check("useTabEngagement.ts: tracks scrolled_past_fold",
      "scrolled_past_fold" in tab_hook_ts)
check("useTabEngagement.ts: tracks interaction_count",
      "interaction_count" in tab_hook_ts)
check("useTabEngagement.ts: listens on tab-content-scroll",
      "tab-content-scroll" in tab_hook_ts)

# ActionableFixes.tsx
check("ActionableFixes.tsx: imports track",
      "from" in fixes_tsx and "analytics" in fixes_tsx and "track" in fixes_tsx)
check("ActionableFixes.tsx: trackedCardOpened ref",
      "trackedCardOpened" in fixes_tsx)
check("ActionableFixes.tsx: trackedFixApplied ref",
      "trackedFixApplied" in fixes_tsx)
check("ActionableFixes.tsx: fix_card_opened event",
      '"fix_card_opened"' in fixes_tsx or "'fix_card_opened'" in fixes_tsx)
check("ActionableFixes.tsx: fix_applied event",
      '"fix_applied"' in fixes_tsx or "'fix_applied'" in fixes_tsx)
check("ActionableFixes.tsx: fix_card_opened inside useEffect (not render)",
      "useEffect" in fixes_tsx.split("fix_card_opened")[0].split("import")[-1]
      if "fix_card_opened" in fixes_tsx else False,
      "fix_card_opened may be firing inside render — must be in useEffect")

# App.tsx
check("App.tsx: session_start event",
      '"session_start"' in app_tsx or "'session_start'" in app_tsx)
check("App.tsx: session_start useEffect has [] deps",
      "session_start" in app_tsx and "}, [])" in app_tsx)
check("App.tsx: rip_v2_first_seen localStorage key",
      "rip_v2_first_seen" in app_tsx)
check("App.tsx: is_returning property",
      "is_returning" in app_tsx)

# ─── EVENT NAME AUDIT ──────────────────────────────────────────────────────────

EXPECTED_EVENTS = {
    "analysis_started",
    "analysis_completed",
    "analysis_failed",
    "session_start",
    "jd_uploaded",
    "tab_engagement",
    "fix_card_opened",
    "fix_applied",
    "download_triggered",
    "second_analysis_run",
}

# Collect all event strings passed to track()
all_source = "\n".join([
    analytics_py, orchestrator_py, main_py,
    analytics_ts, tab_hook_ts, fixes_tsx, app_tsx,
])
# Also search tab components and download/JD files
for extra_glob in [
    "frontend/src/components/*.tsx",
    "frontend/src/pages/*.tsx",
    "frontend/src/app/*.tsx",
    "frontend/src/*.tsx",
]:
    for p in Path(".").glob(extra_glob):
        all_source += "\n" + p.read_text(encoding="utf-8", errors="ignore")

found_events = set(re.findall(r'["\']([a-z_]+)["\'](?=\s*,|\s*\))', all_source))
found_events = {e for e in found_events if e in EXPECTED_EVENTS}

for event in sorted(EXPECTED_EVENTS):
    check(f"Event '{event}' found in source",
          event in found_events,
          f"'{event}' not found in any source file")

# ─── DO-NOT-TOUCH REGRESSION CHECK ────────────────────────────────────────────

forbidden_patterns = {
    "fix_plan_builder.py": ["analytics", "track("],
    "gap_analyzer.py": ["analytics", "track("],
}
for fname, patterns in forbidden_patterns.items():
    content = read(f"backend/{fname}") or read(f"backend/engine/{fname}") or read(fname)
    for pat in patterns:
        check(f"{fname}: no analytics injection",
              pat not in content,
              f"Found '{pat}' in {fname} — this file must not be touched")

# ─── REPORT ───────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("RIP V2 Analytics — Day 3 Audit Report")
print("="*60)

passes = [r for r in results if r[1] == PASS]
warnings = [r for r in results if r[1] == WARN]
failures = [r for r in results if r[1] == FAIL]

if failures:
    print(f"\n{FAIL} FAILURES ({len(failures)}):")
    for name, _, detail in failures:
        print(f"  • {name}" + (f"\n    → {detail}" if detail else ""))

if warnings:
    print(f"\n{WARN} WARNINGS ({len(warnings)}):")
    for name, _, detail in warnings:
        print(f"  • {name}" + (f"\n    → {detail}" if detail else ""))

print(f"\n{PASS} PASSED: {len(passes)}/{len(results)} checks")

if failures:
    print("\nAudit FAILED. Fix all failures before marking Day 3 complete.")
    sys.exit(1)
else:
    print("\nAudit PASSED. Proceed to Phase 3 (build gate) and Phase 4 (manual QA).")
    sys.exit(0)
